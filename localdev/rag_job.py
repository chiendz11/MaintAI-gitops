"""Generate one explicit knowledge-owner Job, without applying a workload."""

import argparse
import json
import uuid
from pathlib import Path

import yaml

from .common import identity, load
from .workloads import metadata


def preparation_job(receipt):
    image = identity(receipt, "rag-service")
    lock = load("config/local/app-source.lock.json")
    if (
        receipt.get("imported_context") != "k3d-maintai-local"
        or receipt["source_git_sha"] != lock["source_git_sha"]
    ):
        raise ValueError(
            "Knowledge preparation needs the imported, pinned application image"
        )
    if receipt["source_dirty"]:
        raise ValueError("Commit and rebuild the selected knowledge preparation source")
    settings = load("config/local/rag-runtime.json")
    env = settings["environment"].copy()
    # Preparation can download the selected embedding. Generation Pod is offline.
    env["MODEL_LOCAL_FILES_ONLY"] = "false"
    env = {key: value for key, value in env.items() if not key.startswith("GROQ_")}
    environment = [{"name": key, "value": value} for key, value in sorted(env.items())]
    environment.append(
        {
            "name": "DATABASE_URL",
            "valueFrom": {
                "secretKeyRef": {"name": "local-knowledge-owner", "key": "url"}
            },
        }
    )
    name = "local-rag-prepare-" + uuid.uuid4().hex[:12]
    meta = metadata(name)
    meta["labels"]["maintai.io/owner"] = "explicit-local-operator"
    meta["annotations"] = {
        "maintai.io/source-sha": receipt["source_git_sha"],
        "maintai.io/image-id": receipt["image_id"],
        "maintai.io/knowledge-manifest-sha256": lock["files"][
            "rag-service/knowledge-demo.json"
        ],
        "maintai.io/embedding-revision": env["EMBEDDING_REVISION"],
    }
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": meta,
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 1800,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "metadata": {"labels": meta["labels"]},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "runAsGroup": 10001,
                        "fsGroup": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "knowledge-owner",
                            "image": image,
                            "imagePullPolicy": "Never",
                            "command": ["python", "-m", "ingestion.prepare_demo"],
                            "env": environment,
                            "securityContext": {
                                "readOnlyRootFilesystem": True,
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "250m", "memory": "512Mi"},
                                "limits": {"cpu": "2", "memory": "3Gi"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "embedding-cache",
                                    "mountPath": env["SENTENCE_TRANSFORMERS_HOME"],
                                },
                                {"name": "tmp", "mountPath": "/tmp"},
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "embedding-cache",
                            "persistentVolumeClaim": {
                                "claimName": settings["cache_claim"]
                            },
                        },
                        {"name": "tmp", "emptyDir": {}},
                    ],
                },
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = preparation_job(json.loads(args.receipt.read_text()))
    args.output.write_text(yaml.safe_dump(document, sort_keys=False))
    print("Prepared explicit knowledge-owner Job; no cluster was contacted.")


if __name__ == "__main__":
    main()
