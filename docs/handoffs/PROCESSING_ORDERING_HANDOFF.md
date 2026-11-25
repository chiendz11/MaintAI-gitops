# PROC-ORDER-01 — Processing Concurrency & Ordering Handoff

Application design `1.4.0` (`PROC-ORDER-01`), shared SDK `0.3.1`, bundle `2.0.0`.
Sources: [processing concurrency design](../../../MaintAI/docs/subsystems/PROCESSING_CONCURRENCY_AND_ORDERING.md)
and [implementation report](../../../MaintAI/docs/reports/PROCESSING_ORDERING_IMPLEMENTATION_REPORT.md).

## Execution Semantics

- **Processing Worker (`maintai_processing.worker`):** Strict Keyed FIFO per `machine_id` (`per_key = 1`, no Hybrid out-of-order/`AlertResequencer`), parallel across machines within memory/task budgets, **per-key micro-batching (`PROCESSING_MAX_BATCH_PER_KEY=16`)** calling `POST /api/v1/predict/batch` (with `404` fallback to `/api/v1/predict`), short SQL transaction checking durable assignment generation and `source_sequence` cursor, and safe-prefix offset coordinator (offset `501` completing before `500` must never commit `502`).
- **Processing Outbox Relay (`maintai_processing.outbox_relay`):** Claims per-`(topic, key)` head rows only and dispatches via `publish_batch()` (`KAFKA_LINGER_MS=2`, `lz4`); retry or unknown broker ACK blocks successors until acknowledged.
- **Business & Storage:** Keep serial runner defaults (`64/32` bounded prefetch, `business-consumer` `KAFKA_COMMIT_BATCH_SIZE=16` / `KAFKA_COMMIT_MAX_WAIT_MS=50`) with inbox deduplication, CAS guards, and immutable alert/prediction lifecycle (`INVALID` preserves last valid prediction; `NORMAL` never auto-resolves active alerts).

## Deployment & Rollout Gates

- Processing remains three Deployments sharing `maintai-processing` image and owner database `processing_db` (`worker`, `read-api`, `outbox-relay`).
- Runtime configuration for keyed mode, micro-batching, and budgets (`PROCESSING_EXECUTION_MODE`, `PROCESSING_MAX_BATCH_PER_KEY`, `MAX_ACTIVE_KEYS`, `MAX_PENDING_RECORDS`, `OUTBOX_EXECUTION_MODE`, etc.) is managed purely declaratively via Kustomize manifests in `environments/`.
- In production cutovers, drain legacy writers/relays and run explicit owner migrations (`operations/`) before activating keyed mode.
- Monitoring/alerts must use max aggregation across replicas for DB-wide outbox gauges and never treat missing Prometheus series as healthy/zero.
