"""GitOps-owned automation image only. MLflow publication lives in MaintAI."""
from __future__ import annotations
import argparse,json,os,re,subprocess,tempfile
from pathlib import Path
from .common import ROOT,read_json,DIGEST_IMAGE


def main():
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['automation'],required=True);args=p.parse_args()
    group=args.group;sha=os.environ['SOURCE_SHA']
    if not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('Invalid source SHA')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=sha:raise ValueError('Checked-out source differs from claimed source')
    repository=json.loads(os.environ['IMAGE_REPOSITORIES_JSON'])[group]
    if not re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9/_-]+',repository):raise ValueError('Unexpected ECR repository')
    base_name='PYTHON_BASE_IMAGE'
    base=read_json('versions/build-images.json')[base_name.lower()]
    if not DIGEST_IMAGE.fullmatch(base or ""):raise ValueError('Pin a real base image digest before publication')
    password=subprocess.check_output(['aws','ecr','get-login-password'],text=True)
    subprocess.run(['docker','login','--username','AWS','--password-stdin',repository.split('/')[0]],input=password,text=True,check=True,stdout=subprocess.DEVNULL)
    lookup=subprocess.run(['aws','ecr','describe-images','--repository-name',repository.split('/',1)[1],'--image-ids','imageTag=git-'+sha,'--output','json'],text=True,capture_output=True)
    if lookup.returncode==0:
        digest=json.loads(lookup.stdout)['imageDetails'][0]['imageDigest']
        image=repository+'@'+digest
    elif 'ImageNotFoundException' not in lookup.stderr:
        raise ValueError('Unable to resolve immutable existing image tag')
    else:
        image=build_image(group, repository, sha, base_name, base)
    subprocess.run(['cosign','sign','--yes','-a','git_sha='+sha,'-a','image_group='+group,image],check=True)
    intent={'schema_version':'1.0.0','change_id':group+'-'+sha[:24],'source_repository':'chiendz11/MaintAI-gitops','source_sha':sha,'architecture_revision':'maintai-1.3.1+simulator-ui.1','image_group':group,'image':image,'runtime_config_version':'2.0.0','config_schema_sha256':{}}
    Path(os.environ['RUNNER_TEMP'],'workload-intent.json').write_text(json.dumps(intent))


def build_image(group, repository, sha, base_name, base):
    with tempfile.TemporaryDirectory() as directory:
        metadata=Path(directory)/'metadata.json'
        tag=repository+':git-'+sha
        if group != 'automation':raise ValueError('MLflow images must be built by the MaintAI publisher')
        subprocess.run(['docker','buildx','build','--platform','linux/amd64','--build-arg',base_name+'='+base,'--push','--tag',tag,'--file','runtime/Dockerfile','--metadata-file',str(metadata),'.'],cwd=ROOT,check=True)
        digest=json.loads(metadata.read_text())['containerimage.digest']
        image=repository+'@'+digest
    return image

if __name__=='__main__':main()
