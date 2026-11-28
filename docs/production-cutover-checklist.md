# Production Cutover Checklist (AWS EKS + MSK + Cognito + EMQX)

Danh sách kiểm tra bắt buộc trước khi nâng `replicas > 0` tại [`environments/production/workloads/`](../environments/production/workloads/kustomization.yaml).

## 1. Hạ tầng Terraform (`Maint-infrastructure/terraform/platform`)
- [ ] Điền đầy đủ giá trị thực từ `Maint-infrastructure/environments/production.tfvars.example` (không dùng `0.0.0.0/0` cho EKS API hay `mqtt_ingress_cidrs`).
- [ ] Chạy `terraform plan` / `terraform apply` cho `platform`: xác nhận đã tạo EKS, addon `eks-pod-identity-agent`, EKS Pod Identity associations cho toàn bộ ServiceAccounts (không còn `eks.amazonaws.com/role-arn`), RDS PostgreSQL 17 + `pgvector`, Amazon MSK (`SASL/SCRAM` TLS `9096`), Amazon Cognito User Pool (gồm M2M client `business-worker` với scope `rag:brief`), và 5 S3 buckets (`datasets`, `artifacts`, `raw`, `knowledge`, `drift`).
- [ ] Chạy workflow `sync-gitops-params` trong `Maint-infrastructure` (hoặc đọc SSM Parameter `/maintai/v13/production/platform-metadata`) để cập nhật `environments/production/params/params.env` (domain, ALB cert ARN, Cognito URLs/IDs, MSK brokers, buckets, SQS queue) qua PR trước khi sync.

## 2. Secrets, SSM Parameters & Certificates (AWS -> ESO)
- [ ] Seed toàn bộ giá trị thật vào AWS Secrets Manager (tuyệt đối không commit lên Git):
  - `maintai/v13/production/{business,processing,drift,mlflow,knowledge}-database`
  - `maintai/v13/production/{llm-provider,m7-tokens,mqtt-tls,processing-api-auth,ml-api-auth,rag-api-auth,oidc-business-worker}`
  - `AmazonMSK_maintai-v13-prod_{processing,business,ingestion}` (tài khoản SCRAM-SHA-512 khớp Kafka ACLs, `ingestion` dùng cho `redpanda-connect`)
- [ ] Publish lock artifact JSON vào AWS SSM Parameter Store (`/maintai/v13/production/models/champion_artifacts` và `/maintai/v13/production/models/shadow_artifacts`) và kiểm tra ESO `ExternalSecret` (`aws-secrets-manager`, `aws-parameter-store`) đồng bộ `Ready=True`.

## 3. GitOps Placeholders & Database Migrations
- [ ] Xác nhận `environments/production/params/params.env` và ECR image digests/tags trong [`environments/production/workloads/`](../environments/production/workloads/kustomization.yaml) & [`environments/production/ml-serving/`](../environments/production/ml-serving/kustomization.yaml) đã được điền đầy đủ.
- [ ] Kiểm tra Argo CD `PreSync`/`Sync`/`PostSync` migration hooks (`environments/production/workloads/hooks/`) hoặc chạy thủ công per-owner Alembic migrations + role grants cho 5 owner databases (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`).
- [ ] Nạp tài liệu RAG vào `knowledge_db` (`rag-knowledge-init` hook) và seed approved dataset manifest vào S3 `datasets` bucket.

## 4. Network, Broker & Pipeline Verification
- [ ] Tạo đủ MSK topics (`sensor.readings`, `sensor.rejected`, `inference.results`, `alert.signals`) với replication factor 3, `min.insync.replicas=2`.
- [ ] Khởi động `StatefulSet/emqx` (`replicas: 1+`), xác nhận NLB listener TCP/TLS `8883` reachable từ `mqtt_ingress_cidrs` và strategy `hash_topic`.
- [ ] Xác minh `redpanda-connect` (image `maintai-ingestion-connect` sở hữu bởi `MaintAI/ingestion-connect/`) consume `$share/maintai-ingest/...` QoS 1 và publish vào `sensor.readings` / `sensor.rejected` (`lz4`, idempotent).
- [ ] Xác minh `business-worker` (`8084`) xác thực OIDC M2M (`Cognito client_credentials` + JWKS RS256, scope `rag:brief`) sang `rag-service` (`8002`) cho `BriefRunner`, và `CatalogRunner` đọc từ S3 `drift` bucket mà không cần Kafka.
- [ ] Sync `applications/ml-serving.yaml` (`ml-service-champion` KServe + `ml-service-mirror`), kích hoạt `ml-service-shadow`, mở traffic các workloads (`business-api`, `business-consumer`, `processing-worker`, `processing-outbox-relay`, `storage-consumer`, `rag-service`), gỡ `suspend: true` trên `CronJob/drift-worker` và bật KEDA `ScaledObject` / HPA.
