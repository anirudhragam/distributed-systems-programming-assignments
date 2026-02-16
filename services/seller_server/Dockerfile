FROM python:3.13-slim

WORKDIR /app

# Copy generated protobuf files first
COPY generated/ /app/generated/

# Copy application files
COPY services/seller_server/ /app/

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "app.py"]
