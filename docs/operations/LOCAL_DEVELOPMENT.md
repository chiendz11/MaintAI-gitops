# Local Development — Pure Declarative GitOps (`k3d` + Argo CD)

Tài liệu này mô tả cấu trúc desired state local trong `MaintAI-gitops`, mô hình Pure Declarative Kustomize (CoreDNS + `cert-manager` TLS), luồng cập nhật image tự động qua Argo CD Image Updater, Auth M5 và History M6.

---

## 1. Ownership và Cấu trúc Thư mục Local

| Vị trí trong `MaintAI-gitops` | Trách nhiệm |
| :--- | :--- |
| [`base/`](../../base/) | Manifest Kustomize gốc dùng chung cho cả Local & Production (Deployments, Services chuẩn CoreDNS cho 12 microservices). |
| [`applications/local/`](../../applications/local/) & [`bootstrap/local/`](../../bootstrap/local/) | Root Application, `AppProject`, 3 child Argo Applications (`platform`, `observability`, `apps`) và `ImageUpdater` CR theo dõi nhánh `main`. |
| [`local/platform/`](../../local/platform/) & [`environments/local/platform/`](../../environments/local/platform/) | Argo source path 1: PostgreSQL 17 + pgvector, Kafka 4 KRaft, MinIO, Keycloak dev, `cert-manager` Issuer & certificates. |
| [`local/observability/`](../../local/observability/) & [`environments/local/observability/`](../../environments/local/observability/) | Argo source path 2: Prometheus, Grafana native UI/provisioning, Pushgateway, Loki & Promtail. |
| [`environments/local/apps/`](../../environments/local/apps/) | Argo source path 3: Overlays ứng dụng, PreSync DB Migration Hooks, ExternalSecrets (ESO), Ingress, HPA, PDB, NetworkPolicies, `ml-service-shadow`, `images` tags trong `kustomization.yaml`. |

**Ranh giới sở hữu:**
- **Infrastructure (`Maint-infrastructure`)** tạo cụm `k3d`, kubeconfig cô lập, LocalStack secrets (gồm `maintai/local/gitops`), ESO (`aws-secrets-manager`, `aws-secrets-manager-argocd`), Ingress-NGINX, `cert-manager`, Argo CD và Argo CD Image Updater (`v1.5.0`). `argocd/argocd-image-updater-git-creds` được sync declaratively bởi `ExternalSecret` (`applications/local/image-updater-git-creds.yaml`).
- **GitOps (`MaintAI-gitops`)** giữ toàn bộ desired state K8s trong cluster dưới dạng Pure Kustomize YAML (`selfHeal: true`).
- Platform sử dụng sync waves theo dependency: Namespace (`-60`) → ConfigMaps (`-50`) → Services (`-40`) → Datastores/Keycloak (`-30`) → TLS/Gateway (`-20`) → Bootstrap Jobs (`-10`).

---

## 2. Kiến trúc Kết nối & Bảo mật (CoreDNS + `cert-manager` + Auth M5)

Môi trường local sử dụng mô hình **cloud-native Kubernetes** thuần túy (không còn loopback adapter sidecars):

- **Service Discovery trực tiếp qua CoreDNS:** Các service gọi nhau theo chuẩn Kubernetes DNS nội bộ (`postgres:5432`, `kafka:9092`, `ml-service:8000`, `ml-service-shadow:8000`, `processing-read-api:8004`, `keycloak:8080`).
- **TLS bằng `cert-manager`:** Sử dụng namespaced Issuer & Certificate resources để cấp phát chứng chỉ TLS cho **Ingress local** (`maintai-ingress-tls` cho `*.maintai.local`) và **Keycloak issuer HTTPS** (`local-dev-tls` trên `https://127.0.0.1:18490/realms/maintai`); service-to-service nội bộ giữ HTTP qua CoreDNS + `NetworkPolicy` + JWT. Browser trên laptop cần tin cậy `ca.crt` do `Maint-infrastructure` tạo.
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

- **Kafka 4 KRaft:** 1 broker local, 4 topics canonical × 12 partitions (`sensor.readings`, `sensor.rejected`, `inference.results`, `alert.signals`).
- **PostgreSQL 17 + pgvector:** 5 databases độc lập (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`) với owner logins riêng cho migrations và runtime logins quyền hẹp cho ứng dụng (không cross-owner SQL).
- **MinIO (7 versioned buckets + scoped owner policies):** `raw`, `processed`, `models`, `approved`, `manuals`, `drift`, `mlflow`.
- **4 Giao diện (UI-01):** Business UI (`:18080`), Simulator UI (`:18081`), Grafana native UI (`:13000`, Dual Datasource Prometheus + Loki), MLflow native UI (`:15000`).
- **History M6:** `BUSINESS_HISTORY_ENABLED` và `PROCESSING_HISTORY_ENABLED` bật trong overlays, dùng ExternalSecrets cho RSA signing/cursor keys và `processing_history_meta` credentials. Quy trình tạo khóa và seed LocalStack/ESO nằm ở [`Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md`](../../../Maint-infrastructure/docs/operations/LOCAL_M6_HISTORY.md).

---

## 5. Phân chia Khả năng Infrastructure vs GitOps

| Thành phần | Vị trí chuẩn hiện tại (`Maint-infrastructure` & `MaintAI-gitops`) |
| :--- | :--- |
| Private kubeconfig / context guard / `image-updater-pat` | `Maint-infrastructure/localdev/common.py`, `cli.py` |
| k3d cluster & image pins (Argo CD / Image Updater / ESO) | `Maint-infrastructure/local/config/`, `local/versions/` |
| Kafka / PostgreSQL / MinIO / Apps manifests | `MaintAI-gitops/base/`, `local/platform/`, `environments/local/` |
| Five DB owners & scoped credentials | LocalStack + ESO (`ExternalSecret`) & PreSync owner migration Jobs |
| Monitoring / Grafana / Loki / Pushgateway | `MaintAI-gitops/local/observability/` & `environments/local/observability/` |
| Rollout ứng dụng | App CI push GHCR → Image Updater PR → review/merge `main` → Argo CD reconcile |

*(Lưu ý: không chép raw credentials/Secrets giữa cụm cũ và cụm mới; giữ nguyên `source_sequence` và raw S3 evidence.)*
