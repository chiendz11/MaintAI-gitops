# PROC-ORDER-01 — Processing Concurrency & Ordering Handoff

Application design `1.4.0` (`PROC-ORDER-01`), shared SDK `0.3.1`, bundle `2.0.0`.
Sources: [processing concurrency design](../../../MaintAI/docs/subsystems/PROCESSING_CONCURRENCY_AND_ORDERING.md)
and [implementation report](../../../MaintAI/docs/reports/PROCESSING_ORDERING_IMPLEMENTATION_REPORT.md).

## Execution Semantics

- **Processing Worker (`maintai_processing.worker`):** Keyed FIFO per `machine_id`, parallel across machines within memory/task budgets, short SQL transaction checking durable assignment generation and `source_sequence` cursor, and safe-prefix offset coordinator (offset `501` completing before `500` must never commit `502`).
- **Processing Outbox Relay (`maintai_processing.outbox_relay`):** Claims per-`(topic, key)` head rows only; retry or unknown broker ACK blocks successors until acknowledged.
- **Business & Storage:** Keep serial runner defaults with inbox deduplication, CAS guards, and immutable alert/prediction lifecycle (`INVALID` preserves last valid prediction; `NORMAL` never auto-resolves active alerts).

## Deployment & Rollout Gates

- Processing remains three Deployments sharing `maintai-processing` image and owner database `processing_db` (`worker`, `read-api`, `outbox-relay`).
- Runtime configuration for keyed mode and budgets (`PROCESSING_EXECUTION_MODE`, `MAX_ACTIVE_KEYS`, `MAX_PENDING_RECORDS`, `OUTBOX_EXECUTION_MODE`, etc.) is managed purely declaratively via Kustomize manifests in `environments/`.
- In production cutovers, drain legacy writers/relays and run explicit owner migrations (`operations/`) before activating keyed mode.
- Monitoring/alerts must use max aggregation across replicas for DB-wide outbox gauges and never treat missing Prometheus series as healthy/zero.
