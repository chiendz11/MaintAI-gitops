from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import ROOT, authorize, canonical_sha, read_json, read_yaml, validate, write_json, write_yaml
from .render import render_workloads


def render_platform_runtimes() -> None:
    p=read_json("state/production/platform.json")
    if p.get("status")!="configured":return
    state=read_json("state/production/workloads.json")
    access=read_json("config/access.json")
    for name in ["app","simulator"]:
        path=f"environments/production/edge/{name}.yaml"
        value=read_yaml(path)
        host=("app." if name=="app" else "simulator.")+p["ingress"]["domain"]
        value["spec"]["rules"][0]["host"]=host
        annotations=value["metadata"]["annotations"]
        annotations["external-dns.alpha.kubernetes.io/hostname"]=host
        annotations["alb.ingress.kubernetes.io/certificate-arn"]=p["ingress"]["certificate_arn"] or "REPLACE_WITH_CERTIFICATE_ARN"
        if name=="simulator":annotations["alb.ingress.kubernetes.io/inbound-cidrs"]=",".join(access["simulator_operator_cidrs"]) or "REPLACE_WITH_OPERATOR_CIDRS"
        write_yaml(path,value)
    edge=[]
    enabled=state["components"]
    if enabled["frontend"]["enabled"] and enabled["business-api"]["enabled"]:edge.append("app.yaml")
    if enabled["simulator-ui"]["enabled"] and enabled["sensor"]["enabled"]:
        if not access["simulator_operator_cidrs"] or "0.0.0.0/0" in access["simulator_operator_cidrs"]:
            raise ValueError("Simulator management ingress needs explicit operator CIDRs")
        edge.append("simulator.yaml")
    if edge and not p["ingress"]["certificate_arn"]:raise ValueError("A validated ACM certificate is required")
    k=read_yaml("environments/production/edge/kustomization.yaml");k["resources"]=edge;write_yaml("environments/production/edge/kustomization.yaml",k)
    if state["mlflow"]["image"]:
        value=read_yaml("platform/mlops/mlflow.yaml")
        value["spec"]["template"]["spec"]["containers"][0]["image"]=state["mlflow"]["image"]
        args=value["spec"]["template"]["spec"]["containers"][0]["args"]
        args[args.index("--artifacts-destination")+1]=f's3://{p["storage"]["artifacts"]}/mlflow'
        write_yaml("platform/mlops/mlflow.yaml",value)
    sa=read_yaml("platform/mlops/serviceaccount.yaml")
    sa["metadata"]["annotations"]={"eks.amazonaws.com/role-arn":p["roles"]["mlflow"]}
    write_yaml("platform/mlops/serviceaccount.yaml",sa)
    observation=read_json("config/observability.json")
    monitor=read_yaml("platform/observability/kustomization.yaml")
    if observation["enabled"]:
        from .common import DIGEST_IMAGE
        if not DIGEST_IMAGE.fullmatch(observation.get("pushgateway_image") or ""):
            raise ValueError("Pin Pushgateway to a verified digest before enabling observability")
        value=read_yaml("platform/observability/pushgateway.yaml")
        value["spec"]["template"]["spec"]["containers"][0]["image"]=observation["pushgateway_image"]
        write_yaml("platform/observability/pushgateway.yaml",value)
        monitor["resources"]=read_json("config/observability-resources.json")["resources"]
    else:monitor["resources"]=[]
    write_yaml("platform/observability/kustomization.yaml",monitor)
    # Training image is taken only from reviewed desired state, never from an untrusted event.
    training=read_json("config/training.json")
    context={"schema_version":"1.0.0","training_image":state["training"]["image"],"training_code_sha":state["training"]["source_sha"],"datasets_bucket":p["storage"]["datasets"],"artifacts_bucket":p["storage"]["artifacts"],"kms_key_arn":p["kms_key_arn"],"ledger_table":p["training"]["ledger_table"],"gitops_repository":"chiendz11/MaintAI-gitops","quality_gate_version":training["quality_gate"]["version"],"mlflow_tracking_uri":"http://mlflow.maintai:5000"}
    context["context_sha256"]=canonical_sha(context)
    write_json("state/production/training-context.json",context)
    value=read_yaml("environments/production/training/context.yaml")
    value["data"]["context.json"]=json.dumps(context,sort_keys=True)
    write_yaml("environments/production/training/context.yaml",value)
    workflow=read_yaml("environments/production/training/workflow-template.yaml")
    for template in workflow["spec"]["templates"]:
        if "container" in template:
            group="training" if template["name"]=="train" else "automation"
            if state[group]["image"]:template["container"]["image"]=state[group]["image"]
    write_yaml("environments/production/training/workflow-template.yaml",workflow)
    source=read_yaml("environments/production/training/eventsource.yaml")
    source["spec"]["sqs"]["approved-datasets"]["queue"]=p["training"]["queue_name"]
    source["spec"]["sqs"]["approved-datasets"]["region"]=p["aws"]["region"]
    write_yaml("environments/production/training/eventsource.yaml",source)
    accounts=read_yaml("environments/production/training/accounts.yaml")
    # accounts.yaml is one Kubernetes List so each service account stays explicit.
    for account in accounts["items"]:
        role="sqs-events" if account["metadata"]["name"]=="sqs-eventsource" else "training"
        if account["metadata"]["name"]=="dataset-sensor":continue
        account["metadata"].setdefault("annotations",{})["eks.amazonaws.com/role-arn"]=p["roles"][role]
    write_yaml("environments/production/training/accounts.yaml",accounts)
    root=read_yaml("environments/production/training/kustomization.yaml")
    root["resources"]=read_json("config/training-resources.json")["resources"] if training["enabled"] else []
    if training["enabled"]:
        if not state["training"]["entrypoint_reviewed"] or not state["training"]["image"] or not state["automation"]["image"] or not state["mlflow"]["enabled"]:
            raise ValueError("Review training entrypoint, pin training/automation images and enable MLflow first")
    write_yaml("environments/production/training/kustomization.yaml",root)
    # The active selector is in its own directory to avoid a self-referential Kustomization.
    write_yaml("environments/production/mlops/kustomization.yaml",{"apiVersion":"kustomize.config.k8s.io/v1beta1","kind":"Kustomization","resources":["../../../platform/mlops"] if state["mlflow"]["enabled"] else []})


def reconcile(value: dict) -> str:
    validate(value,"platform-contract-v2")
    authorize("platform")
    write_json("state/production/platform.json",{**value,"status":"configured"})
    p=value
    state=read_json("state/production/workloads.json")
    access=read_json("config/access.json")
    replacements={"REPLACE_WITH_RAW_BUCKET":p["storage"]["raw"],"REPLACE_WITH_ARTIFACTS_BUCKET":p["storage"]["artifacts"],"REPLACE_WITH_KNOWLEDGE_BUCKET":p["storage"]["knowledge"],"REPLACE_WITH_SIMULATOR_ORIGIN":"https://simulator."+p["ingress"]["domain"]}
    if access["oidc_issuer"]:replacements["REPLACE_WITH_OIDC_ISSUER"]=access["oidc_issuer"]
    if access["simulator_public_client_id"]:replacements["REPLACE_WITH_PUBLIC_SIMULATOR_CLIENT_ID"]=access["simulator_public_client_id"]
    if access["business_public_client_id"]:replacements["REPLACE_WITH_PUBLIC_BUSINESS_CLIENT_ID"]=access["business_public_client_id"]
    for release in state["components"].values():
        release["runtime_config"]={key:replacements.get(item,item) for key,item in release.get("runtime_config",{}).items()}
    write_json("state/production/workloads.json",state)
    # Secret values remain in AWS. Only reference ARNs enter manifests.
    for path in (ROOT/"platform/secrets").glob("*.yaml"):
        obj=read_yaml(path)
        if obj.get("kind")=="ClusterSecretStore":obj["spec"]["provider"]["aws"]["region"]=p["aws"]["region"]
        elif obj.get("kind")=="ExternalSecret":
            name=obj["metadata"]["name"]
            arn=p["database"]["master_secret_arn"] if name=="postgres-bootstrap-admin" else p["secrets"][name]
            for entry in obj["spec"]["data"]:entry["remoteRef"]["key"]=arn
        write_yaml(path,obj)
    settings=read_json("config/applications.json")
    for path in (ROOT/"applications/addons").glob("*.yaml"):
        app=read_yaml(path)
        name=app["metadata"]["name"].removeprefix("maintai-")
        values=app["spec"]["source"]["helm"]["valuesObject"]
        role={"external-secrets":"external-secrets","external-dns":"external-dns","load-balancer":"load-balancer"}.get(name)
        if role:values.setdefault("serviceAccount",{}).setdefault("annotations",{})["eks.amazonaws.com/role-arn"]=p["roles"][role]
        if name=="external-dns":values["domainFilters"]=[p["ingress"]["domain"]]
        if name=="load-balancer":values.update(clusterName=p["cluster"]["name"],region=p["aws"]["region"],vpcId=p["cluster"]["vpc_id"])
        write_yaml(path,app)
    root=read_yaml("applications/kustomization.yaml");root["resources"]=["project.yaml"]+settings["children"]
    write_yaml("applications/kustomization.yaml",root)
    for path in list((ROOT/"applications").glob("*.yaml"))+list((ROOT/"applications/addons").glob("*.yaml")):
        app=read_yaml(path)
        if app.get("kind")!="Application":continue
        if settings["automatic_sync"]:app["spec"]["syncPolicy"]["automated"]={"prune":True,"selfHeal":True}
        else:app["spec"]["syncPolicy"].pop("automated",None)
        write_yaml(path,app)
    render_workloads()
    render_platform_runtimes()
    return "platform-"+canonical_sha(value)[:32]


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--contract",required=True);args=parser.parse_args()
    print(json.dumps({"change_id":reconcile(json.loads(Path(args.contract).read_text()))}))

if __name__=="__main__":main()
