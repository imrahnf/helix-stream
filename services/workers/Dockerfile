# services/workers/Dockerfile
FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir grpcio grpcio-tools protobuf numpy torch transformers

COPY services/gateway/gen /app/gen

COPY services/workers/inference_worker.py /app/

ENV PYTHONPATH=/app:/app/gen

CMD ["python", "inference_worker.py"]