from __future__ import annotations

import argparse
import os
import re
import subprocess
from .common import authorize, platform, read_json, require_image, validate


def expected_publisher(intent, groups):
    """Resolve trust from reviewed image-group ownership, never from caller-chosen workflow."""
    group = intent["image_group"]
    definition = groups.get(group)
    if definition is None or intent["source_repository"] != definition["source_repository"]:
        raise ValueError("Image producer ownership mismatch")
    source = definition["source_repository"]
    if source not in {"chiendz11/MaintAI", "chiendz11/MaintAI-gitops"}:
        raise ValueError("Untrusted image producer repository")
    kind = "app" if source == "chiendz11/MaintAI" else "automation"
    default_workflow = "maintai-publish.yml" if kind == "app" else "publish-platform-images.yml"
    workflow = definition.get("publisher_workflow", default_workflow)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*\.ya?ml", workflow):
        raise ValueError("Invalid reviewed publisher workflow")
    values = {"git_sha": intent["source_sha"], "image_group": group,
              "source_repository": source}
    names = definition.get("signature_annotations", ["git_sha", "image_group"])
    if not {"git_sha", "image_group"} <= set(names) or set(names) - set(values):
        raise ValueError("Invalid signature annotation policy")
    annotations = [part for name in names for part in ("-a", name + "=" + values[name])]
    identity = f'https://github.com/{source}/.github/workflows/{workflow}@refs/heads/main'
    return kind, identity, annotations


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--intent",required=True);args=parser.parse_args()
    intent=read_json(args.intent)
    validate(intent,"workload-release-v1")
    groups=read_json("config/image-groups.json")["groups"]
    group=intent["image_group"]
    kind, identity, annotations = expected_publisher(intent, groups)
    authorize(kind, intent["source_repository"])
    require_image(intent["image"],group)
    registry=intent["image"].split("/",1)[0]
    password=subprocess.check_output(["aws","ecr","get-login-password"],text=True)
    subprocess.run(["docker","login","--username","AWS","--password-stdin",registry],input=password,text=True,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(["cosign","verify","--certificate-identity",identity,"--certificate-oidc-issuer","https://token.actions.githubusercontent.com",*annotations,intent["image"]],check=True,stdout=subprocess.DEVNULL)

if __name__=="__main__":main()
