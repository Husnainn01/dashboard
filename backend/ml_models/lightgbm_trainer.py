"""
Optimized LightGBM Trainer for OTC Predictor
Specialized LightGBM implementation with advanced features for trading predictions
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from sklearn.model_selection import train_test_split
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

class LightGBMTrainer:
    """
    Optimized LightGBM Trainer with specialized parameters for trading predictions
    """

    def __init__(self, mongodb_manager: MongoDBManager = None):
        """Initialize the LightGBM trainer"""
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

        # LightGBM parameters - tuned for classification on trading signals
        self.default_params = {
            'n_estimators': 200,
            'max_depth': -1,
            'learning_rate': 0.05,
            'num_leaves': 31,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.0,
            'reg_lambda': 0.0,
            'random_state': self.random_state,
            'n_jobs': -1,
            'objective': 'binary',
            'verbosity': -1
        }

        # Retraining thresholds
        self.min_samples_for_training = 500
        self.min_samples_for_retraining = 100
        self.volatility_threshold = 0.02

    async def create_model(self, params: Dict = None) -> lgb.LGBMClassifier:
        """Create LightGBM model with default params and overrides"""
        model_params = self.default_params.copy()
        if params:
            model_params.update(params)
        return lgb.LGBMClassifier(**model_params)

    async def train_model(self, trading_pair: str, data_limit: int = 2000) -> Dict:
        """Train LightGBM model for a specific trading pair"""
        api_pair = to_api_asset(trading_pair) or trading_pair
        internal_pair = normalize_internal(trading_pair) or trading_pair
        logger.info(f"🧠 Training LightGBM model for {trading_pair} (api={api_pair}, internal={internal_pair})")

        # Prepare training data
        features_df, targets_df = await self.feature_engineer.prepare_training_data(
            trading_pair=api_pair, limit=data_limit
        )

        if features_df.empty or targets_df.empty:
            logger.error("❌ No training data available")
            return {'error': 'No training data available'}

        if len(features_df) < self.min_samples_for_training:
            logger.warning(f"⚠️ Insufficient data: {len(features_df)} samples (need {self.min_samples_for_training})")
            return {'error': f'Insufficient data: {len(features_df)} samples'}

        try:
            # Split
            X_train, X_test, y_train, y_test = train_test_split(
                features_df, targets_df['target'],
                test_size=self.test_size,
                random_state=self.random_state,
                stratify=targets_df['target']
            )

            # Scale
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Create and train
            model = await self.create_model()
            model.fit(
                X_train_scaled, y_train,
                eval_set=[(X_test_scaled, y_test)],
                eval_metric='logloss',
                verbose=False
            )

            # Predict
            y_pred = model.predict(X_test_scaled)
            # LightGBM's predict returns labels; predict_proba for proba
            y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

            # Metrics
            metrics = await self._calculate_metrics(y_test, y_pred, y_pred_proba)

            # Feature importance
            feature_importance = await self._get_feature_importance(model, features_df.columns.tolist())

            # Save
            model_info = await self._save_model(model, scaler, internal_pair, metrics, feature_importance)

            result = {
                'model': model,
                'scaler': scaler,
                'metrics': metrics,
                'feature_importance': feature_importance,
                'model_info': model_info
            }
            logger.info(f"✅ LightGBM training completed - Accuracy: {metrics['accuracy']:.4f}")
            return result
        except Exception as e:
            logger.error(f"❌ Error training LightGBM model: {str(e)}")
            return {'error': str(e)}

    async def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray, y_pred_proba: np.ndarray) -> Dict[str, float]:
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred),
            'recall': recall_score(y_true, y_pred),
            'f1': f1_score(y_true, y_pred),
            'roc_auc': roc_auc_score(y_true, y_pred_proba)
        }
        cm = confusion_matrix(y_true, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        report = classification_report(y_true, y_pred, output_dict=True)
        metrics['classification_report'] = report
        return metrics

    async def _get_feature_importance(self, model: lgb.LGBMClassifier, feature_names: List[str]) -> Dict[str, float]:
        importance = model.feature_importances_
        feature_importance = {}
        for i, name in enumerate(feature_names):
            if i < len(importance):
                feature_importance[name] = float(importance[i])
        feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))
        return feature_importance

    async def _save_model(self, model: lgb.LGBMClassifier, scaler: StandardScaler, trading_pair: str, metrics: Dict, feature_importance: Dict) -> Dict:
        internal_pair = normalize_internal(trading_pair) or trading_pair
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"lightgbm_{internal_pair}_{timestamp}"

        model_data = {
            'model': model,
            'scaler': scaler
        }
        metadata = {
            'model_name': model_name,
            'trading_pair': internal_pair,
            'algorithm': 'lightgbm',
            'timestamp': timestamp,
            'saved_at': datetime.now().isoformat(),
            'metrics': metrics,
            'feature_importance': feature_importance,
            'parameters': model.get_params()
        }

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

    async def load_model(self, model_name: str) -> Optional[Dict]:
        try:
            result = await self.storage_service.load_model(model_name)
            if not result:
                logger.error(f"❌ Model not found in cloud storage: {model_name}")
                return None
            model_data, metadata = result
            return {
                'model': model_data['model'],
                'scaler': model_data['scaler'],
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"❌ Error loading model {model_name}: {str(e)}")
            return None

    async def check_should_retrain(self, trading_pair: str, last_trained_timestamp: Optional[datetime] = None) -> bool:
        if not self.mongodb.is_connected:
            await self.mongodb.connect()
        api_pair = to_api_asset(trading_pair) or trading_pair
        # New candles since last training
        query = {"trading_pair": api_pair}
        if last_trained_timestamp:
            query["timestamp"] = {"$gt": last_trained_timestamp}
        new_candles = await self.mongodb.db.candles.count_documents(query)
        if new_candles >= self.min_samples_for_retraining:
            return True
        # Optional: add volatility-based retrain logic similar to xgboost_trainer
        return False

    async def find_latest_model(self, trading_pair: str) -> Optional[str]:
        try:
            internal_pair = normalize_internal(trading_pair) or trading_pair
            models = await self.storage_service.list_models(trading_pair=internal_pair, algorithm="lightgbm")
            if not models:
                return None
            latest_model = models[0]
            return latest_model.get("model_name")
        except Exception as e:
            logger.error(f"❌ Error finding latest model for {trading_pair}: {str(e)}")
            return None
