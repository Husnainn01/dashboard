"""
Configuration settings for OTC Predictor Backend
"""

import os

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc_predictor')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'otc_predictor')

# PyQuotex Settings
QUOTEX_EMAIL = os.getenv('QUOTEX_EMAIL', 'husnain.shafique234@gmail.com')  # Replace with your PyQuotex email
QUOTEX_PASSWORD = os.getenv('QUOTEX_PASSWORD', 'May4732@123@')     # Replace with your PyQuotex password

# Development Settings
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Trading Settings
DEFAULT_TIMEFRAME = 60  # seconds (1 minute)
DEFAULT_TRADING_PAIRS = [
    'USD/BRL(OTC)',  # Priority pair
    'NZD/CAD(OTC)',
    'USD/BDT(OTC)',
    'USD/EGP(OTC)'
]

# ML Model Settings
MODEL_RETRAIN_INTERVAL = 3600  # seconds (1 hour)
MIN_TRAINING_SAMPLES = 100  # Temporarily reduced from 1000 to allow training with limited data
PREDICTION_CONFIDENCE_THRESHOLD = 0.7

print(f"✅ Configuration loaded - MongoDB: {'Atlas' if 'mongodb+srv' in MONGODB_URI else 'Local'}") 