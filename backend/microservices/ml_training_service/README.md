# ML Training Microservice

This microservice is responsible for training and managing machine learning models for OTC trading predictions.

## Features

- Asynchronous model training with job queue
- Support for multiple ML algorithms (XGBoost, Random Forest, LightGBM)
- REST API for model training and management
- Automatic feature engineering from candle data

## API Endpoints

### REST API

- `GET /` - Service information
- `GET /health` - Health check endpoint
- `GET /models` - List all trained models
- `GET /models/{trading_pair}` - List models for a specific trading pair
- `POST /train` - Train a new model for a trading pair
- `GET /train/status/{job_id}` - Get status of a training job
- `POST /train-all` - Train models for all configured trading pairs
- `GET /queue/status` - Get status of the training queue

## Training Process

The service follows these steps when training a model:

1. Fetch historical candle data from MongoDB
2. Perform feature engineering using technical indicators
3. Split data into training and validation sets
4. Train the specified model type
5. Evaluate model performance
6. Save the trained model and metadata

## Model Types

The service supports the following model types:

- `xgboost` - XGBoost gradient boosting (default)
- `random_forest` - Random Forest classifier
- `lightgbm` - LightGBM gradient boosting

## Running the Service

### Prerequisites

- MongoDB running and accessible
- Sufficient historical data in the database

### Start the Service

```bash
# From the microservice directory
python main.py

# With custom host and port
python main.py --host 0.0.0.0 --port 5002

# With auto-reload for development
python main.py --reload
```

## Docker Deployment

```bash
docker build -t otc-predictor-ml-training .
docker run -p 5002:5002 -e MONGODB_URI="mongodb://host.docker.internal:27017" otc-predictor-ml-training
```
