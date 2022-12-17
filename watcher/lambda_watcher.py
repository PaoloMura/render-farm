import boto3
import botocore
import urllib

dynamodb = boto3.resource('dynamodb')
job_table = dynamodb.Table('JobTable')
s3 = boto3.client('s3', region_name='us-east-1')

png_bucket_name = 'png-files-bucket'


def lambda_handler(event, context):
    mp4_file = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    # Update job status in the DynamoDB table
    file = mp4_file[:-4]
    blender_file = file + '.blend'
    response = job_table.update_item(
        Key={'file': blender_file},
        UpdateExpression='set job_status = :status',
        ExpressionAttributeValues={
            ':status': 'Complete'
        },
        ReturnValues='ALL_NEW'
    )

    # Delete the .png files from S3
    job_range = response['Attributes']['range'].split('-')
    frames = {'Objects': []}
    for i in range(int(job_range[0]), int(job_range[1]) + 1):
        filename = file + '%04d.png' % i
        obj = {'Key': filename}
        frames['Objects'].append(obj)
    try:
        s3.delete_objects(Bucket=png_bucket_name, Delete=frames)
    except botocore.exceptions.ClientError as e:
        raise Exception(f"Failed to delete frames: {e}")
    return f'Attempted to delete {frames}'
