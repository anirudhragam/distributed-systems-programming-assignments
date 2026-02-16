#!/bin/bash

# Run docker-compose
docker-compose up -d --build

# Clean up generated protobuf files from service directories
# (they're already in the central generated/ directory)
echo "Cleaning up duplicate generated files..."
rm -f services/customer-db/*_pb2.py services/customer-db/*_pb2_grpc.py
rm -f services/product-db/*_pb2.py services/product-db/*_pb2_grpc.py

echo "All services are up and running."