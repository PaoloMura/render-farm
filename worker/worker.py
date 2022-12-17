import boto3
import botocore.exceptions
import json
import os
import random
import shutil
import subprocess
import time

# BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_PATH = "blender"
MY_ID = random.randint(0, 10000)

s3 = boto3.client('s3', region_name='us-east-1')
sqs = boto3.resource('sqs', region_name='us-east-1')
job_queue = sqs.get_queue_by_name(QueueName='JobQueue')
logging_queue = sqs.get_queue_by_name(QueueName='LoggingQueue')
sqs_client = boto3.client('sqs', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
job_table = dynamodb.Table('JobTable')

render_bucket_name = 'render-files-bucket'
png_bucket_name = 'png-files-bucket'


def render(blender_file: str, start: str, end: str):
    """Renders the blender file animation, using the given frame range."""
    output_path = blender_file[:-6] + '/' + blender_file[:-6]
    command = [BLENDER_PATH, '-b', blender_file, '-E', 'CYCLES', '-o', output_path, '-s', start, '-e', end, '-a']
    subprocess.run(command, check=True)


def sequence(filename: str):
    """
    Sequences the png output images into an mp4 video file.

    filename: the name of the blender file without the .blend extension
    """
    framerate = '24'
    resolution = '1920x1080'
    file_template = filename + '/' + filename + '%04d.png'
    output_file = filename + '.mp4'
    command = ['ffmpeg',
               '-r', framerate,
               '-s', resolution,
               '-i', file_template,
               output_file]
    subprocess.run(command, check=True)


def cleanup(filename: str, directory: str):
    try:
        if filename:
            os.remove(filename)
        if directory:
            shutil.rmtree(directory)
    except Exception as e:
        body = {'id': MY_ID, 'type': 'error', 'state': 'Clean up', 'message': e}
        logging_queue.send_message(MessageBody=json.dumps(body))


def render_job(blender_file: str, start: str, end: str) -> (bool, str):
    """Completes a render job."""
    log = ""

    # Download the .blend file
    print('Downloading .blend file...')
    try:
        s3.download_file(render_bucket_name, blender_file, blender_file)
    except botocore.exceptions.ClientError as e:
        body = {'id': MY_ID, 'type': 'error', 'state': 'Downloading blend file', 'message': e}
        logging_queue.send_message(MessageBody=json.dumps(body))
        cleanup(blender_file, "")
        return False
    log += str(time.time()) + f",Downloaded file {blender_file} for render\n"

    # Render the animation
    print('Rendering animation...')
    directory = blender_file[:-6] + '/'
    os.mkdir(directory)
    try:
        render(blender_file, start, end)
    except Exception as e:
        body = {'id': MY_ID, 'type': 'error', 'state': 'Rendering animation', 'message': e}
        logging_queue.send_message(MessageBody=json.dumps(body))
        cleanup(blender_file, directory)
        return False
    log += str(time.time()) + f",Rendered animation {blender_file} frames {start} to {end}\n"

    # Upload output frames to S3
    print('Uploading frames to S3...')
    directory = blender_file[:-6] + '/'
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        try:
            s3.upload_file(filepath, png_bucket_name, filename)
        except botocore.exceptions.ClientError as e:
            body = {'id': MY_ID, 'type': 'error', 'state': 'Uploading frames to S3', 'message': e}
            logging_queue.send_message(MessageBody=json.dumps(body))
            cleanup(blender_file, directory)
            return False
    log += str(time.time()) + f",Uploaded {blender_file} frames {start} to {end}\n"

    # Update batch status in the DynamoDB table
    batch = "#" + start + '_' + end
    response = job_table.update_item(
        Key={'file': blender_file},
        UpdateExpression=f'set batches.{batch} = :status',
        ExpressionAttributeNames={batch: start + '-' + end},
        ExpressionAttributeValues={':status': 'Complete'},
        ReturnValues='ALL_NEW'
    )

    # Check if the whole job is complete
    if not ('Processing' in response['Attributes']['batches'].values()):
        # Update the job status
        job_table.update_item(
            Key={'file': blender_file},
            UpdateExpression=f'set job_status = :status',
            ExpressionAttributeValues={
                ':status': 'Processing'
            }
        )

        # Send a sequence job to SQS
        job_range = response['Attributes']['range'].split('-')
        job = {'type': 'sequence', 'file': blender_file, 'start': job_range[0], 'end': job_range[1]}
        job_queue.send_message(MessageBody=json.dumps(job))
        log += str(time.time()) + f",Submitted {blender_file} sequence job\n"

    # Cleanup directory
    print('Cleaning up...')
    cleanup(blender_file, directory)
    return True, log


def sequence_job(blender_file: str, start: str, end: str) -> (bool, str):
    """Completes a sequence job."""
    log = ""

    # Download the output files
    print('Downloading frames...')
    directory = blender_file[:-6] + '/'
    os.mkdir(directory)
    for i in range(int(start), int(end) + 1):
        try:
            filename = blender_file[:-6] + "%04d.png" % i
            s3.download_file(png_bucket_name, filename, filename)
            shutil.move(filename, directory + filename)
        except botocore.exceptions.ClientError as e:
            body = {'id': MY_ID, 'type': 'error', 'state': 'Downloading frames from S3', 'message': e}
            logging_queue.send_message(MessageBody=json.dumps(body))
            cleanup("", directory)
            return False
    log += str(time.time()) + f",Downloaded {blender_file} frames for sequencing\n"

    # Sequence the images
    print('Sequencing images...')
    try:
        sequence(blender_file[:-6])
    except Exception as e:
        body = {'id': MY_ID, 'type': 'error', 'state': 'Sequencing images', 'message': e}
        logging_queue.send_message(MessageBody=json.dumps(body))
        cleanup(blender_file[:-6] + '.mp4', directory)
        return False
    log += str(time.time()) + f",Sequenced {blender_file}\n"

    # Upload mp4 file to S3
    print('Uploading mp4 files...')
    mp4_file = blender_file[:-6] + '.mp4'
    try:
        s3.upload_file(mp4_file, render_bucket_name, mp4_file)
    except botocore.exceptions.ClientError as e:
        body = {'id': MY_ID, 'type': 'error', 'state': 'Uploading mp4 file to S3', 'message': e}
        logging_queue.send_message(MessageBody=json.dumps(body))
        cleanup(mp4_file, directory)
        return False
    log += str(time.time()) + f",Uploaded {blender_file} mp4\n"

    # Cleanup local directory
    print('Cleaning up...')
    cleanup(mp4_file, directory)
    return True, log


def main():
    print('Starting worker node...')
    body = {'id': MY_ID, 'type': 'log', 'success': True, 'message': 'Started running'}
    logging_queue.send_message(MessageBody=json.dumps(body))

    running = True
    while running:
        message = job_queue.receive_messages(MaxNumberOfMessages=1)
        if message:
            job = json.loads(message[0].body)
            print('Received job: ')
            print(job)
            receipt_handle = message[0].receipt_handle
            filename = job['file']
            start_frame = job['start']
            end_frame = job['end']
            process_job = render_job if job['type'] == 'render' else sequence_job
            success, log = process_job(filename, start_frame, end_frame)
            body = {'id': MY_ID, 'type': 'log', 'success': success, 'message': log}
            logging_queue.send_message(MessageBody=json.dumps(body))
            if success:
                sqs_client.delete_message(QueueUrl=job_queue.url, ReceiptHandle=receipt_handle)
                print('Completed job: ')
                print(job)
        else:
            time.sleep(10)


if __name__ == '__main__':
    main()
