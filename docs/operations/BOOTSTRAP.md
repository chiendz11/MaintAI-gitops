# Bootstrap and Activation Order (Production)

Do not treat this document as permission to deploy production workloads until application, contract, and cloud prerequisites are reviewed and verified.

1. Complete AWS infrastructure bootstrap/domain/platform/Argo CD roots as described in `../Maint-infrastructure/docs/operations/BOOTSTRAP.md`. Keep `enable_gitops_root=false` initially. Non-secret AWS outputs are published to SSM Parameter Store (`/maintai/v13/production/platform-metadata`) instead of GitOps dispatch webhooks.
2. Seed AWS Secrets Manager values externally and configure the reviewed external OIDC issuer/clients and AWS RDS public CA bundle (`Global Bundle`).
3. Install/synchronize namespaces, cluster add-ons (`applications/addons/` including `external-secrets` with `external-secrets` IRSA, `argo-events`, and `argocd-image-updater` with `image-updater` ECR-read IRSA), storage, secret-store, and Strimzi Kafka in dependency order. CRDs must exist first.
4. Populate AWS Secrets Manager secret `argocd-image-updater-git-creds` (JSON keys `username` + `password` for Fine-grained PAT, or update `platform/secrets/image-updater-git-creds.yaml` if using GitHub App) and substitute `REPLACE_WITH_SECRET_ARN_argocd-image-updater-git-creds` in [`platform/secrets/image-updater-git-creds.yaml`](../../platform/secrets/image-updater-git-creds.yaml) so ESO syncs `Secret/argocd-image-updater-git-creds` into namespace `argocd` for [`applications/image-updater.yaml`](../../applications/image-updater.yaml).
5. Publish signed application and MLflow images from `MaintAI` (`ghcr.io` or private ECR). Pin immutable digests via reviewed PRs in `environments/production/`.
6. Prepare and explicitly review manual DB bootstrap and per-owner migrations under [`operations/`](../../operations/) (excluded from automatic Argo roots). Run MLflow-managed DB upgrades separately with its owner credential.
7. Enable approved production workloads incrementally via reviewed PRs (setting image digests, valid ConfigMaps, HPA/PDB, and `replicas > 0`).
8. Enable child `automated` sync policies only after initial convergence checks and operator review pass.
