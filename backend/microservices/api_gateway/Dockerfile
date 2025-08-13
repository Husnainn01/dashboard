FROM python:3.9-slim

WORKDIR /app

# Copy shared dependencies first for better caching
COPY requirements.txt /app/requirements.txt
COPY config.py /app/

# Copy shared modules that all services need
COPY ml_models/ /app/ml_models/
COPY database/ /app/database/
COPY services/ /app/services/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the specific service code
COPY microservices/api_gateway/ /app/microservices/api_gateway/

# Create necessary directories
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose the service port
EXPOSE 5000

# Set working directory to service directory
WORKDIR /app/microservices/api_gateway

# Run the service
CMD ["python", "main.py"]
