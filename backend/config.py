"""
Configuration settings for OTC Predictor Backend
"""

import os

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', '')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'otc_predictor')

# PyQuotex Settings
QUOTEX_EMAIL = os.getenv('QUOTEX_EMAIL', '')
QUOTEX_PASSWORD = os.getenv('QUOTEX_PASSWORD', '')

# Development Settings
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Trading Settings
DEFAULT_TIMEFRAME = 60  # seconds (1 minute)
DEFAULT_TRADING_PAIRS = [
    'BRLUSD_otc'
]

# ML Model Settings
MODEL_RETRAIN_INTERVAL = 3600  # seconds (1 hour)
MIN_TRAINING_SAMPLES = 100  # Temporarily reduced from 1000 to allow training with limited data
PREDICTION_CONFIDENCE_THRESHOLD = 0.7

if MONGODB_URI:
    print(f"✅ Configuration loaded - MongoDB: {'Atlas' if 'mongodb+srv' in MONGODB_URI else 'Local'}")
else:
    print("⚠️ Configuration loaded - MONGODB_URI not set")