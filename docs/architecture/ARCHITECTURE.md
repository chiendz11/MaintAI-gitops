# MaintAI Desired State & GitOps Architecture (`MaintAI-gitops`)

Tài liệu này mô tả kiến trúc trạng thái khai báo (Kubernetes Desired State) do `MaintAI-gitops` quản lý: phân tách ranh giới `base/` + `environments/{local,production}`, luồng dữ liệu qua các dịch vụ, ranh giới 5 databases & Kafka, `UI-01`, `PROC-ORDER-01`, `MLflow` / `Shadow ML` và tự động cập nhật image qua Argo CD Image Updater.

---

## 1. Cấu trúc Kustomize & Ranh giới 3 Repository

- **`MaintAI` (Application & Images):** Sở hữu mã nguồn microservices, Dockerfiles, contracts (`1.4.0`), risk policies (`processing/config/risk-policies/`), DB migrations và GitHub Actions workflow build/push container images lên GHCR/ECR. Không trực tiếp commit vào repo GitOps.
- **`MaintAI-gitops` (Desired State trong Kubernetes):** Sở hữu Pure Declarative YAML gồm `base/` (12 workload base manifests), `applications/` & `applications/local/` (Argo CD `AppProject`, child `Application`, `ImageUpdater` CRs), `platform/` & `local/` (Strimzi Kafka / local Kafka KRaft, External Secrets, MinIO/Storage, MLflow, Observability), `environments/local/` (chạy thực trên `k3d`) và `environments/production/` (overlay kế thừa `base/` với `replicas: 0` & AWS placeholders, chờ production ECR digests & review trước khi kích hoạt).
- **`Maint-infrastructure` (Infrastructure & Bootstrap):** Sở hữu Terraform AWS (`bootstrap`, `domain`, `platform`, `argocd`), Terraform Local (`terraform/local/`), cụm `k3d`, LocalStack Secrets Manager (gồm `maintai/local/gitops`), `ClusterSecretStore`, kubeconfig cô lập và cài đặt Argo CD + Argo CD Image Updater. Secret `argocd/argocd-image-updater-git-creds` được ESO đồng bộ declarative qua `ExternalSecret`.

---

## 2. Quyết định Thiết kế Giao diện Bắt buộc (`UI-01`)

Hệ thống tách biệt **4 giao diện độc lập** thay vì gộp proxy điều khiển simulator qua Business API:

```text
Simulator UI (frontend độc lập) ──► Sensor Control API (:8005) + scheduler ──► Ingestion API (:8000) ──► Kafka
Main Frontend (Business UI)     ──► Business REST/SSE API (:8003)
Grafana / MLflow                ──► Native upstream UIs (:13000 / :15000)
```

- Main Frontend (`/api`) đi tới `business-api:8003`, tuyệt đối không gửi lệnh điều khiển simulator hay giữ service key của simulator.
- Simulator UI (`/api/v1/simulator/...`) đi tới `sensor:8005`. `sensor` chạy 1 replica với PVC SQLite bền vững và strategy `Recreate` để đảm bảo một controller duy nhất quản lý lịch phát readings. `Pause` chỉ dừng tạo readings mới, không đóng các Alert đang mở.

---

## 3. Luồng Dữ liệu Ứng dụng & Quyền Sở hữu Dữ liệu

```text
Sensor ──► Ingestion API ──► sensor.readings (12 partitions)
  ├──► Processing Worker ──► DQ ──► ML /api/v1/predict (Champion + Shadow mirroring) ──► Risk ──► processing_db + Outbox
  ├──► Storage Consumer ──► Immutable raw JSONL.gz + manifests (S3/MinIO) + storage catalog
  └──► Business Telemetry Consumer ──► latest unverified telemetry (business_db)

Processing Outbox Relay ──► inference.results / alert.signals
  └──► Business Prediction/Alert Consumers ──► business_db ──► PG NOTIFY ──► tất cả Business API replicas ──► SSE ──► Main UI

Business API ──► Processing Read API (JWT delegation M6: history, evidence, export)
Business API ──► RAG Service (knowledge_db pgvector + Groq LLM; lỗi LLM không chặn Alert)
Drift CronJob ──► Processing VALID window / curated S3 ──► drift_db + S3 + Pushgateway
Approved dataset manifest ──► S3/SQS ──► Argo Events/Workflow ──► Training image ──► Quality Gate ──► Model PR
```

### Phân vùng 5 Owner Databases (Không Cross-Owner SQL)
Một cụm PostgreSQL 17 logic chứa 5 databases độc lập, mỗi owner có login, credentials và migrations riêng:
1. `processing_db` (`processing-worker`, `processing-read-api`, `processing-outbox-relay` — 3 Deployments, chung image group `processing`)
2. `business_db` (`business-api`, `business-consumer` — 2 Deployments, chung image group `business-backend`)
3. `drift_db` (`drift-worker` CronJob)
4. `knowledge_db` (`rag-service` Deployment + `pgvector`)
5. `mlflow_db` (MLflow Server platform)

---

## 4. Bản đồ Workloads Ứng dụng & Nền tảng

| Runtime | Loại Kubernetes | Image Name | Database / Storage |
| :--- | :--- | :--- | :--- |
| `ingestion-api` | Deployment | `maintai-ingestion-api` | Kafka producer (no DB) |
| `processing-worker` / `read-api` / `outbox-relay` | 3 Deployments | `maintai-processing` | `processing_db` |
| `storage-consumer` | Deployment | `maintai-storage-consumer` | S3 / MinIO (`maintai-raw*`) |
| `business-api` / `business-consumer` | 2 Deployments | `maintai-business-backend` | `business_db` |
| `ml-service` & `ml-service-shadow` | 2 Deployments | `maintai-ml-service` | Local/S3 bundle (`logreg-baseline-v0` / `hgb-candidate`) |
| `rag-service` | Deployment | `maintai-rag-service` | `knowledge_db` (`pgvector`) + cache PVC |
| `frontend` | Deployment | `maintai-frontend` | Static Nginx + runtime config |
| `simulator-ui` | Deployment | `maintai-simulator-ui` | Static Nginx + runtime config |
| `sensor` | Deployment (`Recreate`, 1 replica) | `maintai-sensor` | Durable PVC (SQLite state/spool) |
| `drift-worker` | CronJob | `maintai-drift-worker` | `drift_db` + S3 |
| `training` | Argo Workflow Task | `maintai-training` | MLflow HTTP API + S3 |

- **Kiến trúc Shadow Rollout (`ml-service-shadow`):** Triển khai pod shadow (`SERVICE_ROLE=shadow`) song song với Champion; Processing/proxy nhân bản traffic (`Traffic Mirroring`) để đánh giá thực nghiệm mà không ảnh hưởng kết quả dự báo chính và cảnh báo người dùng.
- **MLflow Image Ownership:** Source Dockerfile thuộc `MaintAI/ml-service/mlflow/`; GitOps quản lý Deployment/IRSA/config dưới `platform/mlops/` (production) và `environments/local/apps/mlflow.yaml` (local). Chi tiết xem [MLFLOW_IMAGE_MIGRATION.md](../handoffs/MLFLOW_IMAGE_MIGRATION.md).

---

## 5. Failure Semantics & Processing Concurrency (`PROC-ORDER-01`)

- **At-least-once & Idempotency:** Worker commit `processing_db` + outbox trước khi commit Kafka offset; Relay chỉ đánh dấu published sau broker ACK; Business inbox + projection/alert + audit commit trước offset; Storage commit sau khi object + manifest bền vững. SSE reconnect dùng REST snapshot resync (PG NOTIFY không phải replay log).
- **HTTP & Probes:** Mọi HTTP service có `readinessProbe`/`startupProbe`/`livenessProbe`, rolling update `maxUnavailable: 0, maxSurge: 1` kết hợp `PodDisruptionBudget` và Zero-Trust `NetworkPolicy`.
- **Keyed Processing (`PROC-ORDER-01`):** Worker xử lý FIFO theo từng `machine_id`, song song nhiều máy trong budget cấu hình và chỉ commit safe completed prefix mỗi partition; Relay chỉ gửi head chưa published theo key/topic. Chi tiết cutover cấu hình `PROC-ORDER-01` xem [PROCESSING_ORDERING_HANDOFF.md](../handoffs/PROCESSING_ORDERING_HANDOFF.md).
