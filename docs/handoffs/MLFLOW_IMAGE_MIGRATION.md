# MLflow Image Producer Ownership

Source/Dockerfile ownership for MLflow Server lives in `MaintAI/ml-service/mlflow/`; `MaintAI-gitops` remains the Kubernetes desired-state owner (`platform/mlops/` for production, `environments/local/apps/mlflow.yaml` for local `k3d`).

| Item | Owner |
| --- | --- |
| Dockerfile, server pins, local Compose | `MaintAI/ml-service/mlflow/` |
| Deployment/Service/IRSA/config/secret refs | `MaintAI-gitops` (`platform/mlops/`, `environments/local/apps/mlflow.yaml`) |
| RDS/S3/ECR/IAM/network/cluster | `Maint-infrastructure` |
| Training SDK/evaluation/model data | `MaintAI/ml-service/training/` |

In production, MLflow remains disabled until the server image is built/published from `MaintAI`, signed/verified, IAM roles are aligned, and DB/S3 auth prerequisites are reviewed. Rolling back an image PR does not revert `mlflow_db` migrations.
