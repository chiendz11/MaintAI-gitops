# RISK-POLICY-01 — Chọn policy từ app và tạo ConfigMap local

## 1. Nguồn nội dung và lựa chọn triển khai

Policy chuẩn thuộc app `MaintAI/processing/config/risk-policies/`, gồm JSON,
schema và catalog. GitOps chỉ quản lý `config/local/risk-policy.lock.json`:
app repository/Git SHA, policy version/path, raw file SHA và canonical policy SHA.
Nội dung ngưỡng không được chỉnh riêng trong GitOps hoặc infrastructure.

Selector hiện chọn `demo-risk-v1`. App catalog ghi demo/chưa calibration; các
ngưỡng tham khảo không bảo đảm model hiện tại tạo alert khi đổi scenario Critical.
Thay đổi nghiệp vụ tạo version mới trong app và cần review trước khi đổi selector.

## 2. Chuẩn bị desired state

Operator infrastructure tự truyền `--app-root` tới GitOps prepare. Nếu gọi trực tiếp:

```bash
python -m localdev.release apps \
  --receipts /absolute/path/to/actual-release-receipts.json \
  --profile /absolute/path/to/reviewed-local-profile.json \
  --app-root /absolute/path/to/MaintAI
```

Lệnh trên vẫn cần actual imported images, dependency/evidence gates và full model
identity. Không dùng fixture receipts từ tests để enable workloads.

Khi Worker enabled, tool kiểm app HEAD và các file trong source lock, rồi kiểm
catalog/schema/selector/raw SHA/canonical SHA, đúng version và thứ tự ngưỡng.
Thiếu source, hash lệch, path ngoài policy directory hoặc JSON lỗi bị từ chối.
Tool chỉ đọc JSON/schema, không chạy code app hoặc tự fetch latest.

Generator đưa đúng nội dung app vào Kustomize ConfigMap generator tên
`processing-risk-policy`. Kustomize thêm content hash; Worker volume reference
được rewrite sang tên đó. Mount read-only tại `/local/config`, env:

```text
PROCESSING_RISK_POLICY_FILE=/local/config/risk-policy.json
```

Pod annotations và release.json ghi policy version/canonical SHA/app SHA.
Đổi nội dung policy thay tên ConfigMap và Pod template reference nên đi qua
rollout; Worker đọc lúc khởi động, không hot reload. GitOps diff phải được
review/commit/push trước khi Argo CD thấy cấu hình.

## 3. Profile cũ cần sửa gì?

- Bỏ `files.risk_policy` và mọi entry trỏ file `risk-policy.json` của Worker.
- Không override `PROCESSING_RISK_POLICY_FILE` qua env.
- Giữ `files.model_identity` với `/local/fixtures/model-identity.json` và hash thật.
- Không tạo/copy policy vào infrastructure `local/.local/data/fixtures/` nữa.

Generator từ chối khai báo cũ để không có hai nguồn policy. Private fixtures vẫn
dùng cho model identity; dataset/model mounts và auth không đổi.

## 4. Thứ tự version và kiểm chứng

1. App PR tạo policy version mới, cập nhật catalog/schema nếu cần và chạy tests.
2. Commit app; push commit app trước khi mở CI/PR platform tham chiếu SHA đó.
3. Cập nhật app source locks của cả hai platform và selector GitOps. Không đổi
   published production schemas/locks chỉ để phục vụ local.
4. Source/unit tests và offline Kustomize kiểm content/hash/reference; chúng
   không chứng minh Argo đã sync hoặc pipeline đã chạy.
5. Operator mới thực hiện runtime rollout và kiểm kết quả/evidence thật.

Profile mẫu vẫn disabled. Các tests trong `tests/test_risk_policy.py` tạo policies
và receipts tổng hợp trong temporary directories; không là policy/model release.
