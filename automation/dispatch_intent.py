import argparse,json,os
from pathlib import Path
from urllib.request import Request,urlopen
from .github_app import installation_token

p=argparse.ArgumentParser();p.add_argument('--file',required=True);p.add_argument('--workflow',default='workload-release.yml');args=p.parse_args()
if args.workflow not in ['workload-release.yml','model-release.yml','platform-reconcile.yml']:raise ValueError('Unknown receiver')
repo=os.environ['GITHUB_TARGET_REPOSITORY'];token=installation_token()
request=Request(f'https://api.github.com/repos/{repo}/actions/workflows/{args.workflow}/dispatches',data=json.dumps({'ref':'main','inputs':{'intent':Path(args.file).read_text()}}).encode(),headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},method='POST')
with urlopen(request,timeout=30) as response:
    if response.status!=204:raise ValueError('Dispatch not acknowledged')
print('Intent dispatched; PR creation, merge and deployment remain separate stages.')
