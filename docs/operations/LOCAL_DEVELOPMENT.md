# Local Development — Desired State Được Quản Lý Bằng GitOps (`k3d` + Argo CD)

Tài liệu này mô tả cấu trúc desired state local trong `MaintAI-gitops`, mô hình Pure Declarative Kustomize (CoreDNS + `cert-manager` TLS, không còn loopback adapter sidecars), quy trình phát hành local, auth M5, History M6, và bảng ánh xạ chuyển đổi từ `MaintAI-k3d` cũ sang kiến trúc đa repo hiện tại.

**Trạng thái hiện tại (14/11/2026):** Toàn bộ PR chuẩn hóa kiến trúc declarative và CoreDNS đã được merge vào nhánh **`main`**. CI kiểm tra offline policy, unit tests (`scripts/tests/`), khóa SHA với `MaintAI` (`ee488ad`) và render `kubectl kustomize` trên cả local & production roots (`ci.yml`).

---

## 1. Ownership và Cấu trúc Thư mục Local

| Vị trí trong `MaintAI-gitops` | Trách nhiệm |
| :--- | :--- |
| [`base/`](../../base/) | Manifest Kustomize gốc dùng chung cho cả Local & Production (Deployments, Services chuẩn CoreDNS cho 12 microservices). |
| [`applications/local/`](../../applications/local/) & [`bootstrap/local/`](../../bootstrap/local/) | Root Application & 3 child Argo Applications (`platform`, `observability`, `apps`) theo dõi nhánh `main`. |
| [`environments/local/platform/`](../../environments/local/platform/) | Argo source path 1: PostgreSQL 17 + pgvector, Kafka 4 KRaft, MinIO, Keycloak dev, `cert-manager` Issuer & certificates. |
| [`environments/local/observability/`](../../environments/local/observability/) | Argo source path 2: Prometheus, Grafana native UI/provisioning, Pushgateway, Loki & Promtail. |
| [`environments/local/apps/`](../../environments/local/apps/) | Argo source path 3: Overlays ứng dụng, PreSync DB Migration Hooks, ExternalSecrets (ESO), Ingress, HPA, PDB, NetworkPolicies, `ml-service-shadow`. |
| [`config/local/`](../../config/local/) | `app-source.lock.json`, `risk-policy.lock.json`, `history-runtime.json`, `buckets.json`, `kafka-topology.json`, `platform.lock.json`, `runtime-catalog.json`. |
| [`contracts/local/`](../../contracts/local/) | JSON Schemas `1.0.0` cho reviewed profile & image receipts (tách khỏi production `contracts/runtime-config/`). |
| [`profiles/`](../../profiles/) | `local.example.json` (mọi app mặc định disabled làm template) & `local-training.example.json`. |
| [`scripts/localdev/`](../../scripts/localdev/) | Generator & offline checks (`PYTHONPATH=scripts python -m localdev.checks`, `release.py`, `history.py`). |
| [`versions/local-*.lock.json`](../../versions/) | Khóa hash schema local và fingerprint bảo vệ toàn vẹn các file AWS/production. |

**Ranh giới sở hữu:**
- **Infrastructure (`Maint-infrastructure`)** tạo cụm `k3d`, kubeconfig cô lập, LocalStack secrets, ESO, Ingress-NGINX, `cert-manager` và bootstrap Argo CD.
- **GitOps (`MaintAI-gitops`)** giữ toàn bộ desired state K8s trong cluster. Không chỉnh tay resource trong cụm (Argo `selfHeal: true`).
- Platform sử dụng sync waves theo dependency: Namespace (`-60`) → ConfigMaps (`-50`) → Services (`-40`) → Datastores/Keycloak (`-30`) → TLS/Gateway (`-20`) → Bootstrap Jobs (`-10`).

---

## 2. Kiến trúc Kết nối & Bảo mật (CoreDNS + `cert-manager` + Auth M5)

Từ đợt hợp nhất PR tháng 11/2026 (`b7bce49`, `0de541b`, `59af264`), môi trường local loại bỏ các container loopback adapter sidecar trước đây và chuyển sang mô hình **cloud-native Kubernetes**:

- **Service Discovery trực tiếp qua CoreDNS:** Các service gọi nhau theo chuẩn Kubernetes DNS nội bộ (`postgres:5432`, `kafka:9092`, `ml-service:8000`, `ml-service-shadow:8000`, `processing-read-api:8004`, `keycloak:8080`).
- **TLS nội bộ bằng `cert-manager`:** Sử dụng namespaced Issuer & Certificate resources để cấp phát chứng chỉ TLS cho giao tiếp nội bộ (`sensor`, `processing`, `business`) và Keycloak issuer HTTPS (`https://127.0.0.1:18490/realms/maintai`). Browser trên laptop cần tin cậy `ca.crt` do `Maint-infrastructure` tạo.
- **OIDC / M5 Token Flows:**
  - **Business UI / Simulator UI:** Public PKCE clients độc lập; Business edge `/api` trỏ tới `business-api:8003`, Simulator edge `/api` trỏ tới `sensor:8005`.
  - **Sensor → Ingestion API:** OAuth2 `client_credentials` (`SENSOR_SERVICE`, audience `ingestion`).
  - **Worker → Business Registry & ML:** Service token theo machine scope (`VIEWER` đọc registry, không mutation).
  - **Business API/Consumer → Processing Read API:** `BUSINESS_SERVICE` (`audience: maintai-processing-local`) với short-lived JWT delegation ký bằng RSA cho M6 History.

---

## 3. Quy trình Release & Generator Local

1. Cập nhật code tại `MaintAI` (hoặc kiểm tra commit `ee488ad` trên `main`) và đồng bộ `config/local/app-source.lock.json` + `risk-policy.lock.json` (xem [LOCAL_SOURCE_SYNC.md](LOCAL_SOURCE_SYNC.md)).
2. Với môi trường dùng GHCR images, cập nhật `newTag: sha-...` trong `environments/local/apps/kustomization.yaml` (tự động qua `publish-and-deploy.yml` hoặc chỉnh review qua PR).
3. Nếu sinh manifests từ reviewed local profile & image receipts:
   ```bash
   PYTHONPATH=scripts python -m localdev.release apps \
     --receipts /absolute/path/to/actual-release-receipts.json \
     --profile /absolute/path/to/reviewed-local-profile.json \
     --app-root ../MaintAI
   ```
4. Review diff dưới `environments/local/`, commit và push lên `main`; Argo CD tự động đồng bộ, chạy PreSync DB Migrations (`processing-migration.yaml`, `business-migration.yaml`) và cập nhật Pods (`RollingUpdate`).
5. **Tách biệt mức độ kiểm chứng:** CI render Kustomize / unit checks ≠ Argo Synced ≠ full E2E trên cụm (`MaintAI-system-tests`). Không đưa plaintext Kafka, `replica=1` hoặc local receipts lên `environments/production/`.

---

## 4. Platform Dữ liệu, Bốn UI & History M6

- **Kafka 4 KRaft:** 1 broker local, 4 topics canonical × 12 partitions (`sensor.readings`, `sensor.rejected`, `inference.results`, `alert.signals`) đúng bundle `2.0.0`.
- **PostgreSQL 17 + pgvector:** 5 databases độc lập (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`) với owner logins riêng cho migrations và runtime logins quyền hẹp cho ứng dụng (không cross-owner SQL).
- **MinIO (7 versioned buckets + scoped owner policies):** `raw` (kèm bucket lineage hiện hành `maintai-raw-c8c61d245736`), `processed`, `models`, `approved`, `manuals`, `drift`, `mlflow`.
- **4 Giao diện (UI-01):** Business UI (`:18080`), Simulator UI (`:18081`), Grafana native UI (`:13000`, Dual Datasource Prometheus + Loki), MLflow native UI (`:15000`).
- **History M6 (`config/local/history-runtime.json`):** Bật `BUSINESS_HISTORY_ENABLED` và `PROCESSING_HISTORY_ENABLED`, 3 ExternalSecrets cho RSA signing/cursor keys và `processing_history_meta` credentials. Lệnh tái sinh cấu hình M6:
  ```bash
  PYTHONPATH=scripts ../Maint-infrastructure/.venv/bin/python -m localdev.history \
    --enable \
    --adapter-receipt ../Maint-infrastructure/local/.local/receipts/dev-tools.json
  ```
  Quy trình tạo khóa, seed LocalStack/ESO và cấp grants nằm ở [`Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md`](../../../Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md).

---

## 5. Chuyển đổi từ `MaintAI-k3d` cũ sang Infrastructure + GitOps Local

Kiến trúc hiện tại không còn duy trì repo `MaintAI-k3d` độc lập: `Maint-infrastructure` quản lý cluster/bootstrap/secrets và `MaintAI-gitops` quản lý desired state Kustomize. Bảng đối chiếu vị trí mới:

| Khả năng ở `MaintAI-k3d` cũ | Vị trí chuẩn hiện tại (`Maint-infrastructure` & `MaintAI-gitops`) |
| :--- | :--- |
| Private kubeconfig / context guard | `Maint-infrastructure/localdev/common.py`, `cli.py` |
| k3d schema & image pins | `Maint-infrastructure/local/config/`, `local/versions/` |
| MinIO / MC source builds & images | `Maint-infrastructure/local/images/` + receipts |
| Kafka / PostgreSQL / MinIO / Apps manifests | `MaintAI-gitops/base/`, `local/platform/`, `environments/local/` |
| DB / bucket / topic initialization | Argo PreSync & bootstrap Jobs + `config/local/buckets.json` |
| Five DB owners & scoped credentials | LocalStack + ESO (`ExternalSecret`) & owner migration Jobs |
| Monitoring / Grafana / Loki / Pushgateway | `MaintAI-gitops/local/observability/` |
| App-owned Risk Policy & Source Locks | `MaintAI-gitops/config/local/{app-source,risk-policy}.lock.json` |
| App apply bằng CLI | Declarative Kustomize diff → Git push `main` → Argo CD tự reconcile |

*(Lưu ý cutover: không chép raw credentials/Secrets giữa cụm cũ và cụm mới; giữ nguyên `source_sequence` và raw S3 evidence.)*
