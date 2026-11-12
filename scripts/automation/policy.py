"""Future PR checks. Initial authoring does not execute this module."""
from __future__ import annotations

import hashlib
import json
import re

import yaml
from .common import ROOT, DIGEST_IMAGE, read_json, validate
from .render import activation_gate
from .kafka_contracts import verify_kafka_contracts


def main() -> None:
    mlflow = read_json("config/image-groups.json")["groups"]["mlflow"]
    if (mlflow["source_repository"] != "chiendz11/MaintAI"
        or mlflow.get("publisher_workflow") != "maintai-publish.yml"
        or mlflow["dockerfile"] != "ml-service/mlflow/Dockerfile"
        or mlflow["build_context"] != "ml-service/mlflow"
        or set(mlflow.get("signature_annotations", [])) != {"git_sha", "image_group", "source_repository"}):
        raise ValueError("MLflow must use the reviewed app-owned signed publisher")
    verify_kafka_contracts()
    locks=read_json("versions/contracts.lock.json")["sha256"]
    for relative,digest in locks.items():
        if hashlib.sha256((ROOT/"contracts"/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError("Published contract hash changed without a reviewed version/lock update")
    for path in ROOT.rglob("*.yaml"):
        if ".git" in path.parts:continue
        for resource in yaml.safe_load_all(path.read_text()):
            if not isinstance(resource,dict):continue
            if resource.get("kind")=="Secret":raise ValueError("Secret values must not be committed")
            if resource.get("kind")=="Namespace" and "platform/namespaces" not in str(path):raise ValueError("Duplicate namespace owner")
    protocols=read_json("config/protocols.json")
    state=read_json("state/production/workloads.json")
    for name,value in state["components"].items():
        activation_gate(name,value)
        if value["enabled"]:
            resource = yaml.safe_load((ROOT/f"workloads/{name}/workload.yaml").read_text())
            pod = resource["spec"]["jobTemplate"]["spec"]["template"]["spec"] if resource["kind"] == "CronJob" else resource["spec"]["template"]["spec"]
            if pod["containers"][0]["image"] != value["image"]:
                raise ValueError("Manifest image differs from reviewed desired-state lock")
            if any(not DIGEST_IMAGE.fullmatch(container.get("image", "")) for container in pod.get("initContainers", [])):
                raise ValueError("Enabled init containers require real image digests")
        config=value["runtime_config"]
        schema=read_json(f"contracts/runtime-config/{name}-2.0.0.schema.json")
        import jsonschema
        jsonschema.Draft202012Validator(schema).validate(config)
        if value["enabled"] and not DIGEST_IMAGE.fullmatch(value.get("image") or ""):raise ValueError("Enabled workload has an unpinned image")
    if state["mlflow"]["enabled"] and not DIGEST_IMAGE.fullmatch(state["mlflow"].get("image") or ""):raise ValueError("MLflow must have a digest")
    for group in ["automation","training"]:
        if state[group].get("image") and not DIGEST_IMAGE.fullmatch(state[group]["image"]):raise ValueError("Batch image must have a digest")
    p=read_json("state/production/platform.json")
    if p.get("status")=="configured":validate({k:v for k,v in p.items() if k!="status"},"platform-contract-v2")
    print("Source policy passed; this does not validate Terraform, Kubernetes runtime, application code or model quality.")

if __name__=="__main__":main()
