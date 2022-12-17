# SNAPSHOT v3.0 (Full System with EKS Worker Cluster)

## Requirements

_(Create the following resources via the AWS Web Console.
Where unspecified, use default configurations.)_

### Setup
It is assumed that you have
* [kubectl command line tool](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html)
* [AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* [AWS credentials configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html#cli-configure-quickstart-config)
* IAM role with Admin permissions (LabRole if using the Learner Lab)

### Policies and Roles (if using the learner lab, skip this and replace any usages of the following with LabRole):
* A policy called `ServerPolicy`, using the `server/serverPolicy.JSON` rules
* A policy called `WatcherPolicy`, using the `watcher/watcherPolicy.JSON` rules
* A policy called `LoggerPolicy` using the  `logger/loggerPolicy.JSON` rules
* A role called `serverRole` with `ServerPolicy` attached
* A role called `watcherRole` with `WatcherPolicy` attached
* A role called `loggerRole` with `LoggerPolicy` attached

### Resources:
* Three S3 buckets named 
  * `render-files-bucket`
  * `png-files-bucket`
  * `worker-logging-bucket`
* A DynamoDB database
  * name: `JobTable`
  * partition key: `file`
* An SQS queue
  * standard queue type
  * name: `JobQueue`
  * visibility timeout: `20 minutes`
  * receive message wait time: `20 seconds`
* Another SQS queue
  * standard queue type
  * name: `LoggingQueue`
* A Lambda function
  * name: `server`
  * runtime: `Python 3.9`
  * permissions - existing role: `serverRole`
* Another Lambda function
  * name: `watcher`
  * runtime: `Python 3.9`
  * permissions - existing role: `watcherRole`
* Yet another Lambda function
  * name: `logger`
  * runtime: `python 3.9`
  * permissions - existing role: `loggerRole`


## Set up the Lambda Functions

Use `server/server.py` as the script for the `server` Lambda function.

Use `watcher/watcher.py` as the script for the `watcher` Lambda function.

Add a trigger for the `watcher` function as follows:
* source: `S3`
* bucket: `render-files-bucket`
* suffix: `.mp4`

Use `logger/logger.py` as the script for the `logger` Lambda function.

Add a trigger for the `logger` function as follows:
* source: `SQS`

[comment]: <> (To do: add instructions here)


## Create an ECR repository

Use the following:
* visibility: `Private`
* name: `worker-repository`
* scan on push enabled

## Create the Docker image

Navigate to the `worker` directory.
```shell
cd /path/to/CCW22-55/worker
```

Replace the AWI credentials in the Dockerfile with your own.

Authenticate Docker to your default registry.
```shell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
```

Build the Docker image and push it to ECR.
```shell
docker build -t worker-repository .

docker tag worker-repository:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/worker-repository:latest

docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/worker-repository:latest
```


## Create an EKS Cluster

1. Create a public and private VPC with subnets using CloudFormation

Go to CloudFormation and create a new stack with new resources (standard).

Under Amazon S3 URL, paste:
https://s3.us-west-2.amazonaws.com/amazon-eks/cloudformation/2020-10-29/amazon-eks-vpc-private-subnets.yaml

Stack name: `worker-stack`

CIDR range for VPC should be:
* VPC: 192.168.0.0/16

Once it has been created, select it in the Console and click on the Outputs tab.

Record the VpcId and SubnetIds.

2. Create an EKS cluster using eksctl with a cluster.yaml file

Modify the `CW22-55/cluster/cluster.yaml` file with the following (values from above):
* VPC ID
* Subnet IDs

Run the following to create the cluster:
```shell
cd /path/to/CW22-55/cluster

eksctl create cluster -f cluster.yaml --kubeconfig=~/.kube/config
```

Confirm communication with your cluster:
```shell
kubectl get svc
```

If this doesn't work, try adding configuration details:
```shell
aws eks --region us-east-1 update-kubeconfig --name worker-cluster
```


## Run a Deployment on the Cluster

Modify the `CW22-55/cluster/deployment.yaml` file so that the image refers to the URI of the Docker image you created above.
You should be able to just replace the account number with your own and update the version to match.
Alternatively you can find the URI by going to the AWS Web Console ECR page and selecting the worker-cluster image and the latest version.

Create a deployment.
```shell
kubectl apply -f deployment.yaml
```

Deploy a metrics server.
```shell
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl get deployment metrics-server -n kube-system
```
Wait until it is in a ready state.

Create a horizontal pod autoscaler for the worker cluster.
```shell
kubectl autoscale deployment worker-deployment --cpu-percent=50 --min=1 --max=10

kubectl get hpa
```


## Run a Job

1. Start running the client-side HPA logger.

(This step is purely for performance analysis, feel free to skip it.
Or run `kubectl get hpa` periodically yourself to see the state of HPA.)
```shell
cd /path/to/client

python hpa_logger.py
```

2. Submit a job to the Server Lambda Function.

Upload a Blender file to the `render-files-bucket` S3 bucket.
(e.g. the `rolling_ball.blend` file from `CW22-55/client`).

Open the `server` Lambda function in AWS Web Console.

Create a test called `SubmitRenderJob` with the following contents:
```json
{
  "file": "rolling_ball.blend",
  "start": "1",
  "end": "17"
}
```

Run the test to submit a render job to the cluster.

To see the current state of the cluster, there are several options:
* Re-run the `server` Lambda Function; this will give a high level status check of the job.
* Open the `LoggingQueue` SQS queue via the AWS Web Console.
Poll for messages here to receive any error messages from the cluster.
* Refresh the `worker-logging-bucket` S3 bucket to access logs from each pod on the cluster.

Once the job is complete, refresh the `render-files-bucket` S3 bucket to retrieve the finished `.mp4` file. 


## Cleaning Up

Delete the cluster
```shell
cd /path/to/CW22-55/cluster

kubectl delete deployment/worker-deployment horizontalpodautoscaler.autoscaling/worker-deployment

eksctl delete cluster -f cluster.yaml
```
In AWS Web Console, go to the EC2 service.
Under the Auto Scaling tab, delete all autoscaling groups.

In the AWS Web Console, delete the resources you created above:
* S3
  * `render-files-bucket`
  * `png-files-bucket`
  * `worker-logging-bucket`
* SQS
  * `JobQueue`
  * `LoggingQueue`
* Lambda
  * `server`
  * `watcher`
  * `logger`
* DynamoDB
  * `JobTable`
* ECR
  * `worker-repository`
* Policies
  * ServerPolicy
  * WatcherPolicy
  * LoggerPolicy
* Roles
  * serverRole
  * watcherRole
  * loggerRole
* Subnets
  * worker-stack-PrivateSubnet01
  * worker-stack-PrivateSubnet02
  * worker-stack-PublicSubnet01
  * worker-stack-PublicSubnet02
* VPC
* Cloudformation stacks
  * worker-stack

---

# SNAPSHOT V2.0 (Single Worker, Full Distribution System)

## Requirements

_(Create the following resources via the AWS Web Console.
Where unspecified, use default configurations.)_

### Setup
It is assumed that you have
* AWS CLI
* AWS credentials stored locally (e.g. in `~/.aws/credentials`)
* Docker Desktop

### Roles (if using the learner lab, replace any usages of the following with LabRole):
* A policy called `ServerPolicy`, using the `server/serverPolicy.JSON` rules
* A role called `serverRole` with `serverPolicy` attached
* A policy called `WatcherPolicy`, using the `watcher/watcherPolicy.JSON rules
* A role called `watcherRole` with `WatcherPolicy` attached

### Resources:
* Two S3 buckets named `render-files-bucket` and `png-files-bucket`
* A DynamoDB database
  * name: `JobTable`
  * partition key: `file`
* An SQS queue
  * standard queue type
  * name: `JobQueue`
  * visibility timeout: `20 minutes`
  * receive message wait time: `20 seconds` 
* A Lambda function
  * name: `server`
  * runtime: `Python 3.9`
  * permissions - existing role: `serverRole`
* Another Lambda function
  * name: `watcher`
  * runtime: `Python 3.9`
  * permissions - existing role: `watcherRole`
* An EC2 instance
  * name: `worker`
  * AMI: `Amazon Linux`
  * type: `m5.large`
  * architecture: `Arm`


## Set up the Lambda Functions

Use `server/server.py` as the script for the `server` Lambda function.

Use `watcher/watcher.py` as the script for the `watcher` Lambda function.

Add a trigger for the `watcher` function as follows:
* source: `S3`
* bucket: `render-files-bucket`
* suffix: `.mp4`

## Create an ECR repository

Use the following:
* visibility: `Private`
* name: `worker-repository`
* scan on push enabled

## Create the Docker image

Navigate to the `worker` directory.
```shell
cd /path/to/CCW22-55/worker
```

Replace the AWI credentials in the Dockerfile with your own.

Authenticate Docker to your default registry.
```shell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
```

Build the Docker image and push it to ECR.
```shell
docker build -t worker-repository .

docker tag worker-repository:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/worker-repository:latest

docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/worker-repository:latest
```

## Set up the EC2 instance

SSH into the `worker` EC2 instance you created above.

Configure access to AWS CLI.
```shell
aws configure
```

Install Docker.
```shell
sudo yum update -y

sudo amazon-linux-extras install docker

sudo service docker start

sudo usermod -a -G docker ec2-user
```

Exit and then SSH back in for this to take effect.

Authenticate Docker to your default registry.
```shell
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
```

Pull the Docker image.
```shell
docker pull <account_id>.dkr.ecr.us-east-1.amazonaws.com/worker-repository:latest
```


## Running the System

SSH into your `worker` EC2 instance.

Run the Docker container.
```shell
docker images

docker run <image_id>
```

Upload a Blender file to the `render-files-bucket` S3 bucket.
(e.g. the `rolling_ball.blend` file from `CW22-55/client`).

Open the `server` Lambda function in AWS Web Console.

Create a test called `SubmitRenderJob` with the following contents:
```json
{
  "file": "rolling_ball.blend",
  "start": "1",
  "end": "6"
}
```

Run the test.

_On a single EC2 instance, this is likely to take around 18 minutes (3 minutes per frame)._


---

# SNAPSHOT V1.0 (Single EC2 Worker Node + S3)

Replace the AWI credentials in the Dockerfile with your own.

Build the Docker image and push it to the Docker Hub registry.
```shell
cd /path/to/CW22-55/worker

docker build -t <username>/render-worker:v1 .

docker push <username>/render-worker:v1
```

Start an EC2 instance.
* AMI: ami-0692e7f470db96692 (has Docker and x86 architecture)
* instance type: m5.large (64-bit quad core CPU with SSE2 support, 8 GB RAM, graphics card with 2 GB RAM and OpenGL 4.3)
* minimum security group rules: SSH from your IP && HTTP from your IP

SSH into the instance, pull the image and run a container.
```shell
ssh -i /path/to/<your_key_pair.pem> ec2-user@<instance_public_ip>

docker pull <username>/render-worker:v1

docker images

docker run [-d] -p 80:5000 <image_id>
```

On a terminal on your local client machine, run commands from the client script.
```shell
cd /path/to/CW22-55/client

# Get the state of the job queue
python client.py GET <instance_public_ip>

# Submit a render command
python client.py POST <instance_public_ip> render <filename>.blend <start_frame> <end_frame>

# Submit a sequence command
python client.py POST <instance_public_ip> sequence <filename>.blend <start_frame> <end_frame>
```
