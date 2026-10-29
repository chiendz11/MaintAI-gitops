# MLflow image producer migration — 2026-10-21

This change moves MLflow image **source/publication**, not its production workload.
Source is `chiendz11/MaintAI/ml-service/mlflow/`; this repo remains the desired-state
and operations owner. MLflow stays disabled with no fabricated production digest.

## Ownership

| Item | Owner |
| --- | --- |
| Dockerfile, adapter requirements lock, upstream/server-version pins, local Compose | MaintAI/ml-service/mlflow |
| MLflow image publish + keyless signing workflow | MaintAI/.github/workflows/maintai-publish.yml |
| Deployment/Service/IRSA/config/secret references/resources/enablement | MaintAI-gitops/platform/mlops |
| RDS/S3/ECR/IAM/network/cluster | Maint-infrastructure |
| Training SDK/evaluation/model data | MaintAI/ml-service/training, unchanged |

Deleted `runtime/mlflow.Dockerfile` and removed `mlflow_base_image` from this repo's
`versions/build-images.json`. The GitOps publication command/workflow now accepts
**automation only**. No duplicate MLflow Dockerfile or second producer is retained.
MLflow upstream UI/server is not forked; its app folder does not merge training,
inference and server deployments or introduce an additional database.

## Reviewed image trust

`config/image-groups.json` now declares MLflow producer `chiendz11/MaintAI`,
Dockerfile `ml-service/mlflow/Dockerfile`, build context `ml-service/mlflow`,
publisher `maintai-publish.yml`, and required annotations:

- `git_sha` equal to the intent source commit;
- `image_group=mlflow`;
- `source_repository=chiendz11/MaintAI`.

`automation.verify_image.expected_publisher` derives certificate identity from the
reviewed group, never from an intent-provided workflow:

```text
https://github.com/chiendz11/MaintAI/.github/workflows/maintai-publish.yml@refs/heads/main
issuer: https://token.actions.githubusercontent.com
```

The receiver also requires the app publisher actor and approved ECR repository.
Old GitOps MLflow intents/signatures fail ownership verification; automation images
retain their existing GitOps producer. Do not broaden issuer/subject regexes or
resign old artifacts to bypass the migration. Rebuild/release from the new source.

The handoff is unchanged workload-release1.0.0, with legacy architecture identifier
`maintai-1.3.1+simulator-ui.1` and empty runtime schema map for the platform group.
The app doesn't send platform config or enablement. `release.workload` records
MLflow digest/app source SHA/repository/workflow and renders a reviewable proposal;
it does not enable MLflow or merge the PR. Platform/runtime1.4 migration is separate.

## Activation order (future work, not executed here)

1. Merge both source changes before publishing or accepting a new intent. The app
   owns upstream/server patch/dependency locks; pin a real base digest and validate
   the exact client/server/dependency/CLI/serialization pair first.
2. **Update infrastructure IAM before enabling publication.** Current
   `Maint-infrastructure/terraform/platform/iam.tf` publisher sets still grant
   mlflow ECR to the GitOps role and exclude it from the app role. Move that grant
   to the app role and keep the GitOps role automation-only; review/apply separately.
   The source migration in these two repos does not change deployed IAM.
3. Configure ECR immutability and app publisher role/region/repository mapping,
   environment prod controls, the repository-scoped app installation and receiver
   APP_RELEASE_ALLOWED_ACTOR. Existing image/source pins and cloud resources stay
   unset until operator configuration. No registry or secret is created here.
4. Use the **app** manual maintai-publish workflow for mlflow. It checks pins,
   builds/smokes, pushes/signs an ECR digest and dispatches workload-release here.
   A reused tag must already verify under the app identity; unsigned interrupted
   publications require operator triage, not automatic trust adoption.
5. Review/merge the resulting image PR. Independently review migrations, DB/S3
   credentials/auth and mlflow enabled=true before synchronizing a workload.

The application source CI tests publisher logic offline. This GitOps delivery is
code-first: source syntax/data consistency checks are not Cosign/ECR/DB/Kubernetes
integration or deployment evidence. No platform tests/builds/render/workflows,
Docker, Terraform or cloud changes were run for this migration.

## Rollback

An older compatible **app-signed** MLflow digest may be restored through a reviewed
desired-state PR, with DB migration compatibility checked separately. A Git revert
does not roll back MLflow database migrations/artifacts. Restoring the old GitOps
image producer requires a separate trust-policy/IAM/source migration; do not
silently accept the old signer during this cutover.
