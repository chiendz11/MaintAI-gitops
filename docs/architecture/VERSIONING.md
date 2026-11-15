# Versioning and Immutable Provenance (`MaintAI-gitops`)

Tài liệu này quy định cơ chế khóa phiên bản và cập nhật image cho **Desired State (Production & Local)** trong `MaintAI-gitops`.

---

## 1. Production Provenance & Immutability

- Repository version: [`VERSION`](../../VERSION).
- Platform architectural baseline: `maintai-1.3.1+simulator-ui.1`; application target contracts: `1.4.0` + `PROC-ORDER-01/1.0.0`.
- App image (Production): khóa theo immutable digest (`updateStrategy: digest` hoặc release tags `^v[0-9]+\.[0-9]+\.[0-9]+$` trong [`applications/image-updater.yaml`](../../applications/image-updater.yaml)). Nhóm Processing (`worker`, `read-api`, `outbox-relay`) và Business (`api`, `consumer`) dùng chung tên image của từng group để rollout đồng bộ qua cùng một PR.
- **MLflow image (`MLFLOW-IMAGE-01`):** Source và Dockerfile thuộc `MaintAI/ml-service/mlflow/`; GitOps chỉ quản lý manifest K8s dưới `platform/mlops/`. Xem [MLflow migration](../handoffs/MLFLOW_IMAGE_MIGRATION.md).
- Chart versions và S3 model/dataset artifacts: khóa tường minh version/digest; không auto-promote hoặc mutate artifact in-place.

---

## 2. Local Environment Versioning (`k3d` + Argo CD Image Updater)

Môi trường local (`environments/local/`) tách biệt hoàn toàn khỏi production (`environments/production/`):

- **Immutable Image Tags trong Kustomize:** [`environments/local/apps/kustomization.yaml`](../../environments/local/apps/kustomization.yaml) định nghĩa khối `images:` chuẩn Kustomize gắn tag SHA commit (`sha-<git-sha>` hoặc pinned tag) — cấm `:latest` trong `environments/local/` (kiểm tra tự động bởi `.github/workflows/ci.yml`).
- **Automated Image PR Loop (`Argo CD Image Updater v1.5.0`):**
  - [`applications/local/image-updater.yaml`](../../applications/local/image-updater.yaml) cấu hình `ImageUpdater` (`argocd-image-updater.argoproj.io/v1alpha1`) theo dõi các image `ghcr.io/chiendz11/maintai-*` theo pattern `^sha-[0-9a-f]{40}$` (`updateStrategy: newest-build`).
  - Khi phát hiện tag `sha-*` mới trên GHCR, controller ghi thay đổi vào `environments/local/apps/kustomization.yaml` trên một nhánh tạm (`image-updater-...`) và **tạo Pull Request vào `main`** (`pullRequest.github: {}`), tuyệt đối không commit trực tiếp vào `main`.
  - Fine-grained PAT phục vụ tạo PR được nạp vào Secret `argocd-image-updater-git-creds` trong namespace `argocd`, tách khỏi Git.
- **Kustomize Content Hashes:** `configMapGenerator` tự động sinh suffix hash cho cấu hình/policy (`processing-risk-policy`), đảm bảo Pod rollout ngay khi nội dung config đổi.
- **Tách biệt mức độ kiểm chứng:** CI PR (`ci.yml`) chạy `kubectl kustomize` trên toàn bộ 18 Kustomize roots, `kubeconform` schema validation và policy guards (`Secret`, `:latest`, link integrity). CI xanh không đồng nghĩa với Argo CD `Synced/Healthy` hay E2E cluster tests.
