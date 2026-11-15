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
- Producers keep `acks=all` + `idempotence=true`; consumers disable auto-commit and commit offsets only after durable persistence.

See [PROCESSING_ORDERING_HANDOFF.md](PROCESSING_ORDERING_HANDOFF.md) for keyed concurrency (`PROC-ORDER-01`), safe-prefix offset coordination, and SQL fencing semantics.
