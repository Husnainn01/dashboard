# Running the OTC Predictor Microservices

This guide explains how to run the OTC Predictor microservices system.

## Port Configuration

Each microservice runs on a different port:

| Service | Default Port | Current Port |
|---------|--------------|--------------|
| API Gateway | 5000 | 5001 |
| Data Collection | 5001 | 5008 |
| ML Training | 5002 | 5002 |
| Prediction | 5003 | 5003 |

## Starting the Services

### Option 1: Using the Main Script

The main.py script in the backend directory can run all microservices:

```bash
# From the backend directory
python main.py --architecture microservices
```

### Option 2: Running Individual Services

To run each service individually:

```bash
# Data Collection Service
cd microservices/data_collection_service
source venv/bin/activate  # Activate the virtual environment
python main.py --port 5008

# ML Training Service
cd microservices/ml_training_service
source venv/bin/activate
python main.py

# Prediction Service
cd microservices/prediction_service
source venv/bin/activate
python main.py

# API Gateway
cd microservices/api_gateway
source venv/bin/activate
python main.py --port 5001
```

## Verifying Services

You can check if the services are running correctly:

```bash
# Check Data Collection Service
curl http://localhost:5008/health
curl http://localhost:5008/status

# Check ML Training Service
curl http://localhost:5002/health

# Check Prediction Service
curl http://localhost:5003/health

# Check API Gateway
curl http://localhost:5001/health
```

## Troubleshooting

### API Gateway Can't Connect to Data Collection Service

If the API Gateway shows the data collection service as "unhealthy":

1. Make sure the data collection service is running on port 5008
2. Check that the API Gateway is configured to use port 5008 for the data collection service
3. Restart the API Gateway after updating its configuration

### Services Not Starting Automatically

All services are now configured to auto-start their core functionality when the service starts:

- Data Collection Service automatically starts collecting data
- ML Training Service automatically starts the training worker
- Prediction Service automatically starts generating predictions

If a service doesn't auto-start, you can manually trigger it:

```bash
# Start Data Collection
curl -X POST http://localhost:5008/start

# Start ML Training
curl -X POST http://localhost:5002/train -H "Content-Type: application/json" -d '{"trading_pair": "USD/BRL(OTC)", "model_type": "xgboost", "force_retrain": false}'

# Start Prediction
curl -X POST http://localhost:5003/start
```

### Port Conflicts

If you encounter port conflicts, you can change the ports:

```bash
python main.py --port 5010  # Change the port for any service
```

Remember to update the API Gateway configuration if you change any service ports.
