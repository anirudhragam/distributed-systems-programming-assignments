#!/bin/bash

cp -r ../utils buyer-client/utils
cp -r ../utils seller-client/utils
cp -r ../utils buyer-server/utils
cp -r ../utils seller-server/utils

cd ..

# Stop and remove any existing containers and volumes
echo "Cleaning up old containers..."
docker-compose down -v 2>/dev/null || true

# Run docker-compose
docker-compose up -d --build
# All services are up and running."

cd services

rm -rf buyer-client/utils
rm -rf seller-client/utils
rm -rf buyer-server/utils
rm -rf seller-server/utils