"""
Optimized XGBoost Trainer for OTC Predictor
Specialized XGBoost implementation with advanced features for trading predictions
"""

import numpy as np
import pandas as pd
import xgboost as xgb
import logging
import os
import joblib
import json
import pickle
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager
from ml_models.feature_engineering import FeatureEngineer

# Import model storage service
sys.path.append(str(Path(__file__).parent.parent / "microservices/ml_training_service"))
from storage import ModelStorageService
from shared.pairs import to_api_asset, normalize_internal

logger = logging.getLogger(__name__)

class XGBoostTrainer:
    """
    Optimized XGBoost Trainer with specialized parameters for trading predictions
    """
    
    def __init__(self, mongodb_manager: MongoDBManager = None):
        """Initialize the XGBoost trainer"""
        self.mongodb = mongodb_manager or MongoDBManager()
        self.feature_engineer = FeatureEngineer(self.mongodb)
        
        # Initialize cloud storage service (R2)
        self.storage_service = ModelStorageService(
            storage_type="r2",
            config={
                "access_key": os.environ.get("R2_ACCESS_KEY"),
                "secret_key": os.environ.get("R2_SECRET_KEY"),
                "endpoint_url": os.environ.get("R2_ENDPOINT_URL"),
                "bucket_name": os.environ.get("R2_BUCKET_NAME", "quotex")
            }
        )
        
        # Training parameters
        self.test_size = 0.2
        self.random_state = 42
        self.cv_folds = 5
        
        # XGBoost parameters - optimized for trading
        self.default_params = {
            'n_estimators': 200,           # More trees for better performance
            'max_depth': 6,                # Moderate depth to avoid overfitting
            'learning_rate': 0.05,         # Lower learning rate for better generalization
            'subsample': 0.8,              # Prevent overfitting
            'colsample_bytree': 0.8,       # Feature subsampling
            'min_child_weight': 3,         # Controls overfitting
            'gamma': 0.1,                  # Minimum loss reduction for split
            'reg_alpha': 0.1,              # L1 regularization
            'reg_lambda': 1.0,             # L2 regularization
            'scale_pos_weight': 1.0,       # Balance positive/negative weights
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'random_state': 42,
            'use_label_encoder': False,    # Avoid warning in newer XGBoost versions
            'n_jobs': -1                   # Use all cores
        }
        
        # Retraining thresholds
        self.min_samples_for_training = 500
        self.min_samples_for_retraining = 100
        self.volatility_threshold = 0.02   # 2% price change triggers retraining
        
    async def create_model(self, params: Dict = None) -> xgb.XGBClassifier:
        """
        Create XGBoost model with optimized parameters
        
        Args:
            params: Optional parameter overrides
            
        Returns:
            XGBoost classifier model
        """
        # Use default params with any overrides
        model_params = self.default_params.copy()
        if params:
            model_params.update(params)
            
        return xgb.XGBClassifier(**model_params)
    
    async def train_model(self, trading_pair: str, data_limit: int = 2000) -> Dict:
        """
        Train XGBoost model for a specific trading pair
        
        Args:
            trading_pair: Trading pair to train on (e.g., "USD/BRL(OTC)")
            data_limit: Maximum number of candles to use for training
            
        Returns:
            Dictionary with model results or None if training failed
        """
        # Normalize trading pair usage
        api_pair = to_api_asset(trading_pair) or trading_pair
        internal_pair = normalize_internal(trading_pair) or trading_pair
        logger.info(f"🧠 Training XGBoost model for {trading_pair} (api={api_pair}, internal={internal_pair})")
        
        # Prepare training data
        logger.info("📊 Preparing training data...")
        features_df, targets_df = await self.feature_engineer.prepare_training_data(
            trading_pair=api_pair, limit=data_limit
        )
        
        if features_df.empty or targets_df.empty:
            logger.error("❌ No training data available")
            return {'error': 'No training data available'}
        
        # Check minimum samples requirement
        if len(features_df) < self.min_samples_for_training:
            logger.warning(f"⚠️ Insufficient data: {len(features_df)} samples (need {self.min_samples_for_training})")
            return {'error': f'Insufficient data: {len(features_df)} samples'}
        
        logger.info(f"✅ Training data ready: {features_df.shape[0]} samples, {features_df.shape[1]} features")
        
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features_df, targets_df['target'], 
                test_size=self.test_size, 
                random_state=self.random_state,
                stratify=targets_df['target']
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Create and train model
            model = await self.create_model()
            
            # Train with early stopping
            eval_set = [(X_train_scaled, y_train), (X_test_scaled, y_test)]
            model.fit(
                X_train_scaled, y_train,
                eval_set=eval_set,
                eval_metric='logloss',
                early_stopping_rounds=20,
                verbose=False
            )
            
            # Make predictions
            y_pred = model.predict(X_test_scaled)
            y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            
            # Calculate metrics
            metrics = await self._calculate_metrics(y_test, y_pred, y_pred_proba)
            
            # Get feature importance
            feature_importance = await self._get_feature_importance(model, features_df.columns.tolist())
            
            # Save model
            model_info = await self._save_model(
                model, scaler, internal_pair, metrics, feature_importance
            )
            
            result = {
                'model': model,
                'scaler': scaler,
                'metrics': metrics,
                'feature_importance': feature_importance,
                'model_info': model_info
            }
            
            logger.info(f"✅ XGBoost training completed - Accuracy: {metrics['accuracy']:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error training XGBoost model: {str(e)}")
            return {'error': str(e)}
    
    async def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray, 
                           y_pred_proba: np.ndarray) -> Dict[str, float]:
        """
        Calculate comprehensive model metrics
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_pred_proba: Predicted probabilities
            
        Returns:
            Dictionary of metrics
        """
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred),
            'recall': recall_score(y_true, y_pred),
            'f1': f1_score(y_true, y_pred),
            'roc_auc': roc_auc_score(y_true, y_pred_proba)
        }
        
        # Add confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        
        # Add classification report
        report = classification_report(y_true, y_pred, output_dict=True)
        metrics['classification_report'] = report
        
        return metrics
    
    async def _get_feature_importance(self, model: xgb.XGBClassifier, 
                                feature_names: List[str]) -> Dict[str, float]:
        """
        Extract feature importance from trained model
        
        Args:
            model: Trained XGBoost model
            feature_names: List of feature names
            
        Returns:
            Dictionary of feature importances
        """
        # Get feature importance
        importance = model.feature_importances_
        
        # Create dictionary of feature importance
        feature_importance = {}
        for i, name in enumerate(feature_names):
            if i < len(importance):
                feature_importance[name] = float(importance[i])
        
        # Sort by importance
        feature_importance = dict(sorted(
            feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        ))
        
        return feature_importance
    
    async def _save_model(self, model: xgb.XGBClassifier, scaler: StandardScaler, 
                    trading_pair: str, metrics: Dict, 
                    feature_importance: Dict) -> Dict:
        """
        Save trained model and metadata
        
        Args:
            model: Trained XGBoost model
            scaler: Feature scaler
            trading_pair: Trading pair
            metrics: Model metrics
            feature_importance: Feature importance
            
        Returns:
            Dictionary with model info
        """
        # Ensure internal canonical key is used for naming/metadata
        internal_pair = normalize_internal(trading_pair) or trading_pair
        # Create model name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"xgboost_{internal_pair}_{timestamp}"
        
        # Prepare model data (combine model and scaler)
        model_data = {
            'model': model,
            'scaler': scaler
        }
        
        # Prepare metadata
        metadata = {
            'model_name': model_name,
            'trading_pair': internal_pair,
            'algorithm': 'xgboost',
            'timestamp': timestamp,
            'saved_at': datetime.now().isoformat(),
            'metrics': metrics,
            'feature_importance': feature_importance,
            'parameters': model.get_params()
        }
        
        # Save to cloud storage only (R2)
        try:
            result = await self.storage_service.save_model(
                model_data=model_data,
                metadata=metadata,
                model_id=model_name
            )
            logger.info(f"☁️ Model saved to cloud storage: {model_name}")
            return metadata
        except Exception as e:
            logger.error(f"❌ Error saving model to cloud storage: {str(e)}")
            raise
    
    async def load_model(self, model_name: str) -> Dict:
        """
        Load a trained model with its scaler and metadata
        
        Args:
            model_name: Name of the model to load
            
        Returns:
            Dictionary with model, scaler, and metadata
        """
        try:
            # Load from cloud storage (R2)
            result = await self.storage_service.load_model(model_name)
            
            if not result:
                logger.error(f"❌ Model not found in cloud storage: {model_name}")
                return None
                
            model_data, metadata = result
            
            logger.info(f"☁️ Model loaded from cloud storage: {model_name}")
            
            return {
                'model': model_data['model'],
                'scaler': model_data['scaler'],
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Error loading model {model_name}: {str(e)}")
            return None
    
    async def check_should_retrain(self, trading_pair: str, 
                            last_trained_timestamp: datetime = None) -> bool:
        """
        Check if model should be retrained based on new data and market conditions
        
        Args:
            trading_pair: Trading pair
            last_trained_timestamp: When the model was last trained
            
        Returns:
            Boolean indicating if retraining is recommended
        """
        if not self.mongodb.is_connected:
            await self.mongodb.connect()
        
        # Normalize for DB lookup
        api_pair = to_api_asset(trading_pair) or trading_pair
        internal_pair = normalize_internal(trading_pair) or trading_pair
        
        # Check for new data since last training
        query = {"trading_pair": api_pair}
        if last_trained_timestamp:
            query["timestamp"] = {"$gt": last_trained_timestamp}
        
        # Count new candles
        new_candles_count = await self.mongodb.db.candles.count_documents(query)
        
        # Check if we have enough new data
        if new_candles_count >= self.min_samples_for_retraining:
            logger.info(f"🔄 Retraining recommended: {new_candles_count} new candles")
            return True
        
        # Check for market volatility if we have a last training timestamp
        if last_trained_timestamp:
            # Get recent candles
            recent_candles = await self.mongodb.db.candles.find(
                {"trading_pair": api_pair},
                sort=[("timestamp", -1)],
                limit=100
            ).to_list(length=100)
            
            if recent_candles:
                # Calculate price volatility
                closes = [candle["close"] for candle in recent_candles]
                prices = np.array(closes, dtype=float)
                returns = np.diff(prices) / prices[:-1]
                volatility = np.std(returns)
                
                # Check if volatility exceeds threshold
                if volatility > self.volatility_threshold:
                    logger.info(f"🔄 Retraining recommended: High volatility ({volatility:.4f})")
                    return True
        
        logger.info(f"✅ No retraining needed for {internal_pair}: {new_candles_count} new candles")
        return False
    
    async def find_latest_model(self, trading_pair: str) -> str:
        """
        Find the latest model for a trading pair
        
        Args:
            trading_pair: Trading pair
            
        Returns:
            Model name or None if not found
        """
        try:
            # List models from cloud storage filtered by internal trading pair
            internal_pair = normalize_internal(trading_pair) or trading_pair
            models = await self.storage_service.list_models(trading_pair=internal_pair, algorithm="xgboost")
            
            if not models:
                logger.info(f"No models found for {trading_pair}")
                return None
            
            # Models should already be sorted by saved_at (newest first)
            latest_model = models[0]
            return latest_model.get("model_name")
            
        except Exception as e:
            logger.error(f"❌ Error finding latest model for {trading_pair}: {str(e)}")
            return None
