# API Gateway Microservice

This microservice serves as the unified API gateway for the OTC Predictor system, providing a single entry point for the frontend to communicate with all backend services.

## Features

- Unified REST API for all microservices
- WebSocket proxying for real-time data
- Service health monitoring
- Request forwarding to appropriate services
- Unified WebSocket endpoint for all data types

## API Endpoints

### Core Endpoints

- `GET /` - Service information
- `GET /health` - Health check endpoint for all services
- `GET /status` - Get status of all services
- `GET /trading-pairs` - Get configured trading pairs

### Data Service Endpoints

- `GET /data/candles/{trading_pair}` - Get historical candles for a trading pair

### ML Service Endpoints

- `GET /ml/models` - List all trained models
- `GET /ml/models/{trading_pair}` - List models for a specific trading pair
- `POST /ml/train` - Train a new model for a trading pair
- `POST /ml/train-all` - Train models for all configured trading pairs

### Prediction Service Endpoints

- `POST /predict` - Generate a prediction for a trading pair
- `GET /predict/{trading_pair}` - Quick prediction for a specific trading pair
- `POST /predictions/start` - Start continuous prediction service
- `POST /predictions/stop` - Stop continuous prediction service

### WebSocket Endpoints

- `/ws/market-data` - WebSocket proxy for market data
- `/ws/predictions` - WebSocket proxy for predictions
- `/ws` - Unified WebSocket endpoint for all data types

## Configuration

The API Gateway can be configured using environment variables:

- `DATA_SERVICE_HOST` - Data Collection Service host (default: localhost)
- `DATA_SERVICE_PORT` - Data Collection Service port (default: 5001)
- `ML_SERVICE_HOST` - ML Training Service host (default: localhost)
- `ML_SERVICE_PORT` - ML Training Service port (default: 5002)
- `PREDICTION_SERVICE_HOST` - Prediction Service host (default: localhost)
- `PREDICTION_SERVICE_PORT` - Prediction Service port (default: 5003)

## Running the Service

### Prerequisites

- All microservices (Data Collection, ML Training, Prediction) should be running

### Start the Service

```bash
# From the microservice directory
python main.py

# With custom host and port
python main.py --host 0.0.0.0 --port 5000

# With auto-reload for development
python main.py --reload
```

## Docker Deployment

```bash
docker build -t otc-predictor-api-gateway .
docker run -p 5000:5000 \
  -e DATA_SERVICE_HOST=data-collection \
  -e ML_SERVICE_HOST=ml-training \
  -e PREDICTION_SERVICE_HOST=prediction \
  otc-predictor-api-gateway
```
