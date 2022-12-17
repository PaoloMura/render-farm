import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('JobTable')
s3 = boto3.client('s3', region_name='us-east-1')
sqs = boto3.resource('sqs', region_name='us-east-1')
queue = sqs.get_queue_by_name(QueueName='JobQueue')

JOB_SIZE = 3
bucket_name = 'render-files-bucket'


def validate_input(filename, start_frame, end_frame):
    if len(filename) < 7 or filename[-6:] != '.blend':
        return {
            'statusCode': 400,
            'body': 'Bad Request: File must be a Blender .blend file.'
        }
    elif not start_frame.isnumeric() or not end_frame.isnumeric():
        return {
            'statusCode': 400,
            'body': 'Bad Request: Start and end frames must be integers.'
        }
    elif int(start_frame) > int(end_frame):
        return {
            'statusCode': 400,
            'body': 'Bad Request: Start frame must be less than end frame.'
        }
    else:
        return None


def file_in_s3(filename):
    keys = s3.list_objects_v2(Bucket=bucket_name, Prefix=filename)
    return 'Contents' in keys


def split_job(filename, start_frame, end_frame):
    n_frames = int(end_frame) - int(start_frame) + 1
    n_jobs = n_frames // JOB_SIZE
    jobs = []
    for i in range(n_jobs):
        s = i * JOB_SIZE + 1
        e = s + JOB_SIZE - 1
        job = {'type': 'render', 'file': filename, 'start': str(s), 'end': str(e)}
        jobs.append(job)
    if n_frames % JOB_SIZE > 0:
        s = n_frames - (n_frames % JOB_SIZE) + 1
        job = {'type': 'render', 'file': filename, 'start': str(s), 'end': str(end_frame)}
        jobs.append(job)
    return jobs


def submit_render_job(filename, start_frame, end_frame):
    # Check that the file is actually in S3
    if not file_in_s3(filename):
        return {
            'statusCode': 500,
            'body': 'Internal Server Error: Blender file not found in S3.'
        }

    # Split job into batch jobs
    jobs = split_job(filename, start_frame, end_frame)
    batches = dict()

    # Send jobs to workers via SQS queue
    for job in jobs:
        queue.send_message(MessageBody=json.dumps(job))
        batches[job['start'] + '-' + job['end']] = 'Processing'

    # Upload a job spec to DynamoDB
    response = table.put_item(
        Item={
            'file': filename,
            'range': start_frame + '-' + end_frame,
            'job_status': 'Waiting',
            'batches': batches
        }
    )

    # Return the status
    return {
        'statusCode': 200,
        'body': f'Submitted render job at time {time.time()}.'
    }


def get_status(query_result):
    if query_result['job_status'] == 'Finished':
        return {
            'statusCode': 200,
            'body': 'Sequencing complete: MP4 file ready in S3'
        }
    batches = query_result['batches']
    complete_batches = sum([1 if status == 'Complete' else 0 for status in batches.values()])
    percent_render = (complete_batches / len(batches)) * 100
    return {
        'statusCode': 200,
        'body': '%d/%d batches rendered (%.2f%%)' % (complete_batches, len(batches), percent_render)
    }


def lambda_handler(event, context):
    # Extract the request data
    filename = str(event['file'])
    start_frame = str(event['start'])
    end_frame = str(event['end'])

    # Validate the input
    result = validate_input(filename, start_frame, end_frame)
    if result != None:
        return result

    # Check to see if the given file is being processed
    response = table.get_item(Key={'file': filename})
    if not 'Item' in response:
        result = submit_render_job(filename, start_frame, end_frame)
    else:
        result = get_status(response['Item'])
    return result
