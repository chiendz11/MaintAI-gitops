# Desired state của demo MaintAI — 30/10/2026

Đã triển khai thật lên cluster `maintai-local` từ nhánh `demo/local-k3d`.
Ba Argo Application quản lý riêng platform, observability và app. Đây là local
demo 5 máy, mỗi máy 1 reading/giây; không phải benchmark 100 máy hoặc production rollout.

## Source và image

- App nền ở commit `5b4664bb24e9f107c00a83e1faffb72fc5c1f4e3`.
- Business API/Consumer và Storage dùng image từ bản sửa SDK 0.3.1 tại commit
  `2df0a914287a86f3500731ba05a2ba866bbee160`, [PR22](https://github.com/chiendz11/MaintAI/pull/22).
- Các component còn lại giữ image receipt/source của bản nền. Không khai một
  source SHA giả chung cho những image được build từ các commit khác nhau.
- `config/local/app-source.lock.json` và risk-policy selector đã cập nhật theo
  source review. `environments/local/apps/release.json` giữ profile và từng receipt.
- Local dùng image đã import vào k3d và imagePullPolicy Never; không tuyên bố
  đã publish ECR/registry. AWS/production desired state không được activate.

## Desired state đã thay đổi để chạy được demo

1. Platform/App roots chọn helper/app image đã build và import thật.
2. Bật12 app runtimes sau migration/grants/provision/ordering/knowledge evidence.
3. RAG cache PVC ở wave0, tránh deadlock với WaitForFirstConsumer.
4. Keycloak có heap/memory phù hợp và native basic scope để JWT chứa subject.
   Pod annotation realm hash làm mới service clients sau khi cập nhật cấu hình.
5. RAG dùng Groq model openai/gpt-oss-20b, key lấy từ Kubernetes Secret;
   MiniLM embedding và PVC vẫn là dependency riêng của retrieval.
6. Business/Storage chọn KAFKA_POLL_INTERVAL_SECONDS 0.01; SDK 0.3.1 sửa cơ chế
   prefetch, giữ một handler và durable offset semantics.
7. Relay local chọn OUTBOX_POLL_INTERVAL_MS 10 để tránh hàng đợi DB tăng ở tải
   demo 5 readings/s. Giá trị 250ms trước đó không đủ cho đường relay một message/lượt.

Các ConfigMap hash cũ không còn được active Pod/Deployment/StatefulSet tham chiếu
đã được dọn riêng. Không bật global pruning, xóa PVC/DB/Secret hoặc reset offsets.

## Kết quả quan sát

- Normal: telemetry và prediction thật trên UI, có source event/model/policy.
- Pause/Resume: một máy dừng, máy khác vẫn chạy, sequence tiếp tục sau Resume.
- Critical: có alert mới từ ML/risk thật, không ép state từ tên scenario.
- Recovery: không tự đóng alert; UI thực hiện ACK/START/RESOLVE và feedback với audit.
- Degradation: control và readings/inference mới đã được kiểm; chưa đo toàn ramp 300 mẫu.
- Raw archive: object/manifest vào MinIO versioned; kiểm exact VersionId và SHA-256.
- RAG trực tiếp: HTTP 200, dịch vụ trả GROUNDED, 10 checklist steps, 3 citations.

Business Copilot M7 vẫn chưa tích hợp; không coi lời gọi RAG trực tiếp là kết quả
hiển thị brief trên Business UI. MLflow/Drift/training không bật trong profile này.

Sau tuning, kiểm tra 120 snapshot trong 120 giây của 5 máy cho thấy telemetry và
prediction age đều dưới 5 giây; lớn nhất quan sát được lần lượt1.03 và1.08 giây.
Đây là age snapshot API, không phải p95 event-to-browser hoặc benchmark 100 máy.
DB outbox đã về 0 trong lúc các máy tiếp tục chạy.

GitOps 32 tests và source/contract policies passed. CI, Argo convergence, provider
response và browser E2E được ghi thành các mức bằng chứng riêng.

Hướng dẫn đầy đủ về chuẩn bị, owner Jobs, credential locations, URL, lỗi đã sửa,
tests và giới hạn nằm tại
[báo cáo trong infrastructure](../../Maint-infrastructure/docs/LOCAL_DEMO_RUN_2026-10-30.md).
Private JSON receipts/screenshots/logs nằm tại infrastructure `local/.local/`.
