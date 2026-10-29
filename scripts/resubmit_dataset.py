"""Operator recovery: enqueue the exact approved S3 version again, without creating new data."""
import argparse,json
from urllib.parse import quote_plus
import boto3

p=argparse.ArgumentParser();p.add_argument('--bucket',required=True);p.add_argument('--key',required=True);p.add_argument('--version-id',required=True);p.add_argument('--queue-url',required=True);p.add_argument('--retry-release',action='store_true');p.add_argument('--execute',action='store_true');args=p.parse_args()
if not args.key.startswith('datasets/approved/') or not args.key.endswith('.manifest.json') or args.version_id=='null':raise ValueError('An exact approved manifest version is required')
if not args.execute:raise SystemExit('No message sent. Use --execute only for an explicitly requested recovery.')
body={'Records':[{'eventName':'ObjectCreated:Put','s3':{'bucket':{'name':args.bucket},'object':{'key':quote_plus(args.key,safe='/'),'versionId':args.version_id}}}],'maintaiRetryRelease':args.retry_release}
boto3.client('sqs').send_message(QueueUrl=args.queue_url,MessageBody=json.dumps(body))
print('Recovery event enqueued; follow Workflow, ledger, release PR and deployment separately.')
