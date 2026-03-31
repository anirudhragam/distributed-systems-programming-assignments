#!/bin/bash
for vm in vm1 vm3 vm4; do
  gcloud compute ssh $vm --zone=$ZONE --command="sudo docker ps --format '{{.Names}}' | grep -E 'customer-db|seller-server|buyer-server' | xargs sudo docker restart" -- -o StrictHostKeyChecking=no
done
# Restart only customer-db on VM2, not the app servers
gcloud compute ssh vm2 --zone=$ZONE --command="sudo docker ps --format '{{.Names}}' | grep 'customer-db' | xargs sudo docker restart" -- -o StrictHostKeyChecking=no
sleep 15
bash /opt/app/reset_dbs.sh