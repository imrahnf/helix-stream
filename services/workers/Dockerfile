# services/workers/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN echo "grpcio\ngrpcio-tools\nprotobuf\nnumpy\ntorch\ntransformers" > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/gateway/gen /app/gen

COPY services/workers/inference_worker.py /app/

ENV PYTHONPATH=/app:/app/gen

CMD ["python", "inference_worker.py"]