"""
Extended ModelTrainer with R2 support
"""

import logging
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import sys
from datetime import datetime

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

# ML Libraries
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb
import lightgbm as lgb

from ml_models.model_trainer import ModelTrainer as BaseModelTrainer
from model_storage import ModelStorageManager
from shared.pairs import to_api_asset, normalize_internal

logger = logging.getLogger(__name__)

class ModelTrainerR2(BaseModelTrainer):
    """
    Extended ModelTrainer with R2 support - Optimized for USD/BRL(OTC)
    """
    
    def __init__(self, mongodb_manager=None):
        super().__init__(mongodb_manager)
        self.model_storage_manager = None
        
        # Enhanced parameters for USD/BRL(OTC) trading
        self.test_size = 0.15  # Smaller test size to use more data for training
        self.cv_folds = 5      # Cross-validation folds
        self.is_optimized_for_usd_brl = True  # Flag for USD/BRL specific optimizations
        
        # Always use R2 storage
        from config import STORAGE_CONFIG
        STORAGE_CONFIG["type"] = "r2"  # Force R2 storage
        
    async def list_trained_models(self) -> List[Dict]:
        """List all trained models with their metadata"""
        if self.model_storage_manager:
            try:
                # Use model_storage_manager to list models (async)
                models = await self.model_storage_manager.list_models()
                logger.info(f"✅ Listed {len(models)} models from storage")
                return models
            except Exception as e:
                logger.error(f"❌ Error listing models from storage: {str(e)}")
                # Fall back to local listing if there's an error
                return super().list_trained_models()
        else:
            # Fall back to local listing if model_storage_manager is not set
            return super().list_trained_models()
    
    async def load_model(self, model_id: str) -> Tuple[Any, Any, Dict]:
        """Load a trained model with its scaler and metadata"""
        if self.model_storage_manager:
            try:
                # Use model_storage_manager to load model (async)
                model, scaler, metadata = await self.model_storage_manager.load_model_by_id(model_id)
                logger.info(f"✅ Loaded model {model_id} from storage")
                
                # Ensure metadata is a dictionary
                if metadata is None:
                    logger.warning(f"⚠️ Model {model_id} has no metadata, creating default metadata")
                    metadata = {
                        'model_name': model_id,
                        'algorithm': 'unknown',
                        'trading_pair': 'unknown',
                        'loaded_at': datetime.utcnow().isoformat(),
                        'metrics': {'accuracy': 0.5}
                    }
                elif not isinstance(metadata, dict):
                    logger.warning(f"⚠️ Model {model_id} has invalid metadata format, converting to dict")
                    metadata = {
                        'model_name': model_id,
                        'algorithm': 'unknown',
                        'trading_pair': 'unknown',
                        'loaded_at': datetime.utcnow().isoformat(),
                        'metrics': {'accuracy': 0.5}
                    }
                
                # Ensure essential fields exist
                metadata.setdefault('model_name', model_id)
                metadata.setdefault('loaded_at', datetime.utcnow().isoformat())
                
                return model, scaler, metadata
            except Exception as e:
                logger.error(f"❌ Error loading model from storage: {str(e)}")
                # Fall back to local loading if there's an error
                return super().load_model(model_id)
        else:
            # Fall back to local loading if model_storage_manager is not set
            return super().load_model(model_id)
            
    async def train_model(self, trading_pair: str, model_type: str = "xgboost") -> Dict:
        """
        Train a single ML model for USD/BRL(OTC) with optimized parameters
        
        Args:
            trading_pair: Trading pair to train on (e.g., "USD/BRL(OTC)")
            model_type: Type of model to train (e.g., "xgboost", "random_forest", "lightgbm")
        
        Returns:
            Dictionary with model results or None if training failed
        """
        # Ensure we're using the enhanced feature engineering for USD/BRL(OTC)
        if hasattr(self.feature_engineer, 'is_optimized_for_usd_brl'):
            self.feature_engineer.is_optimized_for_usd_brl = True
        
        # Normalize: API asset for data retrieval, internal key for metadata
        api_pair = to_api_asset(trading_pair) or trading_pair
        internal_pair = normalize_internal(trading_pair) or trading_pair
            
        logger.info(f"🧠 Training optimized {model_type} model for {trading_pair} (api={api_pair}, internal={internal_pair})")
        
        # Train just the specified model type with increased data limit for better accuracy
        results = await self.train_models(
            trading_pair=api_pair,
            algorithms=[model_type],
            data_limit=5000  # Increased data limit for USD/BRL(OTC)
        )
        
        # Return the result for the specific model
        if model_type in results:
            return results[model_type]
        else:
            logger.error(f"❌ Failed to train {model_type} for {trading_pair}")
            return None
    
    async def train_models(self, trading_pair: str = "USD/BRL(OTC)", 
                          algorithms: List[str] = None, 
                          data_limit: int = 5000) -> Dict[str, Dict]:
        """
        Train multiple ML models on historical data - Enhanced for USD/BRL(OTC)
        
        Args:
            trading_pair: Trading pair to train on
            algorithms: List of algorithms to train (default: all)
            data_limit: Maximum number of candles to use for training
            
        Returns:
            Dictionary with training results for each algorithm
        """
        
        # Normalize input just for logging clarity
        api_pair = to_api_asset(trading_pair) or trading_pair
        internal_pair = normalize_internal(trading_pair) or trading_pair
        logger.info(f"🚀 Starting optimized model training for {trading_pair} (api={api_pair}, internal={internal_pair})")
        
        # Ensure we're using the enhanced feature engineering for USD/BRL(OTC)
        if hasattr(self.feature_engineer, 'is_optimized_for_usd_brl'):
            self.feature_engineer.is_optimized_for_usd_brl = True
        
        # Call the base class method to train models
        # Delegate to base with API pair for data retrieval
        results = await super().train_models(api_pair, algorithms, data_limit)
        
        if not results:
            logger.error("❌ Base model training failed")
            return {}
        
        # For each trained model, save to R2 storage
        for algorithm, result in results.items():
            if 'model' in result and 'metrics' in result:
                try:
                    # Save model to R2 storage
                    model_id = await self._save_model_to_r2(
                        result['model'], 
                        result.get('scaler'),  # Get scaler if available
                        algorithm, 
                        internal_pair, 
                        result['metrics']
                    )
                    
                    # Update result with model_id
                    result['model_id'] = model_id
                    result['storage'] = 'r2'
                    
                    logger.info(f"✅ Saved {algorithm} model to R2: {model_id}")
                except Exception as e:
                    logger.error(f"❌ Error saving {algorithm} model to R2: {str(e)}")
        
        return results
    
    async def _save_model_to_r2(self, model: Any, scaler: Any, algorithm: str,
                              trading_pair: str, metrics: Dict[str, float]) -> str:
        """Save trained model to R2 storage"""
        if not self.model_storage_manager:
            logger.error("❌ Model storage manager not initialized")
            # Fall back to local saving
            return await super()._save_model(model, scaler, algorithm, trading_pair, metrics)
        
        try:
            # Save model to R2
            model_id = await self.model_storage_manager.save_model(
                model=model,
                scaler=scaler,
                algorithm=algorithm,
                trading_pair=trading_pair,
                metrics=metrics,
                is_optimized_for_usd_brl=True  # Mark as optimized for USD/BRL
            )
            
            logger.info(f"💾 Model saved to R2: {model_id}")
            return model_id
        except Exception as e:
            logger.error(f"❌ Error saving model to R2: {str(e)}")
            # Fall back to local saving
            return await super()._save_model(model, scaler, algorithm, trading_pair, metrics)
    
    def _create_random_forest(self) -> Any:
        """Create Random Forest model with parameters optimized for USD/BRL(OTC)"""
        if self.is_optimized_for_usd_brl:
            # Enhanced parameters for USD/BRL(OTC)
            return RandomForestClassifier(
                n_estimators=200,           # More trees for better accuracy
                max_depth=12,               # Deeper trees to capture complex patterns
                min_samples_split=4,        # Balanced to prevent overfitting
                min_samples_leaf=2,         # Balanced to prevent overfitting
                class_weight='balanced',    # Handle class imbalance
                random_state=self.random_state,
                n_jobs=-1                   # Use all available cores
            )
        else:
            # Use base implementation
            return super()._create_random_forest()
    
    def _create_xgboost(self) -> Any:
        """Create XGBoost model with parameters optimized for USD/BRL(OTC)"""
        if self.is_optimized_for_usd_brl:
            # Enhanced parameters for USD/BRL(OTC)
            return xgb.XGBClassifier(
                n_estimators=200,           # More trees for better accuracy
                max_depth=7,                # Slightly deeper trees
                learning_rate=0.05,         # Lower learning rate for better generalization
                subsample=0.8,              # Prevent overfitting
                colsample_bytree=0.8,       # Prevent overfitting
                scale_pos_weight=1.0,       # Handle class imbalance
                min_child_weight=3,         # Prevent overfitting
                gamma=0.1,                  # Minimum loss reduction for split
                random_state=self.random_state,
                eval_metric='logloss'
            )
        else:
            # Use base implementation
            return super()._create_xgboost()
    
    def _create_lightgbm(self) -> Any:
        """Create LightGBM model with parameters optimized for USD/BRL(OTC)"""
        if self.is_optimized_for_usd_brl:
            # Enhanced parameters for USD/BRL(OTC)
            return lgb.LGBMClassifier(
                n_estimators=200,           # More trees for better accuracy
                max_depth=7,                # Slightly deeper trees
                learning_rate=0.05,         # Lower learning rate for better generalization
                subsample=0.8,              # Prevent overfitting
                colsample_bytree=0.8,       # Prevent overfitting
                class_weight='balanced',    # Handle class imbalance
                num_leaves=31,              # Control tree complexity
                reg_alpha=0.1,              # L1 regularization
                reg_lambda=0.1,             # L2 regularization
                random_state=self.random_state,
                verbosity=-1
            )
        else:
            # Use base implementation
            return super()._create_lightgbm()
