# MaintAI-gitops Documentation Index

Tài liệu quản lý Desired State (`AWS Production` & `Local k3d + Argo CD`) cho hệ thống MaintAI theo mô hình Pure Declarative GitOps.

## Cấu trúc thư mục

| Thư mục | Phạm vi |
| :--- | :--- |
| [`architecture/`](architecture/) | Kiến trúc Kustomize tổng thể, quy tắc versioning/image pins và nguồn tham khảo ban đầu. |
| [`operations/`](operations/) | Hướng dẫn bootstrap, local development (`k3d` + CoreDNS + `cert-manager`), quy trình CI/CD với Argo CD Image Updater, secrets, training & recovery. |
| [`handoffs/`](handoffs/) | Giao diện tích hợp với app (`APP_INTEGRATION`), Kafka contracts, `PROC-ORDER-01` và sở hữu image MLflow. |
| [`locks/`](locks/) | Snapshot provenance nguồn ứng dụng và tham khảo kiến trúc tại thời điểm thiết kế. |

---

## Danh mục tài liệu

### Architecture & Provenance
- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) — Topology Kustomize (`base/` + `environments/`), Mosquitto + `ingestion-mqtt-bridge`, KServe/Knative KPA `ml-service-champion`, `ml-service-shadow`, failure semantics & `UI-01`.
- [VERSIONING.md](architecture/VERSIONING.md) — Quy ước tag/digest, Kustomize image overrides, Argo CD Image Updater strategy & phân tách kiểm chứng.
- [GITOPS_BLUEPRINT.md](architecture/GITOPS_BLUEPRINT.md) — Tài liệu mẫu chuẩn (project-agnostic) để tái sử dụng kiến trúc Pure Declarative GitOps + Argo CD Image Updater cho các dự án khác.
- [REFERENCES.md](architecture/REFERENCES.md) — Nguồn tham khảo kiến trúc Iris & tài liệu chuẩn Strimzi/EKS/Argo.

### Operations & Runbooks
- [LOCAL_DEVELOPMENT.md](operations/LOCAL_DEVELOPMENT.md) — Cấu trúc local `base/`, `applications/local/`, `environments/local/` (gồm `ml-serving` KServe/Knative/Kourier & Mosquitto), CoreDNS + `cert-manager`, M5 Auth, M6 History.
- [LOCAL_SOURCE_SYNC.md](operations/LOCAL_SOURCE_SYNC.md) — Luồng CI/CD đa repo với `MaintAI` + Argo CD Image Updater (`Fine-grained PAT` + PR mode) & `RISK-POLICY-01`.
- [BOOTSTRAP.md](operations/BOOTSTRAP.md) — Trình tự kích hoạt Production GitOps & manual DB bootstrap.
- [SECRETS.md](operations/SECRETS.md) — Quản lý Secrets, ESO, AWS Secrets Manager / LocalStack, IRSA & `argocd-image-updater-git-creds`.
- [TRAINING.md](operations/TRAINING.md) — Luồng Argo Events / Argo Workflows batch training & candidate review PR.
- [RECOVERY.md](operations/RECOVERY.md) — Khôi phục GitOps PR, cluster/DB/Kafka & S3 backup/restore boundaries.

### Subsystem Handoffs
- [APP_INTEGRATION.md](handoffs/APP_INTEGRATION.md) — Contract tích hợp app, Dockerfiles, MQTT bridge, KServe `/api/v1/predict/batch`, health endpoints & image registry expectations.
- [KAFKA.md](handoffs/KAFKA.md) — Handoff Kafka `1.4` (`OUTCOME-14-ONLY`, Producer pipelining + `lz4`, single-pod MQTT→Kafka bridge, Commit Batching, Strimzi pins).
- [PROCESSING_ORDERING_HANDOFF.md](handoffs/PROCESSING_ORDERING_HANDOFF.md) — Handoff `PROC-ORDER-01` (strict `per_key=1`, per-key micro-batching `<=16`) và config env cho Processing Worker & Outbox Relay.
- [MLFLOW_IMAGE_MIGRATION.md](handoffs/MLFLOW_IMAGE_MIGRATION.md) — Quyền build/publish MLflow server image thuộc `MaintAI/ml-service/mlflow/`.

### Locks
- [application-source-lock.json](locks/application-source-lock.json) — Bản ghi provenance các tài liệu ứng dụng tại thời điểm thiết kế.
- [reference-lock.json](locks/reference-lock.json) — Bản ghi commit tham chiếu Iris & target revision `1.4.0`.
