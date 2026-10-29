from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = "maintai-1.3.1+simulator-ui.1"
DIGEST_IMAGE = re.compile(r"^[a-z0-9][a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def read_json(path: str | Path) -> Any:
    path = Path(path)
    return json.loads((path if path.is_absolute() else ROOT / path).read_text())


def write_json(path: str | Path, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_yaml(path: str | Path) -> dict:
    return yaml.safe_load((ROOT / path).read_text())


def write_yaml(path: str | Path, value: dict) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True))


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(value: Any, schema_name: str) -> None:
    schema = read_json(f"contracts/{schema_name}.schema.json")
    errors = list(jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(value))
    if errors:
        # Do not echo payload contents or schema error repr: an invalid input may contain secrets.
        location = "/".join(str(x) for x in errors[0].absolute_path) or "root"
        raise ValueError(f"Contract {schema_name} rejected at {location}")


def platform() -> dict:
    value = read_json("state/production/platform.json")
    if value.get("status") != "configured":
        raise ValueError("Platform handoff is not configured")
    return value


def require_image(image: str, group: str, p: dict | None = None) -> None:
    p = p or platform()
    if not DIGEST_IMAGE.fullmatch(image or ""):
        raise ValueError("A real repository@sha256 digest is required")
    if image.split("@", 1)[0] != p["images"].get(group):
        raise ValueError(f"Image repository is not allow-listed for {group}")


def require_object(ref: dict, allowed_buckets: set[str]) -> None:
    if ref.get("bucket") not in allowed_buckets:
        raise ValueError("S3 bucket outside platform allow-list")
    if not ref.get("version_id") or ref["version_id"] == "null":
        raise ValueError("An immutable S3 VersionId is required")
    if not SHA.fullmatch(ref.get("sha256", "")):
        raise ValueError("An object SHA-256 is required; ETag is not a checksum contract")
    key = ref.get("key", "")
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError("Invalid S3 object key")


def fetch_object(ref: dict, allowed_buckets: set[str]) -> bytes:
    import boto3
    require_object(ref, allowed_buckets)
    response = boto3.client("s3").get_object(Bucket=ref["bucket"], Key=ref["key"], VersionId=ref["version_id"])
    data = response["Body"].read()
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("S3 object checksum mismatch")
    return data


def authorize(kind: str, source_repository: str | None = None) -> None:
    actor = os.environ.get("DISPATCH_ACTOR", "")
    expected = os.environ.get(f"{kind.upper()}_ALLOWED_ACTOR", "")
    if not actor or not expected or actor != expected:
        raise ValueError(f"Untrusted {kind} publisher identity")
    if source_repository is not None and source_repository not in {"chiendz11/MaintAI", "chiendz11/MaintAI-gitops"}:
        raise ValueError("Untrusted producer repository")


def quality_gate(result: dict) -> None:
    validate(result, "model-result-v1")
    gate = read_json("config/training.json")["quality_gate"]
    scores = result["evaluation"]["candidate"]
    for group in ["candidate", "baseline", "rule_based"]:
        if any(not math.isfinite(float(value)) for value in result["evaluation"][group].values()):
            raise ValueError("Evaluation metrics must be finite")
    for key in ["false_alarms_per_1000_valid", "human_review_ratio"]:
        if not math.isfinite(float(result["evaluation"][key])):
            raise ValueError("Evaluation metrics must be finite")
    if result["quality_gate_version"] != gate["version"]:
        raise ValueError("Quality-gate version mismatch")
    if scores["recall_failure"] < gate["recall_failure_min"] or scores["precision_failure"] < gate["precision_failure_min"]:
        raise ValueError("Candidate failed the offline recall/precision gate")
    if result["evaluation"]["threshold_source"] != "validation":
        raise ValueError("Threshold must be selected on validation, never on test")
