"""Copy this directory to .release/ only after app entrypoints are implemented."""
import hashlib,json,os,re,subprocess,tempfile,sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
group=os.environ['IMAGE_GROUP'];sha=os.environ['SOURCE_SHA']
components=json.loads((root/'.release/components.json').read_text())
if group not in components or not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('Invalid image group or source SHA')
if group == 'mlflow':
    # Reuse the canonical app publisher, including base pins/smoke/signature policy.
    subprocess.run([sys.executable,str(root/'ml-service/mlflow/release.py'),'publish'],cwd=root,check=True)
    raise SystemExit(0)
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!=sha:raise ValueError('Source SHA mismatch')
component=components[group];dockerfile=root/component['dockerfile']
if not dockerfile.exists():raise ValueError('App Dockerfile not implemented')
source=dockerfile.read_text()
if not any(line.strip().upper().startswith('FROM ') for line in source.splitlines()):raise ValueError('Placeholder Dockerfile cannot be published')
repository=json.loads(os.environ['IMAGE_REPOSITORIES_JSON'])[group]
if not re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9/_-]+',repository):raise ValueError('Unexpected ECR repository')
password=subprocess.check_output(['aws','ecr','get-login-password'],text=True)
subprocess.run(['docker','login','--username','AWS','--password-stdin',repository.split('/')[0]],input=password,text=True,check=True,stdout=subprocess.DEVNULL)
lookup=subprocess.run(['aws','ecr','describe-images','--repository-name',repository.split('/',1)[1],'--image-ids','imageTag=git-'+sha,'--output','json'],text=True,capture_output=True)
if lookup.returncode==0:
    image=repository+'@'+json.loads(lookup.stdout)['imageDetails'][0]['imageDigest']
elif 'ImageNotFoundException' not in lookup.stderr:
    raise ValueError('Unable to resolve existing immutable image')
else:
    with tempfile.TemporaryDirectory() as d:
        metadata=Path(d)/'image.json'
        subprocess.run(['docker','buildx','build','--platform','linux/amd64','--file',str(dockerfile),'--tag',repository+':git-'+sha,'--push','--metadata-file',str(metadata),'.'],cwd=root,check=True)
        image=repository+'@'+json.loads(metadata.read_text())['containerimage.digest']
subprocess.run(['cosign','sign','--yes','-a','git_sha='+sha,'-a','image_group='+group,image],check=True)
schemas={name:hashlib.sha256((root/f'.release/contracts/{name}-2.0.0.schema.json').read_bytes()).hexdigest() for name in component['runtimes']}
intent={'schema_version':'1.0.0','change_id':group+'-'+sha[:24],'source_repository':'chiendz11/MaintAI','source_sha':sha,'architecture_revision':'maintai-1.3.1+simulator-ui.1','image_group':group,'image':image,'runtime_config_version':'2.0.0','config_schema_sha256':schemas}
Path(os.environ['RUNNER_TEMP'],'workload-intent.json').write_text(json.dumps(intent))
