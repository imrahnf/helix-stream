# services/gateway/Dockerfile
FROM python:3.12-slim

# Install system libs for Postgres (psycopg/asyncpg build deps)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    grpcio \
    grpcio-tools \
    protobuf \
    asyncpg \
    httpx \
    uvloop \
    watchfiles

# Copy the Gateway source code
# Note: We copy strictly the gateway folder contents into /app
COPY services/gateway /app

# Copy the Gen folder (Protobuf stubs)
# We assume you ran the protoc command locally, so we copy the artifacts
COPY services/gateway/gen /app/gen

# Set python path to find the 'gen' folder
ENV PYTHONPATH=/app:/app/gen

# Expose the port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]