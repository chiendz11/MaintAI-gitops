"""Only mutate allow-listed GitOps files. This tool never calls Kubernetes."""
from __future__ import annotations

import argparse
import hashlib
import jsonschema
import json
import re
import subprocess

from .common import ROOT, authorize, canonical_sha, fetch_object, platform, quality_gate, read_json, read_yaml, require_image, validate, write_json
from .render import render_workloads


def workload(intent: dict) -> str:
    validate(intent, "workload-release-v1")
    definitions = read_json("config/image-groups.json")["groups"]
    group = intent["image_group"]
    if group not in definitions:
        raise ValueError("Unknown image group")
    if intent["source_repository"] != definitions[group]["source_repository"]:
        raise ValueError("Image owner mismatch")
    authorize("app" if intent["source_repository"] == "chiendz11/MaintAI" else "automation", intent["source_repository"])
    require_image(intent["image"], group)
    state = read_json("state/production/workloads.json")
    targets = definitions[group]["runtimes"]
    declared = intent["config_schema_sha256"]
    if set(declared) != set(targets):
        raise ValueError("Image must declare every runtime config schema in its image group")
    for name in targets:
        raw = (ROOT / f"contracts/runtime-config/{name}-2.0.0.schema.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != declared[name]:
            raise ValueError("Producer config schema differs from reviewed GitOps schema")
    if group in {"automation", "training", "mlflow"}:
        state[group]["image"] = intent["image"]
        state[group]["source_sha"] = intent["source_sha"]
        if group == "mlflow":
            state[group]["source_repository"] = intent["source_repository"]
            state[group]["publisher_workflow"] = definitions[group]["publisher_workflow"]
        if intent.get("runtime_configs"):
            raise ValueError("Use reviewed platform config for batch/platform image groups")
    else:
        if set(intent.get("runtime_configs", {})) - set(targets):
            raise ValueError("Config target outside the image owner's runtime group")
        for name in targets:
            value = state["components"][name]
            value.update(image=intent["image"], source_sha=intent["source_sha"])
            if name in intent.get("runtime_configs", {}):
                incoming = intent["runtime_configs"][name]
                original = read_yaml(f"workloads/{name}/config.yaml")["data"]
                if name in {"frontend", "simulator-ui"}:
                    original = json.loads(original["runtime-config.json"])
                if set(incoming) != set(original):
                    raise ValueError("Config keys must match the reviewed runtime schema exactly")
                if any(re.search(r"PASSWORD|TOKEN|PRIVATE_KEY|API_KEY|DATABASE_URL|SECRET", key) for key in incoming):
                    raise ValueError("Runtime config must not contain secret values")
                if any(re.search(r"://[^/\s]+@", item) for item in incoming.values()):
                    raise ValueError("Credentials must not be embedded in config URLs")
                schema = read_json(f"contracts/runtime-config/{name}-2.0.0.schema.json")
                jsonschema.Draft202012Validator(schema).validate(incoming)
                value["runtime_config"] = incoming
            if "enable" in intent:
                value["enabled"] = intent["enable"]
    write_json("state/production/workloads.json", state)
    render_workloads()
    from .platform import render_platform_runtimes
    render_platform_runtimes()
    return intent["change_id"]


def model(intent: dict) -> str:
    validate(intent, "model-release-v1")
    authorize("model")
    p = platform()
    result = json.loads(fetch_object(intent["model_result_object"], {p["storage"]["artifacts"]}))
    if canonical_sha(result) != canonical_sha(intent["model_result"]):
        raise ValueError("Dispatched result differs from immutable evaluation output")
    quality_gate(result)
    require_image(result["training_image"], "training", p)
    for ref in result["artifacts"].values():
        fetch_object(ref, {p["storage"]["artifacts"]})
    report = json.loads(fetch_object(result["evaluation_report"], {p["storage"]["artifacts"]}))
    if canonical_sha(report) != canonical_sha(result["evaluation"]):
        raise ValueError("Evaluation report does not match model result")
    metadata = json.loads(fetch_object(result["artifacts"]["metadata"], {p["storage"]["artifacts"]}))
    reference = json.loads(fetch_object(result["artifacts"]["drift_reference"], {p["storage"]["artifacts"]}))
    if metadata.get("model_version") != result["model_version"] or reference.get("model_version") != result["model_version"]:
        raise ValueError("Model metadata/reference version mismatch")
    reference_dataset = reference.get("reference_dataset_version", reference.get("dataset_version"))
    if reference_dataset != result["dataset_version"]:
        raise ValueError("Reference dataset version does not match model result")
    write_json("state/production/model.json", {"schema_version":"1.0.0","status":"configured", **{key:result[key] for key in ["release_id","model_version","dataset_version","artifacts","evaluation","source_sha","training_image","mlflow_run_id"]}, "model_result_object": intent["model_result_object"]})
    render_workloads()
    from .platform import render_platform_runtimes
    render_platform_runtimes()
    return intent["change_id"]


def recover(intent: dict) -> str:
    validate(intent, "recovery-v1")
    authorize("recovery")
    sha = intent["gitops_commit"]
    # A remote actor cannot inject a Git path or shell command.
    subprocess.run(["git", "merge-base", "--is-ancestor", sha, "origin/main"], cwd=ROOT, check=True)
    path = "state/production/model.json" if intent["scope"] == "model" else "state/production/workloads.json"
    prior = json.loads(subprocess.check_output(["git","show",f"{sha}:{path}"],cwd=ROOT))
    if intent["scope"] == "model":
        if prior.get("status") != "configured":
            raise ValueError("Recovery target has no configured model")
        p = platform()
        for ref in prior["artifacts"].values():
            fetch_object(ref,{p["storage"]["artifacts"]})
        write_json(path, prior)
    else:
        name = intent.get("component")
        current = read_json(path)
        if name not in current["components"] or name not in prior["components"]:
            raise ValueError("Recovery requires a known runtime component")
        restored = prior["components"][name]
        require_image(restored.get("image"),read_json("config/components.json")["components"][name]["image_group"])
        current["components"][name] = restored
        write_json(path,current)
    render_workloads()
    from .platform import render_platform_runtimes
    render_platform_runtimes()
    return intent["change_id"]


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("kind",choices=["workload","model","recovery"])
    parser.add_argument("--intent",required=True)
    args=parser.parse_args()
    intent=json.loads(open(args.intent).read())
    change_id={"workload":workload,"model":model,"recovery":recover}[args.kind](intent)
    print(json.dumps({"change_id":change_id,"kind":args.kind}))

if __name__ == "__main__":
    main()
