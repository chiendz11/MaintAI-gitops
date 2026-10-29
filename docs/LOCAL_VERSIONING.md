# Versioning local

Local profile/receipt schemas1.0.0 độc lập repo VERSION, app contract1.4.0, Kafka
bundle2.0.0 và các runtime schemas production2/3 đã freeze. Không bump app wire
version chỉ vì thêm environment.

Actual local image receipt gồm Docker image ID, content-derived alias, Git commit,
dirty flag, source snapshot SHA256, Dockerfile SHA256, context và imported context.
Một tag như :dev không đủ. Dirty builds chỉ khi operator chọn rõ, không dùng làm
release production hoặc ECR signature evidence. Build không tự commit/push.

Custom platform images MinIO/MC/dev-tools cũng cần receipt và được import trước
Argo sync. Platform lock giữ OCI digests/tool versions, source tar hashes và
Argo manifest SHA256. Argo installer images được thay bằng digest theo lock.
Kubectl dùng cho CI Kustomize được tải từ official URL với SHA256 đã ghi nhận.
Metadata lookup/pins không chứng minh build compatibility hoặc runtime success.

Kustomize configMapGenerator tạo content hashes; không tái sử dụng hash production
cho config local mới. Release preparation chỉ ghi environments/local; muốn đổi
production phải qua paths/workflows/contracts riêng.

Model/dataset/reference cần file SHA256 và metadata matching model version. S3
phải giữ VersionId; ETag không thay checksum. Local artifact init không chứng minh
model quality, chỉ từ chối bytes khác approved lock. Training candidate không tự
trở thành serving model.

`versions/local-contracts.lock.json` bảo vệ schema local mới. Fingerprints trong
`versions/local-production-baseline.lock.json` xác nhận phạm vi local không sửa
AWS/production bytes; thay đổi production về sau phải cập nhật fingerprint bằng
review tương ứng, không bỏ policy để lách.

## Public source synchronization — 2026-10-29

App lock now references committed SHA `7c05489f705e0f55c45d03252869e27760da1c25` (PR15/16/19 and Storage0.2.1).
Both platform CI workflows verify the exact app revision and selected file hashes.
Schema1.0.0, production fingerprints and disabled release gates remain unchanged.
See [source sync](LOCAL_SOURCE_SYNC.md) for public remotes and runtime inputs.
