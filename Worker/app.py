import json
import requests
import hashlib
import base64
import boto3
import re
import os

def work(buffer, iterations):
    output = hashlib.sha512(buffer).digest()
    for _ in range(iterations - 1):
        output = hashlib.sha512(output).digest()
    return output

def terminate_ec2():
    # Get instance ID
    instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text
    
    # Create EC2 client
    ec2_client = boto3.client('ec2')
    
    # Terminate the instance
    ec2_client.terminate_instances(InstanceIds=[instance_id])
    pass

#global ip
#global dequeue_path
#global complete_path
#global kill_worker_path
#global retryNumber

try:
    with open('/home/ubuntu/files/config', 'r') as f:
        config = f.read()
except:
    with open('C:\git\CloudHasher\Endpoint\config', 'r') as f:
        config = f.read()

region = re.search(r'region\s*=\s*(\S+)', config).group(1)

# Set the AWS region
os.environ['AWS_DEFAULT_REGION'] = region

try:
    with open('/home/ubuntu/files/credentials', 'r') as f:
        aws_credentials = f.read()
except:
    with open('C:\git\CloudHasher\Endpoint\credentials', 'r') as f:
        aws_credentials = f.read()

access_key = re.search(r'aws_access_key_id\s*=\s*(\S+)', aws_credentials).group(1)
secret_key = re.search(r'aws_secret_access_key\s*=\s*(\S+)', aws_credentials).group(1)

# Set AWS credentials and region as environment variables
os.environ['AWS_ACCESS_KEY_ID'] = access_key
os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key


dequeue_path = 'dequeue'
complete_path = 'completed'
kill_worker_path = 'killWorker'

headers = {"Content-Type": "application/json"} 

try:
    with open("/home/ubuntu/files/worker_public_ips.json", "r") as file:
        ips_json = file.read()
except:
    with open("worker_public_ips.json", "r") as file:
        ips_json = file.read()

# Parse the JSON content
ips = json.loads(ips_json)

dequeue_ip = ips["IP"] + ':5000/'

is_running = True
retryNumber = 0

while is_running:
    req_path = 'http://'+dequeue_ip+dequeue_path
    print(req_path)
    response = requests.get(req_path)

    if response.status_code != 200:
        print('got error from endpoint')
        break

    json_data = response.json()

    if json_data["gotData"] == False:
        if retryNumber >= 2:
            print('after 3 retries no data received to proccess')
            break
        
        retryNumber += 1
        continue
    
    work_id = json_data["workId"]
    iterations = json_data["iterations"]
    base64_data = json_data["data"]
    destination_ip = json_data["destinationIp"] +':5000/'
    
    data = base64.b64decode(base64_data)
    data = work(data, int(iterations))
    
    post_data = {
        "workId": work_id,
        "finalValue": data
    }
    
    json_post_data = json.dumps(post_data, indent=4, sort_keys=True, default=str)
    
    post_response = requests.post('http://'+destination_ip+complete_path, data=json_post_data, headers=headers)
    print(f'posted worked data. response status code: {post_response.status_code}')
    print(json_post_data)

kill_worker_report_response = requests.post('http://'+dequeue_ip+kill_worker_path, headers=headers)

try:
    terminate_ec2()
except Exception as e:
    print('terminating self have failed')
    print(e)