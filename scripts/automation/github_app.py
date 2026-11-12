from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen

import jwt


def installation_token() -> str:
    issued=int(time.time())
    encoded=jwt.encode({"iat":issued-30,"exp":issued+540,"iss":os.environ["GITHUB_APP_ID"]},os.environ["GITHUB_APP_PRIVATE_KEY"],algorithm="RS256")
    url=f'https://api.github.com/app/installations/{int(os.environ["GITHUB_APP_INSTALLATION_ID"])}/access_tokens'
    repository=os.environ["GITHUB_TARGET_REPOSITORY"].split("/",1)[1]
    payload=json.dumps({"repositories":[repository]}).encode()
    request=Request(url,data=payload,headers={"Authorization":"Bearer "+encoded,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},method="POST")
    with urlopen(request,timeout=30) as response:
        return json.load(response)["token"]

if __name__ == "__main__":
    token=installation_token()
    print("::add-mask::"+token)
    with open(os.environ["GITHUB_ENV"],"a") as out:
        out.write("GH_TOKEN="+token+"\n")
