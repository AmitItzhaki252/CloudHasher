import requests
import time
import json
import boto3
import paramiko
import threading
import os
import getpass
import re
import subprocess

global maxWorkersNumber
global currentWorkersNumber
global latest_queue_size
global latest_manager_ip

maxWorkersNumber = 10
currentWorkersNumber = 0
latest_queue_size = 0
latest_manager_ip = ''

global my_ip

try:
    with open('/home/ubuntu/config', 'r') as f:
        config = f.read()
except:
    with open('C:\git\CloudHasher\Endpoint\config', 'r') as f:
        config = f.read()

region = re.search(r'region\s*=\s*(\S+)', config).group(1)

# Set the AWS region
os.environ['AWS_DEFAULT_REGION'] = region

try:
    with open('/home/ubuntu/credentials', 'r') as f:
        aws_credentials = f.read()
except:
    with open('C:\git\CloudHasher\Endpoint\credentials', 'r') as f:
        aws_credentials = f.read()

access_key = re.search(r'aws_access_key_id\s*=\s*(\S+)', aws_credentials).group(1)
secret_key = re.search(r'aws_secret_access_key\s*=\s*(\S+)', aws_credentials).group(1)

# Set AWS credentials and region as environment variables
os.environ['AWS_ACCESS_KEY_ID'] = access_key
os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key

def periodic_checker():
    global latest_queue_size
    global latest_manager_ip
    
    if latest_queue_size > 10 and maxWorkersNumber > currentWorkersNumber:
        start_new_worker(latest_manager_ip)
        
    time.sleep(30)
    periodic_checker()


timer_thread = threading.Thread(target=periodic_checker)
timer_thread.start()

def message_added(queue_len, manager_ip):
    global currentWorkersNumber
    global maxWorkersNumber
    global latest_queue_size
    global latest_manager_ip

    latest_queue_size = queue_len
    latest_manager_ip = manager_ip
    
    if (currentWorkersNumber == 0 and queue_len == 1) and maxWorkersNumber > currentWorkersNumber:
        currentWorkersNumber += 1
        thread = threading.Thread(target=start_new_worker, args=[manager_ip])
        thread.start()


def decrease_workers():
    global currentWorkersNumber

    currentWorkersNumber -= 1


def start_new_worker(manager_ip):
    global currentWorkersNumber

    try:
        my_ip = get_public_ip()
        start_worker(manager_ip, my_ip)
        print('Worker started')
    except:
       print('creating worker failed')
       currentWorkersNumber -= 1
       if currentWorkersNumber == 0:
           start_new_worker(manager_ip)


def get_public_ip():
    url = 'https://checkip.amazonaws.com'
    response = requests.get(url)
    if response.status_code == 200:
        ip = response.text.strip()
        print(ip)
        return ip
    else:
        return None


def start_worker(manager_ip, my_ip):
    ec2 = boto3.client('ec2')
    key_name = f"Cloud-Computing-{int(time.time())}"
    key_response = ec2.create_key_pair(KeyName=key_name)
    key_pem = f"{key_name}.pem"
    print(key_pem)
        
    # Save the key pair to a file
    with open(key_pem, 'w') as key_file:
        key_file.write(key_response['KeyMaterial'].strip())

    
    # Set permissions for the key pair file
    try:
        # Reset ACLs
        subprocess.call(['icacls.exe', key_pem, '/reset'])

        # Get current username
        username = getpass.getuser()

        # Grant read permissions to the current user
        subprocess.call(['icacls.exe', key_pem, '/grant:r', f'{username}:(r)'])

        # Remove inheritance
        subprocess.call(['icacls.exe', key_pem, '/inheritance:r'])
    except:
        os.chmod(key_pem, 0o600)

    # Create a security group
    security_group_name = f"scriptSG-{int(time.time())}"
    security_group = ec2.create_security_group(
        GroupName=security_group_name, Description="script gen sg")
    print('security group was created')

    # Authorize security group ingress
    ip_permissions = [
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': f'{my_ip}/32'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 5000,
            'ToPort': 5000,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        }
    ]

    if manager_ip != my_ip:
        ip_permissions.append({
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': f'{manager_ip}/32'}]
        })

    print(ip_permissions)

    ec2.authorize_security_group_ingress(
        GroupName=security_group_name,
        IpPermissions=ip_permissions
    )

    # Launch EC2 instances
    ubuntu_20_04_ami = "ami-053b0d53c279acc90"
    instances = ec2.run_instances(
        ImageId=ubuntu_20_04_ami,
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.micro',
        KeyName=key_name,
        SecurityGroups=[security_group_name]
    )['Instances']
    print('instances were requested')

    # Wait for instances to be running
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance['InstanceId'] for instance in instances])
    print('instances are ready')

    # Get the public IPs of the instances
    instance1_id = instances[0]['InstanceId']

    describe_instance1 = ec2.describe_instances(InstanceIds=[instance1_id])
    public_ip1 = describe_instance1['Reservations'][0]['Instances'][0]['PublicIpAddress'].strip()

    # Create the public IPs file
    ips = {
        "IP": my_ip
    }

    # Save the IPs to a file
    with open("worker_public_ips.json", "w") as file:
        json.dump(ips, file, indent=4)

    username = 'ubuntu'
    hostname = public_ip1
    print(hostname)
    key_filename = key_pem

    # Command to execute on the remote server
    command = f'ssh -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {username}@{hostname} sudo mkdir -m 777 /home/ubuntu/files'

    try:
        # Execute the command and capture the output
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, encoding='utf-8')
        print("Command executed successfully")
        print("Output:")
        print(output)
    except subprocess.CalledProcessError as e:
        print("Command failed with error:")
        print(e.output)
        
        try:
            # Execute the command and capture the output
            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, encoding='utf-8')
            print("Command executed successfully 2")
            print("Output:")
            print(output)
        except subprocess.CalledProcessError as e:
            print("Command 2 failed with error:")
            print(e.output)
        
        
    # Use scp to copy the file from the server to the SSH session
    server_file_path = 'worker_public_ips.json'
    ssh_session_dest_path = '/home/ubuntu/files'
    scp_command = f'scp -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {server_file_path} {username}@{hostname}:{ssh_session_dest_path}'

    exit_status = subprocess.call(scp_command, shell=True)

    if exit_status == 0:
        print('ips file copied successfully.')
    else:
        print('ips file copying failed.')
        
    server_file_path = 'InstallWorker.sh'
    ssh_session_dest_path = '/home/ubuntu'
    scp_command = f'scp -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {server_file_path} {username}@{hostname}:{ssh_session_dest_path}'

    exit_status = subprocess.call(scp_command, shell=True)

    if exit_status == 0:
        print('script file copied successfully.')
    else:
        print('script file copying failed.')
        
    server_file_path = '/home/ubuntu/credentials'
    ssh_session_dest_path = '/home/ubuntu/files'
    scp_command = f'scp -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {server_file_path} {username}@{hostname}:{ssh_session_dest_path}'

    exit_status = subprocess.call(scp_command, shell=True)

    if exit_status == 0:
        print('credentials file copied successfully.')
    else:
        print('credentials file copying failed.')

    server_file_path = '/home/ubuntu/config'
    ssh_session_dest_path = '/home/ubuntu/files'
    scp_command = f'scp -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {server_file_path} {username}@{hostname}:{ssh_session_dest_path}'

    exit_status = subprocess.call(scp_command, shell=True)

    if exit_status == 0:
        print('config file copied successfully.')
    else:
        print('config file copying failed.')

    #run install worker script
    server_file_path = 'InstallWorker.sh'
    ssh_session_dest_path = '/home/ubuntu'
    scp_command = f'sudo ssh -o ConnectionAttempts=10 -o StrictHostKeyChecking=no -i {key_filename} {username}@{hostname} sudo bash {ssh_session_dest_path}/{server_file_path}'

    exit_status = subprocess.call(scp_command, shell=True)

    if exit_status == 0:
        print('script ran successfully.')
    else:
        print('script running failed.')