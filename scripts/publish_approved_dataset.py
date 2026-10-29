"""Publish an explicitly approved dataset manifest; never called by sensor/drift."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import boto3
from automation.common import validate,canonical_sha

p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--bucket',required=True);p.add_argument('--key',required=True);p.add_argument('--kms-key-arn',required=True);p.add_argument('--execute',action='store_true');args=p.parse_args()
manifest=json.loads(Path(args.manifest).read_text());validate(manifest,'dataset-manifest-v1')
if not args.key.startswith('datasets/approved/') or not args.key.endswith('.manifest.json'):raise ValueError('Use an approved manifest key')
if not args.execute:raise SystemExit('No dataset published. Explicit approval and --execute are required.')
raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
r=boto3.client('s3').put_object(Bucket=args.bucket,Key=args.key,Body=raw,ContentType='application/json',ServerSideEncryption='aws:kms',SSEKMSKeyId=args.kms_key_arn)
if not r.get('VersionId') or r['VersionId']=='null':raise ValueError('Dataset bucket versioning must be enabled')
print(json.dumps({'bucket':args.bucket,'key':args.key,'version_id':r['VersionId'],'sha256':hashlib.sha256(raw).hexdigest()}))
