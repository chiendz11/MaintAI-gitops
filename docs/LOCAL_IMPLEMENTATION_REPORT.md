# Bàn giao local k3d + Argo CD + GitOps

> Báo cáo dưới đây ghi nhận đợt authoring ban đầu, khi chưa chạy CI. Trạng thái
> sau publication29/10: source đã public và CI source/unit/Kustomize render đã
> thành công; xem [source sync](LOCAL_SOURCE_SYNC.md) và GitHub Actions. Cluster,
> image receipts và E2E vẫn cần operator thực hiện, không suy ra từ CI.

## 1. Kết quả và phạm vi

Đã bổ sung local development trực tiếp vào hai repo, dùng ZIP làm tham khảo và
đối chiếu app M5 ở commit45f46ef. Infrastructure bootstrap cluster/private
kubeconfig/secrets/Argo; GitOps quản lý desired state platform/monitoring/apps.
AWS/production resources/config/contracts cũ giữ nguyên bytes trong lượt này.
Không sửa app checkout/PDF và không xóa/chạy folder MaintAI-k3d.

Source/config/CI/tests đã được viết. Chỉ đọc/so sánh source, parse cú pháp
Python/JSON/YAML và ghi nhận upstream pin metadata qua HTTP read-only. Chưa chạy
unit tests, project validators, Kustomize/Helm render, builds, Docker, k3d,
Argo sync, Terraform, GitHub Actions hoặc E2E. Các repo vẫn chưa commit/push.

## 2. Các quyết định và lý do

- Private kubeconfig và ownership marker giúp tooling local không thay current
  context hoặc vô tình nhận quyền quản lý cluster cũ cùng tên.
- Three Argo Applications tách platform/observability/apps để nhìn rõ readiness;
  app defaults disabled, không tạo ACK/inference/model/Alert giả.
- Sync waves tạo Namespace/ConfigMaps trước Services và Pods, rồi mới chạy
  bootstrap Jobs; tránh vòng chờ readiness khi realm config chưa được tạo.
- Native Keycloak dev + local TLS/PKCE và client credentials giải quyết auth;
  adapters chỉ nối loopback profiles, không sửa app/shared security guards.
- M5 API/Consumer nhận scoped Processing token qua file refresh trước expiry;
  Worker registry token chỉ có read role/machine scope, không có mutation quyền.
- Actual image-ID aliases + Git/dirty/snapshot/Dockerfile receipts thay :dev;
  Kustomize config hashes thay đổi cùng config để rollout có căn cứ.
- Correct owner CLI migrations/grants/provision/activation là explicit Jobs, không
  SQL startup hoặc Terraform. Evidence/offset/source ordering không bị reset.
- Kafka12 partitions/four topics, PostgreSQL17/five DB owners, seven versioned
  buckets/scoped credentials giữ các boundary đã chốt. Smoke dùng topic riêng.
- Business/Simulator UI là hai images/Deployments và hai edge routes; Grafana và
  MLflow dùng native UI. MLflow chỉ bật sau app image/base compatibility review.
- Local training là approved manual Job, ghi immutable dataset manifest locator;
  không tự retrain/promote theo sensor/drift. Runtime/quality gates thuộc ML owner.
- Production/file/schema fingerprints và CI roots tách local/production để không
  dùng local setup làm evidence production hoặc âm thầm đổi frozen contracts.

## 3. Giới hạn và công việc khi chạy thật

Cần commit source, build/import actual images, push GitOps remote thật, trust CA
trong browser, sync platform, owner migrations/grants/registry/ordering rồi mới
prepare app release. ML/RAG/training Dockerfiles hoặc model chưa sẵn sàng phải do
owner hoàn thiện; Drift provider/base pins và MLflow base/server/SDK review cũng
chưa được giả thành xong. Kafka exporter chưa có; Grafana lag panel có thể No data.

Single-node local/PVC/Argo health không chứng minh AWS HA, model quality, complete
pipeline hoặc latency100 máy. Cần chạy các tầng verification riêng khi được yêu
cầu; recorded operator attestations không phải kết quả test/benchmark.

## 4. Danh sách file trong MaintAI-gitops

So với source snapshot trước lượt này: **60 file mới, 5 file sửa**, không xóa file hiện hữu. Repo chưa có commit nên đây là so sánh filesystem hash, không giả định có Git diff từ một release.

| File | Thay đổi | Mục đích |
| --- | --- | --- |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Sửa | Bổ sung locked local dependencies, source/contract/gate tests; GitOps render local và production bằng checksum-pinned kubectl. CI required giữ nguyên tên. |
| [AGENTS.md](../AGENTS.md) | Sửa | Cập nhật phạm vi hai repo, ownership local mới, M5/token invariants và giới hạn code-first. |
| [Makefile](../Makefile) | Mới | Shortcuts explicit local commands; không tự chạy khi mở repo. |
| [README.md](../README.md) | Sửa | Thêm điểm bắt đầu local dev; giữ rõ AWS/production baseline độc lập. |
| [config/local/app-source.lock.json](../config/local/app-source.lock.json) | Mới | Snapshot SHA/Git revision của current app interfaces/Dockerfiles; không là build/deploy evidence. |
| [config/local/buckets.json](../config/local/buckets.json) | Mới | Bảy versioned buckets và read/write scope cho từng bên sử dụng. |
| [config/local/contract.json](../config/local/contract.json) | Mới | Handoff namespace/context/issuer/ports/Argo paths/Kafka baseline giữa hai repo. |
| [config/local/kafka-topology.json](../config/local/kafka-topology.json) | Mới | Canonical app Kafka topology, SDK0.3/bundle2/native outcome1.4; không reader legacy. |
| [config/local/platform.lock.json](../config/local/platform.lock.json) | Mới | OCI/tool/source pins; Keycloak/Argo/kubectl metadata ghi nhận read-only, chưa runtime validation. |
| [config/local/runtime-catalog.json](../config/local/runtime-catalog.json) | Mới | Actual Dockerfile/context/entrypoint/ports/migration catalog, không suy từ placeholder metadata cũ. |
| [contracts/local/image-receipt-v1.schema.json](../contracts/local/image-receipt-v1.schema.json) | Mới | Schema local1.0.0 cho reviewed profiles hoặc actual image receipts; không sửa published production schemas. |
| [contracts/local/local-profile-v1.schema.json](../contracts/local/local-profile-v1.schema.json) | Mới | Schema local1.0.0 cho reviewed profiles hoặc actual image receipts; không sửa published production schemas. |
| [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) | Sửa | Ghi amendment local: cluster/bootstrap ở infrastructure, in-cluster desired state ở GitOps; dated production baseline không tự thành runtime evidence. |
| [docs/LOCAL_DEVELOPMENT.md](../docs/LOCAL_DEVELOPMENT.md) | Mới | Hướng dẫn ownership, release, auth M5, schema/profile, dữ liệu, UI và nghiệm thu local; hoặc entrypoint tới runbook infrastructure. |
| [docs/LOCAL_IMPLEMENTATION_REPORT.md](../docs/LOCAL_IMPLEMENTATION_REPORT.md) | Mới | Báo cáo bàn giao này: chức năng, lý do, danh sách đủ file và giới hạn verification. |
| [docs/LOCAL_MIGRATION.md](../docs/LOCAL_MIGRATION.md) | Mới | Capability map từ MaintAI-k3d, cutover/backup constraints và các bước chỉ xóa folder cũ sau acceptance. |
| [docs/LOCAL_VERSIONING.md](../docs/LOCAL_VERSIONING.md) | Mới | Giải thích immutable image ID/source receipts, config hashes, artifact versions và giới hạn local vs production provenance. |
| [docs/VERSIONING.md](../docs/VERSIONING.md) | Sửa | Ghi independent local handoff/versioning và bảo toàn frozen production state. |
| [environments/local/README.md](../environments/local/README.md) | Mới | Argo source root local tách platform/observability/apps; apps mặc định disabled và chỉ prepare bằng receipts thật. |
| [environments/local/apps/kustomization.yaml](../environments/local/apps/kustomization.yaml) | Mới | Argo source root local tách platform/observability/apps; apps mặc định disabled và chỉ prepare bằng receipts thật. |
| [environments/local/observability/kustomization.yaml](../environments/local/observability/kustomization.yaml) | Mới | Argo source root local tách platform/observability/apps; apps mặc định disabled và chỉ prepare bằng receipts thật. |
| [environments/local/platform/kustomization.yaml](../environments/local/platform/kustomization.yaml) | Mới | Argo source root local tách platform/observability/apps; apps mặc định disabled và chỉ prepare bằng receipts thật. |
| [integrations/MaintAI/LOCAL_DEVELOPMENT.md](../integrations/MaintAI/LOCAL_DEVELOPMENT.md) | Mới | Tài liệu bàn giao cho app owner để cập nhật links/runbooks và interfaces khi chuyển tooling; không sửa app checkout. |
| [local/VERSION](../local/VERSION) | Mới | Phiên bản phần local1.0.0, độc lập app/Kafka/production contract versions. |
| [local/observability/dashboards.yaml](../local/observability/dashboards.yaml) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/observability/datasources.yaml](../local/observability/datasources.yaml) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/observability/kustomization.yaml](../local/observability/kustomization.yaml) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/observability/maintai-local.json](../local/observability/maintai-local.json) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/observability/prometheus.yaml](../local/observability/prometheus.yaml) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/observability/resources.yaml](../local/observability/resources.yaml) | Mới | Prometheus/Grafana/Pushgateway config, native dashboards/real metrics và namespace-scoped discovery; thiếu series không là success. |
| [local/platform/bootstrap.yaml](../local/platform/bootstrap.yaml) | Mới | Argo Sync Jobs có waves/deadlines, chỉ khởi tạo platform sau datastore readiness. |
| [local/platform/idp-bridge.json](../local/platform/idp-bridge.json) | Mới | Route cố định tới Keycloak local, không chấp nhận arbitrary credential sink. |
| [local/platform/idp-gateway.yaml](../local/platform/idp-gateway.yaml) | Mới | TLS identity gateway với local certificate Secret; chỉ bind host loopback qua NodePort. |
| [local/platform/kafka.yaml](../local/platform/kafka.yaml) | Mới | Kafka4 KRaft single-node, internal/external listeners, persistent data và local secret cluster ID. |
| [local/platform/keycloak.yaml](../local/platform/keycloak.yaml) | Mới | Keycloak dev server native, persistent H2, realm import và secret placeholders; không là app auth server mới. |
| [local/platform/kustomization.yaml](../local/platform/kustomization.yaml) | Mới | Base local platform có configMapGenerator; không import production roots. |
| [local/platform/maintai-realm.json](../local/platform/maintai-realm.json) | Mới | OIDC realm, PKCE public clients, machine scope, dev users, service audiences/roles; không có secret values. |
| [local/platform/minio.sh](../local/platform/minio.sh) | Mới | Tạo bảy versioned buckets và scoped users/policies; không cấu hình lifecycle xóa dữ liệu. |
| [local/platform/minio.yaml](../local/platform/minio.yaml) | Mới | MinIO source-built image gate, persistent data, S3/console NodePorts và root secret riêng. |
| [local/platform/policies/drift.json](../local/platform/policies/drift.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/inference.json](../local/platform/policies/inference.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/mlflow.json](../local/platform/policies/mlflow.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/processing-reader.json](../local/platform/policies/processing-reader.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/processing.json](../local/platform/policies/processing.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/rag.json](../local/platform/policies/rag.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/storage.json](../local/platform/policies/storage.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/policies/training.json](../local/platform/policies/training.json) | Mới | MinIO least-privilege bucket/object policy theo owner; không cấp DeleteObject hoặc root vào app. |
| [local/platform/postgres.sh](../local/platform/postgres.sh) | Mới | Idempotent role/DB initialization, CONNECT scoping và pgvector; owner schema migrations/grants tách riêng. |
| [local/platform/postgres.yaml](../local/platform/postgres.yaml) | Mới | Stateful PostgreSQL17/pgvector, persistent storage và secret refs. |
| [local/platform/roles.tsv](../local/platform/roles.tsv) | Mới | Danh sách five DB owners và runtime worker/relay/reader/API/Consumer logins. |
| [local/platform/topics.sh](../local/platform/topics.sh) | Mới | Tạo bốn canonical topics12 partitions, RF/minISR1 local và từ chối partition mismatch. |
| [localdev/__init__.py](../localdev/__init__.py) | Mới | Package local tooling, không có import-time cluster action. |
| [localdev/checks.py](../localdev/checks.py) | Mới | CI offline source policy, app interface/source pins, local contracts và protected-production fingerprints. |
| [localdev/common.py](../localdev/common.py) | Mới | Private-state/context guard, argument-array subprocess, source snapshot identity và kiểm base images bằng digest. |
| [localdev/release.py](../localdev/release.py) | Mới | Tạo diff desired state chỉ dưới environments/local từ reviewed profile và actual image receipts; kiểm dependencies/artifacts/auth invariants. |
| [localdev/workloads.py](../localdev/workloads.py) | Mới | Tạo runtime manifests, M5 token wiring, adapters, đúng DTO hai UI và content-hashed ConfigMaps theo catalog M5. |
| [platform/namespaces/local/kustomization.yaml](../platform/namespaces/local/kustomization.yaml) | Mới | Namespace base dành riêng local, production namespace kustomization không tham chiếu. |
| [platform/namespaces/local/namespace.yaml](../platform/namespaces/local/namespace.yaml) | Mới | Namespace base dành riêng local, production namespace kustomization không tham chiếu. |
| [profiles/local-training.example.json](../profiles/local-training.example.json) | Mới | Mẫu manual approved training có bucket/key/VersionId/SHA256; không có trainer/model giả. |
| [profiles/local.example.json](../profiles/local.example.json) | Mới | Inventory đầy đủ với mọi component disabled, images null, checksums và owner attestations chưa xác nhận. |
| [requirements-local.lock](../requirements-local.lock) | Mới | Dependency lock cho local GitOps release/checks và CI. |
| [scripts/install_local_ci_kubectl.py](../scripts/install_local_ci_kubectl.py) | Mới | Kubectl checksum installer chỉ dành Kustomize rendering CI; không deploy. |
| [tests/test_local_release.py](../tests/test_local_release.py) | Mới | Tests authored cho image spoofing, local path boundary, disabled defaults, M5 dependencies, secrets/namespace và missing ML; chưa chạy. |
| [versions/local-contracts.lock.json](../versions/local-contracts.lock.json) | Mới | SHA lock các schema local mới; bản sao giữa hai repo phải byte-identical. |
| [versions/local-production-baseline.lock.json](../versions/local-production-baseline.lock.json) | Mới | Fingerprints các file AWS/production hiện hữu để CI phát hiện local work sửa nhầm phạm vi. |
