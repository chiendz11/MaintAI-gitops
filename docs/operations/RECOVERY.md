# Recovery boundaries

The recovery workflow opens a PR from an operator-selected historical main commit.
It never force-pushes, patches the cluster or merges. One concurrency group and
an open managed-PR guard prevent simultaneous model/workload/platform/recovery
proposals. A changed main SHA aborts proposal publication rather than applying
against a stale base.

Scope model restores the atomic model/preprocessor/reference/metadata bundle,
checks that historical S3 versions still exist and updates inference/drift rollout
annotations. Scope workload restores a runtime's image/config state; it does not
restore Terraform state or overwrite the current platform secret ARN allow-list.
Validate current API/event/config compatibility before merging either recovery.

Kafka crash/rebalance: re-delivery is normal; application inbox/outbox and unique
IDs must make side effects idempotent. Inspect lag/oldest age before retention is
exceeded. Storage replay uses deterministic batch keys/manifests, not an exactly-
once claim. API/SSE restart needs reconnect+REST snapshot resync.

Training recovery: preserve immutable input version, inspect workflow/ledger,
retry failed execution or explicitly resubmit the approved S3 record. Use
--retry-release after RELEASE_DISPATCHED when receiver/PR creation failed.
Do not call the model deployed just because dispatch succeeded. Old active lease
must expire or be handled by an operator; never run a second controller blindly.

Database/schema rollback, dataset corrections, expired Kafka retention and cloud
resource recovery require separate procedures. Git rollback does not undo them.
Manual operations live under operations/ and are excluded from automatic roots.
No recovery/deployment command was run during initial delivery.
