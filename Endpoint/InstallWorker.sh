#!/home/ubuntu

sudo apt-get update -y
sudo apt-get upgrade -y

sudo apt-get install python3-pip -y

sudo pip3 install --upgrade pip

sudo pip3 install flask

sudo pip3 install paramiko
sudo pip3 install requests
sudo pip3 install boto3

python3 -c "import flask"

sudo pip3 install flask boto3 pillow

sudo apt install python3-flask -y

python3 -c "import boto3"

git clone https://github.com/AmitItzhaki252/CloudHasher.git

cd CloudHasher/Worker

sudo nohup python3 -m app.py > log.txt 2>&1 &