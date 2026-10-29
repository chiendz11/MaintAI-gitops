# Bootstrap and activation order (future operator work)

No commands in this document were executed during initial delivery. Do not treat
this as permission to deploy until application/contract/configuration is ready.

1. Create/publish the two new GitHub repositories when explicitly requested. This
   task only initialized local Git folders; the URLs in manifests are intended URLs.
2. Complete infrastructure bootstrap/domain/platform/Argo CD roots as described in
   ../Maint-infrastructure/docs/BOOTSTRAP.md. Keep enable_gitops_root=false initially.
3. Configure dedicated GitHub Apps/actors and run the future platform handoff.
   Receiver creates a platform PR containing non-secret cloud values, no fake digests.
4. Review and merge platform PR. Seed AWS secret values, review the RDS public CA
   and configure external OIDC clients. Install/synchronize namespaces, add-ons,
   storage, secret-store and Kafka in dependency order. CRDs must exist first.
5. Publish the GitOps automation image through its gated publication workflow;
   `versions/build-images.json` must pin its real Python base digest. MLflow image
   source/base/server pins now belong to `MaintAI/ml-service/mlflow/`; publish that
   group through the **app** maintai-publish workflow and receive its signed digest
   here. Complete the [MLflow signer/IAM migration](MLFLOW_IMAGE_MIGRATION.md)
   before activation. No image publication or cloud configuration was executed.
6. Prepare and explicitly run the manual DB bootstrap package; it is outside all
   Argo roots and ALLOW_DATABASE_BOOTSTRAP defaults to false. Then run reviewed
   per-owner application migrations and MLflow-managed migration separately.
7. Implement/migrate app entrypoints/contracts, including separate simulator-ui.
   Resolve event-schema conflict before enabling relevant Processing/Business consumers.
8. Freeze the training context and approved dataset/protocol. Enable reviewed
   MLflow/training workflow, produce a passing immutable model candidate and merge
   its GitOps PR. No initial dummy model or production fixture is supplied.
9. For each app image, set reviewed entrypoint metadata and valid runtime config,
   then enable through a PR. `python -m automation.configure` writes local desired
   manifests only; it does not apply them. This command was NOT run in this task.
10. Set config/applications.json automatic_sync=true only when ready to let Argo
    reconcile merged changes automatically. The root discovers child Applications;
    child automatic sync starts disabled to keep this draft from activating itself.

Initial config/protocols.json, config/access.json, config/trust.json and state/
contain explicit blockers. Never mark them resolved just to bypass checks.
Separate app/infra/GitOps approvals and actual runtime validation are future work.
