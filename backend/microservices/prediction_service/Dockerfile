FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY microservices/prediction_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the service code and shared modules
COPY microservices/prediction_service /app/microservices/prediction_service/
COPY database /app/database/
COPY ml_models /app/ml_models/
COPY config.py /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/trained_models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV STORAGE_TYPE=r2
ENV USE_CLOUD_STORAGE=true

# Expose the service port
EXPOSE 5003

# Set working directory to service directory
WORKDIR /app/microservices/prediction_service

# Run the service
CMD ["python", "main.py"]
