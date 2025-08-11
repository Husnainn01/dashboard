# OTC Predictor Backend

This is the backend for the OTC Predictor system, which provides real-time predictions for OTC markets using machine learning models.

## Architecture

The system supports two architectures:

1. **Monolithic** - All services run in a single process
2. **Microservices** - Services run as separate processes

### Monolithic Architecture

The monolithic architecture runs all services in a single process, with the following components:

- **Data Collection Service** - Collects real-time market data from PyQuotex
- **Prediction API** - Provides REST API for predictions and model management
- **ML Prediction Service** - Generates predictions using trained models

### Microservices Architecture

The microservices architecture splits the system into separate services:

- **Data Collection Service** - Collects real-time market data from PyQuotex
- **ML Training Service** - Handles model training and management
- **Prediction Service** - Generates predictions using trained models
- **API Gateway** - Provides a unified API for the frontend

## Getting Started

### Prerequisites

- Python 3.8+
- MongoDB
- PyQuotex credentials

### Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up PyQuotex credentials in `config.py` or as environment variables:

```bash
export QUOTEX_EMAIL="your_email@example.com"
export QUOTEX_PASSWORD="your_password"
```

3. Start MongoDB:

```bash
# Using Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### Running the Backend

#### Monolithic Mode

```bash
# Run all services
python main.py

# Run only data collection
python main.py --mode data

# Run only API
python main.py --mode api

# Run only ML service
python main.py --mode ml

# Run with custom ports
python main.py --port 5001 --ml-port 6008
```

#### Microservices Mode

```bash
# Run all services
python main.py --architecture microservices

# Run specific services
python main.py --architecture microservices --mode data
python main.py --architecture microservices --mode api
python main.py --architecture microservices --mode ml

# Run with auto-reload for development
python main.py --architecture microservices --reload
```

#### Docker Compose Mode

```bash
# Run all services using Docker Compose
python main.py --architecture docker
```

Or directly with Docker Compose:

```bash
cd microservices
docker-compose up -d
```

## API Documentation

When running, API documentation is available at:

- Monolithic Mode: `http://localhost:5001/docs`
- Microservices Mode: `http://localhost:5000/docs` (API Gateway)

## Services

### Data Collection Service

Collects real-time market data from PyQuotex and stores in MongoDB.

- **Monolithic Port**: 5001 (part of API)
- **Microservices Port**: 5001

### ML Training Service

Handles model training and management.

- **Monolithic Port**: N/A (part of API)
- **Microservices Port**: 5002

### Prediction Service

Generates predictions using trained models.

- **Monolithic Port**: 6008
- **Microservices Port**: 5003

### API Gateway (Microservices Only)

Provides a unified API for the frontend.

- **Port**: 5000

## WebSocket API

The system provides WebSocket endpoints for real-time data:

- **/ws/market-data** - Real-time market data
- **/ws/predictions** - Real-time predictions
- **/ws** - Unified WebSocket endpoint (Microservices only)

## Directory Structure

```
backend/
├── config.py                  # Configuration
├── data_collection/           # Data collection modules
├── database/                  # Database models and connection
├── main.py                    # Main entry point
├── microservices/             # Microservices architecture
│   ├── api_gateway/           # API Gateway service
│   ├── data_collection_service/ # Data Collection service
│   ├── docker-compose.yml     # Docker Compose configuration
│   ├── ml_training_service/   # ML Training service
│   └── prediction_service/    # Prediction service
├── ml_models/                 # ML model training and prediction
├── services/                  # Monolithic service implementations
└── trained_models/            # Saved trained models
```
