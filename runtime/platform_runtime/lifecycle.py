"""Approved-dataset batch orchestration with durable retry state.

SQS acknowledgement only means Argo received an event. RELEASE_DISPATCHED records
an acknowledged GitHub dispatch, not a merged PR, deployed model, or champion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import unquote_plus
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import ClientError

from automation.common import canonical_sha, fetch_object, quality_gate, require_image, validate
from automation.github_app import installation_token


def normalize(body: dict) -> list[dict]:
    if body.get("Event")=="s3:TestEvent":return []
    records=[]
    seen=set()
    for record in body.get("Records",[]):
        if not record.get("eventName", "").startswith("ObjectCreated:"):continue
        source=record["s3"]
        key=unquote_plus(source["object"]["key"])
        if not key.startswith("datasets/approved/") or not key.endswith(".manifest.json"):continue
        version=source["object"].get("versionId")
        if not version or version=="null":raise ValueError("Approved manifest notification must include S3 VersionId")
        ref={"bucket":source["bucket"]["name"],"key":key,"version_id":version}
        ref["slot"]=canonical_sha(ref)[:24]
        if ref["slot"] not in seen:
            ref["retry_release"] = body.get("maintaiRetryRelease", False) is True
            records.append(ref)
            seen.add(ref["slot"])
    if not records and body.get("Records") is None and body.get("Event")!="s3:TestEvent":
        raise ValueError("Expected an S3 Records envelope; ETag-only dispatch is unsupported")
    return records


def table(context: dict):return boto3.resource("dynamodb").Table(context["ledger_table"])


def outputs(directory: Path, train: bool, publish: bool) -> None:
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"train-required.txt").write_text(str(train).lower())
    (directory/"publish-required.txt").write_text(str(publish).lower())


def prepare(record: dict, release: dict, owner: str, directory: Path, retry_release: bool) -> None:
    outputs(directory,False,False)
    if record["bucket"]!=release["datasets_bucket"]:raise ValueError("Dataset bucket outside approved platform")
    if not record["key"].startswith("datasets/approved/") or not record["key"].endswith(".manifest.json"):raise ValueError("Only approved manifests trigger training")
    response=boto3.client("s3").get_object(Bucket=record["bucket"],Key=record["key"],VersionId=record["version_id"])
    raw=response["Body"].read()
    manifest=json.loads(raw)
    validate(manifest,"dataset-manifest-v1")
    if manifest["training_image"]!=release["training_image"] or manifest["training_code_sha"]!=release["training_code_sha"]:
        raise ValueError("Manifest targets another training image/code revision")
    if manifest["training_context_sha256"]!=release["context_sha256"]:
        raise ValueError("Dataset approval must bind the exact training context")
    data=fetch_object(manifest["data"],{release["datasets_bucket"]})
    protocol=fetch_object(manifest["evaluation_protocol"],{release["datasets_bucket"]})
    training_id=canonical_sha({"manifest_bucket":record["bucket"],"manifest_key":record["key"],"manifest_version_id":record["version_id"],"manifest_sha256":hashlib.sha256(raw).hexdigest(),"context_sha256":release["context_sha256"]})
    context={**release,"training_id":training_id,"workflow_owner":owner,"dataset_version":manifest["dataset_version"],"manifest_object":{**record,"sha256":hashlib.sha256(raw).hexdigest()},"data_object":manifest["data"],"evaluation_protocol":manifest["evaluation_protocol"],"approved_by":manifest["approved_by"],"approved_at":manifest["approved_at"]}
    ledger=table(context)
    existing=ledger.get_item(Key={"training_id":training_id},ConsistentRead=True).get("Item",{})
    if existing.get("status")=="RELEASE_DISPATCHED" and not retry_release:return
    now=int(time.time())
    if existing.get("owner")!=owner and int(existing.get("lease_until",0))>now:return
    try:
        ledger.update_item(Key={"training_id":training_id},UpdateExpression="SET #s=:running, #o=:owner, lease_until=:lease, updated_at=:now, manifest_json=:manifest",ConditionExpression="attribute_not_exists(lease_until) OR lease_until < :now OR #o=:owner",ExpressionAttributeNames={"#s":"status","#o":"owner"},ExpressionAttributeValues={":running":"RUNNING",":owner":owner,":lease":now+10800,":now":now,":manifest":json.dumps(record,sort_keys=True)})
    except ClientError as exc:
        if exc.response["Error"]["Code"]=="ConditionalCheckFailedException":return
        raise
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"context.json").write_text(json.dumps(context,sort_keys=True))
    (directory/"data.csv").write_bytes(data)
    (directory/"evaluation-protocol.json").write_bytes(protocol)
    # A successful prior training result can be reused after a release-dispatch failure.
    result_ref=json.loads(existing["model_result_json"]) if existing.get("model_result_json") else None
    if result_ref:
        result=fetch_object(result_ref,{release["artifacts_bucket"]})
        (directory/"model-result.json").write_bytes(result)
        (directory/"model-result-object.json").write_text(json.dumps(result_ref,sort_keys=True))
        outputs(directory,False,True)
    else:outputs(directory,True,True)


def save_result(directory: Path) -> None:
    context=json.loads((directory/"context.json").read_text())
    result=json.loads((directory/"model-result.json").read_text())
    quality_gate(result)
    if result["dataset_version"]!=context["dataset_version"] or result["source_sha"]!=context["training_code_sha"] or result["training_image"]!=context["training_image"]:
        raise ValueError("Training result provenance mismatch")
    if result["evaluation"]["protocol_sha256"]!=context["evaluation_protocol"]["sha256"]:
        raise ValueError("Evaluation protocol differs from approved dataset protocol")
    for ref in result["artifacts"].values():fetch_object(ref,{context["artifacts_bucket"]})
    raw=json.dumps(result,sort_keys=True,separators=(",",":")).encode()
    digest=hashlib.sha256(raw).hexdigest()
    key=f'training/{context["training_id"]}/model-result-{digest}.json'
    response=boto3.client("s3").put_object(Bucket=context["artifacts_bucket"],Key=key,Body=raw,ContentType="application/json",ServerSideEncryption="aws:kms",SSEKMSKeyId=context["kms_key_arn"])
    version=response.get("VersionId")
    if not version or version=="null":raise ValueError("Model result storage must have versioning enabled")
    ref={"bucket":context["artifacts_bucket"],"key":key,"version_id":version,"sha256":digest}
    table(context).update_item(Key={"training_id":context["training_id"]},UpdateExpression="SET #s=:trained, model_result_json=:result, updated_at=:now",ConditionExpression="#o=:owner",ExpressionAttributeNames={"#s":"status","#o":"owner"},ExpressionAttributeValues={":trained":"TRAINED",":result":json.dumps(ref,sort_keys=True),":now":int(time.time()),":owner":context["workflow_owner"]})
    (directory/"model-result-object.json").write_text(json.dumps(ref,sort_keys=True))


def dispatch(directory: Path) -> None:
    context=json.loads((directory/"context.json").read_text())
    result=json.loads((directory/"model-result.json").read_text())
    quality_gate(result)
    ref=json.loads((directory/"model-result-object.json").read_text())
    if canonical_sha(json.loads(fetch_object(ref,{context["artifacts_bucket"]})))!=canonical_sha(result):raise ValueError("Result checksum/provenance mismatch")
    intent={"schema_version":"1.0.0","change_id":"model-"+context["training_id"][:32],"model_result":result,"model_result_object":ref}
    repository=context["gitops_repository"]
    os.environ["GITHUB_TARGET_REPOSITORY"]=repository
    token=installation_token()
    request=Request(f"https://api.github.com/repos/{repository}/actions/workflows/model-release.yml/dispatches",data=json.dumps({"ref":"main","inputs":{"intent":json.dumps(intent,separators=(",",":"))}}).encode(),headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},method="POST")
    with urlopen(request,timeout=30) as response:
        if response.status!=204:raise ValueError("Model-release dispatch was not acknowledged")
    table(context).update_item(Key={"training_id":context["training_id"]},UpdateExpression="SET #s=:dispatched, lease_until=:zero, updated_at=:now, release_change_id=:change",ConditionExpression="#o=:owner",ExpressionAttributeNames={"#s":"status","#o":"owner"},ExpressionAttributeValues={":dispatched":"RELEASE_DISPATCHED",":zero":0,":now":int(time.time()),":change":intent["change_id"],":owner":context["workflow_owner"]})


def release_failed(workspace: Path, owner: str) -> None:
    for path in workspace.glob("*/context.json"):
        context=json.loads(path.read_text())
        try:
            table(context).update_item(Key={"training_id":context["training_id"]},UpdateExpression="SET #s=:failed, lease_until=:zero, updated_at=:now",ConditionExpression="#o=:owner AND #s <> :dispatched",ExpressionAttributeNames={"#s":"status","#o":"owner"},ExpressionAttributeValues={":failed":"FAILED",":zero":0,":now":int(time.time()),":owner":owner,":dispatched":"RELEASE_DISPATCHED"})
        except ClientError as exc:
            if exc.response["Error"]["Code"]!="ConditionalCheckFailedException":raise


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["normalize","prepare","save-result","dispatch","release-failed"])
    parser.add_argument("--event-body")
    parser.add_argument("--output")
    parser.add_argument("--record")
    parser.add_argument("--context")
    parser.add_argument("--owner")
    parser.add_argument("--directory",default="/workspace")
    parser.add_argument("--retry-release",default="false",choices=["true","false"])
    args=parser.parse_args()
    directory=Path(args.directory)
    if args.command=="normalize":Path(args.output).write_text(json.dumps(normalize(json.loads(args.event_body))))
    elif args.command=="prepare":
        record=json.loads(args.record)
        if not re_slot(record.get("slot","")) or directory.name!=record["slot"]:raise ValueError("Unsafe workspace slot")
        prepare(record,json.loads(Path(args.context).read_text()),args.owner,directory,args.retry_release=="true" or record.get("retry_release",False))
    elif args.command=="save-result":save_result(directory)
    elif args.command=="dispatch":dispatch(directory)
    else:release_failed(directory,args.owner)


def re_slot(value: str) -> bool:
    return len(value)==24 and all(c in "0123456789abcdef" for c in value)

if __name__=="__main__":main()
