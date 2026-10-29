# Kafka application handoff

Application target1.4, shared Python SDK `maintai-messaging==0.2.0`, canonical
contract bundle1.1.0. Platform resources still use the existing Strimzi0.47.0 /
Kafka4.0.0 pins; this change does not migrate every runtime config or application.

App owners read `MaintAI/docs/KAFKA_DEVELOPMENT_GUIDE.md`. Person1 integrates
Ingestion/Processing/Business callbacks; Person4 owns the cluster/ACLs, raw
Storage adapter and deployment wiring. ML/RAG do not require Kafka credentials.

| Topic | Writer | Reader groups |
| --- | --- | --- |
| sensor.readings1.3.0 | maintai-ingestion | processing-v1, raw-archive-v1, business-live-v1 |
| sensor.rejected1.4.0 | maintai-ingestion | raw-rejected-archive-v1 |
| inference.results1.4.0 | maintai-outbox | business-prediction-v1; optional outcome-archive-v1 |
| alert.signals1.0.0 | maintai-outbox | business-alert-v1 |

Result readers support native1.4.0 `kind` and legacy2.0.0 `result_kind`. Deploy
compatible readers before changing writers. No result1.1.0 writer, topic rename,
automatic topic creation or mandatory fifth DQ topic. Topic resources use12
partitions,3 replicas/minISR2,7-day retention, max message1MiB. App bound256KiB
is lower; changing these values requires a reviewed capacity/contract decision.

`config/kafka-contracts.json` carries the exact application manifest SHA-256,
per-file hashes and topology. `config/protocols.json` records the resolved wire
versions. Future `automation.policy` checks pins/topic resources together; no
sibling application checkout is needed. The source SHA is deliberately null
while app source is uncommitted. Before enabling a workload, set it to the real
reviewed app commit and build the image from that commit; a document hash is not
evidence the SDK exists at an earlier HEAD. Never put a fake SHA/digest here.

Changes to the application bundle require a new bundle version/hash and a reviewed
GitOps pin update. Existing `contracts/runtime-config/*-2.0.0.schema.json` and
their immutable hashes are preserved. Protocol wire metadata alone cannot bypass
DB migration/bootstrap and entrypoint gates; workloads remain disabled.

SDK defaults disable auto commit/store and require ACK all/idempotence. Use
existing TLS CA mount and SASL env secrets. `PRODUCER_GIT_SHA` comes from the
application image source annotation, not GitOps HEAD. Worker/read/relay share a
Processing image; Business API/Consumer share another image. Owner wrappers must
provide real module entrypoints/probes and install SDK resources in those images.

The SDK CLI uses fixed role groups from its topology. Legacy `KAFKA_GROUP_ID` /
`KAFKA_TOPIC` config keys describe the original main subscription only; they do
not remove the rejected group from the new Storage process. Business starts3
loops and Storage2 (optional3). Owner entrypoint review must account for this;
do not mutate published config2.0 schemas in place. Need new keys? Publish a
new config schema and PR rather than weakening the old schema.

`DATABASE_URL` remains the per-workload owner secret; the SDK relay/migration CLI
also accepts PROCESSING_DATABASE_URL/BUSINESS_DATABASE_URL. Storage uses IRSA,
versioned S3, exact-byte immutable object/manifest writes. Current raw microbatch
size1 yields2 PUTs/record and needs capacity/cost review at higher loads. Optional
wire outcome archive does not replace Processing-owned history export/cleanup.

No render/build/test/cluster operation was run in this code-first platform change.
The app has unit/contract checks and an opt-in Kafka/PostgreSQL integration suite;
that does not validate Strimzi, EKS, real S3 permissions or deployment readiness.

## PROC-ORDER-01 — SDK0.2.0/bundle1.1.0

The current Kafka pin includes additive Processing migration002 and the archived
bundle1.0 manifest. Wire versions/topics/partition counts and frozen001 remain
unchanged. Keyed mode is Processing-only, serial/legacy remain defaults; owner
DB schema and explicit activation precede ordered mode. Source SHA remains null
until a reviewed app commit is available; all workloads remain disabled.

Offset501 completed while500 is unfinished does not allow commit502. Completion
ledger and assignment generation guard offset progress; durable DB fencing also
rejects stale SQL. Head retry/unknown ACK blocks only that topic/key's successors.
Late duplicates/cross-topic ordering still need Business inbox/CAS/lifecycle.

New config3.0.0 contracts/profile are inactive, not silently inserted into active
config2.0.0. Existing release automation still targets2.0 and must be upgraded in
a reviewed cutover before config3 publication. See
[handoff and remaining gates](PROCESSING_ORDERING_HANDOFF.md).
