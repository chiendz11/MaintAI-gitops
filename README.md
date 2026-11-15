# MaintAI-gitops

Pure Declarative Kubernetes Desired State for MaintAI (`AWS Production` and `Local k3d + Argo CD`).
Public remote: [chiendz11/MaintAI-gitops](https://github.com/chiendz11/MaintAI-gitops).

**Start here:** [docs index](docs/README.md), [architecture](docs/architecture/ARCHITECTURE.md),
[versioning](docs/architecture/VERSIONING.md), [local development](docs/operations/LOCAL_DEVELOPMENT.md),
[source sync](docs/operations/LOCAL_SOURCE_SYNC.md), [bootstrap](docs/operations/BOOTSTRAP.md),
[secrets](docs/operations/SECRETS.md), [recovery](docs/operations/RECOVERY.md).

## Repository Layout

```text
applications/                     Argo CD AppProject, ImageUpdater CRs & child Applications
  ├── addons/                     Production cluster add-ons (ESO, Argo Events, Image Updater)
  └── local/                      Local k3d root, platform, observability, apps & ImageUpdater
base/                             Pure declarative Kustomize workload bases (12 services)
bootstrap/                        Root Application bootstraps for local & production
docs/                             Architecture, operations runbooks, subsystem handoffs & locks
environments/
  ├── local/                      Active k3d overlays (platform/, observability/, apps/)
  └── production/                 AWS EKS overlays (workloads disabled until production review)
local/                            Local non-secret platform/observability manifests
operations/                       Explicit manual DB bootstrap & per-owner migration manifests
platform/                         Production platform components (Kafka, storage, secrets, MLOps)
.github/workflows/ci.yml          Pure YAML CI: kustomize build (18 roots) + kubeconform + link/secret guards
```

## Core Architecture & Image Automation

- **Pure Declarative Kustomize:** All cluster desired state is rendered directly by Argo CD from Kustomize roots (`environments/local/{platform,observability,apps}` and `environments/production/*`) — no Python manifest compiler, JSON lock engine, or imperative release scripts live in this repository.
- **Automated Image Updates via Argo CD Image Updater (`v1.5.0`):**
  - App CI (`MaintAI/.github/workflows/publish-and-deploy.yml`) builds and pushes container images to GHCR (`ghcr.io/chiendz11/maintai-*:sha-<commit>`) without writing back to GitOps.
  - `ImageUpdater` CRs in [`applications/local/image-updater.yaml`](applications/local/image-updater.yaml) and [`applications/image-updater.yaml`](applications/image-updater.yaml) watch registry digests/tags, update Kustomize `images` overrides in `kustomization.yaml`, and open Pull Requests against `main` (`pullRequest.github`) using a Fine-grained PAT synced via `ExternalSecret` (`argocd/argocd-image-updater-git-creds`) from LocalStack (`maintai/local/gitops`) or AWS Secrets Manager (`REPLACE_WITH_SECRET_ARN_argocd-image-updater-git-creds`), never committed to Git.
- **Secrets & TLS:** External Secrets Operator (`ESO`) syncs runtime credentials from AWS Secrets Manager (or LocalStack in local `k3d`) into Kubernetes Secrets. Internal service-to-service TLS and OIDC issuer TLS are issued by `cert-manager`.
- **UI & Workload Boundaries:** Main UI -> Business REST/SSE API (`:8003`); Simulator UI -> Sensor Control API (`:8005`); Processing (`worker`, `read-api`, `outbox-relay`) and Business (`api`, `consumer`) stay separated with strict DB owner isolation.
- **Validation Scope:** [GitHub CI](.github/workflows/ci.yml) validates Kustomize builds, Kubernetes schemas (`kubeconform`), and repository guards (no committed `Secret`, no `:latest` in local overlays, valid markdown links). CI passing does not replace Argo convergence or E2E cluster tests.
