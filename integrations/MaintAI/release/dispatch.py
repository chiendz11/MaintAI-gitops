import json,os,subprocess,sys
from pathlib import Path
from urllib.request import Request,urlopen
from github_app import installation_token

intent_path=Path(os.environ['RUNNER_TEMP'],'workload-intent.json')
if json.loads(intent_path.read_text()).get('image_group') == 'mlflow':
    root=Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable,str(root/'ml-service/mlflow/release.py'),'dispatch'],cwd=root,check=True)
    raise SystemExit(0)
repo=os.environ['GITHUB_TARGET_REPOSITORY'];token=installation_token()
request=Request(f'https://api.github.com/repos/{repo}/actions/workflows/workload-release.yml/dispatches',data=json.dumps({'ref':'main','inputs':{'intent':Path(os.environ['RUNNER_TEMP'],'workload-intent.json').read_text()}}).encode(),headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},method='POST')
with urlopen(request,timeout=30) as r:
    if r.status!=204:raise ValueError('Dispatch was not acknowledged')
print('Workload intent dispatched; no automatic merge or deployment.')
