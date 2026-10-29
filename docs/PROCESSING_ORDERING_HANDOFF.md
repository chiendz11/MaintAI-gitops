# PROC-ORDER-01 — Processing handoff, config và activation

**Amendment2026-10-23, decision1.0.0.** Current application design1.4.0;
SDK0.2.0/bundle1.1.0/Processing transport0.1.0. Platform baseline1.3.1 và active
runtime-config2.0.0 vẫn giữ version riêng. Đây không là bằng chứng rollout.

Nguồn chuẩn: [app decision](../../MaintAI/docs/PROCESSING_CONCURRENCY_AND_ORDERING.md),
[implementation report](../../MaintAI/docs/PROCESSING_ORDERING_IMPLEMENTATION_REPORT.md),
Contracts §42, Guide §53. Người1 làm app/SQL/callbacks; Người2 thống nhất ML budget;
Người4 làm Kafka/DB/platform/config/metrics. RAG ngoài critical alert path.

## 1. App đã cung cấp gì?

- Worker keyed FIFO: cùng máy tuần tự, khác máy song song trong budget.
- Completion coordinator chỉ commit safe completed prefix từng partition;
  offset501 xong khi500 chưa durable không cho commit502.
- Short SQL transaction kiểm durable assignment generation/source cursor;
  prepare DQ/ML ngoài SQL, callback persist ghi owner history/risk/outbox.
- Relay chỉ claim head topic/máy, retry/unknown ACK chặn successor; key cursor
  chỉ advance sau broker ACK + durable mark. Không hứa physical duplicates biến mất.
- Wrappers/factory thật ở maintai_processing.worker/outbox_relay/handlers.
  Real DQ/ML/risk/history callbacks, health server và buildable image còn pending.
- Local unit + Kafka4/PostgreSQL17 integration evidence ở app report. Không coi
  evidence đó là Strimzi/EKS/production permissions hoặc load1.000 readings/s.

Processing vẫn ba runtimes cùng image group/owner DB; queues/coordinator không
thêm Deployment. Read API vẫn read-only. Business/Storage giữ serial defaults,
Business inbox/CAS/projection guards và alert lifecycle vẫn bắt buộc.

## 2. Versioned config mới nằm ở đâu?

| Artifact | Vai trò |
| --- | --- |
| [Worker config3 schema](../contracts/runtime-config/processing-worker-3.0.0.schema.json) | Keyed mode, factory/callback identities, capacity/deadline budgets |
| [Relay config3 schema](../contracts/runtime-config/processing-outbox-relay-3.0.0.schema.json) | Ordered mode và batch size, kế thừa lease/poll/Kafka config |
| [Inactive profile](../config/processing-ordering.json) | Exact schema hashes, SDK/bundle pins, pending activation gates |
| [Kafka pin](../config/kafka-contracts.json) | Exact bundle1.1 manifest/hash, package0.2, source SHA chưa phát hành |
| versions/contracts.lock.json | Giữ mọi hash2.0 cũ, thêm immutable3.0 schema hashes |
| integrations/MaintAI/release/contracts/ | Byte-identical copies của hai schema3 cho bàn giao tương lai |

**Không thêm fields mới vào config2.0.0 đã freeze.** Active production state/
ConfigMaps/renderer/receiver/publisher hiện vẫn dùng2.0.0, profile3 là
NOT_ACTIVATED. Không sửa generated ConfigMap rồi bỏ qua hash/state/contract.
SDK CLI/env hỗ trợ mode mới không tự làm release receiver hiểu schema3.

Worker fields mới: PROCESSING_EXECUTION_MODE, PROCESSING_HANDLER_FACTORY,
PROCESSING_PREPARE_CALLBACK, PROCESSING_PERSIST_CALLBACK, MAX_ACTIVE_KEYS,
MAX_PENDING_RECORDS/BYTES/PER_KEY, MAX_UNCOMMITTED_PER_PARTITION,
RESUME_LOW_WATERMARK, HANDLER_TIMEOUT_SECONDS, DRAIN_TIMEOUT_SECONDS (các budget
có prefix PROCESSING_). Relay thêm OUTBOX_EXECUTION_MODE/OUTBOX_BATCH_SIZE.
Defaults/finite bounds trong app report; caller phải cung cấp real callbacks,
không đặt fixture hoặc tên module không tồn tại vào production.

## 3. Cutover cần làm trước khi phát hành config3

1. Review real app callbacks, SQL/history, health endpoint, Dockerfile/image,
   actual source SHA và signed digest; source wrappers chưa đủ entrypoint_reviewed.
2. Review config3 receiver/publisher version selection. Hiện hard-coded2.0 ở
   automation/release.py, policy.py và integration publish template; cần PR riêng
   để chấp nhận version/hash mới, không weaken old additionalProperties=false.
3. Processing shared image gồm Worker/Read API/Relay, trong khi release envelope
   hiện có một runtime_config_version cho cả group. Phải chốt per-runtime mapping
   hoặc compatibility schema3 cho Read API cùng contract review; hai draft schemas
   mới chưa tự hoàn tất bước này. Không phát processing group3 thiếu Read API pin.
4. Chốt budgets toàn replicas: keyed tasks/record+byte queues, fetch reserve,
   ML concurrency, DB pool/statement timeouts, poll/deadline/drain/grace và retention.
   Partition count giới hạn members, không bằng active machine tasks/member.
5. Dừng/drain legacy writers/relays, chạy Processing migrations001/002 bằng owner
   migration job đã review. Activation riêng, không migrate ở mỗi Pod startup.
   Legacy pending outbox/initial source inbox cần verified bootstrap riêng; app
   release hiện fail closed, không tự backfill hoặc xóa inbox.
6. Chỉ enable sau actual activation/config/health/image evidence; canary/rebalance/
   kill/rollback drill. Không set owner_migrations_reviewed từ source test result.

No resources/desired-state flags are activated by this handoff. Existing null
source SHA/image values are intentional blockers, not permission to fabricate pins.

## 4. Metrics và sự cố

Owner expose registry chứa ProcessingMetrics/OutboxOrderMetrics; management
scrape/probes9100 còn cần HTTP server trong app. Panels cần active keys/queue
wait/pending bytes, frontier stall + broker lag, blocked-head age và stale completion.
IDs không là labels; Outbox gauges DB-wide dùng max qua replicas, không sum.
Missing series/query failure không được hiển thị thành0/healthy.

Revoke/lost fence SQL lẫn offset, unfinished input replay. ACK loss có thể publish
lại cùng ID/bytes; late physical duplicates/cross-topic reordering vẫn cần inbox/
CAS và alert lifecycle. INVALID giữ valid prediction lịch sử; NORMAL mới không
tự resolve Alert. Metrics/tracking outage không làm rollback business success.

No new Kafka topics/partition counts, databases, Terraform resources, Grafana/MLflow
UIs or scheduler services are introduced. Old schema/state/provider locks stay
intact; contracts/metadata checks do not validate a deployed production platform.
