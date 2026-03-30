#!/bin/bash
# Reset product-db and customer-db tables between performance test runs.
# Run from test-runner VM after sourcing .env:
#   cd /opt/app && source .env && bash reset_dbs.sh

set -e
ZONE="${ZONE:-us-west1-a}"

echo "Truncating product-db tables on VM1 (nodes 0 and 1)..."
gcloud compute ssh vm1 --zone="$ZONE" --command="
  sudo docker exec product-db-0 psql -U product_user -d product_db -c 'TRUNCATE TABLE products RESTART IDENTITY CASCADE;'
  sudo docker exec product-db-1 psql -U product_user -d product_db -c 'TRUNCATE TABLE products RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating product-db tables on VM2..."
gcloud compute ssh vm2 --zone="$ZONE" --command="
  sudo docker exec product-db-2 psql -U product_user -d product_db -c 'TRUNCATE TABLE products RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating product-db tables on VM3..."
gcloud compute ssh vm3 --zone="$ZONE" --command="
  sudo docker exec product-db-3 psql -U product_user -d product_db -c 'TRUNCATE TABLE products RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating product-db tables on VM4..."
gcloud compute ssh vm4 --zone="$ZONE" --command="
  sudo docker exec product-db-4 psql -U product_user -d product_db -c 'TRUNCATE TABLE products RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating customer-db tables on VM1 (nodes 0 and 1)..."
gcloud compute ssh vm1 --zone="$ZONE" --command="
  sudo docker exec customer-db-0 psql -U customer_user -d customer_db \
    -c 'TRUNCATE TABLE sellers, buyers, seller_sessions, buyer_sessions, active_carts, saved_carts, transactions, purchases RESTART IDENTITY CASCADE;'
  sudo docker exec customer-db-1 psql -U customer_user -d customer_db \
    -c 'TRUNCATE TABLE sellers, buyers, seller_sessions, buyer_sessions, active_carts, saved_carts, transactions, purchases RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating customer-db tables on VM2..."
gcloud compute ssh vm2 --zone="$ZONE" --command="
  sudo docker exec customer-db-2 psql -U customer_user -d customer_db \
    -c 'TRUNCATE TABLE sellers, buyers, seller_sessions, buyer_sessions, active_carts, saved_carts, transactions, purchases RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating customer-db tables on VM3..."
gcloud compute ssh vm3 --zone="$ZONE" --command="
  sudo docker exec customer-db-3 psql -U customer_user -d customer_db \
    -c 'TRUNCATE TABLE sellers, buyers, seller_sessions, buyer_sessions, active_carts, saved_carts, transactions, purchases RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "Truncating customer-db tables on VM4..."
gcloud compute ssh vm4 --zone="$ZONE" --command="
  sudo docker exec customer-db-4 psql -U customer_user -d customer_db \
    -c 'TRUNCATE TABLE sellers, buyers, seller_sessions, buyer_sessions, active_carts, saved_carts, transactions, purchases RESTART IDENTITY CASCADE;'
" -- -o StrictHostKeyChecking=no  

echo "All databases reset successfully."