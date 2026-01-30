FROM python:3.12-slim

WORKDIR /app

# Install system deps for git-based installs
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY microservices/api_gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the service code and shared modules
COPY microservices/api_gateway /app/microservices/api_gateway/
COPY config.py /app/
COPY microservices/api_gateway/config.py /app/microservices/api_gateway/

# Create necessary directories
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose the service port
EXPOSE ${PORT:-5001}

# Set working directory to service directory
WORKDIR /app/microservices/api_gateway

# Run the service (PORT env var is set by Railway)
CMD ["python", "main.py"]
