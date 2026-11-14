# Versioning and immutable provenance (MaintAI-gitops)

Tài liệu này quy định cơ chế khóa phiên bản và xuất xứ bất biến cho toàn bộ **Desired State (Production & Local)** trong `MaintAI-gitops`.

---

## 1. Production / Platform Provenance & Contracts

- Repository version: `VERSION` (initial `0.1.0`).
- Platform architectural baseline: `maintai-1.3.1+simulator-ui.1`; application target contracts: `1.4.0` + `PROC-ORDER-01/1.0.0`.
- Platform handoff schema: **2.0.0** (`contracts/platform-contract-v2.schema.json`); workload/model/dataset/recovery intents: `1.0.0` schemas.
- Runtime config schemas: **2.0.0** (active/frozen) và **3.0.0** (opt-in `PROC-ORDER-01` trong `config/processing-ordering.json`), bất biến theo filename và SHA-256 trong `versions/contracts.lock.json`.
- Event contracts: `config/kafka-contracts.json` khóa manifest và bundle hashes (`MaintAI/contracts/kafka/`). Xem [Kafka](../handoffs/KAFKA.md).
- App image (Production): khóa theo `repository@sha256`, source Git SHA, owner/signature workflow. Nhóm Processing (`worker`, `read-api`, `outbox-relay`) và Business (`api`, `consumer`) cập nhật atomic theo image group.
- **MLflow image (`MLFLOW-IMAGE-01`):** Dù platform giữ `platform/mlops/`, Dockerfile, pins và keyless publisher thuộc `MaintAI/ml-service/mlflow/` (`maintai-publish.yml`). GitOps chỉ pin signed digest do app phát hành. Xem [MLflow migration](../handoffs/MLFLOW_IMAGE_MIGRATION.md).
- Chart/provider versions và S3 artifacts (`model`, `preprocessor`, `drift_reference`, `metadata`, `evaluation_report`): khóa chính xác pin, `S3 VersionId + SHA-256` (ETag không thay thế checksum). Không mutate in-place; thay đổi phải đi qua PR mới.

---

## 2. Local Environment Versioning (`k3d` + Declarative Overlays)

Phần local được phát triển và khóa độc lập với frozen production contracts (`versions/local-production-baseline.lock.json` xác nhận thay đổi local không tự động sửa AWS/production bytes):

- **App Source Lock & Policy:** `config/local/app-source.lock.json` khóa commit SHA của `chiendz11/MaintAI` (hiện đồng bộ tại **`e67d42d0d2fd347c686a39928906c20b68f03992`**, `main`) kèm SHA-256 toàn bộ Dockerfiles, interfaces và config schemas. `config/local/risk-policy.lock.json` khóa `demo-risk-v1` trực tiếp từ `MaintAI/processing/config/risk-policies/`. Chi tiết quy trình đồng bộ xem [LOCAL_SOURCE_SYNC.md](../operations/LOCAL_SOURCE_SYNC.md).
- **Local Contract Locks:** `versions/local-contracts.lock.json` bảo vệ `contracts/local/*.schema.json` (`1.0.0`).
- **Actual Local Image Receipts:** Bao gồm Docker image ID, content-derived alias, Git commit, `dirty` flag, source snapshot SHA-256, Dockerfile SHA-256 và imported context (chỉ dùng cho local `k3d`; không dùng tag `:dev` trôi nổi và không thay thế ECR signature cho production).
- **Kustomize Content Hashes:** `configMapGenerator` tự động sinh suffix hash cho cấu hình app/policy (`processing-risk-policy` v.v.), đảm bảo Pod tự động rollout khi nội dung config hoặc policy thay đổi.
- **Tách biệt mức độ kiểm chứng:** CI PR (`ci.yml`) kiểm tra offline policy, unit tests (`scripts/tests/`), app source SHA và `kubectl kustomize` render cho cả local & production roots; dispatch ACK ≠ PR merged ≠ Argo convergence ≠ serving a validated model.
