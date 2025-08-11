# Prediction Microservice

This microservice is responsible for generating predictions using trained ML models for OTC trading.

## Features

- Real-time predictions using trained models
- WebSocket API for streaming predictions to clients
- REST API for on-demand predictions
- Continuous prediction mode for all trading pairs

## API Endpoints

### REST API

- `GET /` - Service information
- `GET /health` - Health check endpoint
- `GET /status` - Get service status
- `POST /predict` - Generate a prediction for a trading pair
- `GET /predict/{trading_pair}` - Quick prediction for a specific trading pair
- `POST /start` - Start continuous prediction service
- `POST /stop` - Stop continuous prediction service

### WebSocket API

- `/ws/predictions` - WebSocket endpoint for real-time predictions
  - Subscribe to a trading pair: `{"action": "subscribe", "trading_pair": "USD/BRL(OTC)"}`

## Prediction Process

The service follows these steps when making a prediction:

1. Fetch the best trained model for the requested trading pair
2. Get recent candle data from MongoDB
3. Extract features using the same feature engineering process used in training
4. Scale features using the model's scaler
5. Generate prediction using the trained model
6. Save prediction to MongoDB
7. Broadcast prediction to WebSocket subscribers

## Running the Service

### Prerequisites

- MongoDB running and accessible
- Trained models available (created by the ML Training Service)

### Start the Service

```bash
# From the microservice directory
python main.py

# With custom host and port
python main.py --host 0.0.0.0 --port 5003

# With auto-reload for development
python main.py --reload
```

## Docker Deployment

```bash
docker build -t otc-predictor-prediction .
docker run -p 5003:5003 -e MONGODB_URI="mongodb://host.docker.internal:27017" otc-predictor-prediction
```
