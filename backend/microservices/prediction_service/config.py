"""
Configuration for ML Training Service
"""

import os
from pathlib import Path

# Trading Configuration
# Focusing exclusively on USD/BRL(OTC) for improved prediction accuracy
DEFAULT_TRADING_PAIRS = [
    "USD/BRL(OTC)"
]

# Disabled pairs (kept for reference)
# DISABLED_PAIRS = [
#     "NZD/CAD(OTC)",
#     "USD/BDT(OTC)",
#     "USD/EGP(OTC)"
# ]

# ML Model Configuration - Enhanced for USD/BRL(OTC)
MODEL_RETRAIN_INTERVAL = int(os.environ.get("MODEL_RETRAIN_INTERVAL", "12"))  # hours (more frequent retraining)
MIN_TRAINING_SAMPLES = int(os.environ.get("MIN_TRAINING_SAMPLES", "50"))  # reduced minimum samples for faster adaptation
PREDICTION_CONFIDENCE_THRESHOLD = float(os.environ.get("PREDICTION_CONFIDENCE_THRESHOLD", "0.60"))  # increased confidence threshold
MODEL_CACHE_TTL = 300  # Model cache time-to-live in seconds (5 minutes)
FEATURE_CACHE_TTL = 60  # Feature cache time-to-live in seconds (1 minute)
ENSEMBLE_PREDICTION = True  # Use ensemble prediction (combine multiple models)
PREDICTION_HISTORY_LENGTH = 10  # Number of past predictions to keep for trend analysis
TECHNICAL_INDICATORS_WEIGHT = 0.7  # Weight for technical indicators vs price action

# R2 Storage Configuration
R2_CONFIG = {
    "access_key": os.environ.get("R2_ACCESS_KEY", "d9a6fe72723211dee3e123b32a25ebba"),
    "secret_key": os.environ.get("R2_SECRET_KEY", "205483e352a6af41c9dc40022dfe3eedba21422a7e393f8d155fae1dd128ce75"),
    "endpoint_url": os.environ.get("R2_ENDPOINT_URL", "https://dffe00b2c327c69b4a869d74b4e7a2a2.r2.cloudflarestorage.com"),
    "bucket_name": os.environ.get("R2_BUCKET_NAME", "quotex"),
    "account_id": os.environ.get("R2_ACCOUNT_ID", "dffe00b2c327c69b4a869d74b4e7a2a2"),
}

# Storage Configuration
STORAGE_CONFIG = {
    "type": os.environ.get("STORAGE_TYPE", "r2"),  # "local" or "r2" - Default to R2 storage
    "local_dir": os.environ.get("LOCAL_STORAGE_DIR", str(Path(__file__).parent.parent.parent / "trained_models")),
    "r2": R2_CONFIG,
}

# Model Versioning Configuration
MODEL_VERSIONING = {
    "enable_versioning": True,
    "max_versions_per_model": 5,  # Keep only the 5 most recent versions of each model
    "version_naming": "timestamp",  # "semantic" or "timestamp"
}

# Data Retention Configuration
DATA_RETENTION = {
    "retention_days": int(os.environ.get("DATA_RETENTION_DAYS", "90")),  # Keep data for 90 days by default
    "enable_auto_cleanup": True,  # Automatically clean up old data
    "cleanup_interval_hours": 24,  # Run cleanup every 24 hours
}