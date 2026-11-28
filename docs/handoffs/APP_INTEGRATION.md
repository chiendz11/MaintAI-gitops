# Application Integration Contract

## Images, Entrypoints & Health Probes

Container images are built and pushed by `MaintAI` (`.github/workflows/publish-and-deploy.yml`) and rolled out through `MaintAI-gitops` Kustomize `images` overrides (via reviewed PRs opened by Argo CD Image Updater).

| Owner | Build source (`MaintAI` / upstream) | Target service / port |
|---|---|---|
| Ingestion | Upstream `emqx:5.8.6` & `redpandadata/connect:4.50.0` | `emqx` (`:8883` MQTTS / `:1883`) -> `redpanda-connect` (`:4195`, `$share/maintai-ingest` QoS 1 -> Kafka) |
| Processing | `processing/Dockerfile` | `worker`, `read-api`, `outbox-relay` (`maintai-processing`) |
| Business | `backend/Dockerfile` | `business-api` (`:8003`), `business-consumer` (`maintai-business-backend`) |
| Storage | `storage-consumer/Dockerfile` | `maintai-storage-consumer` |
| ML inference | `ml-service/inference/Dockerfile` | `maintai-ml-service` (`/api/v1/predict/batch` & `/api/v1/predict`, `:8001`, `UVICORN_WORKERS=1`) |
| RAG | `rag-service/Dockerfile` | `maintai-rag-service` (`:8002`) |
| Sensor | `sensor/Dockerfile` | `maintai-sensor` (control API `:8005` + SQLite Spool v2 + `SIM_TRANSPORT_MODE=mqtt\|http`) |
| Main UI | `frontend/Dockerfile` | non-root HTTP `:8080`, `/runtime-config.json` |
| Simulator UI | `sensor-simulator-UI/Dockerfile` | independent HTTP `:8080`, same-origin Sensor control |

- HTTP APIs expose readiness/liveness probes (`/health/live`, `/health/ready`) and drain gracefully; `redpanda-connect` exposes `/ready` and `/ping` (`:4195`) while bridging `$share/maintai-ingest` MQTT QoS 1 to Kafka (`sensor.readings` / `sensor.rejected`); Kafka consumers handle rebalance fences and commit offsets only after durable DB/object persistence.
- `ml-service` Champion runs in local as a KServe `InferenceService` (Knative Serving + Kourier + KPA `minReplicas=2`, `maxReplicas=6`, `UVICORN_WORKERS=1`, zero-pandas vectorized fast path) behind `ml-service-mirror` (Nginx 5% async mirror to `ml-service-shadow`). Both `POST /api/v1/predict/batch` (max 64 items) and `POST /api/v1/predict` remain active.
- Main Frontend calls Business REST/SSE; Simulator UI calls Sensor control API (`UI-01`). Browser bundles receive zero internal service keys or LLM keys.
- **MLflow Exception:** MLflow upstream server/Dockerfile lives in `MaintAI/ml-service/mlflow/` while GitOps manages its Kubernetes manifests (`platform/mlops/`, `environments/local/apps/mlflow.yaml`). See [MLFLOW_IMAGE_MIGRATION.md](MLFLOW_IMAGE_MIGRATION.md).
