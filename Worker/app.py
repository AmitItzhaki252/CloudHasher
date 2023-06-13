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

#global ip
#global dequeue_path
#global complete_path
#global kill_worker_path
#global retryNumber

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
    response = requests.get('http://'+dequeue_ip+dequeue_path, headers=headers)

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
except:
    print('terminating self have failed')