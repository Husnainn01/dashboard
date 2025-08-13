FROM python:3.9-slim

WORKDIR /app

# Install Python dependencies
COPY microservices/ml_training_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the service code and shared modules
COPY microservices/ml_training_service /app/microservices/ml_training_service/
COPY ml_models /app/ml_models/
COPY database /app/database/
COPY config.py /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/trained_models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose the service port
EXPOSE 5002

# Set working directory to service directory
WORKDIR /app/microservices/ml_training_service

# Run the service
CMD ["python", "main.py"]
