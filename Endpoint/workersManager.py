import requests
import time
import json
import boto3
import paramiko
import threading
import os
import stat

global maxWorkersNumber
global currentWorkersNumber

maxWorkersNumber = 10
currentWorkersNumber = 0

global my_ip


def message_added(queue_len, manager_ip):
    global currentWorkersNumber
    global maxWorkersNumber

    if (currentWorkersNumber == 0 or queue_len > 1) and maxWorkersNumber > currentWorkersNumber:
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
    # Read AWS credentials from file
    credentials_path = os.path.expanduser("credentials")
    config_path = os.path.expanduser("config")

    # Set AWS credentials and region using environment variables
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = credentials_path
    os.environ["AWS_CONFIG_FILE"] = config_path

    print(os.environ["AWS_SHARED_CREDENTIALS_FILE"])
    print(os.environ["AWS_CONFIG_FILE"])

    # Create an EC2 client
    ec2 = boto3.client('ec2')

    # Generate a key pair
    key_name = f"Cloud-Computing-{int(time.time())}"
    key_response = ec2.create_key_pair(KeyName=key_name, KeyType='ed25519')
    key_pem = f"{key_name}.pem"
    print('key was created')

    # Save the key pair to a file
    with open(key_pem, 'w') as key_file:
        key_file.write(key_response['KeyMaterial'].strip())

    # Set permissions for the key pair file
    os.chmod(key_pem, stat.S_IRUSR | stat.S_IWUSR)

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
    public_ip1 = describe_instance1['Reservations'][0]['Instances'][0]['PublicIpAddress']

    # Create the public IPs file
    ips = {
        "IP": my_ip
    }

    # Save the IPs to a file
    with open("worker_public_ips.json", "w") as file:
        json.dump(ips, file, indent=4)

    paramiko.util.loglevel = paramiko.util.DEBUG

    # Create an SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())

    # Copy and execute the script on the first instance
    print(key_pem)
    #ssh.connect(public_ip1, username='ubuntu', key_filename=key_pem, look_for_keys=True, allow_agent=False)
    try:
        run_scripts_on_remote(ssh, public_ip1, key_pem)
    except:
        print('retrying')
        time.sleep(5)

        run_scripts_on_remote(ssh, public_ip1, key_pem)

    print('worker is running')


def run_scripts_on_remote(ssh, public_ip1, key_pem):
    ssh.connect(public_ip1, username='ubuntu', key_filename=key_pem)
    #sftp.put("worker_public_ips.json", "/home/ubuntu")
    stdin, stdout, stderr = ssh.exec_command(
        'sudo mv worker_public_ips.json /home/ubuntu')

    # Wait for the command to complete
    stdout.channel.recv_exit_status()

    stdin, stdout, stderr = ssh.exec_command(
        'sudo mv credentials /home/ubuntu')

    # Wait for the command to complete
    stdout.channel.recv_exit_status()
    stdin, stdout, stderr = ssh.exec_command('sudo mv config /home/ubuntu')

    # Wait for the command to complete
    stdout.channel.recv_exit_status()
    stdin, stdout, stderr = ssh.exec_command(
        'sudo mv InstallWorker.sh /home/ubuntu')

    # Wait for the command to complete
    stdout.channel.recv_exit_status()

    ssh.exec_command("sudo bash /home/ubuntu/InstallWorker.sh")

    ssh.close()