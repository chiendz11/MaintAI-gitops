# Local Development — Pure Declarative GitOps (`k3d` + Argo CD)

Tài liệu này mô tả cấu trúc desired state local trong `MaintAI-gitops`, mô hình Pure Declarative Kustomize (CoreDNS + `cert-manager` TLS), luồng cập nhật image tự động qua Argo CD Image Updater, Auth M5 và History M6.

---

## 1. Ownership và Cấu trúc Thư mục Local

| Vị trí trong `MaintAI-gitops` | Trách nhiệm |
| :--- | :--- |
| [`base/`](../../base/) | Manifest Kustomize gốc dùng chung cho cả Local & Production (Deployments, Services chuẩn CoreDNS cho 12 microservices). |
| [`applications/local/`](../../applications/local/) & [`bootstrap/local/`](../../bootstrap/local/) | Root Application, `AppProject`, 11 child Argo Applications (`platform`, `observability`, `apps`, `training`, `argo-events`, `argo-workflows`, `knative-crds`, `knative-serving`, `kserve-crds`, `kserve`, `ml-serving`) và `ImageUpdater` CR theo dõi nhánh `main`. |
| [`local/platform/`](../../local/platform/) & [`environments/local/platform/`](../../environments/local/platform/) | Argo source path `platform`: PostgreSQL 17 + pgvector, Kafka 4 KRaft, Eclipse Mosquitto 2.1.4 (PVC 1Gi `sync-wave: '-30'`), MinIO, Keycloak dev, `cert-manager` Issuer & certificates. |
| [`local/observability/`](../../local/observability/) & [`environments/local/observability/`](../../environments/local/observability/) | Argo source path `observability`: Prometheus (gồm scrape KServe/Knative), Grafana native UI/provisioning, Pushgateway, Loki & Promtail. |
| [`environments/local/ml-serving/`](../../environments/local/ml-serving/) | Argo source paths `ml-serving` (`crds`, `core`, `workloads`): Knative Serving `v1.21.3`, Kourier `v1.21.1`, KServe `v0.18.1`, `InferenceService/ml-service-champion` (KPA `min=2/max=6`, `UVICORN_WORKERS=1`) và `ml-service-mirror` (Nginx 5% shadow). |
| [`environments/local/apps/`](../../environments/local/apps/) | Argo source path `apps`: Overlays ứng dụng, unified `ingestion-api` (`1` pod `Recreate` phục vụ MQTT QoS 1 + HTTP fallback), PreSync DB Migration Hooks (chờ `postgres:5432` TCP cho `kube-router`), ExternalSecrets (ESO), Ingress `*.maintai.localhost`, HPA, PDB, NetworkPolicies (`allow-sensor-ingestion-to-mosquitto`), `ml-service-shadow`, `images` tags trong `kustomization.yaml`. |

**Ranh giới sở hữu:**
- **Infrastructure (`Maint-infrastructure`)** tạo cụm `k3d`, kubeconfig cô lập, LocalStack secrets (gồm `maintai/local/gitops`), ESO (`aws-secrets-manager`, `aws-secrets-manager-argocd`), Ingress-NGINX, `cert-manager`, Argo CD và Argo CD Image Updater (`v1.5.0`). `argocd/argocd-image-updater-git-creds` được sync declaratively bởi `ExternalSecret` (`applications/local/image-updater-git-creds.yaml`).
- **GitOps (`MaintAI-gitops`)** giữ toàn bộ desired state K8s trong cluster dưới dạng Pure Kustomize YAML (`selfHeal: true`).
- Platform sử dụng sync waves theo dependency: Namespace (`-60`) → ConfigMaps (`-50`) → Services (`-40`) → Datastores/Keycloak (`-30`) → TLS/Gateway (`-20`) → Bootstrap Jobs (`-10`).

---

## 2. Kiến trúc Kết nối & Bảo mật (CoreDNS + `cert-manager` + Auth M5)

Môi trường local sử dụng mô hình **cloud-native Kubernetes** thuần túy (không còn loopback adapter sidecars):

- **Service Discovery trực tiếp qua CoreDNS:** Các service gọi nhau theo chuẩn Kubernetes DNS nội bộ (`postgres:5432`, `kafka:9092`, `mosquitto:1883`, `ml-service-mirror:8001`, `kourier-internal.kourier-system.svc.cluster.local:80`, `ml-service-shadow:8001`, `processing-read-api:8004`, `keycloak:8080`). `NetworkPolicy` chặn mặc định (`default-deny-all`), mở tường minh qua `allow-intra-namespace`, `allow-sensor-ingestion-to-mosquitto`, `allow-mirror-to-kourier-internal`, `allow-knative-kourier-to-kserve-predictor`; riêng hook `business-db-migration` chờ `postgres:5432` TCP sẵn sàng trước khi migrate để tránh race khởi tạo ipset của `kube-router`.
- **TLS bằng `cert-manager`:** Sử dụng namespaced Issuer & Certificate resources để cấp phát chứng chỉ TLS cho **Ingress local** (`maintai-ingress-tls` cho `*.maintai.localhost` và `*.maintai.local`) và **Keycloak issuer HTTPS** (`local-dev-tls` trên `https://127.0.0.1:18490/realms/maintai`); service-to-service nội bộ giữ HTTP qua CoreDNS + `NetworkPolicy` + JWT. Browser trên laptop cần tin cậy `ca.crt` do `Maint-infrastructure` tạo.
- **OIDC / M5 Token Flows:**
  - **Business UI / Simulator UI:** Public PKCE clients độc lập; Business edge `/api` trỏ tới `business-api:8003`, Simulator edge `/api` trỏ tới `sensor:8005`.
  - **Sensor → Ingestion API:** OAuth2 `client_credentials` (`SENSOR_SERVICE`, audience `ingestion`).
  - **Worker → Business Registry & ML:** Service token theo machine scope (`VIEWER` đọc registry, không mutation).
  - **Business API/Consumer → Processing Read API:** `BUSINESS_SERVICE` (`audience: maintai-processing-local`) với short-lived JWT delegation ký bằng RSA cho M6 History.

---

## 3. Quy trình Build & Deploy Pure GitOps (CI + Argo CD Image Updater)

1. Khi code trên `MaintAI` thay đổi và merge vào `main`, GitHub Actions workflow `.github/workflows/publish-and-deploy.yml` build các services bị ảnh hưởng và đẩy image `ghcr.io/chiendz11/maintai-<service>:sha-<40-hex-sha>` lên GHCR.
2. **Argo CD Image Updater** chạy trong namespace `argocd` polling GHCR theo cấu hình [`applications/local/image-updater.yaml`](../../applications/local/image-updater.yaml):
   - Khi có tag `sha-*` mới hơn tag hiện tại trong [`environments/local/apps/kustomization.yaml`](../../environments/local/apps/kustomization.yaml), controller tạo branch mới và **mở Pull Request** vào `main` trên `MaintAI-gitops`.
3. CI trên `MaintAI-gitops` ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) chạy `kubectl kustomize` + `kubeconform` validate toàn bộ manifests trong PR.
4. Sau khi PR được merge vào `main`, Argo CD tự động phát hiện commit mới, chạy PreSync DB Migrations (`environments/local/apps/hooks/`) và rolling update các Pods.
5. **Tách biệt mức độ kiểm chứng:** CI render Kustomize / kubeconform ≠ Argo Synced ≠ full E2E trên cụm. Không đưa plaintext Kafka, `replica=1` hoặc config local lên `environments/production/`.

---

## 4. Platform Dữ liệu, Bốn UI & History M6

- **Eclipse Mosquitto 2.1.4 & Unified `ingestion-api` MQTT Bridge:** Broker `mosquitto:1883` chạy persistence trên PVC `local-mosquitto-data` (1Gi `local-path`, đặt cùng `sync-wave: '-30'` với `Deployment/mosquitto` để tránh deadlock `WaitForFirstConsumer`); `ingestion-api` (`1` replica `Recreate`, `INGESTION_MQTT_ENABLED=true`, không `$share/`, `INGESTION_MQTT_TOPIC_FILTER=maintai/v1/site/+/machines/+/telemetry`, batch `32 / 5 ms`, giữ đồng thời HTTP `/api/v1/sensor-readings`) nhận từ `sensor` (`SIM_TRANSPORT_MODE=mqtt`, SQLite Spool v2 `100k` / `128 MiB`). Production overlay mount `/certs/mqtt` để bật TLS `8883` + auth/mTLS.
- **KServe `v0.18.1` + Knative Serving `v1.21.3` + Kourier `v1.21.1`:** `InferenceService/ml-service-champion` chạy Custom Predictor Container (`minReplicas: 2`, `maxReplicas: 6`, `scaleMetric: concurrency`, `scaleTarget: 4`, `containerConcurrency: 8`, `UVICORN_WORKERS=1`, zero-pandas fast path `/api/v1/predict/batch`), kết hợp custom Lua health check `serving.kserve.io_InferenceService` trong `argocd-cm`. `ml-service-mirror` (`2` pods Nginx) đẩy traffic qua Kourier internal và mirror `5%` tới `ml-service-shadow` (`1` pod, `UVICORN_WORKERS=1`).
- **Kafka 4 KRaft:** 1 broker local, 4 topics canonical × 12 partitions (`sensor.readings`, `sensor.rejected`, `inference.results`, `alert.signals`), producer `KAFKA_LINGER_MS=2` + `lz4`.
- **PostgreSQL 17 + pgvector:** 5 databases độc lập (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`) với owner logins riêng cho migrations và runtime logins quyền hẹp cho ứng dụng (không cross-owner SQL). Local tuning trên `postgres-0`: `max_connections=300`, `synchronous_commit=off`, `shared_buffers=512MB`, `wal_buffers=16MB`, `max_wal_size=2GB`, `checkpoint_timeout=15min`, `wal_writer_delay=20ms`, `limits.memory=2Gi`.
- **MinIO (7 versioned buckets + scoped owner policies):** `raw`, `processed`, `models`, `approved`, `manuals`, `drift`, `mlflow`.
- **4 Giao diện (UI-01):** Business UI (`https://app.maintai.localhost` / `:18080`), Simulator UI (`https://simulator.maintai.localhost` / `:18081`), Grafana native UI (`https://grafana.maintai.localhost` / `:13000`, Dual Datasource Prometheus + Loki), MLflow native UI (`https://mlflow.maintai.localhost` / `:15000`).
- **History M6:** `BUSINESS_HISTORY_ENABLED` và `PROCESSING_HISTORY_ENABLED` bật trong overlays, dùng ExternalSecrets cho RSA signing/cursor keys và `processing_history_meta` credentials. Quy trình tạo khóa và seed LocalStack/ESO nằm ở [`Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md`](../../../Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md).

## 5. Baseline Vận hành Local 50 máy (`k3d` Laptop `15–16 GiB RAM`)

- **Inventory & Tải chuẩn:** `SIM_MACHINE_COUNT=50` (`M-001`..`M-050`), `SIM_INTERVAL_MS=1000` (`1 reading/s/máy`, tổng `50 readings/s`), đồng bộ giữa `sensor-config`, `local-reviewed-machines`, `INGESTION_MQTT_ALLOWED_MACHINE_IDS` và claims `machine_ids` trong `local/platform/maintai-realm.json`. (Thiết kế kiến trúc vẫn giữ khả năng mở rộng cho mốc `100` máy và `X > 100` trên hạ tầng lớn hơn.)
- **Replicas & tuning trong `environments/local/`:** `processing-worker=6` (`PROCESSING_MAX_BATCH_PER_KEY=16`, `per_key=1`), `business-consumer=4` (`KAFKA_COMMIT_BATCH_SIZE=16`, `KAFKA_COMMIT_MAX_WAIT_MS=50`), `ingestion-api=1` (`Recreate`, hợp nhất MQTT QoS 1 bridge + HTTP `/api/v1/sensor-readings`), `mosquitto=1` (`Recreate`), `ml-service-champion=2..6` (KServe KPA, `UVICORN_WORKERS=1`), `ml-service-mirror=2`, `ml-service-shadow=1` (`UVICORN_WORKERS=1`), `processing-outbox-relay=2` (`ordered`), `sensor=1` (`mqtt`, Spool v2 `100k`/`128 MiB`), `business-api=2`, các workload nền còn lại `1`.
- **Lưu ý `sensor` `source_identity`, LocalStack & `/data` `DiskPressure`:**
  1. Đổi `SIM_MACHINE_COUNT=100 -> 50` trên PVC `/state/state.sqlite3` cũ sẽ vấp `source_identity` guard của `sensor`; cần PVC mới hoặc reset/archive state volume rõ ràng (và re-import Keycloak realm nếu realm cũ đã bootstrap). Nâng cấp từ `schema_version=1` lên `2` của Spool v2 chạy auto-migration idempotent lúc startup.
  2. Trên node đơn local, k3s kích hoạt `DiskPressure=True` khi phân vùng chứa kubelet/storage vượt `85%` (`<15%` trống), làm pod mới bị `Pending`; hãy giữ `/data` dưới ngưỡng `85%` và Pause các máy trên Simulator UI khi không cần chạy liên tục.
  3. Sau mỗi lần `k3d cluster stop/start`, LocalStack chạy in-memory nên cần chạy lại `Maint-infrastructure/local/manifests/seed_localstack_secrets.py` và `localdev.history.seed()` để `ExternalSecret` khôi phục `SecretSynced`.

---

## 6. Phân chia Khả năng Infrastructure vs GitOps

| Thành phần | Vị trí chuẩn hiện tại (`Maint-infrastructure` & `MaintAI-gitops`) |
| :--- | :--- |
| Private kubeconfig / context guard / `image-updater-pat` | `Maint-infrastructure/localdev/common.py`, `cli.py` |
| k3d cluster & image pins (Argo CD / Image Updater / ESO) | `Maint-infrastructure/local/config/`, `local/versions/` |
| Kafka / PostgreSQL / MinIO / Apps manifests | `MaintAI-gitops/base/`, `local/platform/`, `environments/local/` |
| Five DB owners & scoped credentials | LocalStack + ESO (`ExternalSecret`) & PreSync owner migration Jobs |
| Monitoring / Grafana / Loki / Pushgateway | `MaintAI-gitops/local/observability/` & `environments/local/observability/` |
| Rollout ứng dụng | App CI push GHCR → Image Updater PR → review/merge `main` → Argo CD reconcile |

*(Lưu ý: không chép raw credentials/Secrets giữa cụm cũ và cụm mới; giữ nguyên `source_sequence` và raw S3 evidence.)*
