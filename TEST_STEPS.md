## Steps to run on test runner vm for PA3

---

One-time Setup
```bash
gcloud compute ssh test-runner-vm --zone=us-west1-a
cd /opt/app && source .env

# verify all containers are up
for vm in vm1 vm2 vm3 vm4; do
  echo "=== $vm ==="
  gcloud compute ssh $vm --zone=$ZONE --command="sudo docker ps --format '{{.Names}} {{.Status}}'" -- -o StrictHostKeyChecking=no
done

bash /opt/app/restart_services.sh
```

## Failure Condition A: All replicas running (baseline)

```bash
python3 performance_tests.py --num-sellers 1 --num-buyers 1 2>&1 | tee ~/results_a_1x1.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 10 --num-buyers 10 2>&1 | tee ~/results_a_10x10.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 100 --num-buyers 100 2>&1 | tee ~/results_a_100x100.txt
```

---

## Failure Condition B: One seller-server and one buyer-server fail

Stop VM1's app servers so that clients with id=1,5,9,... (idx=0) hit the failed server and retry against VM2:

```bash
gcloud compute ssh vm1 --zone=$ZONE --command="sudo docker stop seller-server-0 buyer-server-0" -- -o StrictHostKeyChecking=no

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 1 --num-buyers 1 2>&1 | tee ~/results_b_1x1.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 10 --num-buyers 10 2>&1 | tee ~/results_b_10x10.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 100 --num-buyers 100 2>&1 | tee ~/results_b_100x100.txt

# Restore
gcloud compute ssh vm1 --zone=$ZONE --command="sudo docker start seller-server-0 buyer-server-0" -- -o StrictHostKeyChecking=no

bash /opt/app/restart_services.sh
```

---

## Failure Condition C: One non-leader product-db replica fails


Identify the leader before starting Condition D:

```bash
for vm in vm1 vm2 vm3 vm4; do
  echo "=== $vm ==="
  gcloud compute ssh $vm --zone=$ZONE --command="
    for c in \$(sudo docker ps --format '{{.Names}}' | grep product-db); do
      echo \$c:; sudo docker logs \$c 2>&1 | grep '\[RAFT\]' | tail -2
    done
  " -- -o StrictHostKeyChecking=no
done
```

The node that prints <-- THIS NODE is the leader. Assuming product-db-3 on VM3 is non-leader (adjust vm/container name if not): 

```bash
gcloud compute ssh vm3 --zone=$ZONE --command="sudo docker stop product-db-3" -- -o StrictHostKeyChecking=no

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 1 --num-buyers 1 2>&1 | tee ~/results_c_1x1.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 10 --num-buyers 10 2>&1 | tee ~/results_c_10x10.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 100 --num-buyers 100 2>&1 | tee ~/results_c_100x100.txt

# Restore
gcloud compute ssh vm3 --zone=$ZONE --command="sudo docker start product-db-3" -- -o StrictHostKeyChecking=no
sleep 30  # wait for node to catch up

bash /opt/app/restart_services.sh
```

---

## Failure Condition D: Leader product-db replica fails

Identify the leader before starting Condition D:

```bash
for vm in vm1 vm2 vm3 vm4; do
  echo "=== $vm ==="
  gcloud compute ssh $vm --zone=$ZONE --command="
    for c in \$(sudo docker ps --format '{{.Names}}' | grep product-db); do
      echo \$c:; sudo docker logs \$c 2>&1 | grep '\[RAFT\]' | tail -2
    done
  " -- -o StrictHostKeyChecking=no
done
```

The node that prints <-- THIS NODE is the leader. Note which VM and container name it is, then stop it:

Assuming product-db-0 on VM1 is leader (adjust vm/container name if not):

```bash
gcloud compute ssh vm1 --zone=$ZONE --command="sudo docker stop product-db-0" -- -o StrictHostKeyChecking=no
sleep 10  # wait for re-election (~150-500ms, but allow extra margin)

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 1 --num-buyers 1 2>&1 | tee ~/results_d_1x1.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 10 --num-buyers 10 2>&1 | tee ~/results_d_10x10.txt

bash /opt/app/restart_services.sh && python3 performance_tests.py --num-sellers 100 --num-buyers 100 2>&1 | tee ~/results_d_100x100.txt

# Restore
gcloud compute ssh vm1 --zone=$ZONE --command="sudo docker start product-db-0" -- -o StrictHostKeyChecking=no
sleep 30
```
