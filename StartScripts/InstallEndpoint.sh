#!/home/ubuntu

git clone https://github.com/AmitItzhaki252/CloudHasher.git

cd CloudHasher/Endpoint

sudo apt-get update -y
sudo apt-get upgrade -y

sudo apt-get install python3-pip -y

sudo pip3 install --upgrade pip

sudo pip3 install flask

sudo pip3 install flasgger
sudo pip3 install paramiko
sudo pip3 install requests

sudo pip3 install flask boto3 pillow

sudo apt install python3-flask -y

sudo python3 -m flask run --host=0.0.0.0