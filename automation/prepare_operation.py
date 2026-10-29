"""Prepare a manual operation manifest; this command does not apply anything."""
import argparse
from .common import read_json,read_yaml,write_yaml,require_image,platform

p=argparse.ArgumentParser();p.add_argument('operation',choices=['database-bootstrap','processing','business','drift','knowledge']);args=p.parse_args()
cloud=platform();state=read_json('state/production/workloads.json')
if args.operation=='database-bootstrap':
    image=state['automation']['image'];require_image(image,'automation')
    path='operations/database-bootstrap/job.yaml';job=read_yaml(path);container=job['spec']['template']['spec']['containers'][0];container['image']=image
    for item in container['env']:
        if item['name']=='PGHOST':item['value']=cloud['database']['host']
        if item['name']=='PGVECTOR_VERSION':item['value']=cloud['database']['pgvector_version']
    # ALLOW_DATABASE_BOOTSTRAP remains false; operator must explicitly change it after review.
else:
    runtime={'processing':'processing-worker','business':'business-api','drift':'drift-worker','knowledge':'rag-service'}[args.operation]
    group=read_json('config/components.json')['components'][runtime]['image_group']
    image=state['components'][runtime]['image'];require_image(image,group)
    path=f'operations/migrations/{args.operation}/job.yaml';job=read_yaml(path);job['spec']['template']['spec']['containers'][0]['image']=image
write_yaml(path,job)
print('Manual operation manifest prepared. Nothing was applied; review the entrypoint, credentials and DB state first.')
