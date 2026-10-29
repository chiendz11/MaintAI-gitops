"""Local release identities are separate from frozen production contracts."""

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ALIAS = re.compile(r"maintai-local/[a-z0-9-]+:image-([0-9a-f]{64})")
DIGEST = re.compile(r"[^\s]+@sha256:[0-9a-f]{64}")


def load(name):
    return json.loads((ROOT / name).read_text())


def identity(receipt, component):
    Draft202012Validator(load("contracts/local/image-receipt-v1.schema.json")).validate(receipt)
    if receipt.get("component") != component or receipt.get("schema_version") != "1.0.0":
        raise ValueError("Receipt runtime identity differs")
    image = receipt.get("image", "")
    match = LOCAL_ALIAS.fullmatch(image)
    if not match or receipt.get("image_id") != "sha256:" + match[1]:
        raise ValueError("Local image must be bound to its actual Docker image ID")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", receipt.get("source_git_sha", "")):
        raise ValueError("Image requires a genuine source revision")
    for key in ("source_snapshot_sha256", "dockerfile_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", receipt.get(key, "")):
            raise ValueError("Image source/build identity is incomplete")
    if type(receipt.get("source_dirty")) is not bool:
        raise ValueError("Dirty source status must be explicit")
    return image


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assert_local(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / "environments/local"):
        raise ValueError("Local release writer cannot modify production paths")
    return path
