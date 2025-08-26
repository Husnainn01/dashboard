"""
ML Training Service for OTC Predictor
Handles model training, retraining, and management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import os

# FastAPI
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager
from ml_models.xgboost_trainer import XGBoostTrainer
from ml_models.feature_engineering import FeatureEngineer
from config import MODEL_RETRAIN_INTERVAL, MIN_TRAINING_SAMPLES
from shared.pairs import normalize_internal

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MLTrainingService:
    """
    Service for ML model training and management
    
    This service handles:
    - Training new models
    - Retraining models based on data thresholds
    - Model evaluation and selection
    - Model storage and retrieval
    """
    
    def __init__(self):
        """Initialize the ML training service"""
        self.mongodb = MongoDBManager()
        self.xgboost_trainer = XGBoostTrainer(self.mongodb)
        self.feature_engineer = FeatureEngineer(self.mongodb)
        
        # Training status tracking
        self.training_status = {}
        self.active_training_tasks = {}
        
        # Model registry
        self.models_dir = Path(__file__).parent.parent / "trained_models"
        self.models_dir.mkdir(exist_ok=True)
        
        # Config
        self.config = {
            'retraining_enabled': True,
            'retraining_interval_hours': 24,
            'min_samples_for_retraining': 100,
            'volatility_threshold': 0.02,
            'data_limit': 2000
        }
        
        logger.info("🚀 ML Training Service initialized")
    
    async def start(self):
        """Start the ML training service"""
        await self.mongodb.connect()
        
        # Start background retraining task
        if self.config['retraining_enabled']:
            asyncio.create_task(self._background_retraining_task())
        
        logger.info("✅ ML Training Service started")
    
    async def stop(self):
        """Stop the ML training service"""
        # Cancel any active training tasks
        for task in self.active_training_tasks.values():
            task.cancel()
        
        logger.info("🛑 ML Training Service stopped")
    
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
                    
                # Filter by trading pair if specified (normalize to internal canonical)
                if trading_pair:
                    requested_internal = normalize_internal(trading_pair) or trading_pair
                    meta_internal = normalize_internal(metadata.get('trading_pair', '')) or metadata.get('trading_pair')
                    if meta_internal != requested_internal:
                        continue
                    
                models.append(metadata)
            except Exception as e:
                logger.error(f"❌ Error loading metadata for {model_dir.name}: {str(e)}")
        
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
        model_dir = self.models_dir / model_name
        
        if not model_dir.exists() or not model_dir.is_dir():
            return {'error': f'Model {model_name} not found'}
        
        # Check for metadata file
        metadata_path = model_dir / "metadata.json"
        if not metadata_path.exists():
            return {'error': f'Metadata for model {model_name} not found'}
        
        try:
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            return metadata
        except Exception as e:
            logger.error(f"❌ Error loading metadata for {model_name}: {str(e)}")
            return {'error': f'Error loading metadata: {str(e)}'}
    
    async def get_latest_model_info(self, trading_pair: str, algorithm: str = "xgboost") -> Dict:
        """
        Fetch the latest model info for a trading pair from R2 storage.
        Currently supports XGBoost via the XGBoostTrainer helper.
        """
        try:
            if algorithm != "xgboost":
                return {'error': f'Algorithm {algorithm} not supported for latest lookup'}
            latest_model_name = await self.xgboost_trainer.find_latest_model(trading_pair)
            if not latest_model_name:
                return {'error': f'No models found for {trading_pair}'}
            loaded = await self.xgboost_trainer.load_model(latest_model_name)
            if not loaded:
                return {'error': f'Unable to load latest model {latest_model_name}'}
            return {
                'model_name': latest_model_name,
                'metadata': loaded.get('metadata')
            }
        except Exception as e:
            logger.error(f"❌ Error fetching latest model info: {str(e)}")
            return {'error': str(e)}
    
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


# Create FastAPI endpoints for the ML Training Service
def create_ml_training_api(app: FastAPI, ml_training_service: MLTrainingService):
    """
    Create FastAPI endpoints for the ML Training Service
    
    Args:
        app: FastAPI application
        ml_training_service: ML Training Service instance
    """
    
    @app.post("/ml/train")
    async def train_model(
        trading_pair: str = Query(..., description="Trading pair to train for (e.g., 'USD/BRL(OTC)')"),
        background: bool = Query(True, description="Whether to train in the background"),
        background_tasks: BackgroundTasks = BackgroundTasks()
    ):
        """Train a model for a specific trading pair"""
        try:
            result = await ml_training_service.train_model(
                trading_pair=trading_pair,
                background=background
            )
            return result
        except Exception as e:
            logger.error(f"❌ Error in train_model endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error training model: {str(e)}"
            )
    
    @app.get("/ml/status")
    async def get_training_status(task_id: str = None):
        """Get status of training tasks"""
        try:
            result = await ml_training_service.get_training_status(task_id)
            return result
        except Exception as e:
            logger.error(f"❌ Error in get_training_status endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting training status: {str(e)}"
            )
    
    @app.get("/ml/models")
    async def list_models(trading_pair: str = None):
        """List available trained models"""
        try:
            result = await ml_training_service.list_models(trading_pair)
            return result
        except Exception as e:
            logger.error(f"❌ Error in list_models endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listing models: {str(e)}"
            )
    
    @app.get("/ml/models/{model_name}")
    async def get_model_details(model_name: str):
        """Get detailed information about a specific model"""
        try:
            result = await ml_training_service.get_model_details(model_name)
            if 'error' in result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result['error']
                )
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error in get_model_details endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting model details: {str(e)}"
            )
    
    @app.get("/ml/models/latest")
    async def get_latest_model(
        trading_pair: str = Query(..., description="Trading pair, e.g., 'USD/BRL(OTC)'")
    ):
        """Get latest model metadata for a trading pair (algorithm defaults to xgboost)."""
        try:
            result = await ml_training_service.get_latest_model_info(trading_pair=trading_pair, algorithm="xgboost")
            if 'error' in result:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result['error'])
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error in get_latest_model endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting latest model: {str(e)}"
            )
    
    @app.put("/ml/config")
    async def update_config(config_updates: Dict):
        """Update service configuration"""
        try:
            result = await ml_training_service.update_config(config_updates)
            return result
        except Exception as e:
            logger.error(f"❌ Error in update_config endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating config: {str(e)}"
            )
    
    @app.get("/ml/config")
    async def get_config():
        """Get current service configuration"""
        try:
            result = await ml_training_service.get_config()
            return result
        except Exception as e:
            logger.error(f"❌ Error in get_config endpoint: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting config: {str(e)}"
            )
    
    logger.info("✅ ML Training API endpoints registered")
