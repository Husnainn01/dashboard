# Model Storage and Data Retention

This document explains how model storage and data retention work in the OTC Predictor system.

## Model Storage

OTC Predictor supports two storage backends for trained ML models:

1. **Local Storage** - Models are saved to the local filesystem
2. **Cloudflare R2 Storage** - Models are saved to Cloudflare R2 (S3-compatible storage)

### Configuration

Storage configuration is managed in `config.py` and can be overridden with environment variables:

```python
# Storage Configuration
STORAGE_CONFIG = {
    "type": os.environ.get("STORAGE_TYPE", "local"),  # "local" or "r2"
    "local_dir": os.environ.get("LOCAL_STORAGE_DIR", str(Path(__file__).parent.parent.parent / "trained_models")),
    "r2": {
        "access_key": os.environ.get("R2_ACCESS_KEY"),
        "secret_key": os.environ.get("R2_SECRET_KEY"),
        "endpoint_url": os.environ.get("R2_ENDPOINT_URL"),
        "bucket_name": os.environ.get("R2_BUCKET_NAME", "quotex"),
        "account_id": os.environ.get("R2_ACCOUNT_ID"),
    },
}
```

### Model Versioning

Models are automatically versioned when saved. The versioning system keeps track of:

- Trading pair
- Algorithm type
- Training date
- Performance metrics
- Dataset information

By default, the system keeps the 5 most recent versions of each model. Older versions are automatically deleted.

### API Endpoints

The ML Training Service provides the following endpoints for managing model storage:

- `GET /models` - List all trained models (both local and cloud)
- `GET /models/{trading_pair}` - List models for a specific trading pair
- `GET /storage/config` - Get current storage configuration
- `POST /storage/config` - Update storage configuration

## Data Retention

To prevent MongoDB from growing too large, OTC Predictor implements a data retention policy that automatically deletes old data.

### Configuration

Data retention configuration is managed in `config.py` and can be overridden with environment variables:

```python
# Data Retention Configuration
DATA_RETENTION = {
    "retention_days": int(os.environ.get("DATA_RETENTION_DAYS", "90")),  # Keep data for 90 days by default
    "enable_auto_cleanup": True,  # Automatically clean up old data
    "cleanup_interval_hours": 24,  # Run cleanup every 24 hours
}
```

### How It Works

1. **TTL Indexes** - MongoDB TTL (Time-To-Live) indexes are created on the `timestamp` field of collections
2. **Automatic Cleanup** - A background task runs periodically to delete data older than the retention period
3. **Manual Cleanup** - You can also trigger cleanup manually through the API

### API Endpoints

The ML Training Service provides the following endpoints for managing data retention:

- `GET /retention/config` - Get current data retention configuration
- `POST /retention/config` - Update data retention configuration
- `POST /retention/cleanup` - Run manual data cleanup
- `GET /retention/status` - Get data retention status

## Setting Up Cloudflare R2 Storage

To use Cloudflare R2 for model storage:

1. Create a `.env` file in the `ml_training_service` directory based on `.env.example`
2. Set `STORAGE_TYPE=r2`
3. Fill in your R2 credentials:
   - `R2_ACCESS_KEY`
   - `R2_SECRET_KEY`
   - `R2_ENDPOINT_URL`
   - `R2_BUCKET_NAME`
   - `R2_ACCOUNT_ID`

Alternatively, you can update the configuration through the API:

```bash
curl -X POST http://localhost:5002/storage/config \
  -H "Content-Type: application/json" \
  -d '{
    "storage_type": "r2",
    "r2_config": {
      "access_key": "your_access_key",
      "endpoint_url": "your_endpoint_url",
      "bucket_name": "your_bucket_name",
      "account_id": "your_account_id"
    }
  }'
```

## Updating Data Retention Policy

You can update the data retention policy through the API:

```bash
curl -X POST http://localhost:5002/retention/config \
  -H "Content-Type: application/json" \
  -d '{
    "retention_days": 30,
    "enable_auto_cleanup": true,
    "cleanup_interval_hours": 12
  }'
```

## Checking Storage and Retention Status

To check the current status:

```bash
# Check storage configuration
curl http://localhost:5002/storage/config

# Check data retention status
curl http://localhost:5002/retention/status
```
