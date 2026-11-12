"""M6 local wiring, shared by the existing generator and the scoped rollout."""

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from .common import ROOT, identity, load


def selection():
    path = ROOT / "config/local/history-runtime.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if value.get("schema_version") != "1.0.0" or value.get("issuer") != "http://127.0.0.1:18091/maintai-history":
        raise ValueError("Invalid local delegation issuer")
    if not isinstance(value.get("enabled"), bool) or not value.get("service_subject"):
        raise ValueError("Explicit service identity and history state required")
    for key in value["jwks"]["keys"]:
        if set(key) != {"kty", "n", "e", "kid", "alg", "use"} or key["kid"] != value["signing_key_id"]:
            raise ValueError("The selector may contain only reviewed public signing keys")
    return value


def put_named(values, value):
    for index, current in enumerate(values):
        if current["name"] == value["name"]:
            values[index] = value
            return
    values.append(value)


def wire(name, documents, configs):
    config = selection()
    if not config or not config["enabled"] or name not in {"business-api", "processing-read-api", "storage-consumer"}:
        return documents, configs
    if not config.get("adapter_image"):
        raise ValueError("Import a reviewed JWKS-capable adapter before enabling history")
    deployment = next(d for d in documents if d["kind"] == "Deployment")
    service = next(d for d in documents if d["kind"] == "Service")
    pod = deployment["spec"]["template"]["spec"]
    primary = next(c for c in pod["containers"] if c["name"] == name)
    if name == "storage-consumer":
        replicas = config.get("archive_replicas", 1)
        if type(replicas) is not int or not 1 <= replicas <= 3:
            raise ValueError("Local archive supports one to three reviewed replicas")
        deployment["spec"]["replicas"] = replicas
        env_config = next(c for c in configs if c["name"] == name + "-config")
        env = dict(row.split("=", 1) for row in env_config["literals"])
        env.update({"S3_RAW_BUCKET": config.get("raw_bucket", "maintai-raw"), "STORAGE_CATALOG_ENABLED": "true",
                    "STORAGE_CATALOG_INTERVAL_SECONDS": "1", "STORAGE_CATALOG_POLL_SECONDS": "2",
                    "STORAGE_CATALOG_HEARTBEAT_SECONDS": "15", "KAFKA_POLL_INTERVAL_SECONDS": "0.01"})
        if config.get("archive_group_prefix"):
            env["KAFKA_GROUP_PREFIX"] = config["archive_group_prefix"]
        env_config["literals"] = [key + "=" + value for key, value in sorted(env.items())]
        return documents, configs
    helper = next(c for c in pod["containers"] if c["name"] == "local-adapter")
    helper["image"] = config["adapter_image"]
    for init in pod.get("initContainers", []):
        if init["name"] == "initialize-service-tokens":
            init["image"] = config["adapter_image"]
    env_config = next(c for c in configs if c["name"] == name + "-config")
    env = dict(row.split("=", 1) for row in env_config["literals"])
    bridge_config = next(c for c in configs if c["name"] == name + "-bridge")
    bridge = json.loads(bridge_config["literals"][0].split("=", 1)[1])
    if name == "business-api":
        env.update({"BUSINESS_HISTORY_ENABLED": "true", "BUSINESS_HISTORY_SIGNING_KEY_FILE": "/history/signing-key.pem",
                    "BUSINESS_HISTORY_SIGNING_KEY_ID": config["signing_key_id"], "BUSINESS_HISTORY_DELEGATION_ISSUER": config["issuer"],
                    "BUSINESS_HISTORY_SERVICE_SUBJECT": config["service_subject"], "BUSINESS_HISTORY_CURSOR_KEY_FILE": "/history/cursor-keys.json"})
        key_secret = "local-business-history-keys"
        put_named(pod["volumes"], {"name": "history-jwks", "configMap": {"name": "local-history-jwks"}})
        put_named(helper["volumeMounts"], {"name": "history-jwks", "mountPath": "/history-jwks", "readOnly": True})
        bridge["jwks"] = [{"bind": "0.0.0.0", "port": 18091, "file": "/history-jwks/jwks.json"}]
        put_named(service["spec"]["ports"], {"name": "history-jwks", "port": 18091, "targetPort": 18091})
    else:
        env.update({"PROCESSING_HISTORY_ENABLED": "true", "PROCESSING_HISTORY_META_SCHEMA": "history_meta",
                    "PROCESSING_HISTORY_DELEGATION_ISSUER": config["issuer"],
                    "PROCESSING_HISTORY_DELEGATION_JWKS_URL": "http://127.0.0.1:18091/.well-known/jwks.json",
                    "PROCESSING_HISTORY_CURSOR_KEY_FILE": "/history/cursor-keys.json",
                    "PROCESSING_HISTORY_RAW_BUCKET": config.get("raw_bucket", "maintai-raw"), "PROCESSING_HISTORY_EXPORT_BUCKET": "maintai-processed",
                    "PROCESSING_HISTORY_S3_ENDPOINT": "http://127.0.0.1:19000", "PROCESSING_RETENTION_ENABLED": "false", "PROCESSING_CLEANER_DRY_RUN": "true"})
        key_secret = "local-processing-history-keys"
        reference = {"secretRef": {"name": "local-processing-history-env"}}
        if reference not in primary["envFrom"]:
            primary["envFrom"].append(reference)
        bridge["http"] = [x for x in bridge["http"] if x["port"] != 18091] + [{"port": 18091, "bind": "127.0.0.1", "target_host": "business-api", "target_port": 18091}]
        bridge["tcp"] = [x for x in bridge["tcp"] if x["port"] != 19000] + [{"port": 19000, "target_host": "minio", "target_port": 9000}]
    put_named(pod["volumes"], {"name": "history-keys", "secret": {"secretName": key_secret, "defaultMode": 288}})
    put_named(primary["volumeMounts"], {"name": "history-keys", "mountPath": "/history", "readOnly": True})
    env_config["literals"] = [key + "=" + value for key, value in sorted(env.items())]
    bridge_config["literals"] = ["bridge.json=" + json.dumps(bridge, sort_keys=True)]
    annotations = deployment["spec"]["template"]["metadata"].setdefault("annotations", {})
    annotations["maintai.io/history-config-sha256"] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return documents, configs


def add_jwks(generators):
    config = selection()
    if config and config["enabled"]:
        put_named(generators, {"name": "local-history-jwks", "literals": ["jwks.json=" + json.dumps(config["jwks"], sort_keys=True)]})


def prepare_current():
    folder = ROOT / "environments/local/apps"
    path = folder / "kustomization.yaml"
    document = yaml.safe_load(path.read_text())
    for name in ("business-api", "processing-read-api", "storage-consumer"):
        manifest = folder / ("generated/" + name + ".yaml")
        resources, _ = wire(name, list(yaml.safe_load_all(manifest.read_text())), document["configMapGenerator"])
        manifest.write_text(yaml.safe_dump_all(resources, sort_keys=False))
    add_jwks(document["configMapGenerator"])
    path.write_text(yaml.safe_dump(document, sort_keys=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--adapter-receipt", type=Path)
    args = parser.parse_args()
    if args.enable:
        receipt = json.loads(args.adapter_receipt.read_text())
        image = identity(receipt, "dev-tools")
        if receipt.get("imported_context") != "k3d-maintai-local" or receipt.get("source_dirty"):
            raise ValueError("History needs a clean imported adapter image")
        config = selection()
        config.update(enabled=True, adapter_image=image)
        (ROOT / "config/local/history-runtime.json").write_text(json.dumps(config, indent=2) + "\n")
    prepare_current()
    print("Prepared only M6 local manifests; review and push before Argo sync.")


if __name__ == "__main__":
    main()
