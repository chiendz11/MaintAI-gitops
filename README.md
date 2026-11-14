# MaintAI-gitops

GitOps source for MaintAI: AWS production and local **k3d + Argo CD** have separate
desired-state roots. Public remote: [chiendz11/MaintAI-gitops](https://github.com/chiendz11/MaintAI-gitops).
The AWS baseline remains1.3.1; local source locks track the reviewed application
commit, native outcome1.4.0, ML inference and RAG. Publishing source does not
activate workloads or prove a cluster deployment.

**Start here:** [docs index](docs/README.md), [architecture](docs/architecture/ARCHITECTURE.md),
[bootstrap](docs/operations/BOOTSTRAP.md), [application handoff](docs/handoffs/APP_INTEGRATION.md),
[training](docs/operations/TRAINING.md), [versioning](docs/architecture/VERSIONING.md),
[secrets](docs/operations/SECRETS.md), [recovery](docs/operations/RECOVERY.md).

Kafka handoff now follows application1.4 wire freeze with the shared Python SDK;
see [Kafka contracts and owners](docs/handoffs/KAFKA.md). This is a scoped Kafka update,
not a claim that all platform/runtime metadata migrated to1.4.

MLflow image source/local dev/publisher now live in `MaintAI/ml-service/mlflow/`.
This repo keeps its production deployment/config and verifies the app-signed
digest; GitOps publication is automation-only. See
[MLflow image migration](docs/handoffs/MLFLOW_IMAGE_MIGRATION.md) for signer/IAM cutover
and remaining activation inputs. No MLflow image or workload is enabled here.

```text
applications/                 Argo CD AppProject/add-on/local/child Application sources
base/                         Pure declarative Kustomize workload bases (12 services)
bootstrap/                    Root Application bootstraps for local & production
docs/                         Organized documentation (architecture, operations, handoffs, locks)
platform/                     Kafka, secrets, storage, monitoring and MLflow
workloads/                    Component patches & runtime overlays
config/                       Versioned component/protocol/access/quality/local locks
environments/{local,production}/  Active Kustomize roots (local k3d vs AWS production)
contracts/                    Neutral platform, workload, dataset, model & local schemas
scripts/                      Automation, renderers, localdev release/checks & unit tests
runtime/                      Platform helper image, artifact downloader, training ledger
integrations/MaintAI/         App CI/schema templates; not installed into the app
operations/                   Manual DB bootstrap/owner migrations; outside Argo roots
versions/                     Chart/base-image pins and immutable contract hashes
.github/workflows/            CI checks, gated PR receivers and image publication
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
Reference main commits are captured in [reference-lock](docs/locks/reference-lock.json).
This new code does not reuse the old underscore deployment folders as active state.

Đã chạy demo local trên `maintai-local` (xem báo cáo thực thi tại [`Maint-infrastructure/docs/demos/LOCAL_DEMO_RUN_2026-10-30.md`](../Maint-infrastructure/docs/demos/LOCAL_DEMO_RUN_2026-10-30.md)), và đã hợp nhất kiến trúc Pure Declarative (`CoreDNS` + `cert-manager` + `main` tracking); không suy kết quả local thành production readiness hoặc chức năng Copilot M7.

## Application alignment — PROC-ORDER-01,2026-10-23

The current app design is [v1.4 + PROC-ORDER-01](../MaintAI/docs/subsystems/PROCESSING_CONCURRENCY_AND_ORDERING.md),
with [SDK0.2/bundle1.1 implementation evidence](../MaintAI/docs/reports/PROCESSING_ORDERING_IMPLEMENTATION_REPORT.md).
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

Start with [local development](docs/operations/LOCAL_DEVELOPMENT.md) (bao gồm cấu trúc pure declarative, M5/M6 và chuyển đổi từ `MaintAI-k3d`) and [versioning](docs/architecture/VERSIONING.md).

See [source synchronization, publication and RISK-POLICY-01](docs/operations/LOCAL_SOURCE_SYNC.md) for the current app revision (`e67d42d`), `processing-risk-policy` ConfigMap và trình tự vận hành.
