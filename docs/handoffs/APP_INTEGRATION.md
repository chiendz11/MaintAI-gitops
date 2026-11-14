# Application integration contract

General integration templates live in this GitOps repository. The MLflow image
publisher is now implemented directly in MaintAI/ml-service/mlflow with the
app's actual maintai-publish workflow; do not overwrite it with a broad template.
Source owner and API behavior still follow the supplied app contracts. User's
separate Simulator UI decision overrides the former Business control facade.

## Images and entrypoints

MLflow is the scoped exception to application runtime templates: app-owned
`ml-service/mlflow/Dockerfile` produces the server image, while platform/mlops
here keeps its production configuration. Group mlflow uses app actor + exact
app workflow/signature annotations. See [migration](MLFLOW_IMAGE_MIGRATION.md).
The actual app workflow currently publishes only this migrated group; it does
not enable publication of all the skeletons listed below.

`config/components.json` declares proposed runtime modules/ports. Application
teams may change the proposed modules through a reviewed interface PR, then
implement matching Dockerfiles, health endpoints and dependencies. In particular,
legacy sensor CLI and direct-SQL drift image do NOT satisfy the new runtime contract.

| Owner | Build source | Target entrypoints |
|---|---|---|
| Ingestion | ingestion-api/Dockerfile | maintai_ingestion.api, port 8000 |
| Processing | processing/worker/Dockerfile | worker/read_api/outbox_relay under maintai_processing |
| Business | backend/business-api/Dockerfile | maintai_business.api/consumer |
| Storage | storage-consumer/Dockerfile | maintai_storage.consumer |
| ML inference | ml-service/inference/Dockerfile | maintai_ml.inference, /api/v1/predict |
| Training | ml-service/training/Dockerfile | python -m maintai_training |
| RAG | rag-service/Dockerfile | maintai_rag.api |
| Sensor | sensor/Dockerfile | maintai_sensor.controller, control API + replay |
| Drift | drift-worker/Dockerfile | maintai_drift.run, one-shot API/curated-S3 reads |
| Main UI | frontend/Dockerfile | non-root HTTP 8080, /runtime-config.json |
| Simulator UI | simulator-ui/Dockerfile | independent HTTP 8080, same-origin Sensor control |

Python commands are proposed integration entrypoints, not existing app modules.
Workers must expose HTTP health/metrics on 9100 or revise these manifests/probes
before enablement. Frontend images must serve /health/live, /health/ready and the
mounted runtime config as UID 10001 without requiring writes outside /tmp.
HTTP APIs need graceful draining; consumers need correct offset/rebalance handling.

## Integrate producer CI later

Copy `integrations/MaintAI/release/` to the app's `.release/` and the workflow
`integrations/MaintAI/.github/workflows/maintai-publish.yml` to its `.github/workflows/`.
Review this in a separate app PR. Configure ECR allow-list, OIDC publisher role and
an Actions-write-only release publisher App; enable publication only after code
is implemented. Placeholder/missing Dockerfiles are refused. Base images should
be pinned in the app Dockerfiles/build contract.

The producer publishes image digest + source SHA + runtime schema hashes. It
knows no production manifest paths and receives no cluster credentials. Receiver
checks the real publisher actor, owning repository, ECR allow-list and Cosign
identity plus source/group annotations before opening a GitOps-owned PR.

Main Frontend calls Business REST/SSE. Simulator UI calls Sensor control API.
Browser code must never receive internal service keys, cloud keys or LLM keys.
Auth issuer/audiences/public client IDs are public metadata; permission enforcement
is implemented in Business and Sensor. Business simulator_facade is obsolete for
this topology. Current app skeleton still contains it; migrate through an app PR.

## Remaining contract decisions

1. Resolve inference.results 2.0.0 vs 1.1.0 in supplied section 33.5, generate schemas
   and migrate producer/consumers together. Do not just flip the protocol flag.
2. Define a read-only drift-report/checkpoint bridge into Business (API or versioned
   S3/index/projection). Business must not connect directly to drift_db.
3. Define a durable Business brief-job executor. Argo training is not that executor.
4. Implement auth login/token issuance integration and recommendation accept/reject.
5. Implement per-owner migrations and durable per-machine ordering/spool recovery.

These gaps do not cause this platform repo to invent application implementations
or to label the app production-ready.

## Processing transport source update23/10

maintai_processing.worker/outbox_relay and handlers:make_handler now exist in
MaintAI/processing/src. The built-in factory needs real PREPARE/PERSIST callback
module:function values and owner DB; missing callbacks fail closed. These
wrappers do not supply the DQ/ML/risk/history application, health server or a
buildable Processing image. Do not mark entrypoint_reviewed solely from module help.
Config3/Kafka bundle and safe activation gates:
[Processing handoff](PROCESSING_ORDERING_HANDOFF.md). Existing release templates
remain config2.0.0; do not copy a template over the actual app publisher/CI.
