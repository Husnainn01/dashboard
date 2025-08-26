"""
Configuration for Data Collection Service
"""

import os
from pathlib import Path

# Trading Configuration
# Focusing exclusively on USD/BRL(OTC) for improved prediction accuracy
DEFAULT_TRADING_PAIRS = [
    "BRLUSD_otc"
]

# Disabled pairs (kept for reference)
# DISABLED_PAIRS = [
#     "NZD/CAD(OTC)",
#     "USD/BDT(OTC)",
#     "USD/EGP(OTC)"
# ]

# PyQuotex Settings
QUOTEX_EMAIL = os.getenv('QUOTEX_EMAIL', 'husnain.shafique234@gmail.com')
QUOTEX_PASSWORD = os.getenv('QUOTEX_PASSWORD', 'May4732@123@')

# Data Collection Settings - Optimized for USD/BRL(OTC)
DATA_COLLECTION_INTERVAL = int(os.environ.get("DATA_COLLECTION_INTERVAL", "30"))  # seconds (more frequent collection)
DEFAULT_TIMEFRAME = int(os.environ.get("DEFAULT_TIMEFRAME", "60"))  # seconds (1 minute)
HISTORICAL_DATA_DAYS = int(os.environ.get("HISTORICAL_DATA_DAYS", "180"))  # Collect 6 months of historical data on startup
DATA_QUALITY_CHECKS = True  # Enable data quality checks
RETRY_ON_ERROR = True  # Retry data collection on error
MAX_RETRIES = 3  # Maximum number of retries

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
    "type": os.environ.get("STORAGE_TYPE", "local"),  # "local" or "r2"
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
    "retention_days": int(os.environ.get("DATA_RETENTION_DAYS", "210")),  # Keep data for ~7 months by default
    "enable_auto_cleanup": True,  # Automatically clean up old data
    "cleanup_interval_hours": 24,  # Run cleanup every 24 hours
}