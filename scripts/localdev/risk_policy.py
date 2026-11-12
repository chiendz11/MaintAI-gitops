"""Read app-owned policy source and prepare a verified ConfigMap input."""

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .common import load

POLICY_DIRECTORY = Path("processing/config/risk-policies")
POLICY_CONFIGMAP = "processing-risk-policy"
POLICY_MOUNT = "/local/config"


def strict_document(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate risk policy JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Non-finite risk policy JSON number")

    document = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(document, dict):
        raise ValueError("Risk policy metadata must be a JSON object")
    json.dumps(document, allow_nan=False)
    return document


def read_policy(app_root):
    # Import here to avoid a module cycle when checks also validates the selector.
    from .checks import verify_application_source

    if app_root is None:
        raise ValueError("Worker policy preparation requires --app-root")
    app_root = Path(app_root).resolve()
    source = load("config/local/app-source.lock.json")
    selection = load("config/local/risk-policy.lock.json")
    keys = {
        "schema_version",
        "source_repository",
        "source_git_sha",
        "policy_version",
        "path",
        "sha256",
        "policy_sha256",
    }
    if set(selection) != keys or selection["schema_version"] != "1.0.0":
        raise ValueError("Unexpected risk policy selection format")
    if any(not isinstance(selection[key], str) or not selection[key].strip() for key in keys):
        raise ValueError("Risk policy selection values must be non-empty strings")
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", selection[key]) for key in ("sha256", "policy_sha256")
    ):
        raise ValueError("Risk policy selection requires complete SHA256 values")
    if (selection["source_repository"], selection["source_git_sha"]) != (
        source["source_repository"],
        source["source_git_sha"],
    ):
        raise ValueError("Risk policy selection differs from the reviewed app revision")
    verify_application_source(app_root, source)
    directory = (app_root / POLICY_DIRECTORY).resolve()

    def member(name):
        path = (app_root / name).resolve()
        if not path.is_relative_to(directory) or not directory.is_relative_to(app_root):
            raise ValueError("Risk policy source path escapes its app directory")
        relative = path.relative_to(app_root).as_posix()
        if relative not in source["files"]:
            raise ValueError("Risk policy member is absent from the reviewed source lock")
        return path

    manifest = strict_document(member(POLICY_DIRECTORY / "manifest.json").read_bytes())
    if manifest.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported app policy catalog version")
    if selection["policy_version"] not in manifest["policies"]:
        raise ValueError("Selected risk policy version is absent from the app catalog")
    entry = manifest["policies"][selection["policy_version"]]
    if str(POLICY_DIRECTORY / entry["path"]) != selection["path"]:
        raise ValueError("Selected policy path differs from the app catalog")
    schema_bytes = member(POLICY_DIRECTORY / manifest["schema_path"]).read_bytes()
    if hashlib.sha256(schema_bytes).hexdigest() != manifest["schema_sha256"]:
        raise ValueError("Risk policy schema checksum differs")
    raw = member(selection["path"]).read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != selection["sha256"]
        or selection["sha256"] != entry["sha256"]
    ):
        raise ValueError("Risk policy file checksum differs from its selection/catalog")
    document = strict_document(raw)
    schema = strict_document(schema_bytes)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
    thresholds = document["thresholds"]
    if not thresholds["watch"] < thresholds["high"] < thresholds["critical"]:
        raise ValueError("Risk policy thresholds must be strictly increasing")
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    canonical_sha = hashlib.sha256(canonical).hexdigest()
    if (
        document["policy_version"] != selection["policy_version"]
        or canonical_sha != selection["policy_sha256"]
        or canonical_sha != entry["policy_sha256"]
    ):
        raise ValueError("Risk policy version/canonical checksum differs")
    metadata = {
        **selection,
        "usage": entry["usage"],
        "calibration_status": entry["calibration_status"],
    }
    return raw.decode("utf-8"), metadata
