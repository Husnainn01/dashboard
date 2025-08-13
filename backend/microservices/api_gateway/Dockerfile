FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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
EXPOSE 5001

# Set working directory to service directory
WORKDIR /app/microservices/api_gateway

# Run the service
CMD ["python", "main.py"]
