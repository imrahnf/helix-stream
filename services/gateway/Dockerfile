# services/gateway/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/gateway/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/gateway /app

COPY services/gateway/gen /app/gen

ENV PYTHONPATH=/app:/app/gen

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]