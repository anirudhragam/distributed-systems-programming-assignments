#!/bin/bash
set -e

# Function to start gRPC server after PostgreSQL is ready
start_grpc_server() {
    echo "Waiting for PostgreSQL to be ready..."
    until pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB} > /dev/null 2>&1; do
        sleep 1
    done

    echo "PostgreSQL is ready! Starting gRPC server..."
    sleep 2  # Extra safety margin

    cd /app
    python3 grpc_server.py
}

# Start gRPC server in background
start_grpc_server &
GRPC_PID=$!

# Start PostgreSQL in foreground (this is the main process)
exec docker-entrypoint.sh postgres
