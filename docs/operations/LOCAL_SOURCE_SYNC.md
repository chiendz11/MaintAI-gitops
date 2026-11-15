# Tách biệt Repo CI/CD, Argo CD Image Updater & Risk Policy (`RISK-POLICY-01`)

---

## 1. Hệ 3 Repository & Ranh giới Tự động hóa

- **App Repo (`https://github.com/chiendz11/MaintAI`):** Mã nguồn microservices, Dockerfiles, contracts, ML bundles và risk policies. CI workflow (`publish-and-deploy.yml`) **chỉ build & push images** lên GHCR (`ghcr.io/chiendz11/maintai-*:sha-<commit>`); không giữ token ghi ngược sang GitOps.
- **GitOps Repo (`https://github.com/chiendz11/MaintAI-gitops`):** Pure Declarative Kubernetes YAML (`base/`, `environments/{local,production}/`, `applications/`). Cụm `maintai-local` theo dõi trực tiếp nhánh **`main`** (`targetRevision: main`).
- **Infrastructure Repo (`https://github.com/chiendz11/Maint-infrastructure`):** AWS Terraform, `k3d` bootstrap, LocalStack/ESO/cert-manager, cài đặt Argo CD + Argo CD Image Updater (`v1.5.0`) và nạp Fine-grained PAT vào cluster Secret.

---

## 2. Cơ chế Argo CD Image Updater (`Fine-grained PAT` + PR Mode)

Thay cho các script release/commit chéo repo trước đây, luồng cập nhật image dùng chuẩn **GitOps Pull Request**:

1. **Authentication:** Operator tạo một GitHub **Fine-grained Personal Access Token (PAT)** chỉ cấp quyền:
   - Repository access: `Only select repositories` → `chiendz11/MaintAI-gitops`
   - Permissions: `Contents: Read and write` + `Pull requests: Read and write`
   Token được nạp vào LocalStack Secrets Manager (`maintai/local/gitops`) và lưu private ở `local/.local/secrets/` (`0600`) qua lệnh `python -m localdev image-updater-pat` (từ `Maint-infrastructure`), sau đó ESO `ExternalSecret` (`applications/local/image-updater-git-creds.yaml`) đồng bộ thành Secret `argocd-image-updater-git-creds` trong namespace `argocd`, **không bao giờ lưu trong Git**.
2. **Watch & Write-back:** [`applications/local/image-updater.yaml`](../../applications/local/image-updater.yaml) cấu hình `ImageUpdater` (`v1alpha1`) theo dõi `maintai-local-apps`, dùng chiến lược `newest-build` khớp pattern `^sha-[0-9a-f]{40}$` với `writeBackConfig.method: git:secret:argocd-image-updater-git-creds` và `pullRequest.github: {}`.
3. **Review Gate:** Mọi cập nhật `images:` trong [`environments/local/apps/kustomization.yaml`](../../environments/local/apps/kustomization.yaml) đều đi qua **Pull Request** với đầy đủ CI checks (`kubectl kustomize` + `kubeconform`), đảm bảo nhánh `main` luôn sạch và có thể rollback qua `git revert`.

---

## 3. Chính Sách Rủi Ro Do App Sở Hữu (`RISK-POLICY-01`)

- **Source chuẩn:** `MaintAI/processing/config/risk-policies/` (gồm JSON policy, JSON schema và catalog). Không tạo bản ngưỡng chỉnh tay khác biệt trong infrastructure fixtures.
- **Mount & Runtime:** ConfigMap `processing-risk-policy` trong `environments/local/apps/` được Worker mount read-only tại `/local/config/risk-policy.json` với `PROCESSING_RISK_POLICY_FILE=/local/config/risk-policy.json`.
- `demo-risk-v1` là policy tham khảo cho demo local (chưa calibration production); mọi thay đổi ngưỡng nghiệp vụ phải review ở `MaintAI` trước khi cập nhật desired state.

---

## 4. Tích hợp Dữ liệu ML, RAG & Trình tự Vận hành

- **ML Local Baseline & Shadow:** `ml-service` dùng bundle `logreg-baseline-v0`, và `ml-service-shadow` chạy song song (`SERVICE_ROLE=shadow`) với `hgb-interactions-candidate-v1`. Dataset AI4I 10.000 dòng nằm tại `Maint-infrastructure/local/.local/data/datasets/ai4i2020.csv` (ngoài Git).
- **RAG (`rag-service`):** Sử dụng embedding MiniLM multilingual cache trên PVC dùng chung với Job `prepare_demo`, và sinh câu trả lời qua Groq HTTPS (`Secret rag-groq`). Chi tiết model identity và seed knowledge xem tại [`MaintAI/docs/operations/LOCAL_DEMO_PREPARATION.md`](../../../MaintAI/docs/operations/LOCAL_DEMO_PREPARATION.md).
- **Trình tự chuẩn:** Khởi tạo cụm/secrets/Argo CD bằng `Maint-infrastructure` → nạp `image-updater-pat` → Argo CD reconcile `platform`, `observability`, `apps` (PreSync DB migrations & grants) → kiểm tra `Synced / Healthy` → mở Simulator UI (`:18081`).
