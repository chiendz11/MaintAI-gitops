# Local Desired State (`k3d`)

`platform/`, `observability/`, and `apps/` are three separate Argo CD Applications managed declaratively via Kustomize.
Read [LOCAL_DEVELOPMENT.md](../../docs/operations/LOCAL_DEVELOPMENT.md). No production root imports these paths.

## Baseline 50 máy cho môi trường local (`15–16 GiB RAM`)

Overlay `environments/local/` được chuẩn hóa cho baseline vận hành local **50 máy (`M-001`..`M-050`, `SIM_MACHINE_COUNT=50`, `SIM_INTERVAL_MS=1000` -> `50 readings/s`)** trên laptop đơn nút:

- `processing-worker`: `6` replicas (KEDA `min/max=6`, `PROCESSING_MAX_ACTIVE_KEYS=8`, `PROCESSING_REGISTRY_CACHE_SECONDS=30`, `KAFKA_POLL_INTERVAL_SECONDS=0.01`).
- `business-consumer`: `4` replicas (KEDA `min/max=4`, `KAFKA_POLL_INTERVAL_SECONDS=0.01` cho `50` live + `50` prediction = `100 msg/s`).
- `emqx`: `1` replica (`8883` MQTTS / `1883` MQTT), `redpanda-connect`: `1` replica (`$share/maintai-ingest`), `ml-service-champion`: KServe KPA `min=2/max=6`, `ml-service-shadow`: `1` replica qua `ml-service-mirror` (`5%` shadow sample), `processing-outbox-relay`: `2` replicas (`OUTBOX_BATCH_SIZE=64`, `OUTBOX_POLL_INTERVAL_MS=10`), `sensor`: `1` replica (`SIM_SEND_WORKERS=32`).
- **Lưu ý chuyển đổi `100 -> 50` trên PVC `local-sensor-state` đang có:** `sensor` kiểm `source_identity` khi khởi động; đổi `SIM_MACHINE_COUNT` trên `/state/state.sqlite3` cũ sẽ bị từ chối cho tới khi dùng state volume mới hoặc migration riêng.
- **Lưu ý `/data` `DiskPressure`:** k3s bật `DiskPressure=True` khi phân vùng `/data` còn `<15%` trống (`>=85%` used) và ngăn schedule pod; cần giữ `>=15–20%` trống và tạm pause `sensor` khi không đo đạc.
