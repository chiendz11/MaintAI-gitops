# Pure Declarative GitOps Blueprint (Kubernetes + Argo CD + Image Updater)

Tài liệu mẫu chuẩn (project-agnostic) để tái sử dụng kiến trúc **Pure Declarative GitOps** cho bất kỳ hệ thống microservices/AI nào chạy trên Kubernetes (từ cụm **Local `k3d`** đến **Production `EKS`**).

> Tài liệu này được đúc kết từ kiến trúc vận hành thực tế của `MaintAI-gitops` (Argo CD + Argo CD Image Updater `v1.5.0` + Kustomize + External Secrets Operator). Chỉ cần thay các placeholder `<project>`, `<org>`, `<app-repo>`, `<gitops-repo>`, `<registry>` là có thể áp dụng ngay cho dự án mới.

---

## 1. Kiến trúc tổng thể & Nguyên tắc bất biến

### Mô hình 3 repository tách biệt

| Repository | Vai trò duy nhất | Công cụ chính | Không được làm |
| :--- | :--- | :--- | :--- |
| **`<project>-app`** | Build code, chạy unit/integration test, build & push container image (`sha-<40>` / `vX.Y.Z`) | GitHub Actions, Docker Buildx, GHCR / ECR | Không clone/commit trực tiếp vào GitOps repo; không giữ Kubernetes YAML deploy |
| **`<project>-infra`** | Provision hạ tầng (VPC, EKS/k3d, RDS, S3, KMS, IAM/IRSA, ESO, Argo CD bootstrap) | Terraform, Helm, CLI bootstrap | Không lưu secret plaintext trong TF state; không nhúng business manifests |
| **`<project>-gitops`** | Nguồn chân lý duy nhất (**Single Source of Truth**) cho trạng thái Kubernetes | Kustomize, Argo CD (`Application` / `AppProject`), Image Updater CR | Không lưu `kind: Secret` plaintext; không dùng tag `:latest`; không chạy script deploy ad-hoc |

### Luồng Continuous Delivery chuẩn (Zero Direct Push to `main`)

```text
[<project>-app: main / release tag]
       │
       │  (1) CI build & push image: <registry>/<svc>:sha-<40> (hoặc vX.Y.Z)
       ▼
[Container Registry (GHCR / Amazon ECR)]
       │
       │  (2) Image Updater poll theo lịch (~2m) + lọc AllowTags regex
       ▼
[Argo CD Image Updater v1.5.0 (CRD ImageUpdater)]
       │
       │  (3) Ghi Kustomize `images:` override vào nhánh `image-updater-*`
       │      và mở Pull Request (pullRequest.github: {})
       ▼
[<project>-gitops: Pull Request]
       │
       │  (4) GitOps CI chạy: kubectl kustomize + kubeconform + Secret/latest guards
       ▼
[Merge vào main] ──▶ [Argo CD tự động Sync (prune + selfHeal) vào Cluster]
```

### 6 nguyên tắc bắt buộc
1. **Pure Declarative Manifests**: Mọi Workload phải render ra được từ `kubectl kustomize <overlay>` mà không cần script tiền xử lý hay thay chuỗi thủ công.
2. **Immutable Image Tags / Digests**: Tuyệt đối cấm `:latest` trong manifests. Local/Dev dùng `sha-<40-char-git-sha>`; Production dùng `vX.Y.Z` ghim kèm `@sha256:<digest>` (`updateStrategy: digest`).
3. **Pull Request Gate cho mọi thay đổi Image**: Dùng `writeBackConfig.method: git:...` kết hợp `pullRequest.github: {}` để Image Updater mở PR thay vì commit thẳng vào `main`.
4. **Zero Plaintext Secrets in Git**: GitOps chỉ chứa `ExternalSecret` (sync từ AWS Secrets Manager / LocalStack / Vault qua ESO). Các Bootstrap Secret bắt buộc có trước khi sync (ví dụ Git credentials cho Argo CD / Image Updater) được nạp trực tiếp vào cluster bởi Infra CLI hoặc ESO.
5. **Tách biệt App-of-Apps theo tầng**: Chia nhỏ theo `bootstrap` -> `platform` (ESO, Ingress, Cert-Manager, DB operators) -> `observability` (Prometheus/Grafana/Loki) -> `applications` (Workloads) để tránh lỗi circular dependency và giúp rollback theo từng tầng.
6. **Schema Validation Gate trên PR**: Mọi PR vào GitOps đều phải pass `kubectl kustomize` + `kubeconform` + kiểm tra policy trước khi merge.

---

## 2. Cấu trúc thư mục chuẩn của `<project>-gitops`

```text
<project>-gitops/
├── .github/
│   └── workflows/
│       └── ci.yml                       # Render kustomize + kubeconform + policy guards
├── bootstrap/
│   ├── local/
│   │   ├── kustomization.yaml
│   │   ├── project.yaml                 # AppProject cho local
│   │   └── root-app.yaml                # Application root (App-of-Apps)
│   └── production/
│       ├── kustomization.yaml
│       ├── project.yaml
│       └── root-app.yaml
├── applications/
│   ├── addons/
│   │   └── argocd-image-updater.yaml    # Helm Application cài đặt Image Updater v1.5.0
│   ├── local/
│   │   ├── kustomization.yaml
│   │   ├── platform.yaml                # Application: environments/local/platform
│   │   ├── observability.yaml           # Application: environments/local/observability
│   │   ├── apps.yaml                    # Application: environments/local/apps
│   │   └── image-updater.yaml           # CRD ImageUpdater (local dev tracking sha-*)
│   └── production/
│       ├── kustomization.yaml
│       ├── platform.yaml
│       ├── apps.yaml
│       └── image-updater.yaml           # CRD ImageUpdater (prod tracking semver/digest)
├── base/
│   ├── <service-a>/
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── external-secret.yaml         # ExternalSecret thay cho Secret plaintext
│   └── <service-b>/
│       └── ...
├── environments/
│   ├── local/
│   │   ├── platform/kustomization.yaml
│   │   ├── observability/kustomization.yaml
│   │   └── apps/kustomization.yaml      # Nơi Image Updater ghi block `images:`
│   └── production/
│       ├── platform/kustomization.yaml
│       └── apps/kustomization.yaml
├── operations/
│   ├── database-bootstrap/              # Argo CD Hook / Job tạo schema, role khởi tạo
│   └── migrations/                      # Manual / Sync-wave migration Jobs
└── docs/
    └── README.md
```

> **Lưu ý về cấu trúc `applications/`**: Nếu một `root-app` theo dõi `applications/local/`, hãy đặt các `Application` theo thứ tự **`sync-wave`** (`argocd.argoproj.io/sync-wave: "-2"`, `"-1"`, `"0"`, `"1"`) để `platform` + `addons` chạy ổn định trước khi `apps` khởi động.

---

## 3. Bộ Manifest mẫu chuẩn (Copy-Paste & Thay Placeholder)

### 3.1. `bootstrap/<env>/root-app.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <project>-<env>-root
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argocdproj.io
spec:
  project: <project>-<env>
  source:
    repoURL: https://github.com/<org>/<project>-gitops.git
    targetRevision: main
    path: applications/<env>
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### 3.2. `applications/addons/argocd-image-updater.yaml` (Helm v1.1.0 / Image Updater v1.5.0+)

Kể từ Argo CD Image Updater `v1.5.0` (Helm chart `1.1.x`), cấu hình theo dõi image chuyển sang **CRD `ImageUpdater`** thay vì nhồi hàng chục annotation dài vào `Application`. Chart có tùy chọn tạo controller chạy trong namespace `argocd`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd-image-updater
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
spec:
  project: <project>-<env>
  source:
    repoURL: https://argoproj.github.io/argo-helm
    chart: argocd-image-updater
    targetRevision: 1.1.0
    helm:
      releaseName: argocd-image-updater
      valuesObject:
        metrics:
          enabled: true
        # Nếu dùng ECR private trên EKS Production, gắn IRSA annotation tại đây:
        # serviceAccount:
        #   annotations:
        #     eks.amazonaws.com/role-arn: arn:aws:iam::<ACCOUNT_ID>:role/<project>-image-updater
        config:
          registries:
            - name: GitHub Container Registry
              api_url: https://ghcr.io
              prefix: ghcr.io
              default: true
              # Nếu repo GHCR private, cấu hình credentials từ Secret:
              # credentials: secret:argocd/ghcr-pull-creds#creds
            # Ví dụ Amazon ECR cho Production:
            # - name: Amazon ECR
            #   api_url: https://<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
            #   prefix: <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
            #   ping: yes
            #   credentials: ext:/scripts/ecr-login.sh
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 3.3. `applications/<env>/image-updater.yaml` (CRD `ImageUpdater` `v1alpha1`)

Dưới đây là mẫu chuẩn ghi đè khối `images:` vào file `kustomization.yaml` của overlay `environments/<env>/apps/` và tự động mở GitHub PR:

```yaml
apiVersion: argocd-image-updater.argoproj.io/v1alpha1
kind: ImageUpdater
metadata:
  name: <project>-<env>-image-updater
  namespace: argocd
spec:
  namespace: argocd
  commonUpdateSettings:
    # Local/Staging: dùng "newest-build" với regex sha-40 ký tự
    # Production: nên dùng "digest" (hoặc "semver") với regex ^v[0-9]+\.[0-9]+\.[0-9]+$
    updateStrategy: newest-build
    allowTags: "regexp:^sha-[0-9a-f]{40}$"
    forceUpdate: true
  writeBackConfig:
    method: "git:secret:argocd/argocd-image-updater-git-creds"
    gitConfig:
      repository: "https://github.com/<org>/<project>-gitops.git"
      branch: "main"
      writeBackTarget: "kustomization:../../environments/<env>/apps"
      pullRequest:
        github: {}
  applicationRefs:
    - namePattern: "<project>-<env>-apps"
      images:
        - alias: "api"
          imageName: "ghcr.io/<org>/<project>-api:sha-0000000000000000000000000000000000000000"
        - alias: "worker"
          imageName: "ghcr.io/<org>/<project>-worker:sha-0000000000000000000000000000000000000000"
```

> **Lưu ý quan trọng về đường dẫn `writeBackTarget`**:
> `writeBackTarget: "kustomization:<relative-path>"` được tính **tương đối so với `spec.source.path` của `Application` được match (`<project>-<env>-apps`)**, KHÔNG phải so với root repo!
> - Nếu `Application` trỏ trực tiếp vào `environments/local/apps` -> `writeBackTarget: "kustomization:."` (hoặc `"kustomization:../../environments/local/apps"` nếu source ở `applications/local`). Hãy kiểm tra đúng `spec.source.path` của `Application` mục tiêu!
> - Đối với Production, nên đổi:
>   - `updateStrategy: digest` (hoặc `semver`)
>   - `allowTags: "regexp:^v[0-9]+\\.[0-9]+\\.[0-9]+$"` (ghim chặt version release đã qua QA, chỉ cho Image Updater mở PR cập nhật digest/patch).

### 3.4. `environments/<env>/apps/kustomization.yaml` (Nơi nhận `images:` override)

Mọi workload trong `base/` chỉ khai báo tên image ngắn hoặc placeholder (ví dụ `image: <project>-api`), còn overlay `environments/<env>/apps/kustomization.yaml` ánh xạ về registry và tag thực:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: <project>-<env>

resources:
  - ../../../base/<service-a>
  - ../../../base/<service-b>

images:
  - name: <project>-api
    newName: ghcr.io/<org>/<project>-api
    newTag: sha-<40-char-sha>
  - name: <project>-worker
    newName: ghcr.io/<org>/<project>-worker
    newTag: sha-<40-char-sha>
```

---

## 4. Xác thực Git cho Image Updater (`argocd-image-updater-git-creds`)

Khuyến nghị có 2 lựa chọn tùy quy mô team:

| Tiêu chí | Option A: **Fine-grained PAT** (Nhanh gọn cho cá nhân / team nhỏ) | Option B: **GitHub App** (Chuẩn Production / Enterprise) |
| :--- | :--- | :--- |
| **Cách hoạt động** | Bot dùng PAT cá nhân giới hạn quyền | Bot dùng token ngắn hạn sinh từ Private Key của App |
| **Phạm vi quyền (Least Privilege)** | Chỉ cấp **1 repo** `<project>-gitops`: `Contents: Read and write` + `Pull requests: Read and write` | Cài App chỉ trên `<project>-gitops`: `Contents: Read/Write`, `Pull requests: Read/Write` |
| **Cấu trúc Secret `argocd/argocd-image-updater-git-creds`** | Keys: `username` (`<github-user>`), `password` (`github_pat_...`) | Keys: `githubAppID`, `githubAppInstallationID`, `githubAppPrivateKey` |
| **Rủi ro & Bảo trì** | Hết hạn định kỳ (30–90 ngày), gắn với account tạo PAT | Không phụ thuộc nhân sự nghỉ việc, audit log riêng theo tên App (`app[bot]`) |

Ví dụ nạp Secret cho Option A (không bao giờ commit file này vào Git):

```bash
kubectl -n argocd create secret generic argocd-image-updater-git-creds \
  --from-literal=username="<github-username>" \
  --from-literal=password="<fine-grained-pat>" \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 5. Chiến lược Secrets 2 tầng (Zero Plaintext Secrets in Git)

1. **Tầng Bootstrap (Out-of-band, nạp trước khi Argo CD sync)**:
   - Git SSH key / PAT cho Argo CD & Image Updater (`argocd` namespace).
   - Quyền root cho External Secrets Operator (ví dụ AWS IAM IRSA trên EKS, hoặc Static Secret/LocalStack credentials trên local).
2. **Tầng Application & Platform (Declarative trong GitOps qua ESO)**:
   - Toàn bộ DB passwords, API keys, TLS signing keys lưu tại **AWS Secrets Manager** (Prod) hoặc **LocalStack Secrets Manager** (Local).
   - GitOps chỉ khai báo `ClusterSecretStore` + `ExternalSecret` ở từng service trong `base/<service>/external-secret.yaml`:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: <service>-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager
  target:
    name: <service>-secrets
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: <project>/<env>/<service>
```

---

## 6. Mẫu CI/CD cho App Repo và GitOps Repo

### 6.1. App Repo (`.github/workflows/build-and-push.yml`)

App CI **chỉ build và push image** với tag bất biến `sha-${{ github.sha }}` (và tag `vX.Y.Z` nếu push git tag). Tuyệt đối không sửa file trong repo GitOps!

```yaml
name: Build and Push
on:
  push:
    branches: [main]
    tags: ["v*.*.*"]

jobs:
  docker:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository_owner }}/<project>-api
          tags: |
            type=sha,prefix=sha-,format=long
            type=semver,pattern={{version}}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
```

### 6.2. GitOps Repo (`.github/workflows/ci.yml`)

Chạy bắt buộc trên mọi Pull Request (kể cả PR tự động từ Image Updater) và `main`:

```yaml
name: GitOps CI
on:
  pull_request: {}
  push:
    branches: [main]

jobs:
  validate:
    name: CI / required
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Install kubeconform & kustomize
        run: |
          KUBECONFORM_VER=v0.7.0
          curl -fsSL "https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VER}/kubeconform-linux-amd64.tar.gz" | tar -xz -C /usr/local/bin kubeconform
      - name: Render & Validate Kustomize roots
        run: |
          set -euo pipefail
          for dir in bootstrap/local bootstrap/production applications/local applications/production environments/local/platform environments/local/apps environments/production/platform environments/production/apps; do
            echo "==> Validating $dir"
            kubectl kustomize "$dir" | kubeconform -strict -ignore-missing-schemas -summary
          done
      - name: Policy Guards (No Secrets, No :latest, Broken Links)
        run: |
          python3 - <<'PYTHON'
          from pathlib import Path
          import re
          root = Path(".")
          for p in root.rglob("*.yaml"):
              txt = p.read_text(encoding="utf-8")
              if re.search(r"^kind:\s*Secret\s*$", txt, re.M):
                  raise ValueError(f"Plaintext Kubernetes Secret is forbidden: {p}")
              if re.search(r"image:\s*[^\n]*:latest\b", txt):
                  raise ValueError(f"Mutable :latest tag is forbidden: {p}")
          PYTHON
```

---

## 7. Checklist áp dụng cho dự án mới

- [ ] Khởi tạo 3 repo `<project>-app`, `<project>-infra`, `<project>-gitops` theo đúng ranh giới trách nhiệm.
- [ ] Cấu hình App CI build image tag `sha-${{ github.sha }}` (và `vX.Y.Z` cho release), không giữ deploy token sang GitOps.
- [ ] Cài Argo CD + External Secrets Operator + Argo CD Image Updater (`v1.5.0`+) từ `<project>-infra`.
- [ ] Tạo Fine-grained PAT (scope duy nhất `<project>-gitops`, `Contents: RW`, `Pull requests: RW`) hoặc GitHub App và nạp Secret `argocd/argocd-image-updater-git-creds`.
- [ ] Nạp secrets ứng dụng vào AWS Secrets Manager / LocalStack và khai báo `ExternalSecret` trong `base/`.
- [ ] Khai báo CRD `ImageUpdater` với `pullRequest.github: {}` và bật Branch Protection trên `main` của `<project>-gitops` yêu cầu `CI / required` pass trước khi merge.
- [ ] Kiểm thử chu trình thực tế: merge PR code ở `<project>-app` -> image mới lên registry -> Image Updater tự mở PR ở `<project>-gitops` -> `CI / required` xanh -> merge -> Argo CD sync cụm `Synced / Healthy`.
