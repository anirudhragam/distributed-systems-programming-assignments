FROM python:3.10-slim

WORKDIR /app

# Copy application files
COPY . /app/

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "server.py"]
