"""
Test script for the Optimized ML Training Service
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import local modules
from database.mongodb_models import MongoDBManager
from ml_models.xgboost_trainer import XGBoostTrainer
from ml_models.feature_engineering import FeatureEngineer
from ml_service import OptimizedMLService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def test_ml_service():
    """Test the optimized ML service"""
    logger.info("🚀 Starting test of Optimized ML Service")
    
    # Set up R2 environment variables for cloud storage
    logger.info("☁️ Setting up R2 environment variables...")
    os.environ["R2_ACCESS_KEY"] = "d9a6fe72723211dee3e123b32a25ebba"  # Replace with your actual R2 access key
    os.environ["R2_SECRET_KEY"] = "205483e352a6af41c9dc40022dfe3eedba21422a7e393f8d155fae1dd128ce75"  # Replace with your actual R2 secret key
    os.environ["R2_ENDPOINT_URL"] = "https://dffe00b2c327c69b4a869d74b4e7a2a2.r2.cloudflarestorage.com"  # Replace with your R2 endpoint
    os.environ["R2_BUCKET_NAME"] = "quotex"  # Replace with your R2 bucket name
    
    logger.info("✅ R2 environment variables set")
    
    # Initialize MongoDB connection
    logger.info("🔌 Connecting to MongoDB...")
    mongodb_uri = "mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor"
    mongodb_manager = MongoDBManager(uri=mongodb_uri)
    
    if not await mongodb_manager.connect():
        logger.error("❌ Failed to connect to MongoDB")
        return
    
    logger.info("✅ MongoDB connected successfully")
    
    # Initialize ML service with cloud storage configuration
    logger.info("🧠 Initializing Optimized ML Service...")
    ml_service = OptimizedMLService(mongodb_manager)
    
    # Configure cloud storage
    logger.info("☁️ Configuring cloud storage...")
    ml_service.config["use_cloud_storage"] = True
    
    # Set start time as datetime object for proper uptime calculation
    ml_service._start_time = datetime.now()
    logger.info(f"🕒 Setting service start time: {ml_service._start_time}")
    
    await ml_service.start()
    
    # Test listing active trading pairs
    logger.info("📋 Getting active trading pairs...")
    trading_pairs = await ml_service._get_active_trading_pairs()
    logger.info(f"Found {len(trading_pairs)} active trading pairs: {trading_pairs}")
    
    if not trading_pairs:
        logger.warning("⚠️ No active trading pairs found")
        test_pair = "USDBRL OTC"
        logger.info(f"Using test pair: {test_pair}")
    else:
        test_pair = trading_pairs[0]
        logger.info(f"Using first pair for testing: {test_pair}")
    
    # Test model training
    logger.info(f"🏋️ Training model for {test_pair}...")
    training_result = await ml_service.train_model(
        trading_pair=test_pair,
        background=False
    )
    
    if 'error' in training_result:
        logger.error(f"❌ Training failed: {training_result['error']}")
    else:
        logger.info(f"✅ Training completed: {training_result['status']}")
        
        # Test listing models
        logger.info("📋 Listing trained models...")
        models = await ml_service.list_models(trading_pair=test_pair)
        logger.info(f"Found {len(models)} models for {test_pair}")
        
        if models:
            # Test getting model details
            model_name = models[0].get('model_name')
            logger.info(f"📊 Getting details for model {model_name}...")
            model_details = await ml_service.get_model_details(model_name)
            logger.info(f"Model details: {model_details}")
    
    # Test service status
    logger.info("📊 Getting service status...")
    ml_service._start_time = asyncio.get_event_loop().time()
    status = await ml_service.get_service_status()
    logger.info(f"Service status: {status}")
    
    # Test config update
    logger.info("⚙️ Testing config update...")
    config_updates = {
        'retraining_interval_hours': 12,
        'min_samples_for_retraining': 50
    }
    updated_config = await ml_service.update_config(config_updates)
    logger.info(f"Updated config: {updated_config}")
    
    # Clean up
    logger.info("🧹 Cleaning up...")
    await ml_service.stop()
    await mongodb_manager.disconnect()
    
    logger.info("✅ Test completed successfully")

if __name__ == "__main__":
    asyncio.run(test_ml_service())
