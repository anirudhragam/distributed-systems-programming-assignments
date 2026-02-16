FROM postgres:15

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --break-system-packages grpcio grpcio-tools psycopg2-binary

COPY services/product-db/init-schema.sql /docker-entrypoint-initdb.d/
COPY services/product-db/grpc_server.py /app/
COPY generated/ /app/generated/
COPY services/product-db/startup.sh /app/

RUN chmod +x /app/startup.sh

# Expose PostgreSQL and gRPC ports
EXPOSE 5432 50051

# Use custom startup script
CMD ["/app/startup.sh"]
