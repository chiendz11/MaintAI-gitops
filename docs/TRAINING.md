# Approved-dataset batch training

This is event-triggered batch retraining, not partial_fit for every sensor reading.

```text
curate raw data -> review/approve versioned manifest -> S3 ObjectCreated
-> SQS -> Argo EventSource/Sensor -> Workflow
-> normalize every S3 Records entry (not just Records[0])
-> verify exact manifest/data/protocol S3 versions and SHA-256
-> claim durable DynamoDB training identity/lease
-> app training image -> offline quality gate -> immutable result checkpoint
-> release publisher dispatch -> GitOps receiver -> protected model PR
-> operator merge -> Argo reconcile model bundle
```

Only `datasets/approved/*.manifest.json` triggers the S3 notification. Sensor raw
objects, every new CSV and drift reports do not trigger training. Operators must
actually review before publishing `approved=true`; a boolean alone is not proof
of human approval. `scripts/publish_approved_dataset.py` is an explicit tool,
not a background auto-approver. Dataset publisher IAM is separate from training;
training cannot write into the approved input prefix.

`contracts/dataset-manifest-v1.schema.json` requires approver/time, six feature
columns, target, data/protocol immutable refs, training image/code SHA and frozen
training-context hash. Export the neutral context from state/production to the
producer before approval; a changed training image/context requires fresh approval.
Never use IDs/timestamps/target/failure-type labels as model input.

## App training image contract

`python -m maintai_training --context <context.json> --output <model-result.json>`

Input directory contains data.csv and evaluation-protocol.json. The app must train
its baseline and candidate, compare rule-based baseline, handle class imbalance,
select thresholds on validation and report on the same frozen test split.
It uploads model, preprocessor, drift reference, metadata and evaluation report to
versioned S3, registers an immutable MLflow candidate using HTTP, and outputs
`model-result-v1`. App training is not reimplemented in the GitOps helper image.
It must use training_id to avoid duplicate registration/artifact side effects on retry.

Offline gate requires Recall_failure >= 0.85, Precision_failure >= 0.50, all required
metrics, common evaluation protocol/test hashes and baseline/rule evidence. These
are target gates, not measured results. The helper verifies output provenance and
checksum before dispatch; GitOps verifies again from the immutable result object.

## Retry, acknowledgement and recovery

Training identity binds manifest bucket/key/VersionId/hash and training context.
A conditional owner/lease prevents concurrent processing. Per-record workspace
slots avoid overwriting inputs when an S3 envelope contains multiple records.
Results are checkpointed in S3 + DynamoDB; publish failure can reuse a trained
result. A crashed workflow can be retried after failure/lease expiry.

Ledger RELEASE_DISPATCHED means GitHub accepted workflow_dispatch. It does NOT
mean the receiver passed, a PR exists, the PR merged, or a model is serving.
Monitor Argo workflow failures, receiver runs, PR state and serving separately.
Argo/SQS acknowledgement is not an end-to-end retry guarantee. For a downstream
failure, use `python -m scripts.resubmit_dataset ... --retry-release --execute`
with the SAME approved manifest VersionId, or explicitly retry the failed workflow.
An unacknowledged or quarantined event still needs operator triage/DLQ handling.

No task patches a serving Deployment or auto-merges a PR. No task automatically
moves MLflow champion. Set an alias only after separately confirmed GitOps rollout
and validation; that observation/promoter is outside this initial app contract.
