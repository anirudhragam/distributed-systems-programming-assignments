# distributed-systems-programming-assignments
Repository containing all the programming assignments for CSCI-5673: Distributed Systems Spring 2026.

Terminal 1:
sh build_containers.sh
docker-compose ps

Terminal 2:
docker exec -it seller_client_container python seller_cli.py

Terminal 3:
docker exec -it customer_db_container psql -U customer_user -d customer_db

Terminal 4:
docker exec -it product_db_container psql -U product_user -d product_db

Terminal 5:
docker exec -it buyer_client_container python buyer_cli.py


GCE creation commands:
gcloud compute instances create pa1-vm \
  --zone=us-west1-a \
  --machine-type=e2-standard-2 \
  --boot-disk-size=20GB \
  --image-family=ubuntu-2004-lts \
  --tags=pa1 \
  --image-project=ubuntu-os-cloud \
  --metadata=startup-script='#!/bin/bash
    apt-get update
    apt-get install -y docker.io docker-compose
    apt-get install -y git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker $USER
    apt-get install -y curl wget vim'

gcloud compute firewall-rules create allow-seller-server \
  --allow=tcp:5001 \
  --target-tags=pa1 \
  --description="Allow traffic on seller server port 5001" \
  --direction=INGRESS

gcloud compute firewall-rules create allow-buyer-server \
  --allow=tcp:6001 \
  --target-tags=pa1 \
  --description="Allow traffic on buyer server port 6001" \
  --direction=INGRESS

SSH to GCE:
gcloud compute ssh pa1-vm --zone=us-west1-a

Clone repository:
git clone https://github.com/anirudhragam/distributed-systems-programming-assignments.git

Bring up services:
cd services
bash build_containers.sh

Run performance tests:
python performance_tests.py --num-sellers 10 --num-buyers 10 > results_10x10.txt 2>&1 | tee results_10x10.txt




