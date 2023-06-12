$DateTime = (Get-Date).ToUniversalTime()
$UnixTimeStamp = [System.Math]::Truncate((Get-Date -Date $DateTime -UFormat %s))

$KEY_NAME = "Cloud-Computing-" + $UnixTimeStamp
$KEY_PEM = $KEY_NAME + ".pem"

$SEC_GRP = "scriptSG-" + $UnixTimeStamp

# Read AWS credentials from file
$awsCredentials = Get-Content -Raw -Path "./credentials"

# Read AWS region from file
$awsConfig = Get-Content -Raw -Path "./config"

# Extract the AWS access key, secret key, and session token from the credentials file
$accessKey = ($awsCredentials | Select-String -Pattern "aws_access_key_id\s*=\s*(\S+)" | ForEach-Object { $_.Matches.Groups[1].Value })
$secretKey = ($awsCredentials | Select-String -Pattern "aws_secret_access_key\s*=\s*(\S+)" | ForEach-Object { $_.Matches.Groups[1].Value })
$sessionToken = ($awsCredentials | Select-String -Pattern "aws_session_token\s*=\s*(\S+)" | ForEach-Object { $_.Matches.Groups[1].Value })

# Extract the AWS region from the config file
$region = ($awsConfig | Select-String -Pattern "region\s*=\s*(\S+)" | ForEach-Object { $_.Matches.Groups[1].Value })

# Set AWS credentials and region using environment variables
$env:AWS_ACCESS_KEY_ID = $accessKey
$env:AWS_SECRET_ACCESS_KEY = $secretKey
$env:AWS_SESSION_TOKEN = $sessionToken
$env:AWS_DEFAULT_REGION = $region

# Create key pair
aws ec2 create-key-pair --key-name $KEY_NAME --query 'KeyMaterial' --output text > $KEY_PEM

# Read the content of the file
$fileContent = Get-Content -Raw -Path $KEY_PEM

# Trim the newline characters at the end
$fileContent = $fileContent -replace '[\r\n\s]+$'

# Write the modified content back to the file
$fileContent | Set-Content -Path $KEY_PEM

icacls.exe $KEY_PEM /reset
icacls.exe $KEY_PEM /grant:r "$($env:username):(r)"
icacls.exe $KEY_PEM /inheritance:r

# Create security group
aws ec2 create-security-group --group-name $SEC_GRP --description "script gen sg"

# Get public IP
$MY_IP = curl https://checkip.amazonaws.com
$MY_IP = $MY_IP -replace '\s+$'

# Authorize security group ingress
aws ec2 authorize-security-group-ingress --group-name $SEC_GRP --protocol tcp --port 22 --cidr $MY_IP/32
aws ec2 authorize-security-group-ingress --group-name $SEC_GRP --protocol tcp --port 5000 --cidr 0.0.0.0/0

# Start EC2 instance
$UBUNTU_20_04_AMI = "ami-053b0d53c279acc90"
$RUN_INSTANCES = aws ec2 run-instances --image-id $UBUNTU_20_04_AMI --count 2 --instance-type t2.micro --key-name $KEY_NAME --security-groups $SEC_GRP


$RUN_INSTANCES_Convert = $RUN_INSTANCES | ConvertFrom-Json
$INSTANCE1_ID = $RUN_INSTANCES_Convert.Instances[0].InstanceId
$INSTANCE2_ID = $RUN_INSTANCES_Convert.Instances[1].InstanceId

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids $INSTANCE1_ID
aws ec2 wait instance-running --instance-ids $INSTANCE2_ID

# Get public IP of 1 instance
$Describe_Instance1 = aws ec2 describe-instances --instance-ids $INSTANCE1_ID
$Describe_Instance1_Convert = $Describe_Instance1 | ConvertFrom-Json
$PUBLIC_IP1 = $Describe_Instance1_Convert.Reservations[0].Instances[0].PublicIpAddress

# Get public IP of 2 instance
$Describe_Instance2 = aws ec2 describe-instances --instance-ids $INSTANCE2_ID
$Describe_Instance2_Convert = $Describe_Instance2 | ConvertFrom-Json
$PUBLIC_IP2 = $Describe_Instance2_Convert.Reservations[0].Instances[1].PublicIpAddress

# Creates the public IPs file
$IPs = @{
    IP1 = $PUBLIC_IP1
    IP2 = $PUBLIC_IP2
	MY = $MY_IP
}

# Convert the IPs to JSON format
$IPsJson = $IPs | ConvertTo-Json -Depth 4

# Save the IPs to a file
$IPsJson | Set-Content -Path "public_ips.json"

# Copy script and execute it on instance 1
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" public_ips.json ubuntu@${PUBLIC_IP1}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./credentials ubuntu@${PUBLIC_IP1}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./config ubuntu@${PUBLIC_IP1}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./InstallEndpoint.sh ubuntu@${PUBLIC_IP1}:/home/ubuntu
ssh -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ubuntu@${PUBLIC_IP1} "sudo bash /home/ubuntu/InstallEndpoint.sh"

# Copy script and execute it on instance 2
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" public_ips.json ubuntu@${PUBLIC_IP2}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./credentials ubuntu@${PUBLIC_IP2}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./config ubuntu@${PUBLIC_IP2}:/home/ubuntu
scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ./InstallEndpoint.sh ubuntu@${PUBLIC_IP2}:/home/ubuntu
ssh -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ubuntu@${PUBLIC_IP2} "sudo bash /home/ubuntu/InstallEndpoint.sh"
