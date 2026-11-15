# MaintAI-gitops — Repository Rules & Boundaries

Read [README.md](README.md), [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md), and [docs/architecture/VERSIONING.md](docs/architecture/VERSIONING.md) before modifying manifests.

## Core Principles

1. **Pure Declarative Kustomize Only:** This repository holds only Kubernetes/Kustomize YAML, Argo CD Application/AppProject/ImageUpdater manifests, and documentation. Do not reintroduce Python compilers, JSON state generators, shell deployment scripts, or committed `kind: Secret` resources.
2. **Never Commit Sensitive Material:** Never commit real passwords, Fine-grained PATs, OIDC client secrets, private TLS keys, AWS secrets, Terraform state, or raw datasets.
   - Secret `argocd-image-updater-git-creds` (Fine-grained PAT for Argo CD Image Updater PR creation) is synced into the `argocd` namespace via External Secrets Operator (`ExternalSecret` reading AWS Secrets Manager in Production or LocalStack `maintai/local/gitops` in local dev, seeded via `Maint-infrastructure` CLI `python -m localdev image-updater-pat`), never committed inside Git manifests.
   - Runtime credentials come from External Secrets Operator (`ExternalSecret` -> AWS Secrets Manager / LocalStack) and Strimzi / `cert-manager`.
3. **Pull Request Discipline for Image Updates:**
   - Application CI (`MaintAI`) only builds and pushes container images to the registry (`ghcr.io` / ECR); it never pushes commits directly to `MaintAI-gitops`.
   - Argo CD Image Updater (`ImageUpdater` CRD) proposes image updates via native GitHub Pull Requests (`pullRequest.github: {}`) against `main` so CI (`kustomize` + `kubeconform`) runs before merge.
4. **Repository Ownership Split:**
   - **MaintAI:** Application source code, Dockerfiles, contracts (`1.4.0`), ML inference/training, risk policies, DB migrations, and container image publishing CI.
   - **MaintAI-gitops:** Kubernetes desired state (`base/`, `environments/`, `applications/`, `bootstrap/`, `platform/`, `local/`, `operations/`).
   - **Maint-infrastructure:** Cluster provisioning (AWS EKS / local `k3d`), LocalStack, ESO/cert-manager/Ingress/Argo CD/Image Updater bootstrap, kubeconfig isolation, and local secret injection.
5. **Architectural Invariants:**
   - Separate Simulator UI (`sensor` control API) from Main UI (`business-api` REST/SSE) (`UI-01`).
   - Strict 5-database owner isolation (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`); no cross-owner SQL.
   - Production workloads in `environments/production/` keep `enabled`/replicas disabled until real ECR digests, DB bootstrap, and reviews are complete.
   - Local overlays (`environments/local/`) must never leak plaintext secrets, `:latest` application tags, or `replication: 1` assumptions into `environments/production/`.
   - Preserve `PROC-ORDER-01` failure semantics, Kafka `OUTCOME-14-ONLY` contract compatibility, and drift/training isolation (drift never auto-promotes or retrains a model).

## Verification Scope

Running [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (`kubectl kustomize` + `kubeconform`) verifies manifest structure and repository safety rules offline. It does not prove live Argo CD convergence, database readiness, or E2E application behavior.
