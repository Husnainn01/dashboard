FROM python:3.12-slim

WORKDIR /app

# System deps for git-based installs and ML libs
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY microservices/data_collection_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the service code and shared modules
COPY microservices/data_collection_service /app/microservices/data_collection_service/
COPY data_collection /app/data_collection/
COPY database /app/database/
COPY shared /app/shared/
COPY config.py /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/trained_models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose the service port
EXPOSE 5008

# Set working directory to service directory
WORKDIR /app/microservices/data_collection_service

# Run the service
CMD ["python", "main.py"]
