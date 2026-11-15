# Recovery Boundaries

- **GitOps Desired-State Rollback:** Roll back an application image or manifest change by opening a revert Pull Request against `main` in `MaintAI-gitops` so CI (`kustomize` + `kubeconform`) validates the restored state before Argo CD syncs it. Do not force-push `main` or manually patch synced cluster resources (`selfHeal: true`).
- **Model Bundle Rollback:** Restore the pinned model/preprocessor/reference/metadata bundle digest/S3 VersionId via a GitOps PR checking S3 object availability and API compatibility before merge.
- **Kafka Crash / Rebalance:** Redelivery is expected under at-least-once semantics. Application inbox/outbox and unique IDs keep side effects idempotent. Inspect consumer lag and oldest offset age before retention is exceeded; API/SSE reconnect relies on REST snapshot resync.
- **Training Recovery:** Preserve immutable approved dataset manifest VersionIds and workflow checkpoints before retrying failed Argo Workflow steps.
- **Out-of-Band State:** Database/schema rollback, dataset corrections, expired Kafka retention, and cloud resource recovery require separate operator procedures — GitOps PR rollback does not undo database migrations. Manual operations live under [`operations/`](../../operations/) and stay outside automatic Argo roots.
