# Approved-Dataset Batch Training

Event-triggered batch retraining via Argo Events and Argo Workflows (never `partial_fit` per sensor reading):

```text
curate raw data -> approve versioned dataset manifest -> S3 ObjectCreated
-> SQS -> Argo EventSource/Sensor -> Argo Workflow
-> verify exact manifest/data/protocol S3 VersionIds & SHA-256
-> app training image (MaintAI) -> offline quality gate -> MLflow candidate
-> candidate bundle PR in MaintAI-gitops -> operator review & merge
-> Argo CD reconciles updated model bundle
```

## Guardrails

- Only `datasets/approved/*.manifest.json` triggers training (raw sensor objects and drift reports do not trigger retraining).
- Six allowlisted features only (`air_temperature_k`, `process_temperature_k`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`, plus `type` encoding); never feed IDs, timestamps, or fault labels as features.
- Training writes an immutable candidate to versioned S3 and registers it in MLflow using `training_id` idempotency; it never patches serving Deployments directly or auto-promotes the MLflow champion alias.
- Production promotion requires offline quality gates (`Recall_failure >= 0.85`, `Precision_failure >= 0.50`) and human review of the resulting GitOps Pull Request.
