# Kafka application handoff

Application target `1.4`, shared Python SDK (`maintai-messaging`), canonical contract bundle (`2.0.0` cho local `k3d`, `1.1.0` trong snapshot `config/kafka-contracts.json`). Platform production sử dụng Strimzi `0.47.0` / Kafka `4.0.0` pins.

App owners đọc [`MaintAI/docs/subsystems/KAFKA_DEVELOPMENT_GUIDE.md`](../../../MaintAI/docs/subsystems/KAFKA_DEVELOPMENT_GUIDE.md). Ingestion/Processing/Business callbacks thuộc codebase app; cluster/ACLs, raw Storage adapter và deployment wiring thuộc platform. ML/RAG không dùng Kafka credentials.

| Topic | Writer | Reader groups |
| --- | --- | --- |
| `sensor.readings` `1.3.0` | `maintai-ingestion` | `processing-v1`, `raw-archive-v1`, `business-live-v1` |
| `sensor.rejected` `1.4.0` | `maintai-ingestion` | `raw-rejected-archive-v1` |
| `inference.results` `1.4.0` | `maintai-outbox` | `business-prediction-v1`; optional `outcome-archive-v1` |
| `alert.signals` `1.0.0` | `maintai-outbox` | `business-alert-v1` |

- Production topic resources: `12` partitions, `3` replicas / `minISR=2` (local k3d dùng `1` replica / `minISR=1` nhưng giữ nguyên `12` partitions), retention `7 ngày`, max message `1 MiB` (app bound `256 KiB`).
- Wire `OUTCOME-14-ONLY` trên local SDK `0.3.1` / bundle `2.0.0` chỉ đọc/ghi `kind` (`1.4.0`), không dùng adapter legacy `2.0`.
- `config/kafka-contracts.json` giữ manifest SHA-256 và file hashes. Không sửa in-place schema `config 2.0.0` đã freeze; mọi thay đổi bundle version phải qua PR cập nhật đồng bộ cả lock và runtime config schema.
- SDK mặc định tắt auto commit/store, yêu cầu `acks=all` + `idempotence=true`, dùng SCRAM + TLS CA (production) hoặc SASL/internal DNS (local). `PRODUCER_GIT_SHA` lấy từ image annotation của ứng dụng.
- Storage Consumer ghi raw + manifest immutable lên S3/MinIO (với microbatch và `VersionId` + SHA-256).

Về cơ chế xử lý song song theo máy (`PROC-ORDER-01`), safe-prefix offset coordinator, SQL generation fence và lộ trình cutover lên runtime config `3.0.0` ở production, xem chi tiết tại [PROCESSING_ORDERING_HANDOFF.md](PROCESSING_ORDERING_HANDOFF.md).
