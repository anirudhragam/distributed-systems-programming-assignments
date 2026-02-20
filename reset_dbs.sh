#!/bin/bash
# Reset databases between performance test runs.
# Run from the test-runner VM after sourcing .env:
#   cd /opt/app && source .env && bash reset_dbs.sh

set -e

ZONE="${ZONE:-us-west1-a}"

echo "Resetting product-db..."
gcloud compute ssh product-db-vm --zone="$ZONE" --command="
  sudo docker stop product-db
  sudo docker rm product-db
  sudo docker volume rm product_db_data
  sudo docker run -d \
    --name product-db \
    --restart unless-stopped \
    -p 50051:50051 \
    -e POSTGRES_DB=product_db \
    -e POSTGRES_USER=product_user \
    -e POSTGRES_PASSWORD=product_password \
    -v product_db_data:/var/lib/postgresql/data \
    product-db:latest
"

echo "Resetting customer-db..."
gcloud compute ssh customer-db-vm --zone="$ZONE" --command="
  sudo docker stop customer-db
  sudo docker rm customer-db
  sudo docker volume rm customer_db_data
  sudo docker run -d \
    --name customer-db \
    --restart unless-stopped \
    -p 50052:50052 \
    -e POSTGRES_DB=customer_db \
    -e POSTGRES_USER=customer_user \
    -e POSTGRES_PASSWORD=customer_password \
    -v customer_db_data:/var/lib/postgresql/data \
    customer-db:latest
"

echo "Waiting for databases to initialize..."
sleep 15

echo "Databases reset successfully."
