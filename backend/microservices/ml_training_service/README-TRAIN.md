# ML Training Service API Guide

This guide explains how to use the ML Training Service API to train and manage machine learning models.

## Training a Model

To train a new model, send a POST request to the `/train` endpoint with a JSON body containing the training parameters:

```bash
curl -X POST http://localhost:5002/train \
  -H "Content-Type: application/json" \
  -d '{
    "trading_pair": "USD/BRL(OTC)",
    "model_type": "xgboost",
    "data_limit": 2000,
    "force_retrain": false
  }'
```

### Parameters

- `trading_pair` (required): The trading pair to train the model for (e.g., "USD/BRL(OTC)")
- `model_type` (optional): The type of model to train. Options: "xgboost", "random_forest", "lightgbm". Default: "xgboost"
- `force_retrain` (optional): Whether to force retraining even if a model already exists. Default: false

Note: The `data_limit` parameter is defined in the API but not currently supported by the underlying model trainer.

### Response

```json
{
  "job_id": "USD_BRL(OTC)_xgboost_20250807170549",
  "trading_pair": "USD/BRL(OTC)",
  "model_type": "xgboost",
  "status": "queued",
  "submitted_at": "2025-08-07T17:05:49.262646"
}
```

## Checking Training Status

To check the status of a training job, send a GET request to the `/jobs/{job_id}` endpoint:

```bash
curl -X GET http://localhost:5002/jobs/USD_BRL(OTC)_xgboost_20250807170549
```

### Response

```json
{
  "job_id": "USD_BRL(OTC)_xgboost_20250807170549",
  "trading_pair": "USD/BRL(OTC)",
  "model_type": "xgboost",
  "status": "completed",
  "submitted_at": "2025-08-07T17:05:49.262646",
  "completed_at": "2025-08-07T17:06:12.123456",
  "model_path": "trained_models/xgboost_USD_BRL(OTC)_20250807170612"
}
```

## Listing Trained Models

To list all trained models, send a GET request to the `/models` endpoint:

```bash
curl -X GET http://localhost:5002/models
```

### Response

```json
{
  "models": [
    {
      "id": "xgboost_USD_BRL(OTC)_20250807170612",
      "algorithm": "xgboost",
      "trading_pair": "USD/BRL(OTC)",
      "created_at": "2025-08-07T17:06:12.123456",
      "accuracy": 0.76,
      "f1_score": 0.74
    }
  ],
  "count": 1
}
```

## Getting Models for a Specific Trading Pair

To get models for a specific trading pair, send a GET request to the `/models/{trading_pair}` endpoint:

```bash
curl -X GET http://localhost:5002/models/USD%2FBRL%28OTC%29
```

### Response

```json
{
  "trading_pair": "USD/BRL(OTC)",
  "models": [
    {
      "id": "xgboost_USD_BRL(OTC)_20250807170612",
      "algorithm": "xgboost",
      "trading_pair": "USD/BRL(OTC)",
      "created_at": "2025-08-07T17:06:12.123456",
      "accuracy": 0.76,
      "f1_score": 0.74
    }
  ],
  "count": 1
}
```

## Common Issues

### 422 Unprocessable Entity

If you receive a 422 error when trying to train a model, it means the request body is missing or invalid:

```
{"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]}
```

**Solution**: Make sure you're sending a valid JSON body with the required parameters and that you've set the `Content-Type: application/json` header.

### 503 Service Unavailable

If you receive a 503 error, it means the ML service is not properly initialized:

```
{"detail":"ML service not initialized"}
```

**Solution**: Restart the ML Training Service and check the logs for any initialization errors.

### Not Enough Data

If the training fails because there's not enough data:

**Solution**: Make sure the data collection service has been running long enough to collect sufficient data for the specified trading pair.
