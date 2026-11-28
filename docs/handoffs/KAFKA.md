# Kafka Application Handoff

Application target `1.4`, shared Python SDK (`maintai-messaging` `0.3.1`), canonical contract bundle (`2.0.0`). Production plans Strimzi `0.47.0` / Kafka `4.0.0`.

App owners follow [`MaintAI/docs/subsystems/KAFKA_DEVELOPMENT_GUIDE.md`](../../../MaintAI/docs/subsystems/KAFKA_DEVELOPMENT_GUIDE.md). Ingestion/Processing/Business callbacks belong to `MaintAI`; cluster/ACLs and Kubernetes deployment wiring belong to `MaintAI-gitops`. ML/RAG do not hold Kafka credentials.

| Topic | Writer | Reader groups |
| --- | --- | --- |
| `sensor.readings` `1.3.0` | `maintai-ingestion` | `processing-v1`, `raw-archive-v1`, `business-live-v1` |
| `sensor.rejected` `1.4.0` | `maintai-ingestion` | `raw-rejected-archive-v1` |
| `inference.results` `1.4.0` | `maintai-outbox` | `business-prediction-v1`; optional `outcome-archive-v1` |
| `alert.signals` `1.0.0` | `maintai-outbox` | `business-alert-v1` |

- Topic configuration: `12` partitions across both environments (`3` replicas / `minISR=2` production; `1` replica / `minISR=1` local `k3d`), `7 days` retention, `1 MiB` broker max message size.
- Wire `OUTCOME-14-ONLY` reads/writes canonical `kind` (`1.4.0`) only — no legacy reader adapter or probability-to-risk fallback.
- Producers use `KafkaPublisher.publish_batch()` pipelining (`acks=all` + `idempotence=true`, `poll(0.005)` jitter fix, `KAFKA_LINGER_MS=2` local, `KAFKA_COMPRESSION_TYPE=lz4`) without holding the publisher lock across broker RTT.
- **Stateless MQTT→Kafka Ingestion (`EMQX` -> `Redpanda Connect`):** `EMQX 5.8.6` nhận MQTT QoS 1 từ `sensor` (MQTTS `:8883` hoặc `:1883`, `hash_topic`); `Deployment/redpanda-connect` (`connect:4.50.0`) subscribe `$share/maintai-ingest/maintai/v1/site/+/machines/+/telemetry` QoS 1, kiểm tra allowlist 6 trường AI4I, gán 4 Kafka headers (`schema_version`, `message_id`, `correlation_id`, `producer_git_sha`) và ghi `sensor.readings` / `sensor.rejected` (`lz4`, idempotent). Secret `KafkaUser/maintai-ingestion` / `msk-scram-ingestion` được giữ lại cho `redpanda-connect`.
- Consumers disable auto-commit and commit offsets only after durable persistence; `business-consumer` keeps bounded prefetch (`64/32`) with synchronous commit batching (`KAFKA_COMMIT_BATCH_SIZE=16`, `KAFKA_COMMIT_MAX_WAIT_MS=50` local).

See [PROCESSING_ORDERING_HANDOFF.md](PROCESSING_ORDERING_HANDOFF.md) for keyed concurrency (`PROC-ORDER-01`), per-key micro-batching, safe-prefix offset coordination, and SQL fencing semantics.
