"""Source checks for the local environment, separate from frozen production state."""

import argparse
import ast
import hashlib
import json
import subprocess
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .common import ROOT, load


def verify_application_source(app, lock):
    """Verify both the reviewed Git revision and its selected interface bytes."""
    if lock.get("schema_version") != "1.0.0" or lock.get("source_repository") != "chiendz11/MaintAI":
        raise ValueError("Unexpected application source lock identity")
    sha = lock.get("source_git_sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) or not lock.get("files"):
        raise ValueError("Application source lock requires a real revision and file hashes")
    actual = subprocess.check_output(["git", "-C", str(app), "rev-parse", "HEAD"], text=True).strip()
    if actual != sha:
        raise ValueError("Application checkout HEAD differs from the reviewed source lock")
    for name, expected in lock["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid application source lock entry: " + name)
        if hashlib.sha256((app / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Application interface drift requires review: " + name)


def check(app=None, companion=None):
    for path in (ROOT / "localdev").glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    for filename in ("local-contracts.lock.json", "local-production-baseline.lock.json"):
        for name, expected in load("versions/" + filename)["sha256"].items():
            path = ROOT / "contracts/local" / name if filename == "local-contracts.lock.json" else ROOT / name
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Protected contract/production bytes changed: " + name)
    Draft202012Validator(load("contracts/local/local-profile-v1.schema.json")).validate(load("profiles/local.example.json"))
    if any(value["enabled"] for value in load("profiles/local.example.json")["components"].values()):
        raise ValueError("Example profile must keep workloads disabled")
    topic_config = load("config/local/kafka-topology.json")
    if set(topic_config["topics"]) != {"sensor.readings", "sensor.rejected", "inference.results", "alert.signals"}:
        raise ValueError("Canonical topic set differs")
    if any(value["partitions"] != 12 for value in topic_config["topics"].values()):
        raise ValueError("Local topic topology must preserve the reviewed partition mapping")
    if set(topic_config["topics"]["inference.results"]["reader_schemas"]) != {"1.4.0"}:
        raise ValueError("Local app accepts only native outcome1.4.0")
    for folder in (ROOT / "local", ROOT / "environments/local"):
        for path in folder.rglob("*.yaml"):
            for doc in yaml.safe_load_all(path.read_text()):
                if not isinstance(doc, dict):
                    continue
                if doc.get("kind") == "Secret":
                    raise ValueError("Secret values belong to bootstrap private state")
                ns = doc.get("metadata", {}).get("namespace")
                if ns and ns != "maintai-local":
                    raise ValueError("Local manifest escapes its namespace")
                text = path.read_text()
                if re.search(r"image:\s*[^\n]*:latest\b", text):
                    raise ValueError("Mutable upstream image in local source")
    realm = load("local/platform/maintai-realm.json")
    for client in realm["clients"]:
        if not client.get("publicClient") and not client["secret"].startswith("${"):
            raise ValueError("Keycloak client secret value must not be committed")
    if app:
        verify_application_source(app, load("config/local/app-source.lock.json"))
        from .risk_policy import read_policy
        read_policy(app)
    if companion:
        for left, right in [("config/local/app-source.lock.json", "local/versions/app-source.lock.json"),
                            ("config/local/contract.json", "local/config/contract.json"), ("config/local/runtime-catalog.json", "local/config/runtime-catalog.json"),
                            ("config/local/platform.lock.json", "local/versions/platform.lock.json"), ("config/local/buckets.json", "local/config/buckets.json")]:
            if (ROOT / left).read_bytes() != (companion / right).read_bytes():
                raise ValueError("Local handoff bytes differ: " + left)
    print("Local source policy passed; images, providers, Argo sync and E2E remain separate evidence.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", type=Path)
    parser.add_argument("--infrastructure-root", type=Path)
    args = parser.parse_args()
    check(args.app_root, args.infrastructure_root)


if __name__ == "__main__":
    main()
