from __future__ import annotations

import json
from .common import ROOT, canonical_sha, platform, read_json, read_yaml, require_image, write_yaml


def render_runtime(name: str, release: dict) -> None:
    definitions = read_json("config/components.json")["components"]
    definition = definitions[name]
    path = f"workloads/{name}"
    manifest = read_yaml(f"{path}/workload.yaml")
    template = manifest["spec"]["jobTemplate"]["spec"]["template"] if manifest["kind"] == "CronJob" else manifest["spec"]["template"]
    pod = template["spec"]
    if release.get("image"):
        require_image(release["image"], definition["image_group"])
        pod["containers"][0]["image"] = release["image"]
    config = read_yaml(f"{path}/config.yaml")
    values = release.get("runtime_config")
    if values is None:
        values = json.loads(config["data"]["runtime-config.json"]) if name in {"frontend", "simulator-ui"} else config["data"]
    digest = canonical_sha(values)
    config_name = f"{name}-config-{digest[:12]}"
    config["metadata"]["name"] = config_name
    config["data"] = {"runtime-config.json": json.dumps(values, sort_keys=True)} if name in {"frontend", "simulator-ui"} else values
    template["metadata"]["annotations"]["maintai.io/config-sha256"] = digest
    if name in {"frontend", "simulator-ui"}:
        for volume in pod["volumes"]:
            if volume["name"] == "runtime-config":
                volume["configMap"]["name"] = config_name
    else:
        pod["containers"][0]["envFrom"] = [{"configMapRef": {"name": config_name}}]
    if manifest["kind"] == "CronJob":
        manifest["spec"]["suspend"] = not release["enabled"]
    if release.get("source_sha"):
        template["metadata"]["annotations"]["maintai.io/source-sha"] = release["source_sha"]
    model = read_json("state/production/model.json")
    if name in {"ml-service", "drift-worker"}:
        template["metadata"]["annotations"]["maintai.io/model-release"] = model.get("release_id") or "unconfigured"
    state = read_json("state/production/workloads.json")
    automation_image = state["automation"].get("image")
    for init in pod.get("initContainers", []):
        if automation_image:
            require_image(automation_image, "automation")
            init["image"] = automation_image
    p = platform()
    account = read_yaml(f"{path}/serviceaccount.yaml")
    if name in p["roles"]:
        account["metadata"].setdefault("annotations", {})["eks.amazonaws.com/role-arn"] = p["roles"][name]
        account["automountServiceAccountToken"] = True
        pod["automountServiceAccountToken"] = True
    write_yaml(f"{path}/serviceaccount.yaml", account)
    write_yaml(f"{path}/config.yaml", config)
    write_yaml(f"{path}/workload.yaml", manifest)


def activation_gate(name: str, release: dict) -> None:
    if not release["enabled"]:
        return
    require_image(release.get("image"), read_json("config/components.json")["components"][name]["image_group"])
    if not release.get("entrypoint_reviewed"):
        raise ValueError(f"Application entrypoint is not reviewed for {name}")
    definition = read_json("config/components.json")["components"][name]
    if definition.get("logical_database"):
        import hashlib
        trust = read_json("config/trust.json")
        bundle = read_yaml("platform/secrets/rds-ca.yaml")["data"]["global-bundle.pem"]
        if not trust["rds_ca_bundle_sha256"] or hashlib.sha256(bundle.encode()).hexdigest() != trust["rds_ca_bundle_sha256"] or "BEGIN CERTIFICATE" not in bundle:
            raise ValueError("Review and pin the AWS RDS CA bundle before enabling DB clients")
    protocols = read_json("config/protocols.json")
    if not protocols["database_bootstrap_reviewed"] or not protocols["owner_migrations_reviewed"]:
        raise ValueError("Database bootstrap and owner migrations must be reviewed before enablement")
    if name in {"processing-worker", "processing-outbox-relay", "business-consumer"} and protocols["inference_results_schema_version"] is None:
        raise ValueError("Resolve inference.results schema-version conflict first")
    if name in {"ingestion-api", "processing-worker", "processing-outbox-relay", "business-consumer", "storage-consumer"}:
        import re
        pin = read_json("config/kafka-contracts.json")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", pin["source"].get("git_sha") or ""):
            raise ValueError("Pin a reviewed application commit for the Kafka contract bundle first")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", release.get("source_sha") or ""):
            raise ValueError("Kafka workloads require an actual image source Git SHA")
    config = release.get("runtime_config", {})
    if any("REPLACE_WITH" in value for value in config.values()):
        raise ValueError(f"Runtime config remains unconfigured: {name}")
    if name in {"sensor", "ml-service", "drift-worker"}:
        if not read_json("state/production/workloads.json")["automation"].get("image"):
            raise ValueError("A reviewed automation image digest is required for init containers")
    if name in {"ml-service", "drift-worker"} and read_json("state/production/model.json")["status"] != "configured":
        raise ValueError("A model/preprocessor/reference bundle must be released first")


def render_workloads() -> None:
    releases = read_json("state/production/workloads.json")
    resources = []
    for name, release in releases["components"].items():
        activation_gate(name, release)
        render_runtime(name, release)
        if release["enabled"]:
            resources.append(f"../../../workloads/{name}")
    path = "environments/production/workloads/kustomization.yaml"
    value = read_yaml(path)
    value["resources"] = resources
    write_yaml(path, value)
    model = read_json("state/production/model.json")
    path = "environments/production/config/maintai-model-release.yaml"
    value = read_yaml(path)
    value["data"]["model.json"] = json.dumps(model, sort_keys=True)
    write_yaml(path, value)
