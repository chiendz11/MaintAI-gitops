# Explicit Database Operations

These manifests are outside every active Argo Application root (`environments/`, `applications/`) and are not automatic deployment hooks.

- `database-bootstrap/` initializes the five isolated owner databases/roles (`processing_db`, `business_db`, `drift_db`, `knowledge_db`, `mlflow_db`) and `vector` extension in production RDS.
- Per-owner migration manifests run separately using only that owner's credential and reviewed image digest. Never run all owner migrations automatically inside every application Pod startup.
- Rolling back an application image PR does not revert SQL schema changes. Sensor PVC keeps `Prune=false` so durable SQLite/Kafka state is not dropped during sync cleanup.
