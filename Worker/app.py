from flask import Flask, request
import math
import random
from datetime import datetime
import json
import requests
import hashlib
import base64
import boto3

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

global ip
global dequeue_path
global complete_path
global kill_worker_path
global retryNumber

dequeue_path = 'dequeue'
complete_path = 'completed'
kill_worker_path = 'killWorker'

with open("worker_public_ips.json", "r") as file:
    ips_json = file.read()

# Parse the JSON content
ips = json.loads(ips_json)

dequeue_ip = ips["IP"] + ':5000/'

is_running = True
retryNumber = 0

while is_running:
    response = requests.get(dequeue_ip+dequeue_path)

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
    destination_ip = json_data["destinationData"]
    
    data = base64.b64decode(base64_data)
    data = work(data, iterations)
    
    post_data = {
        'workId': work_id,
        'finalValue': data
    }
    
    post_response = requests.post(destination_ip+':5000/'+complete_path, data=post_data)
    print(f'posted worked data. response status code: {post_response.status_code}')
    

kill_worker_report_response = requests.post(dequeue_ip+kill_worker_path)

try:
    terminate_ec2()
except:
    print('terminating self have failed')