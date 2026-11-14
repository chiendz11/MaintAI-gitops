# Đồng bộ Source Local, Public Remotes & App-Owned Risk Policy (`RISK-POLICY-01`)

**Cập nhật:** 14/11/2026 (sau khi merge toàn bộ PR vào nhánh `main` trên cả 3 repository).

---

## 1. Hệ 3 Repository & Nguồn Argo CD Theo Dõi

- **App Repo:** `https://github.com/chiendz11/MaintAI` — mã nguồn microservices, Dockerfiles, contracts, ML bundles và risk policies.
- **GitOps Repo:** `https://github.com/chiendz11/MaintAI-gitops` — desired state Kubernetes (`base/`, `environments/{local,production}/`, `applications/`) và release/policy tools (`scripts/`).
- **Infrastructure Repo:** `https://github.com/chiendz11/Maint-infrastructure` — AWS Terraform, `k3d` bootstrap, LocalStack/ESO/cert-manager, private credentials và Argo CD root bootstrap.

Cụm `maintai-local` theo dõi trực tiếp nhánh **`main`** của `https://github.com/chiendz11/MaintAI-gitops.git` (`targetRevision: main` trong `applications/local/` và `bootstrap/local/`). Argo CD chỉ đọc commit đã push lên remote.

---

## 2. Cơ Chế Khóa Source (`app-source.lock.json`)

Hai bản lock ở 2 repo phải khớp nhau:
- **GitOps:** `config/local/app-source.lock.json`
- **Infrastructure:** `local/versions/app-source.lock.json`

Lock hiện tại khóa **Git SHA `e67d42d0d2fd347c686a39928906c20b68f03992`** (`chiendz11/MaintAI`, nhánh `main` — tổng hợp đầy đủ M5 Alert Lifecycle, M6 History/Export + Catalog EOF fix `#40/#41`, CoreDNS networking `#42`, RAG Groq `#35`, ML Shadow `SERVICE_ROLE` & reproducible candidate bundle `#37/#39`), cùng SHA-256 của 40+ Dockerfiles, settings, contracts và policy files.

**Quy tắc đồng bộ:**
- GitHub Actions CI (`ci.yml`) ở cả `MaintAI-gitops` và `Maint-infrastructure` đều checkout chính xác SHA trong `app-source.lock.json` vào `.ci-app` và chạy `scripts/localdev/checks.py --app-root .ci-app` để kiểm tra từng byte hash.
- Khi `MaintAI` có commit mới trên `main`, cần chạy đồng bộ lại `app-source.lock.json` và `risk-policy.lock.json` ở cả 2 repo platform rồi push; không sửa tay checksum để bỏ qua khác biệt mã nguồn.

---

## 3. Chính Sách Rủi Ro Do App Sở Hữu (`RISK-POLICY-01`)

### 3.1. Nguồn chuẩn và Lock GitOps
- **Source chuẩn:** `MaintAI/processing/config/risk-policies/` (gồm JSON policy, JSON schema và catalog). Không chỉnh sửa hay tạo bản ngưỡng riêng trong `MaintAI-gitops` hoặc `Maint-infrastructure/local/.local/data/fixtures/`.
- **Selector GitOps:** `config/local/risk-policy.lock.json` khóa `source_git_sha` (`e67d42d0d2fd347c686a39928906c20b68f03992`), `policy_version` (`demo-risk-v1`), `policy_path`, raw file SHA-256 và canonical policy SHA-256.
- `demo-risk-v1` là policy tham khảo phục vụ demo (chưa calibration production); mọi thay đổi ngưỡng nghiệp vụ phải tạo version mới trong `MaintAI` trước khi đổi selector.

### 3.2. Cách Chuẩn Bị & Rollout ConfigMap `processing-risk-policy`
Operator từ `Maint-infrastructure` tự động truyền `--app-root` tới GitOps generator, hoặc chạy trực tiếp từ root `MaintAI-gitops`:

```bash
PYTHONPATH=scripts python -m localdev.release apps \
  --receipts /absolute/path/to/actual-release-receipts.json \
  --profile /absolute/path/to/reviewed-local-profile.json \
  --app-root /absolute/path/to/MaintAI
```

**Cơ chế kiểm chứng & phát hành:**
1. Generator đối chiếu `HEAD` của `--app-root` với `app-source.lock.json`, xác thực catalog, JSON schema, selector, `raw_sha256` và `canonical_sha256`. Sai lệch SHA hoặc JSON lỗi sẽ bị từ chối ngay (`fail closed`).
2. Nội dung hợp lệ được đưa vào Kustomize `configMapGenerator` tên `processing-risk-policy` (gắn content hash hậu tố). Worker mount read-only tại `/local/config/risk-policy.json` với biến môi trường `PROCESSING_RISK_POLICY_FILE=/local/config/risk-policy.json`.
3. Mọi profile cũ khai báo `files.risk_policy` hoặc override `PROCESSING_RISK_POLICY_FILE` qua env đều bị từ chối để đảm bảo duy nhất 1 nguồn policy.
4. Khi policy thay đổi, content hash đổi theo khiến Pod Worker tự động rollout qua GitOps PR. Model identity (`/local/fixtures/model-identity.json`) vẫn được giữ tách biệt với risk policy.

---

## 4. Tích hợp Dữ liệu ML, RAG & Trình tự Vận hành Sau Khi Sync

- **ML Local Baseline & Shadow:** Worker dùng policy ConfigMap từ `RISK-POLICY-01`; `ml-service` dùng bundle `logreg-baseline-v0` (`pipeline.joblib`, `metadata.json`, `evaluation.json`, `drift_reference.json`), và `ml-service-shadow` chạy song song (`SERVICE_ROLE=shadow`) với `hgb-interactions-candidate-v1`. Dataset AI4I 10.000 dòng nằm tại `Maint-infrastructure/local/.local/data/datasets/ai4i2020.csv` (ngoài Git).
- **RAG (`rag-service`):** Sử dụng embedding MiniLM multilingual (`rag-service/embedding-lock.json`) cache trên PVC dùng chung với PreSync/Owner Job `prepare_demo`, và sinh câu trả lời qua Groq HTTPS (`Secret rag-groq`). Chi tiết quy trình model identity và seed knowledge xem tại [`MaintAI/docs/operations/LOCAL_DEMO_PREPARATION.md`](../../../MaintAI/docs/operations/LOCAL_DEMO_PREPARATION.md).
- **Trình tự chuẩn:** Pull cả 3 repo trên nhánh `main` → khởi tạo cụm/secrets bằng Terraform hoặc `Maint-infrastructure` CLI → Argo CD reconcile `platform`, `observability`, `apps` (tự động chạy PreSync DB migrations & grants) → kiểm tra `Synced / Healthy` → mở Simulator UI (`:18081`) chuyển từ `PAUSED` sang `RUNNING`.
