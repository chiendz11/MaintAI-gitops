# MaintAI-gitops Documentation Index

Tài liệu quản lý Desired State (`AWS Production` & `Local k3d + Argo CD`) của hệ thống MaintAI.

## Cấu trúc thư mục

| Thư mục | Phạm vi |
| :--- | :--- |
| [`architecture/`](architecture/) | Kiến trúc GitOps tổng thể, quy tắc versioning/provenance và nguồn tham khảo ban đầu. |
| [`operations/`](operations/) | Hướng dẫn bootstrap, local development (`k3d` + CoreDNS + `cert-manager`), đồng bộ source lock (`RISK-POLICY-01`), secrets, training & recovery. |
| [`handoffs/`](handoffs/) | Giao diện tích hợp với app (`APP_INTEGRATION`), Kafka contracts, `PROC-ORDER-01` và chuyển dịch MLflow image publisher. |
| [`locks/`](locks/) | Snapshot khóa provenance nguồn ứng dụng và tham khảo kiến trúc. |

---

## Danh mục tài liệu

### Architecture & Provenance
- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) — Topology Kustomize, 12 workloads, `ml-service-shadow`, failure semantics & `UI-01`.
- [VERSIONING.md](architecture/VERSIONING.md) — Khóa phiên bản Production & Local (`app-source.lock.json`, `risk-policy.lock.json`, `contracts.lock.json`).
- [REFERENCES.md](architecture/REFERENCES.md) — Nguồn tham khảo kiến trúc Iris & tài liệu chuẩn Strimzi/EKS/Argo.

### Operations & Runbooks
- [LOCAL_DEVELOPMENT.md](operations/LOCAL_DEVELOPMENT.md) — Cấu trúc local `base/`, `applications/local/`, `environments/local/`, CoreDNS + `cert-manager`, M5 Auth, M6 History & chuyển đổi từ `MaintAI-k3d`.
- [LOCAL_SOURCE_SYNC.md](operations/LOCAL_SOURCE_SYNC.md) — Đồng bộ SHA giữa `MaintAI` (`e67d42d`) & `MaintAI-gitops`, publication CI và `RISK-POLICY-01`.
- [BOOTSTRAP.md](operations/BOOTSTRAP.md) — Trình tự kích hoạt Production GitOps & manual DB bootstrap.
- [SECRETS.md](operations/SECRETS.md) — Quản lý Secrets, ESO, IRSA, DB owner isolation & KMS.
- [TRAINING.md](operations/TRAINING.md) — Luồng Argo Events / Argo Workflows batch training & candidate review PR.
- [RECOVERY.md](operations/RECOVERY.md) — Khôi phục cluster/DB/Kafka & S3 backup/restore intents.

### Subsystem Handoffs
- [APP_INTEGRATION.md](handoffs/APP_INTEGRATION.md) — Contract tích hợp app, Dockerfiles, health endpoints & CI publisher template.
- [KAFKA.md](handoffs/KAFKA.md) — Handoff Kafka `1.4` (`OUTCOME-14-ONLY`, `sensor.readings`, `inference.results`, `alert.signals`, Strimzi pins).
- [PROCESSING_ORDERING_HANDOFF.md](handoffs/PROCESSING_ORDERING_HANDOFF.md) — Handoff `PROC-ORDER-01` và config `3.0.0` cho Processing Worker & Outbox Relay.
- [MLFLOW_IMAGE_MIGRATION.md](handoffs/MLFLOW_IMAGE_MIGRATION.md) — Chuyển quyền build/publish MLflow server image sang `MaintAI/ml-service/mlflow/` (`maintai-publish.yml`).

### Locks
- [application-source-lock.json](locks/application-source-lock.json) — Bản ghi provenance các tài liệu ứng dụng tại thời điểm thiết kế.
- [reference-lock.json](locks/reference-lock.json) — Bản ghi commit tham chiếu Iris & target revision `1.4.0`.
