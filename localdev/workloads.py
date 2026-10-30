"""Reviewed local app interfaces; adapters are explicit development workloads."""

import json
import hashlib

from .common import load
from .risk_policy import POLICY_CONFIGMAP, POLICY_MOUNT

NS = "maintai-local"
ISSUER = "https://127.0.0.1:18490/realms/maintai"
JWKS = "http://127.0.0.1:18090/realms/maintai/protocol/openid-connect/certs"
TOOLS = "registry.invalid/maintai-local/dev-tools:NOT_BUILT"


def metadata(name):
    return {"name": name, "namespace": NS, "labels": {"app.kubernetes.io/name": name, "app.kubernetes.io/part-of": "maintai-local"}}


def tcp(port, host, target):
    return {"port": port, "target_host": host, "target_port": target}


def http(port, host, target, *, public=False, tls=False, oauth=None):
    result = {"port": port, "bind": "0.0.0.0" if public else "127.0.0.1", "target_host": host, "target_port": target}
    if tls:
        result["tls"] = True
    if oauth:
        result["oauth"] = oauth
    return result


def oauth(name):
    return {"client_id": "maintai-" + name, "secret_file": "/credentials/" + name + "/client_secret",
            "token_url": "http://keycloak:8080/realms/maintai/protocol/openid-connect/token"}


def configuration(name, count):
    kafka = {"KAFKA_LOCAL_MODE": "true", "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT",
             "KAFKA_BOOTSTRAP_SERVERS": "127.0.0.1:19092", "KAFKA_GROUP_PREFIX": "local-"}
    bridge = {"environment": "local-k3d", "tcp": [], "http": [], "oauth": {}, "token_directory": "/tokens"}
    env, secrets, mounts = {}, [], []
    if name in {"processing-worker", "processing-outbox-relay", "business-consumer", "ingestion-api", "storage-consumer"}:
        env.update(kafka)
        bridge["tcp"].append(tcp(19092, "kafka", 9092))
    if name in {"processing-worker", "processing-outbox-relay", "processing-read-api", "business-consumer", "business-api"}:
        bridge["tcp"].append(tcp(25432, "postgres", 5432))
        secrets.append("local-" + name + "-env")
    if name in {"ingestion-api", "business-api", "processing-read-api"}:
        bridge["http"].append(http(18090, "keycloak", 8080))
    if name == "ingestion-api":
        env.update({"INGESTION_ENV": "local", "AUTH_MODE": "oidc", "INGESTION_HOST": "0.0.0.0", "INGESTION_PORT": "8000",
                    "OIDC_ISSUER": ISSUER, "OIDC_JWKS_URL": JWKS, "OIDC_AUDIENCE": "ingestion",
                    "OIDC_ROLES_CLAIM": "roles", "OIDC_MACHINES_CLAIM": "machine_ids", "BUSINESS_PUBLIC_ORIGIN": "http://127.0.0.1:18080"})
    if name == "processing-worker":
        env.update({"PROCESSING_PROFILE": "local-fixture", "PROCESSING_EXECUTION_MODE": "keyed", "PROCESSING_HEALTH_PORT": "18081",
                    "BUSINESS_BASE_URL": "http://127.0.0.1:18003", "ML_BASE_URL": "http://127.0.0.1:18001",
                    "PROCESSING_SCHEMA_DIRECTORY": "/app/http-contracts", "PROCESSING_RISK_POLICY_FILE": POLICY_MOUNT + "/risk-policy.json",
                    "PROCESSING_MODEL_IDENTITY_FIXTURE": "/local/fixtures/model-identity.json"})
        bridge["http"] += [http(18003, "business-api", 8003, oauth="registry"), http(18001, "ml-service", 8001, oauth="ml"), http(8081, "127.0.0.1", 18081, public=True)]
        bridge["oauth"] = {key: oauth(key) for key in ("registry", "ml")}
        mounts.append("fixtures")
    if name == "processing-outbox-relay":
        env.update({"PROCESSING_PROFILE": "local-fixture", "PROCESSING_HEALTH_PORT": "18082", "OUTBOX_EXECUTION_MODE": "ordered",
                    "OUTBOX_CLAIM_LEASE_SECONDS": "120", "OUTBOX_POLL_INTERVAL_MS": "250"})
        bridge["http"].append(http(8082, "127.0.0.1", 18082, public=True))
    if name == "processing-read-api":
        env.update({"PROCESSING_READ_PROFILE": "local-test", "PROCESSING_READ_HOST": "127.0.0.1", "PROCESSING_READ_PORT": "18004",
                    "PROCESSING_READ_OIDC_ISSUER": ISSUER, "PROCESSING_READ_OIDC_JWKS_URL": JWKS,
                    "PROCESSING_READ_OIDC_AUDIENCE": "maintai-processing-local", "PROCESSING_READ_ROLES_CLAIM": "roles", "PROCESSING_READ_MACHINES_CLAIM": "machine_ids"})
        bridge["http"].append(http(8004, "127.0.0.1", 18004, public=True))
    if name in {"business-api", "business-consumer"}:
        env.update({"BUSINESS_PROCESSING_READ_URL": "http://127.0.0.1:18004", "BUSINESS_PROCESSING_TOKEN_FILE": "/tokens/processing.jwt",
                    "BUSINESS_NOTIFY_CHANNEL": "maintai_business_live_v1", "BUSINESS_ALERT_NOTIFY_CHANNEL": "maintai_business_alert_v1"})
        bridge["http"].append(http(18004, "processing-read-api", 8004))
        bridge["oauth"]["processing"] = oauth("processing")
    if name == "business-api":
        env.update({"BUSINESS_PROFILE": "local-test", "BUSINESS_HOST": "127.0.0.1", "BUSINESS_PORT": "18003",
                    "BUSINESS_OIDC_ISSUER": ISSUER, "BUSINESS_OIDC_JWKS_URL": JWKS, "BUSINESS_OIDC_AUDIENCE": "maintai-business-local",
                    "BUSINESS_ROLES_CLAIM": "roles", "BUSINESS_MACHINES_CLAIM": "machine_ids"})
        bridge["http"].append(http(8003, "127.0.0.1", 18003, public=True))
    if name == "business-consumer":
        env.update({"BUSINESS_CONSUMER_PROFILE": "local-test", "BUSINESS_CONSUMER_HOST": "127.0.0.1", "BUSINESS_CONSUMER_PORT": "18083"})
        bridge["http"].append(http(8083, "127.0.0.1", 18083, public=True))
    if name == "storage-consumer":
        env.update({"STORAGE_HTTP_HOST": "0.0.0.0", "STORAGE_HTTP_PORT": "8008", "S3_RAW_BUCKET": "maintai-raw", "S3_RAW_PREFIX": "raw-sensor",
                    "S3_ENDPOINT_URL": "http://minio:9000", "S3_ADDRESSING_STYLE": "path", "S3_ALLOW_UNVERSIONED": "false", "STORAGE_ARCHIVE_OUTCOMES": "false"})
        secrets.append("local-storage-env")
    if name == "sensor":
        env.update({"SIM_HOST": "0.0.0.0", "SIM_PORT": "8005", "SIM_AUTH_MODE": "jwt", "SIM_JWT_ISSUER": ISSUER,
                    "SIM_JWKS_URL": ISSUER + "/protocol/openid-connect/certs", "SIM_JWT_AUDIENCE": "simulator-control",
                    "SIM_ROLES_CLAIM": "roles", "SIM_MACHINES_CLAIM": "machine_ids", "SIM_CONTROL_SCOPE": "simulator:control",
                    "BACKEND_BASE_URL": "https://127.0.0.1:18400", "SIM_INGESTION_AUTH": "oauth", "SIM_OAUTH_TOKEN_URL": ISSUER + "/protocol/openid-connect/token",
                    "SIM_OAUTH_CLIENT_ID": "maintai-sensor", "SIM_OAUTH_SECRET_FILE": "/credentials/sensor/client_secret", "SIM_OAUTH_SCOPE": "sensor:write",
                    "SIM_DATASET_PATH": "/local/datasets/ai4i2020.csv", "SIM_STATE_PATH": "/state/state.sqlite3", "SIM_MACHINE_COUNT": str(count),
                    "SIM_INTERVAL_MS": "1000", "SIM_INITIAL_STATE": "PAUSED", "SIM_LOOP_DATASET": "true", "SSL_CERT_FILE": "/tls/ca.crt"})
        bridge["http"] += [http(18490, "keycloak", 8080, tls=True), http(18400, "ingestion-api", 8000, tls=True)]
        mounts += ["datasets", "sensor-secret"]
    if name in {"ml-service", "rag-service", "drift-worker", "mlflow", "training"}:
        mounts.append("models" if name in {"ml-service", "drift-worker"} else "datasets")
        env.update({"AWS_REGION": "us-east-1", "AWS_DEFAULT_REGION": "us-east-1", "S3_ENDPOINT_URL": "http://minio:9000", "MLFLOW_TRACKING_URI": "http://mlflow:5000"})
        if name in {"mlflow", "rag-service", "drift-worker", "training", "ml-service"}:
            secrets.append("local-" + name + "-env")
        if name == "drift-worker":
            mounts.append("fixtures")
    if name == "mlflow":
        env.update({"MLFLOW_S3_ENDPOINT_URL": "http://minio:9000"})
    if name == "ml-service":
        # Match the supplied PR15 bundle and the existing read-only models mount.
        # This explicit local prototype flag does not provide service authentication.
        env.update({"MAINTAI_LOCAL_ONLY": "1", "MODEL_DIR": "/local/models/logreg-baseline-v0"})
    if name == "rag-service":
        env.update(load("config/local/rag-runtime.json")["environment"])
    return env, bridge, secrets, mounts


def ui_config(name):
    if name == "frontend":
        return {"mode": "live", "apiBaseUrl": "/api/v1", "freshMs": 2000, "staleMs": 5000,
                "auth": {"authority": ISSUER, "clientId": "maintai-business-ui", "scope": "openid profile", "audience": "maintai-business-local", "rolesClaim": "roles"}}
    return {"mode": "live", "apiBaseUrl": "", "pollIntervalMs": 5000, "requestTimeoutMs": 8000, "staleAfterMs": 20000,
            "auth": {"mode": "oidc", "authority": ISSUER, "clientId": "maintai-simulator-ui", "scope": "openid profile simulator:control", "audience": "simulator-control"},
            "links": {"business": "http://127.0.0.1:18080", "grafana": "http://127.0.0.1:13000", "mlflow": "http://127.0.0.1:15000"}}


def resources(name, spec, count, source_sha):
    catalog = load("config/local/runtime-catalog.json")["components"][name]
    env, bridge, secrets, mounts = configuration(name, count)
    env["PRODUCER_GIT_SHA"] = source_sha
    env.update(spec.get("env", {}))
    # These are app settings only. A caller cannot disable authentication or replace M5 channels.
    forbidden = {"AUTH_ENABLED", "SIM_AUTH_MODE", "BUSINESS_ALERT_NOTIFY_CHANNEL", "BUSINESS_PROCESSING_TOKEN_FILE",
                 "PROCESSING_RISK_POLICY_FILE",
                 "BUSINESS_PROCESSING_READ_URL", "KAFKA_ENABLE_AUTO_COMMIT", "KAFKA_ENABLE_AUTO_OFFSET_STORE",
                 "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_LOCAL_MODE", "KAFKA_SECURITY_PROTOCOL", "PRODUCER_GIT_SHA"}
    if forbidden.intersection(spec.get("env", {})):
        raise ValueError("Local override attempts to weaken a fixed runtime invariant")
    if name == "rag-service" and any(key.startswith("OLLAMA_") or key in {"EMBEDDING_MODEL", "EMBEDDING_REVISION", "HF_HOME", "SENTENCE_TRANSFORMERS_HOME", "MODEL_LOCAL_FILES_ONLY"} for key in spec.get("env", {})):
        raise ValueError("RAG embedding/cache/provider wiring belongs to the reviewed runtime selection")
    port = catalog["port"]
    primary = {"name": name, "image": "registry.invalid/maintai-local/" + name + ":NOT_BUILT", "imagePullPolicy": "Never",
               "envFrom": [{"configMapRef": {"name": name + "-config"}}] + [{"secretRef": {"name": value}} for value in secrets],
               "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"memory": "1Gi"}},
               "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
               "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}]}
    if catalog["command"]:
        primary["command"] = catalog["command"]
    if name == "mlflow":
        primary["command"] = ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--serve-artifacts", "--artifacts-destination", "s3://maintai-mlflow/artifacts", "--allowed-hosts", "127.0.0.1:15000,localhost:15000,mlflow:5000,mlflow.maintai-local.svc.cluster.local:5000"]
    volumes = [{"name": "tmp", "emptyDir": {}}, {"name": "tls", "secret": {"secretName": "local-dev-tls", "defaultMode": 288}}]
    containers, init = [primary], []
    if name == "rag-service":
        rag = load("config/local/rag-runtime.json")
        primary["env"] = [{"name": "GROQ_API_KEY", "valueFrom": {"secretKeyRef": {"name": rag["groq_secret"], "key": "GROQ_API_KEY"}}}]
        volumes.append({"name": "embedding-cache", "persistentVolumeClaim": {"claimName": rag["cache_claim"]}})
        primary["volumeMounts"].append({"name": "embedding-cache", "mountPath": rag["environment"]["SENTENCE_TRANSFORMERS_HOME"]})
        primary["resources"] = {"requests": {"cpu": "250m", "memory": "512Mi"}, "limits": {"cpu": "2", "memory": "2Gi"}}
        # Provider quota/network failures belong to readiness, not process startup.
    if name == "processing-worker":
        volumes.append({"name": "risk-policy", "configMap": {"name": POLICY_CONFIGMAP}})
        primary["volumeMounts"].append({"name": "risk-policy", "mountPath": POLICY_MOUNT, "readOnly": True})
    configs = [{"name": name + "-config", "literals": [key + "=" + value for key, value in sorted(env.items())]}]
    if bridge["tcp"] or bridge["http"] or bridge["oauth"]:
        configs.append({"name": name + "-bridge", "literals": ["bridge.json=" + json.dumps(bridge, sort_keys=True)]})
        volumes += [{"name": "bridge-config", "configMap": {"name": name + "-bridge"}}, {"name": "tokens", "emptyDir": {"medium": "Memory"}}]
        bridge_mounts = [{"name": "bridge-config", "mountPath": "/config", "readOnly": True}, {"name": "tokens", "mountPath": "/tokens"}, {"name": "tls", "mountPath": "/tls", "readOnly": True}]
        for client in bridge["oauth"]:
            volume = "oidc-" + client
            volumes.append({"name": volume, "secret": {"secretName": "local-oidc-" + client, "defaultMode": 288}})
            bridge_mounts.append({"name": volume, "mountPath": "/credentials/" + client, "readOnly": True})
        helper = {"name": "local-adapter", "image": TOOLS, "imagePullPolicy": "Never", "args": ["serve"], "volumeMounts": bridge_mounts,
                  "resources": {"requests": {"cpu": "25m", "memory": "32Mi"}, "limits": {"memory": "256Mi"}},
                  "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}}
        containers.append(helper)
        primary["volumeMounts"].append({"name": "tokens", "mountPath": "/tokens", "readOnly": True})
        if name in {"business-api", "business-consumer"}:
            init.append({**helper, "name": "initialize-service-tokens", "args": ["tokens-once"]})
    for area in mounts:
        if area == "sensor-secret":
            volumes.append({"name": "sensor-client", "secret": {"secretName": "local-oidc-sensor", "defaultMode": 288}})
            primary["volumeMounts"].append({"name": "sensor-client", "mountPath": "/credentials/sensor", "readOnly": True})
            primary["volumeMounts"].append({"name": "tls", "mountPath": "/tls", "readOnly": True})
        else:
            volumes.append({"name": area, "hostPath": {"path": "/mnt/maintai-local/" + area, "type": "Directory"}})
            primary["volumeMounts"].append({"name": area, "mountPath": "/local/" + area, "readOnly": True})
    if name == "sensor":
        volumes.append({"name": "state", "persistentVolumeClaim": {"claimName": "local-sensor-state"}})
        primary["volumeMounts"].append({"name": "state", "mountPath": "/state"})
    if name in {"frontend", "simulator-ui"}:
        configs = [{"name": name + "-config", "literals": ["runtime-config.json=" + json.dumps(ui_config(name), sort_keys=True)]}]
        primary["envFrom"] = []
        volumes.append({"name": "runtime-config", "configMap": {"name": name + "-config"}})
        primary["volumeMounts"].append({"name": "runtime-config", "mountPath": "/usr/share/nginx/html/runtime-config.json", "subPath": "runtime-config.json", "readOnly": True})
    pod = {"automountServiceAccountToken": False, "terminationGracePeriodSeconds": 90,
           "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
           "containers": containers, "volumes": volumes}
    if init:
        pod["initContainers"] = init
    docs = []
    labels = metadata(name)["labels"]
    if catalog["kind"] == "Deployment":
        primary["ports"] = [{"containerPort": port, "name": "http"}]
        for probe in ("startupProbe", "readinessProbe", "livenessProbe"):
            primary[probe] = {"httpGet": {"path": "/health" if name == "mlflow" else "/health/live" if probe == "livenessProbe" else "/health/ready", "port": port}, "periodSeconds": 5, "timeoutSeconds": 2, "failureThreshold": 60 if probe == "startupProbe" else 3}
        if name == "rag-service":
            primary["startupProbe"]["httpGet"]["path"] = "/health/live"
            primary["readinessProbe"]["timeoutSeconds"] = 10
        deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata(name), "spec": {"replicas": 1,
                      "strategy": {"type": "Recreate"} if name in {"sensor", "ml-service", "mlflow"} else {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}},
                      "selector": {"matchLabels": {"app.kubernetes.io/name": name}}, "template": {"metadata": {"labels": labels}, "spec": pod}}}
        if name in {"business-api", "business-consumer", "processing-worker", "sensor"}:
            from .common import ROOT
            deployment["spec"]["template"]["metadata"]["annotations"] = {"maintai.io/identity-realm-sha256": hashlib.sha256((ROOT / "local/platform/maintai-realm.json").read_bytes()).hexdigest()}
        docs += [deployment, {"apiVersion": "v1", "kind": "Service", "metadata": metadata(name), "spec": {"selector": {"app.kubernetes.io/name": name}, "ports": [{"name": "http", "port": port, "targetPort": port}]}}]
    else:
        pod["restartPolicy"] = "Never"
        docs.append({"apiVersion": "batch/v1", "kind": "CronJob", "metadata": metadata(name), "spec": {"schedule": spec.get("schedule", "*/5 * * * *"), "suspend": not spec.get("schedule_enabled", False),
                    "concurrencyPolicy": "Forbid", "jobTemplate": {"spec": {"backoffLimit": 1, "activeDeadlineSeconds": 300, "template": {"metadata": {"labels": labels}, "spec": pod}}}}})
    return docs, configs
