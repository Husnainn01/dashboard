# OTC Predictor Microservices Architecture

This directory contains the refactored microservices for the OTC Predictor system. The goal is to separate the monolithic backend into smaller, more focused services that can be deployed and scaled independently.

## Architecture Overview

The system is divided into the following microservices:

1. **Data Collection Service**: Responsible for collecting real-time market data from PyQuotex
2. **ML Training Service**: Handles model training and management
3. **Prediction Service**: Generates predictions using trained models
4. **API Gateway**: Provides a unified API for the frontend and handles WebSocket connections

## Communication Between Services

Services communicate with each other using:

1. **MongoDB**: Shared database for persistent storage
2. **REST APIs**: For synchronous request-response communication
3. **WebSockets**: For real-time data streaming

## Directory Structure

```
microservices/
├── data_collection_service/    # Collects market data from PyQuotex
├── ml_training_service/        # Trains and manages ML models
├── prediction_service/         # Generates predictions using trained models
├── api_gateway/                # Unified API for the frontend
└── shared/                     # Shared code and utilities
```

## Getting Started

Each service can be run independently. See the README in each service directory for specific instructions.

To run all services:

```bash
# Start MongoDB (required for all services)
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Start each service in a separate terminal
cd microservices/data_collection_service
python main.py

cd microservices/ml_training_service
python main.py

cd microservices/prediction_service
python main.py

cd microservices/api_gateway
python main.py
```

## Deployment

Each service can be deployed as a separate container using Docker and orchestrated with Docker Compose or Kubernetes.

For Railway deployment, each service has its own `nixpacks.toml` configuration.
