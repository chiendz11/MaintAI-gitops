# Chuyển từ MaintAI-k3d sang infrastructure + GitOps local

Quyết định hiện tại: không tạo thêm repo k3d độc lập. Infrastructure có local
cluster/bootstrap; GitOps có local desired state. Folder cũ được giữ làm tham
khảo, chưa bị xóa hoặc chạy commands trong lần viết code này.

| Khả năng cũ | Vị trí mới |
| --- | --- |
| Private kubeconfig/context guard | infrastructure/localdev/common.py, cli.py |
| k3d source/schema/image pins | infrastructure/local/config và local/versions |
| MinIO/MC source builds | infrastructure/local/images + actual build/import receipts |
| Kafka/PostgreSQL/MinIO manifests | GitOps/local/platform, environments/local/platform |
| DB/bucket/topic initialization | GitOps bootstrap Jobs và scripts/configMaps |
| Five DB owners + scoped users | infrastructure secret bootstrap; GitOps DB init; owner image grants Jobs |
| Seven versioned buckets/policies | GitOps config/local/buckets.json, local/platform/policies |
| Monitoring/Grafana/Pushgateway | GitOps/local/observability |
| MLflow handoff | App-owned image; GitOps local release gate/manifest |
| App catalog/readiness | Hai repo local runtime-catalog, profile schema, source locks |
| App apply bằng CLI | Prepare diff → review/commit/push → Argo; CLI không apply app Deployments |
| Explicit owner migration | infrastructure CLI dùng actual app image entrypoints |
| Approved local training | Explicit submit-training Job; không tự retrain/promote |

Không sao chép raw credentials hoặc rendered Secrets giữa old/new. Nếu cluster
cũ đã chạy, chốt backup/cutover riêng: PostgreSQL logical backup, MinIO objects và
versions, Kafka offsets/cursors phù hợp replay policy, Sensor SQLite state và
Keycloak/CA mới. Đây không phải filesystem-copy migration đã kiểm chứng.

Cluster cùng tên được bảo vệ bằng ownership marker; tooling mới từ chối nhận
cluster không do nó tạo. Không xóa/recreate cluster cũ để làm command chạy xanh.
Giữ source sequence và raw evidence; không đoán lại order bằng timestamps.

Sau khi có acceptance platform + M5 pipeline, cập nhật app docs/AGENTS/README đang
trỏ MaintAI-k3d sang hai runbooks mới rồi mới quyết định xóa old folder. Lượt này
chỉ sửa hai repo platform, không tự thay đổi app checkout/PDF hoặc xóa local data.

Production pin/config handoff cũ chưa tự lên v1.4 bởi việc thêm local. Local lock
SDK0.3/bundle2/outcome1.4 riêng; production activation và migration cần review riêng.
