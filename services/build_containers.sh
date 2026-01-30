#!/bin/bash

cp -r ../utils buyer_client/utils
cp -r ../utils seller_client/utils
cp -r ../utils buyer_server/utils
cp -r ../utils seller_server/utils

cd ..

# Run docker-compose
docker-compose up -d --build
# All services are up and running."

cd services

rm -rf buyer_client/utils
rm -rf seller_client/utils
rm -rf buyer_server/utils
rm -rf seller_server/utils