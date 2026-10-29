"""Prepare reviewable local Git files. Never commit, push or contact a cluster."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .common import ROOT, assert_local, fingerprint, identity, load
from .risk_policy import POLICY_CONFIGMAP, read_policy
from .workloads import TOOLS, metadata, resources


def write(path, value):
    target = assert_local(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False) if isinstance(value, dict) else value)


def image_override(name, image):
    repository, tag = image.rsplit(":", 1)
    return {"name": "registry.invalid/maintai-local/" + name, "newName": repository, "newTag": tag}


def prepare_platform(receipts):
    images = []
    selected = {}
    for name in ("minio", "mc", "dev-tools"):
        image = identity(receipts[name], name)
        if receipts[name].get("imported_context") != "k3d-maintai-local":
            raise ValueError("Platform image has no import receipt for this cluster")
        images.append(image_override(name, image))
        selected[name] = receipts[name]
    folder = ROOT / "environments/local/platform"
    write(folder / "kustomization.yaml", {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization", "resources": ["../../../local/platform"], "images": images})
    write(folder / "release.json", json.dumps({"schema_version": "1.0.0", "images": selected,
          "platform_lock_sha256": fingerprint(load("config/local/platform.lock.json"))}, indent=2) + "\n")


def validate_profile(profile, receipts):
    Draft202012Validator(load("contracts/local/local-profile-v1.schema.json")).validate(profile)
    catalog = load("config/local/runtime-catalog.json")["components"]
    if profile.get("schema_version") != "1.0.0" or profile.get("namespace") != "maintai-local":
        raise ValueError("Unexpected local profile identity")
    if type(profile.get("machine_count")) is not int or not 1 <= profile["machine_count"] <= 100:
        raise ValueError("Use one to 100 explicitly provisioned local machines")
    if set(profile["components"]) != set(catalog):
        raise ValueError("Profile component inventory differs from the local runtime contract")
    enabled = {name for name, spec in profile["components"].items() if spec.get("enabled") is True}
    evidence = profile["evidence"]
    prerequisites = {
        "sensor": {"ingestion-api"}, "frontend": {"business-api"}, "simulator-ui": {"sensor"},
        "processing-worker": {"business-api", "ml-service"}, "business-consumer": {"processing-read-api"},
    }
    for name in enabled:
        if not prerequisites.get(name, set()) <= enabled:
            raise ValueError("Enabled runtime has a disabled dependency: " + name)
        if name == "training":
            raise ValueError("Training is a manually submitted Job, never a long-running app")
        spec = profile["components"][name]
        actual = identity(receipts[name], name)
        if receipts[name].get("imported_context") != "k3d-maintai-local":
            raise ValueError("App image must have been imported into this cluster")
        if spec.get("image") not in {None, actual}:
            raise ValueError("Profile image differs from the actual receipt")
        if catalog[name]["source_status"] == "owner_input_required" and spec.get("runtime_reviewed") is not True:
            raise ValueError("Owner must explicitly review the real runtime interface: " + name)
        if name == "mlflow" and not evidence.get("mlflow_compatibility_reviewed"):
            raise ValueError("MLflow app image/base/server-client compatibility is unresolved")
        if any(re.search(r"PASSWORD|SECRET|BEARER_TOKEN|API_KEY|PRIVATE_KEY", key) for key in spec.get("env", {})):
            raise ValueError("Use Kubernetes Secret references, not credential values in Git profiles")
        for key, value in spec.get("env", {}).items():
            if key == "DATABASE_URL" or key.endswith("_DATABASE_URL") or key == "MLFLOW_BACKEND_STORE_URI":
                raise ValueError("Database credentials are supplied only through scoped runtime Secrets")
            if isinstance(value, str) and "://" in value:
                parsed = urlsplit(value)
                if parsed.username or parsed.password:
                    raise ValueError("Credential-bearing URLs must not be written to Git")
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in spec.get("env", {}).items()):
            raise ValueError("Runtime environment values must be explicit strings")
        for artifact in spec.get("files", {}).values():
            path = Path(artifact["path"])
            if not str(path).startswith("/local/") or ".." in path.parts or not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")):
                raise ValueError("Artifacts require local read-only paths and SHA256")
    if enabled & {"processing-worker", "processing-read-api", "processing-outbox-relay", "business-api", "business-consumer"}:
        if not all(evidence.get(key) is True for key in ("owner_migrations_applied", "runtime_grants_applied", "machines_provisioned")):
            raise ValueError("Owner migration, runtime grants and registry provisioning require operator attestation")
    if enabled & {"processing-worker", "processing-outbox-relay"} and evidence.get("ordering_activated") is not True:
        raise ValueError("PROC-ORDER-01 activation is an explicit owner operation")
    if "processing-worker" in enabled:
        required = {"/local/fixtures/model-identity.json"}
        declared = {entry["path"] for entry in profile["components"]["processing-worker"]["files"].values()}
        entries = profile["components"]["processing-worker"]["files"]
        if "PROCESSING_RISK_POLICY_FILE" in profile["components"]["processing-worker"].get("env", {}):
            raise ValueError("Worker risk policy path is managed by its app-owned ConfigMap")
        if "risk_policy" in entries or any(Path(path).name == "risk-policy.json" for path in declared):
            raise ValueError("Remove the legacy risk_policy file; policy now comes from the app-owned ConfigMap")
        if not required <= declared or evidence.get("model_identity_reviewed") is not True:
            raise ValueError("Worker needs checksummed model identity matching the serving model")
    if "sensor" in enabled:
        declared = {entry["path"] for entry in profile["components"]["sensor"]["files"].values()}
        if "/local/datasets/ai4i2020.csv" not in declared or evidence.get("dataset_reviewed") is not True:
            raise ValueError("Sensor needs an approved checksummed AI4I input")
    if "ml-service" in enabled:
        model_files = profile["components"]["ml-service"]["files"].values()
        if not any(entry["path"].startswith("/local/models/") for entry in model_files):
            raise ValueError("Serving ML requires checksummed model bundle files")
    if "drift-worker" in enabled:
        declared = {entry["path"] for entry in profile["components"]["drift-worker"]["files"].values()}
        if "/local/fixtures/drift.yaml" not in declared or not any(path.startswith("/local/models/") for path in declared):
            raise ValueError("Drift needs reviewed provider config and a model-matching reference")
    identity(receipts["dev-tools"], "dev-tools")
    return enabled


def edge(name, frontend, backend, port, node):
    config = {"environment": "local-k3d", "http": [{"bind": "0.0.0.0", "port": port, "routes": [
        {"prefix": "/api/", "target_host": backend, "target_port": 8003 if backend == "business-api" else 8005},
        {"prefix": "/", "target_host": frontend, "target_port": 8080}]}]}
    deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": metadata(name), "spec": {"replicas": 1,
        "selector": {"matchLabels": {"app": name}}, "template": {"metadata": {"labels": {"app": name}}, "spec": {
            "automountServiceAccountToken": False, "securityContext": {"runAsUser": 10001, "runAsNonRoot": True},
            "containers": [{"name": "edge", "image": TOOLS, "imagePullPolicy": "Never", "args": ["serve"],
                "volumeMounts": [{"name": "config", "mountPath": "/config", "readOnly": True}],
                "ports": [{"containerPort": port}], "readinessProbe": {"tcpSocket": {"port": port}, "periodSeconds": 5},
                "resources": {"requests": {"cpu": "25m", "memory": "32Mi"}, "limits": {"memory": "256Mi"}}}],
            "volumes": [{"name": "config", "configMap": {"name": name + "-config"}}]}}}}
    service = {"apiVersion": "v1", "kind": "Service", "metadata": metadata(name), "spec": {"type": "NodePort", "selector": {"app": name}, "ports": [{"port": port, "targetPort": port, "nodePort": node}]}}
    return [deployment, service], {"name": name + "-config", "literals": ["bridge.json=" + json.dumps(config, sort_keys=True)]}


def prepare_apps(profile, receipts, app_root=None):
    enabled = validate_profile(profile, receipts)
    policy_text, policy_metadata = read_policy(app_root) if "processing-worker" in enabled else (None, None)
    folder = ROOT / "environments/local/apps"
    generated, generators, images = [], [], [image_override("dev-tools", receipts["dev-tools"]["image"])]
    if policy_text is not None:
        generators.append({"name": POLICY_CONFIGMAP, "literals": ["risk-policy.json=" + policy_text]})
    for name in sorted(enabled):
        spec = profile["components"][name]
        docs, configs = resources(name, spec, profile["machine_count"], receipts[name]["source_git_sha"])
        artifact_files = list(spec.get("files", {}).values())
        if artifact_files:
            pod = docs[0]["spec"]["template"]["spec"] if docs[0]["kind"] == "Deployment" else docs[0]["spec"]["jobTemplate"]["spec"]["template"]["spec"]
            generators.append({"name": name + "-artifacts", "literals": ["artifacts.json=" + json.dumps(artifact_files, sort_keys=True)]})
            pod["volumes"].append({"name": "artifact-lock", "configMap": {"name": name + "-artifacts"}})
            data_mounts = [mount.copy() for mount in pod["containers"][0]["volumeMounts"] if mount["mountPath"].startswith("/local/")]
            pod.setdefault("initContainers", []).insert(0, {"name": "verify-artifact-checksums", "image": TOOLS, "imagePullPolicy": "Never",
                "args": ["verify-files", "--config", "/artifact-lock/artifacts.json"],
                "volumeMounts": data_mounts + [{"name": "artifact-lock", "mountPath": "/artifact-lock", "readOnly": True}],
                "resources": {"requests": {"cpu": "25m", "memory": "32Mi"}, "limits": {"memory": "128Mi"}}})
        for document in docs:
            if document["kind"] == "Deployment":
                annotations = document["spec"]["template"]["metadata"].setdefault("annotations", {})
                annotations.update({"maintai.io/source-sha": receipts[name]["source_git_sha"], "maintai.io/source-snapshot": receipts[name]["source_snapshot_sha256"],
                                    "maintai.io/source-dirty": str(receipts[name]["source_dirty"]).lower(), "prometheus.io/scrape": "false" if name in {"frontend", "simulator-ui", "mlflow"} else "true",
                                    "prometheus.io/port": str(load("config/local/runtime-catalog.json")["components"][name]["port"])})
                if name == "processing-worker":
                    annotations.update({"maintai.io/risk-policy-version": policy_metadata["policy_version"],
                                        "maintai.io/risk-policy-sha256": policy_metadata["policy_sha256"],
                                        "maintai.io/risk-policy-source-sha": policy_metadata["source_git_sha"]})
        file = "generated/" + name + ".yaml"
        write(folder / file, yaml.safe_dump_all(docs, sort_keys=False))
        generated.append(file)
        generators += configs
        images.append(image_override(name, identity(receipts[name], name)))
    for front, back, name, port, node in (("frontend", "business-api", "business-edge", 8080, 30080), ("simulator-ui", "sensor", "simulator-edge", 8080, 30081)):
        if front in enabled:
            docs, config = edge(name, front, back, port, node)
            file = "generated/" + name + ".yaml"
            write(folder / file, yaml.safe_dump_all(docs, sort_keys=False))
            generated.append(file)
            generators.append(config)
    if "sensor" in enabled:
        file = "generated/sensor-pvc.yaml"
        write(folder / file, {"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": metadata("local-sensor-state"), "spec": {"accessModes": ["ReadWriteOnce"], "storageClassName": "local-path", "resources": {"requests": {"storage": "1Gi"}}}})
        generated.append(file)
    if "mlflow" in enabled:
        file = "generated/mlflow-nodeport.yaml"
        write(folder / file, {"apiVersion": "v1", "kind": "Service", "metadata": metadata("mlflow-local-ui"), "spec": {"type": "NodePort", "selector": {"app.kubernetes.io/name": "mlflow"}, "ports": [{"port": 5000, "targetPort": 5000, "nodePort": 30500}]}})
        generated.append(file)
    generators.append({"name": "local-app-release-status", "literals": ["enabled=" + ",".join(sorted(enabled)), "profile-sha256=" + fingerprint(profile)]})
    write(folder / "kustomization.yaml", {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization", "namespace": "maintai-local",
        "resources": generated, "configMapGenerator": generators, "images": images})
    write(folder / "release.json", json.dumps({"schema_version": "1.0.0", "profile": profile, "risk_policy": policy_metadata,
          "receipts": {key: receipts[key] for key in sorted(enabled | {"dev-tools"})}}, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare local-only desired state for Git review")
    parser.add_argument("operation", choices=["platform", "apps"])
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--app-root", type=Path, help="Reviewed app checkout required when preparing Worker policy")
    args = parser.parse_args(argv)
    try:
        receipts = json.loads(args.receipts.read_text())
        if args.operation == "platform":
            prepare_platform(receipts)
        else:
            if args.profile is None:
                parser.error("apps requires --profile")
            prepare_apps(json.loads(args.profile.read_text()), receipts, args.app_root)
    except (ValueError, ValidationError, KeyError, OSError):
        parser.exit(2, "Local release refused: check profile/schema/receipts and reviewed dependencies. No credential values are logged.\n")
    print("Local desired state prepared. No commit, push, image publication or cluster action occurred.")


if __name__ == "__main__":
    main()
