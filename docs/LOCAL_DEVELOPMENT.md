# Local development — desired state được Argo CD quản lý

Phần local phiên bản1.0.0 bổ sung vào repo GitOps. AWS/production roots, published
runtime config2.0.0, SQL và release envelopes giữ nguyên bytes trong lượt này.
Local có contract/schema/catalog riêng, tham chiếu app SDK0.3.0, Kafka bundle2.0.0
và native outcome1.4.0. Không phục hồi reader legacy2.0.

**Trạng thái: source/config/CI đã viết; chưa chạy unit tests, Kustomize render,
image build, Argo sync hoặc E2E.** Không có deployment/image receipt thật được
ship trong repo. Hai ZIP chỉ là tài liệu tham khảo, không là source runtime.

## 1. Ownership và cấu trúc

| Vị trí | Ý nghĩa |
| --- | --- |
| `config/local/` | Namespace/ports/issuer, runtime catalog, Kafka topology, bảy bucket và pins |
| `contracts/local/` | Profile/receipt1.0.0 tách khỏi các published contracts production |
| `profiles/local.example.json` | Tất cả app mặc định disabled, không có image/model giả |
| `local/platform/` | PostgreSQL/Kafka/MinIO/Keycloak và initialization Jobs |
| `local/observability/` | Prometheus, Grafana native UI/provisioning và Pushgateway |
| `platform/namespaces/local/` | Owner duy nhất của namespace manifest local |
| `environments/local/platform/` | Argo source path1; image overrides + platform release receipt |
| `environments/local/observability/` | Argo source path2; monitoring |
| `environments/local/apps/` | Argo source path3; mặc định chỉ có status DISABLED |
| `localdev/workloads.py` | Một generator cho runtime manifests/config/adapters theo catalog hiện hành |
| `localdev/release.py` | Chuẩn bị diff local từ profile và actual image receipts; không commit/push/apply |
| `versions/local-*.lock.json` | Bảo vệ schema local và fingerprint các file production hiện hữu |

Hạ tầng tạo cluster/private kubeconfig/secrets và bootstrap Argo. Sau đó GitOps
sở hữu manifests trong cluster; infrastructure không apply cạnh tranh cùng
Kafka/DB/MinIO/app Deployments. Owner migrations/grants/provisioning là operator
Jobs riêng, không phải Terraform hoặc auto-migration trong app startup.

Platform dùng sync waves theo dependency: Namespace (-60), generated ConfigMaps
(-50), Services (-40), datastores/Keycloak (-30), TLS gateway (-20), rồi bootstrap
Jobs (-10). Config phải có trước Pod sử dụng nó; nếu để ConfigMap ở wave0, Argo
có thể chờ readiness của Keycloak vô hạn trước khi tới bước tạo realm config.

Production bases còn dùng baseline cấu hình đã freeze và nhiều placeholder.
Local vì vậy có catalog/generator riêng cho app đã khóa revision, không patch đè các schema
production để hợp thức hóa key mới. Các file sinh ra vẫn là Kustomize desired
state bình thường, review/version trong Git và để Argo reconcile. Khi migrate
production runtime contract sau này cần một thay đổi riêng, không dùng local
profile làm production defaults.

## 2. Quy trình release local

1. Làm bootstrap/image import ở `Maint-infrastructure/local/README.md`.
2. Tooling tạo actual receipts từ Docker image ID, Git SHA, dirty flag, source
   snapshot, Dockerfile hash và context. Không chấp nhận tag :dev là identity.
3. `prepare platform` hoặc `prepare apps` ghi diff vào đúng local path.
4. Review diff, commit và push nhánh GitOps đã cấu hình cho Argo.
5. Argo lấy manifests ở remote, render Kustomize và đồng bộ; xem sync/health riêng.

Argo không build images, không đọc file Git chưa push, không tự cấp secret values
và không biến model placeholder thành inference thật. Private repo cần credential
Argo riêng ngoài Git. Local bootstrap mặc định selfHeal=true/prune=false; việc
bật prune phải được review, đặc biệt với PVC, ConfigMaps và dữ liệu.

Kustomize configMapGenerator tạo content hash cho app/adapter/runtime config.
Pod references nhận tên hash mới để rollout đúng config. Image alias chứa actual
image ID được import vào k3d và imagePullPolicy Never; đó là identity local, không
là production registry/signature attestation. Dirty source luôn được ghi rõ.

## 3. Chuẩn bị profile và invariants

Copy `profiles/local.example.json`. `machine_count` phải khớp số máy đã provision;
5 là default dev, còn100 máy là design baseline cần đo riêng. Một browser stream
vẫn nhận nhiều máy; không tạo100 partition hay100 consumers.

- `components.*.enabled`: chỉ true khi runtime/image/dependencies thật đã có.
- `files`: đường dẫn `/local/datasets|models|fixtures/...` và SHA256; không commit
  dataset/model/secret values. Prepare kiểm file host và init container kiểm lại.
- `runtime_reviewed`: bắt buộc cho ML/RAG/MLflow/training/Drift còn cần owner input.
- `evidence`: operator xác nhận migrations, least-privilege grants, registry và
  ordering activation; không dùng những flags này như kết quả benchmark/tests.
- Không đưa PASSWORD, SECRET, BEARER_TOKEN/API_KEY values vào env profile. Credentials
  dùng Secrets từ bootstrap; URI chứa password cũng không được commit.
- Không bật training như Deployment/CronJob app. Training là submitted approved Job.
- Drift CronJob mặc định suspended; chỉ bật schedule sau khi owner review provider,
  model/reference/config. Source Drift cũ không được coi tự tương thích v1.4.

Worker chỉ bật khi có Business registry và real ML service. M5 Consumer cần
Processing Read API, URL + token file. Frontend cần Business API, Simulator UI
cần Sensor. Hệ thống không tạo response thành công giả khi thiếu dependencies.

ML/RAG có source từ PR15/16, base image đã pin trong PR19. Catalog vẫn giữ
`owner_input_required` để yêu cầu operator review artifact/auth/knowledge và image
receipts; đây không còn là tuyên bố hai service chỉ có skeleton. ML generator
mount model tại `/local/models/logreg-baseline-v0` và bật explicit local prototype.
Xem [source synchronization](LOCAL_SOURCE_SYNC.md) cho source lock và cấu hình RAG.

Ví dụ khai báo checksum file trong component Worker (thay hash bằng giá trị thật):

```json
"files": {
  "risk_policy": {"path": "/local/fixtures/risk-policy.json", "sha256": "ACTUAL_SHA256"},
  "model_identity": {"path": "/local/fixtures/model-identity.json", "sha256": "ACTUAL_SHA256"}
}
```

Ví dụ này cố ý không qua schema cho đến khi có hash thật. Identity/model/policy
phải khớp runtime ML được deploy; không lấy reference từ live window cho đủ field.

## 4. Auth và kết nối M5

Realm Keycloak dev cấu hình public clients PKCE cho Business/Simulator UI, ba users
viewer/technician/administrator, machine_ids cụ thể M-001..M-100 và service clients.
Realm JSON chỉ chứa placeholders; secrets được đọc từ env Kubernetes khi import.
Issuer dùng TLS loopback18490; browser phải trust local CA do operator tạo.

| Caller | Credential/quyền |
| --- | --- |
| Business UI | Public PKCE client; role và scope máy từ signed access token |
| Simulator UI | Public PKCE client; SIMULATOR_OPERATOR/ADMIN và simulator:control |
| Sensor → Ingestion | OAuth client credentials, SENSOR_SERVICE, audience ingestion |
| Worker → Business registry | Service token VIEWER theo machine scope, không mutation |
| Business API/Consumer → Processing Read | BUSINESS_SERVICE, audience maintai-processing-local |
| Worker → ML | Service token scope/audience dành ML; ML owner phải triển khai xác thực tương ứng |

M5 token agent refresh file theo expires_in, xóa token đã hết hạn nếu refresh lỗi;
app tiếp tục fail closed. Chỉ Worker registry/ML adapter inject bearer và chỉ bind
loopback. Các routes REST/SSE khác giữ Authorization của caller và không retry
mutation POST. M5 state/audit/feedback vẫn do Business app transaction quyết định.

Business/Read/Worker runtime hiện có loopback guards của local test profiles.
Adapter local kết nối chúng với DNS services; không sửa app guards hoặc nói rằng
production/shared runtime đã hoàn tất. Sensor JWT mode vẫn dùng HTTPS ingress
bridge và CA mount, bắt đầu PAUSED với SQLite PVC/Recreate.

## 5. Platform và dữ liệu

Kafka4 KRaft một broker, replication/minISR1 cho local; giữ12 partitions và4 topics
canonical đúng bundle2.0.0. Internal listener cho Pods và EXTERNAL listener cho
host forward. Smoke topic riêng không làm bẩn sensor.readings. Không đổi partition
mapping trong demo hoặc reset group/offset để che lỗi ordering.

PostgreSQL17 + pgvector0.8 có processing/business/drift/knowledge/mlflow DB riêng.
Runtime logins cho worker, relay, read API, Business Consumer/API có grants riêng;
owner passwords chỉ dùng bootstrap/migration/provision Jobs. Không có cross-owner
SQL shortcut. Keycloak dev dùng PVC/H2 riêng, không tạo domain DB thứ sáu.

Bảy buckets đều versioned: raw, processed, models, approved, manuals, drift,
mlflow. Mỗi bên có S3 account/policy riêng; không dùng MinIO root trong app. Không
có DeleteObject quyền ứng dụng hoặc lifecycle tự xóa version/retention mới.
Storage Consumer chỉ archive raw/quarantine; processed history/archive là phần
Processing/M6, không tự được implement vì bucket đã tồn tại.

## 6. Bốn UI và monitoring

Business UI và Simulator UI có image/Deployment riêng, hai edge routes riêng.
Business edge `/api` chỉ tới Business; Simulator edge `/api` chỉ tới Sensor.
Runtime config JSON dùng đúng DTO hiện hành, không dùng các key uppercase cũ.

Grafana/MLflow dùng UI upstream, không tạo React UI mới. Grafana có datasource và
panels từ metrics thực; thiếu app/exporter có thể cho No data, không được suy ra
hệ thống khỏe. Kafka lag panel cần exporter chưa có trong baseline local này.
Prometheus chỉ list/get/watch Pods trong namespace; không đọc Secrets.

MLflow image vẫn thuộc app `ml-service/mlflow/`, profile disabled đến khi owner
chốt server/base digest/SDK compatibility. Local không kéo upstream :latest để
bỏ qua quyết định packaging. Native UI ở15000 chỉ khi runtime thật được bật.

## 7. Giới hạn và nghiệm thu

Một server/storage local không chứng minh broker/RDS HA, rolling/failover trên
AWS hay latency100 máy. Nhánh app hiện đã có M5; mô tả ZIP rằng Alert loops chưa
có không còn là căn cứ trạng thái. ML/RAG/training, M6 history và M7 Copilot vẫn
cần nguồn/kiểm chứng tương ứng. Không xem Argo Synced hoặc broker smoke là E2E.

CI authored kiểm source/contract/gates, Kustomize local và production; chưa được
thực thi trong lượt này. Runbook kiểm chứng cần theo từng tầng và ghi rõ fixture
so với provider thật. Xem `LOCAL_MIGRATION.md` để chuyển từ folder k3d cũ.
