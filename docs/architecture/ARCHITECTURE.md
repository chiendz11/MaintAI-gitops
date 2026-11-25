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
Simulator UI (frontend độc lập) ──► Sensor Control API (:8005) + Spool v2 ──► Mosquitto (:1883) / Ingestion HTTP (:8000) ──► Kafka
Main Frontend (Business UI)     ──► Business REST/SSE API (:8003)
Grafana / MLflow                ──► Native upstream UIs (:13000 / :15000)
```

- Main Frontend (`/api`) đi tới `business-api:8003`, tuyệt đối không gửi lệnh điều khiển simulator hay giữ service key của simulator.
- Simulator UI (`/api/v1/simulator/...`) đi tới `sensor:8005`. `sensor` chạy 1 replica với PVC SQLite bền vững và strategy `Recreate` để đảm bảo một controller duy nhất quản lý lịch phát readings. `Pause` chỉ dừng tạo readings mới, không đóng các Alert đang mở.

---

## 3. Luồng Dữ liệu Ứng dụng & Quyền Sở hữu Dữ liệu

```text
Sensor (MQTT QoS 1 + Spool v2) ──► Mosquitto (:1883/:8883) ──┐
HTTP Clients (/api/v1/sensor-readings) ───────────────────────┴─► Unified ingestion-api (1 pod Recreate) ─► sensor.readings (12 partitions, lz4)
  ├──► Processing Worker (keyed FIFO per_key=1, micro-batch <=16) ──► DQ ──► ml-service-mirror (:8001)
  │        ├──(95%/100% primary)──► Kourier (:80) ──► KServe ml-service-champion (KPA min=2/max=6, UVICORN_WORKERS=1)
  │        └──(5% async mirror)────► ml-service-shadow (UVICORN_WORKERS=1)
  │      ──► Risk ──► processing_db + Outbox
  ├──► Storage Consumer ──► Immutable raw JSONL.gz + manifests (S3/MinIO) + storage catalog
  └──► Business Telemetry Consumer ──► latest unverified telemetry (business_db)

Processing Outbox Relay (ordered mode + publish_batch lz4) ──► inference.results / alert.signals
  └──► Business Consumer (serial 64/32 + commit batch 16/50ms) ──► business_db ──► PG NOTIFY ──► tất cả Business API replicas ──► SSE ──► Main UI

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
| `mosquitto` (local) | Deployment (`Recreate`, 1 replica) + Service `:1883` | `eclipse-mosquitto:2` (`2.1.4`) | PVC `local-mosquitto-data` (1Gi, `sync-wave: '-30'`) |
| `ingestion-api` | Deployment (`Recreate`, 1 replica, HTTP `:8000` + MQTT QoS 1 bridge) | `maintai-ingestion-api` | Non-`$share` MQTT + HTTP fallback → Kafka (`publish_batch`, `poll(0.005)`, `lz4`), TLS/mTLS ready |
| `processing-worker` / `read-api` / `outbox-relay` | 3 Deployments | `maintai-processing` | `processing_db` |
| `storage-consumer` | Deployment | `maintai-storage-consumer` | S3 / MinIO (`maintai-raw*`) |
| `business-api` / `business-consumer` | 2 Deployments | `maintai-business-backend` | `business_db` |
| `ml-service-champion` | KServe `InferenceService` (KPA `min=2/max=6`, `UVICORN_WORKERS=1`) | `maintai-ml-service` | Local/S3 bundle (`logreg-baseline-v0`, vectorized fast path) |
| `ml-service-mirror` & `ml-service-shadow` | 2 Deployments (Nginx mirror 5% + Shadow `UVICORN_WORKERS=1`) | `nginx-unprivileged` / `maintai-ml-service` | Routing Kourier + shadow bundle (`hgb-candidate`) |
| `rag-service` | Deployment | `maintai-rag-service` | `knowledge_db` (`pgvector`) + cache PVC |
| `frontend` | Deployment | `maintai-frontend` | Static Nginx + runtime config |
| `simulator-ui` | Deployment | `maintai-simulator-ui` | Static Nginx + runtime config |
| `sensor` | Deployment (`Recreate`, 1 replica) | `maintai-sensor` | Durable PVC (SQLite Spool v2 `100k`/`128 MiB`, MQTT/HTTP) |
| `drift-worker` | CronJob | `maintai-drift-worker` | `drift_db` + S3 |
| `training` | Argo Workflow Task | `maintai-training` | MLflow HTTP API + S3 |

- **Kiến trúc KServe KPA & Shadow Rollout:** `ml-service-champion` chạy qua **KServe `v0.18.1` + Knative Serving `v1.21.3` + Kourier `v1.21.1`** (`scaleMetric: concurrency`, `scaleTarget: 4`, `containerConcurrency: 8`, `minReplicas: 2`, `maxReplicas: 6`, `UVICORN_WORKERS=1`). `ml-service-mirror` (`2` pods) chuyển traffic chính qua Kourier internal và nhân bản `5%` bất đồng bộ sang `ml-service-shadow` (`1` pod).
- **MLflow Image Ownership:** Source Dockerfile thuộc `MaintAI/ml-service/mlflow/`; GitOps quản lý Deployment/IRSA/config dưới `platform/mlops/` (production) và `environments/local/apps/mlflow.yaml` (local). Chi tiết xem [MLFLOW_IMAGE_MIGRATION.md](../handoffs/MLFLOW_IMAGE_MIGRATION.md).

---

## 5. Failure Semantics & Processing Concurrency (`PROC-ORDER-01`)

- **At-least-once & Idempotency:** `sensor` chỉ xóa Spool v2 sau MQTT `PUBACK`; unified `ingestion-api` chỉ `PUBACK` sau Kafka durable ACK; Worker commit `processing_db` + outbox trước khi commit safe-prefix Kafka offset; Relay chỉ đánh dấu published sau broker ACK; Business inbox + projection/alert + audit commit trước offset (gom commit đồng bộ theo `KAFKA_COMMIT_BATCH_SIZE=16`, `KAFKA_COMMIT_MAX_WAIT_MS=50`); Storage commit sau khi object + manifest bền vững. SSE reconnect dùng REST snapshot resync (PG NOTIFY không phải replay log).
- **HTTP & Probes:** Mọi HTTP service có `readinessProbe`/`startupProbe`/`livenessProbe`, rolling update `maxUnavailable: 0, maxSurge: 1` kết hợp `PodDisruptionBudget` và Zero-Trust `NetworkPolicy` (gồm `allow-sensor-ingestion-to-mosquitto`, `allow-mirror-to-kourier-internal`, `allow-knative-kourier-to-kserve-predictor`).
- **Keyed Processing (`PROC-ORDER-01`):** Worker giữ `per_key=1` FIFO nghiêm ngặt theo từng `machine_id`, bật per-key micro-batching (`PROCESSING_MAX_BATCH_PER_KEY=16`) gọi `/api/v1/predict/batch`, song song nhiều máy trong budget cấu hình và chỉ commit safe completed prefix mỗi partition; Relay chỉ gửi head chưa published theo key/topic với `publish_batch()` + `lz4` (`KAFKA_LINGER_MS=2`). Chi tiết cutover cấu hình `PROC-ORDER-01` xem [PROCESSING_ORDERING_HANDOFF.md](../handoffs/PROCESSING_ORDERING_HANDOFF.md).
