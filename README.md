# MaintAI-gitops

GitOps source for MaintAI: AWS production and local **k3d + Argo CD** have separate
desired-state roots. Public remote: [chiendz11/MaintAI-gitops](https://github.com/chiendz11/MaintAI-gitops).
The AWS baseline remains1.3.1; local source locks track the reviewed application
commit, native outcome1.4.0, ML inference and RAG. Publishing source does not
activate workloads or prove a cluster deployment.

**Start here:** [architecture](docs/ARCHITECTURE.md),
[bootstrap](docs/BOOTSTRAP.md), [application handoff](docs/APP_INTEGRATION.md),
[training](docs/TRAINING.md), [versioning](docs/VERSIONING.md),
[secrets](docs/SECRETS.md), [recovery](docs/RECOVERY.md).

Kafka handoff now follows application1.4 wire freeze with the shared Python SDK;
see [Kafka contracts and owners](docs/KAFKA.md). This is a scoped Kafka update,
not a claim that all platform/runtime metadata migrated to1.4.

MLflow image source/local dev/publisher now live in `MaintAI/ml-service/mlflow/`.
This repo keeps its production deployment/config and verifies the app-signed
digest; GitOps publication is automation-only. See
[MLflow image migration](docs/MLFLOW_IMAGE_MIGRATION.md) for signer/IAM cutover
and remaining activation inputs. No MLflow image or workload is enabled here.

```text
applications/                 Argo CD AppProject/add-on/child Application sources
platform/                     Kafka, secrets, storage, monitoring and MLflow
workloads/                    13 application runtime manifest packages
config/                       versioned component/protocol/access/quality policies
state/production/             reviewed desired image/model/platform state
environments/production/      active Kustomize roots, initially workloads disabled
contracts/                    neutral platform, workload, dataset and model schemas
automation/                   identity checks, renderers, signatures, PR/recovery
runtime/                      platform helper image, artifact downloader, training ledger
integrations/MaintAI/         app CI/schema templates; not installed into the app
operations/                   manual DB bootstrap/owner migrations; outside Argo roots
versions/                     chart/base-image pins and immutable contract hashes
.github/workflows/            gated PR receivers, image publication and future CI
```

Production is the only deployment environment; no fictional staging is added.
Main UI -> Business API; Simulator UI -> Sensor Control API. Processing remains
three Deployments, Business two. ML training/inference are separate images.

All app `enabled` flags are false. Images/base digests and cloud values are unset
rather than fabricated. The active app root contains no executable workload.
The Argo root starts with AppProject only; platform handoff proposes children.
Children initially require manual sync; automatic sync requires a reviewed config
change. Initial workload enablement additionally requires reviewed entrypoints,
DB bootstrap/migrations, TLS CA and resolved protocol metadata.

Iris patterns reused: Terraform/Argo ownership, neutral release intents, receiver-
owned PRs, protected main, immutable artifacts and independent lifecycle stages.
Reference main commits are captured in [reference-lock](docs/reference-lock.json).
This new code does not reuse the old underscore deployment folders as active state.

## Application alignment — PROC-ORDER-01,2026-10-23

The current app design is [v1.4 + PROC-ORDER-01](../MaintAI/docs/PROCESSING_CONCURRENCY_AND_ORDERING.md),
with [SDK0.2/bundle1.1 implementation evidence](../MaintAI/docs/PROCESSING_ORDERING_IMPLEMENTATION_REPORT.md).
This supplements the existing platform1.3.1 baseline; it is not a full platform
migration or deployment. Keyed queues/offset coordinator stay inside Worker;
ordered key cursor stays with Relay. No new workload/database/UI is introduced.
All image/enablement/cloud gates remain as configured; real callbacks, owner DB
activation and image/runtime/config review are still required.

## Local development — k3d + Argo CD (1.0.0)

Local development is now part of these two platform repositories. Infrastructure
bootstraps the cluster/private kubeconfig/secrets/Argo CD; GitOps owns local
platform and app desired state. AWS production sources remain independently
versioned. Source is published and checked by [GitHub CI](https://github.com/chiendz11/MaintAI-gitops/actions/workflows/ci.yml).
Image builds, Argo synchronization and a full local demo require separate runtime evidence.

Start with [local development](docs/LOCAL_DEVELOPMENT.md), [migration](docs/LOCAL_MIGRATION.md) and [versioning](docs/LOCAL_VERSIONING.md).

See [source synchronization and publication](docs/LOCAL_SOURCE_SYNC.md) for the
current app revision, ML/RAG runtime inputs and the distinction between source
CI and running the demo.
