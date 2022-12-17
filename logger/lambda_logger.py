import boto3
from botocore.exceptions import ClientError

s3 = boto3.client('s3', region_name='us-east-1')
bucket_name = 'worker-logging-bucket'


def lambda_handler(event, context):
    for record in event['Records']:
        payload = record['Body']
        if payload['type'] == 'error':
            # Leave the error message in the queue
            pass
        elif payload['type'] == 'log':
            # Upload the log to S3
            id = payload['id']
            message = payload['message']
            filename = str(id) + '.csv'
            try:
                s3.download_file(bucket_name, filename, '/temp/' + filename)
                with open('/temp/' + filename, 'a') as f:
                    f.write(message)
            except ClientError as e:
                with open('/temp/' + filename, 'w') as f:
                    f.write(message)
            s3.upload_file('/temp/' + filename, bucket_name, filename)
