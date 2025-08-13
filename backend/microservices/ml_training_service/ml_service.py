"""
Optimized ML Training Service for OTC Predictor
Uses XGBoost as the primary model with advanced feature engineering
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import os
import sys

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from database.mongodb_models import MongoDBManager
from ml_models.xgboost_trainer import XGBoostTrainer
from ml_models.feature_engineering import FeatureEngineer
from config import MODEL_RETRAIN_INTERVAL, MIN_TRAINING_SAMPLES

# Import storage service
from storage import ModelStorageService

# Set up logging
logger = logging.getLogger(__name__)

class OptimizedMLService:
    """
    Optimized ML Service using XGBoost with advanced feature engineering
    
    This service handles:
    - Training XGBoost models with optimized parameters
    - Retraining based on data thresholds and market volatility
    - Model storage and retrieval
    - Feature engineering with composite indicators
    """
    
    def __init__(self, mongodb_manager: MongoDBManager = None):
        """Initialize the ML service"""
        self.mongodb = mongodb_manager or MongoDBManager()
        
        # Config
        self.config = {
            'retraining_enabled': True,
            'retraining_interval_hours': 24,
            'min_samples_for_retraining': 100,
            'volatility_threshold': 0.02,
            'data_limit': 2000,
            'auto_training_enabled': True,
            'trading_pairs': [],
            'use_cloud_storage': True  # Default to using cloud storage
        }
        
        # Initialize XGBoost trainer with proper storage configuration
        self.xgboost_trainer = XGBoostTrainer(self.mongodb)
        self.feature_engineer = FeatureEngineer(self.mongodb)
        
        # Training status tracking
        self.training_status = {}
        self.active_training_tasks = {}
        
        # Initialize storage service for direct access if needed
        self.storage_service = ModelStorageService(
            storage_type="r2",
            config={
                "access_key": os.environ.get("R2_ACCESS_KEY"),
                "secret_key": os.environ.get("R2_SECRET_KEY"),
                "endpoint_url": os.environ.get("R2_ENDPOINT_URL"),
                "bucket_name": os.environ.get("R2_BUCKET_NAME", "quotex")
            }
        )
        
        logger.info("🚀 Optimized ML Service initialized")
    
    async def start(self):
        """Start the ML service"""
        await self.mongodb.connect()
        
        # Log storage configuration
        if self.config['use_cloud_storage']:
            logger.info("☁️ Using cloud storage (R2) for model saving/loading")
            # Ensure XGBoost trainer is using cloud storage
            if not hasattr(self.xgboost_trainer, 'storage_service') or \
               self.xgboost_trainer.storage_service.storage_type != 'r2':
                logger.warning("⚠️ XGBoost trainer not properly configured for cloud storage, reconfiguring...")
                self.xgboost_trainer = XGBoostTrainer(self.mongodb)
        else:
            logger.info("📁 Using local storage for model saving/loading")
        
        # Start background retraining task
        if self.config['retraining_enabled']:
            asyncio.create_task(self._background_retraining_task())
        
        logger.info("✅ Optimized ML Service started")
    
    async def stop(self):
        """Stop the ML service"""
        # Cancel any active training tasks
        for task in self.active_training_tasks.values():
            task.cancel()
        
        logger.info("🛑 Optimized ML Service stopped")
    
    async def train_model(self, trading_pair: str, background: bool = True) -> Dict:
        """
        Train a model for a specific trading pair
        
        Args:
            trading_pair: Trading pair to train for (e.g., "USD/BRL(OTC)")
            background: Whether to train in the background
            
        Returns:
            Training status information
        """
        # Update training status
        task_id = f"train_{trading_pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.training_status[task_id] = {
            'trading_pair': trading_pair,
            'status': 'starting',
            'start_time': datetime.now(),
            'progress': 0
        }
        
        if background:
            # Start training in background
            task = asyncio.create_task(self._train_model_task(task_id, trading_pair))
            self.active_training_tasks[task_id] = task
            
            return {
                'task_id': task_id,
                'status': 'training_started',
                'trading_pair': trading_pair
            }
        else:
            # Train synchronously
            result = await self._train_model_task(task_id, trading_pair)
            return result
    
    async def _train_model_task(self, task_id: str, trading_pair: str) -> Dict:
        """
        Background task for model training
        
        Args:
            task_id: Task identifier
            trading_pair: Trading pair to train for
            
        Returns:
            Training result
        """
        try:
            # Update status
            self.training_status[task_id]['status'] = 'training'
            
            # Train model
            result = await self.xgboost_trainer.train_model(
                trading_pair=trading_pair,
                data_limit=self.config['data_limit']
            )
            
            # Update status based on result
            if 'error' in result:
                self.training_status[task_id]['status'] = 'failed'
                self.training_status[task_id]['error'] = result['error']
            else:
                self.training_status[task_id]['status'] = 'completed'
                self.training_status[task_id]['model_info'] = result['model_info']
                self.training_status[task_id]['metrics'] = result['metrics']
            
            self.training_status[task_id]['end_time'] = datetime.now()
            self.training_status[task_id]['progress'] = 100
            
            return self.training_status[task_id]
            
        except Exception as e:
            logger.error(f"❌ Error in training task: {str(e)}")
            self.training_status[task_id]['status'] = 'failed'
            self.training_status[task_id]['error'] = str(e)
            self.training_status[task_id]['end_time'] = datetime.now()
            
            return self.training_status[task_id]
        finally:
            # Remove from active tasks
            if task_id in self.active_training_tasks:
                del self.active_training_tasks[task_id]
    
    async def get_training_status(self, task_id: str = None) -> Dict:
        """
        Get status of training tasks
        
        Args:
            task_id: Optional task ID to get status for
            
        Returns:
            Dictionary with training status
        """
        if task_id:
            if task_id in self.training_status:
                return self.training_status[task_id]
            else:
                return {'error': f'Task {task_id} not found'}
        else:
            # Return all training statuses
            return self.training_status
    
    async def list_models(self, trading_pair: str = None) -> List[Dict]:
        """
        List available trained models
        
        Args:
            trading_pair: Optional filter by trading pair
            
        Returns:
            List of model information
        """
        models = []
        
        try:
            if self.config['use_cloud_storage']:
                # Use cloud storage to list models
                logger.info("☁️ Listing models from cloud storage")
                model_list = await self.storage_service.list_models()
                
                for model_metadata in model_list:
                    # Filter by trading pair if specified
                    if trading_pair and model_metadata.get('trading_pair') != trading_pair:
                        continue
                    models.append(model_metadata)
            else:
                # Use local filesystem to list models (legacy approach)
                logger.info("📁 Listing models from local storage")
                # List all model directories
                for model_dir in self.models_dir.iterdir():
                    if not model_dir.is_dir():
                        continue
                    
                    # Check for metadata file
                    metadata_path = model_dir / "metadata.json"
                    if not metadata_path.exists():
                        continue
                    
                    try:
                        # Load metadata
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        
                        # Filter by trading pair if specified
                        if trading_pair and metadata.get('trading_pair') != trading_pair:
                            continue
                        
                        models.append(metadata)
                    except Exception as e:
                        logger.error(f"❌ Error loading metadata for {model_dir.name}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error listing models: {str(e)}")
        
        # Sort by timestamp (newest first)
        models.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return models
    
    async def get_model_details(self, model_name: str) -> Dict:
        """
        Get detailed information about a specific model
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with model details
        """
        try:
            if self.config['use_cloud_storage']:
                # Use cloud storage to get model details
                logger.info(f"☁️ Getting model details from cloud storage: {model_name}")
                try:
                    # Load metadata from cloud storage
                    metadata = await self.storage_service.get_model_metadata(model_name)
                    return metadata
                except Exception as e:
                    logger.error(f"❌ Error loading metadata from cloud storage for {model_name}: {str(e)}")
                    return {'error': f'Error loading metadata from cloud: {str(e)}'}
            else:
                # Use local filesystem (legacy approach)
                logger.info(f"📁 Getting model details from local storage: {model_name}")
                model_dir = self.models_dir / model_name
                
                if not model_dir.exists() or not model_dir.is_dir():
                    return {'error': f'Model {model_name} not found'}
                
                # Check for metadata file
                metadata_path = model_dir / "metadata.json"
                if not metadata_path.exists():
                    return {'error': f'Metadata for model {model_name} not found'}
                
                # Load metadata
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    
                return metadata
        except Exception as e:
            logger.error(f"❌ Error getting model details for {model_name}: {str(e)}")
            return {'error': f'Error loading model details: {str(e)}'}
    
    async def _background_retraining_task(self):
        """Background task for automatic model retraining"""
        logger.info("🔄 Starting background retraining task")
        
        while True:
            try:
                # Sleep first to avoid immediate retraining on startup
                await asyncio.sleep(3600)  # Check every hour
                
                # Get list of trading pairs
                trading_pairs = await self._get_active_trading_pairs()
                
                for trading_pair in trading_pairs:
                    try:
                        # Find latest model for this pair
                        latest_model = await self.xgboost_trainer.find_latest_model(trading_pair)
                        
                        if latest_model:
                            # Get model metadata
                            model_data = await self.xgboost_trainer.load_model(latest_model)
                            
                            if model_data and 'metadata' in model_data:
                                # Check if model should be retrained
                                last_trained = datetime.strptime(
                                    model_data['metadata'].get('timestamp', '20000101_000000'),
                                    "%Y%m%d_%H%M%S"
                                )
                                
                                # Check if enough time has passed since last training
                                time_since_training = datetime.now() - last_trained
                                if time_since_training > timedelta(hours=self.config['retraining_interval_hours']):
                                    # Check if we have enough new data to retrain
                                    should_retrain = await self.xgboost_trainer.check_should_retrain(
                                        trading_pair, last_trained
                                    )
                                    
                                    if should_retrain:
                                        logger.info(f"🔄 Auto-retraining model for {trading_pair}")
                                        await self.train_model(trading_pair, background=True)
                        else:
                            # No model exists, train a new one
                            logger.info(f"🆕 No model found for {trading_pair}, training new model")
                            await self.train_model(trading_pair, background=True)
                    
                    except Exception as e:
                        logger.error(f"❌ Error checking retraining for {trading_pair}: {str(e)}")
            
            except Exception as e:
                logger.error(f"❌ Error in background retraining task: {str(e)}")
    
    async def _get_active_trading_pairs(self) -> List[str]:
        """Get list of active trading pairs from the database"""
        if not self.mongodb.is_connected:
            await self.mongodb.connect()
        
        # Get unique trading pairs from candle data
        cursor = self.mongodb.db.candle_data.distinct("trading_pair")
        trading_pairs = await cursor
        
        return trading_pairs
    
    async def update_config(self, config_updates: Dict) -> Dict:
        """
        Update service configuration
        
        Args:
            config_updates: Dictionary with configuration updates
            
        Returns:
            Updated configuration
        """
        # Update config with new values
        for key, value in config_updates.items():
            if key in self.config:
                self.config[key] = value
        
        # Update trainer config
        self.xgboost_trainer.min_samples_for_retraining = self.config['min_samples_for_retraining']
        self.xgboost_trainer.volatility_threshold = self.config['volatility_threshold']
        
        logger.info(f"⚙️ Configuration updated: {self.config}")
        return self.config
    
    async def get_config(self) -> Dict:
        """
        Get current service configuration
        
        Returns:
            Current configuration
        """
        return self.config
    
    async def get_service_status(self) -> Dict:
        """
        Get comprehensive service status
        
        Returns:
            Dictionary with service status information
        """
        # Count active training tasks
        active_tasks = len(self.active_training_tasks)
        
        # Count total models
        try:
            models = await self.list_models()
            total_models = len(models)
        except Exception as e:
            logger.error(f"❌ Error counting models: {str(e)}")
            total_models = 0
        
        # Get MongoDB status
        mongodb_status = "connected" if self.mongodb.is_connected else "disconnected"
        
        # Calculate uptime
        if hasattr(self, '_start_time'):
            # Handle both datetime and float start times
            if isinstance(self._start_time, datetime):
                uptime = datetime.now() - self._start_time
            elif isinstance(self._start_time, (int, float)):
                # Convert seconds to timedelta
                uptime = timedelta(seconds=asyncio.get_event_loop().time() - self._start_time)
            else:
                uptime = timedelta(0)
                logger.warning(f"⚠️ Unknown start time type: {type(self._start_time)}")
        else:
            uptime = timedelta(0)
        
        return {
            'status': 'running',
            'uptime': str(uptime),
            'mongodb_status': mongodb_status,
            'active_training_tasks': active_tasks,
            'total_models': total_models,
            'config': self.config
        }
    
    async def train_all_models(self, force_retrain: bool = False) -> Dict:
        """
        Train models for all active trading pairs
        
        Args:
            force_retrain: Whether to force retraining even if recent models exist
            
        Returns:
            Dictionary with training status for each pair
        """
        # Get list of trading pairs
        trading_pairs = await self._get_active_trading_pairs()
        
        if not trading_pairs:
            return {'error': 'No active trading pairs found'}
        
        results = {}
        
        for trading_pair in trading_pairs:
            # Check if we should retrain
            should_train = force_retrain
            
            if not should_train:
                # Find latest model
                latest_model = await self.xgboost_trainer.find_latest_model(trading_pair)
                
                if not latest_model:
                    # No model exists, train a new one
                    should_train = True
                else:
                    # Check if model should be retrained
                    model_data = await self.xgboost_trainer.load_model(latest_model)
                    
                    if model_data and 'metadata' in model_data:
                        last_trained = datetime.strptime(
                            model_data['metadata'].get('timestamp', '20000101_000000'),
                            "%Y%m%d_%H%M%S"
                        )
                        
                        # Check if enough time has passed
                        time_since_training = datetime.now() - last_trained
                        if time_since_training > timedelta(hours=self.config['retraining_interval_hours']):
                            should_train = True
            
            if should_train:
                # Train model
                result = await self.train_model(trading_pair, background=True)
                results[trading_pair] = result
            else:
                results[trading_pair] = {'status': 'skipped', 'reason': 'recent model exists'}
        
        return results
