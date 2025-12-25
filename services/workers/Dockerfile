# workers/Dockerfile

# Base image with Python
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies for gRPC and (eventually) PyTorch/ESM-2
RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    protobuf \
    numpy 
    # torch -- We will add the heavy ML libs in Phase 3

# Copy the worker source code
COPY . .

# Default command (keeps container alive if script is missing)
CMD ["python", "inference_worker.py"]