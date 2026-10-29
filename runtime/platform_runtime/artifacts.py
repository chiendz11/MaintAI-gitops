from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import boto3

FILES = {"model":"model.joblib","preprocessor":"preprocessor.joblib","drift_reference":"drift_reference.json","metadata":"metadata.json"}


def download(ref: dict, target: Path) -> None:
    if not ref.get("version_id") or ref["version_id"] == "null":
        raise ValueError("A versioned S3 object is required")
    expected=ref.get("sha256", "")
    if len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("Invalid SHA-256")
    response=boto3.client("s3").get_object(Bucket=ref["bucket"],Key=ref["key"],VersionId=ref["version_id"])
    digest=hashlib.sha256()
    with target.open("wb") as out:
        for chunk in response["Body"].iter_chunks(chunk_size=1024*1024):
            if chunk:
                digest.update(chunk);out.write(chunk)
        out.flush();os.fsync(out.fileno())
    if digest.hexdigest()!=expected:
        target.unlink(missing_ok=True)
        raise ValueError("Artifact checksum mismatch")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("kind",choices=["model","dataset"])
    parser.add_argument("--lock",required=True)
    parser.add_argument("--directory",required=True)
    args=parser.parse_args()
    lock=json.loads(Path(args.lock).read_text())
    directory=Path(args.directory)
    directory.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory,prefix=".download-") as temp:
        temp=Path(temp)
        if args.kind=="dataset":
            if not lock.get("object"):raise ValueError("Sensor dataset lock is unconfigured")
            download(lock["object"],temp/"ai4i2020.csv")
            os.replace(temp/"ai4i2020.csv",directory/"ai4i2020.csv")
            return
        if lock.get("status")!="configured" or set(lock.get("artifacts",{}))!=set(FILES):
            raise ValueError("A complete atomic model/preprocessor/reference/metadata release is required")
        for role,filename in FILES.items():download(lock["artifacts"][role],temp/filename)
        metadata=json.loads((temp/"metadata.json").read_text())
        reference=json.loads((temp/"drift_reference.json").read_text())
        if metadata.get("model_version")!=lock["model_version"] or reference.get("model_version")!=lock["model_version"]:
            raise ValueError("Model and reference version mismatch")
        if reference.get("reference_dataset_version",reference.get("dataset_version"))!=lock["dataset_version"]:
            raise ValueError("Reference dataset version mismatch")
        for filename in FILES.values():os.replace(temp/filename,directory/filename)
        (directory/"release.json").write_text(json.dumps(lock,sort_keys=True))

if __name__=="__main__":main()
