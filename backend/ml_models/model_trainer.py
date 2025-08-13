"""
ML Model Training System for OTC Predictor
Supports multiple algorithms: Random Forest, XGBoost, LightGBM, and Neural Networks
"""

import numpy as np
import pandas as pd
import joblib
import json
import os
import io
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from pathlib import Path
import logging

# ML Libraries
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder
import xgboost as xgb
import lightgbm as lgb

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent))
from database.mongodb_models import MongoDBManager, PredictionData
from ml_models.feature_engineering import FeatureEngineer
from config import MODEL_RETRAIN_INTERVAL, MIN_TRAINING_SAMPLES, PREDICTION_CONFIDENCE_THRESHOLD

# Import storage service
sys.path.append(str(Path(__file__).parent.parent / "microservices" / "ml_training_service"))
from storage import ModelStorageService

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    ML Model Training and Management System
    """
    
    def __init__(self, mongodb_manager: MongoDBManager = None):
        self.mongodb = mongodb_manager or MongoDBManager()
        self.feature_engineer = FeatureEngineer(self.mongodb)
        
        # Model storage
        self.models_dir = Path(__file__).parent.parent / "trained_models"
        
        # Initialize storage service for cloud storage
        self.storage_service = ModelStorageService(
            storage_type="r2",
            config={
                "access_key": os.environ.get("R2_ACCESS_KEY"),
                "secret_key": os.environ.get("R2_SECRET_KEY"),
                "endpoint_url": os.environ.get("R2_ENDPOINT_URL"),
                "bucket_name": os.environ.get("R2_BUCKET_NAME", "quotex")
            }
        )
        
        # Flag to control storage behavior
        self.use_cloud_storage = os.environ.get("USE_CLOUD_STORAGE", "true").lower() == "true"
        
        if self.use_cloud_storage:
            logger.info("☁️ ModelTrainer configured to use cloud storage (R2)")
        else:
            logger.info("📁 ModelTrainer configured to use local storage")
        self.models_dir.mkdir(exist_ok=True)
        
        # Available algorithms
        self.algorithms = {
            'random_forest': self._create_random_forest,
            'xgboost': self._create_xgboost,
            'lightgbm': self._create_lightgbm,
            # 'neural_network': self._create_neural_network,  # Add if TensorFlow is installed
        }
        
        # Model performance tracking
        self.model_metrics = {}
        self.feature_importance = {}
        
        # Training parameters
        self.test_size = 0.2
        self.random_state = 42
        self.cv_folds = 5
        
    async def train_model(self, trading_pair: str, model_type: str = "xgboost") -> Dict:
        """
        Train a single ML model for a specific trading pair and model type
        
        This is a convenience wrapper around train_models that trains just one model type
        
        Args:
            trading_pair: Trading pair to train on (e.g., "USD/BRL(OTC)")
            model_type: Type of model to train (e.g., "xgboost", "random_forest")
        
        Returns:
            Dictionary with model results or None if training failed
        """
        # Format trading pair to match how it's stored in MongoDB
        formatted_pair = trading_pair
        
        # Handle USD/BRL(OTC) format
        if '/' in trading_pair and '(' in trading_pair:
            # Convert USD/BRL(OTC) to EURUSD OTC format
            currency_pair = trading_pair.split('(')[0]  # Get USD/BRL
            base, quote = currency_pair.split('/')      # Split into USD and BRL
            
            # MongoDB format is "EURUSD OTC" (not USDBRL)
            # For USD/BRL, we need to check both USDBRL and BRLUSD formats
            if base == "USD":
                formatted_pair = f"{base}{quote} OTC"  # USDBRL OTC
            else:
                formatted_pair = f"{base}{quote} OTC"  # EURUSD OTC
            
        logger.info(f"🧠 Training {model_type} model for {trading_pair} (formatted as {formatted_pair})")
        
        # Train just the specified model type
        results = await self.train_models(
            trading_pair=formatted_pair,
            algorithms=[model_type],
            data_limit=2000
        )
        
        # Return the result for the specific model
        if model_type in results:
            return results[model_type]
        else:
            logger.error(f"❌ Failed to train {model_type} for {trading_pair}")
            return None
    
    async def train_models(self, trading_pair: str = "EURUSD OTC", 
                          algorithms: List[str] = None, 
                          data_limit: int = 2000) -> Dict[str, Dict]:
        """
        Train multiple ML models on historical data
        
        Args:
            trading_pair: Trading pair to train on
            algorithms: List of algorithms to train (default: all)
            data_limit: Maximum number of candles to use for training
            
        Returns:
            Dictionary with training results for each algorithm
        """
        
        logger.info(f"🚀 Starting model training for {trading_pair}")
        
        # Prepare training data
        logger.info("📊 Preparing training data...")
        features_df, targets_df = await self.feature_engineer.prepare_training_data(
            trading_pair=trading_pair, limit=data_limit
        )
        
        if features_df.empty or targets_df.empty:
            logger.error("❌ No training data available")
            return {}
        
        # Check minimum samples requirement (use dynamic config)
        from config import MIN_TRAINING_SAMPLES as min_samples
        if len(features_df) < min_samples:
            logger.warning(f"⚠️ Insufficient data: {len(features_df)} samples (need {min_samples})")
            return {}
        
        logger.info(f"✅ Training data ready: {features_df.shape[0]} samples, {features_df.shape[1]} features")
        
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
        
        # Use specified algorithms or all available
        algorithms_to_train = algorithms or list(self.algorithms.keys())
        
        results = {}
        
        for algorithm in algorithms_to_train:
            if algorithm not in self.algorithms:
                logger.warning(f"⚠️ Unknown algorithm: {algorithm}")
                continue
            
            logger.info(f"🔧 Training {algorithm}...")
            
            try:
                # Train model
                model_result = await self._train_single_model(
                    algorithm, X_train_scaled, X_test_scaled, y_train, y_test,
                    features_df.columns.tolist(), trading_pair
                )
                
                # Save model and scaler
                await self._save_model(
                    model_result['model'], scaler, algorithm, 
                    trading_pair, model_result['metrics']
                )
                
                results[algorithm] = model_result
                logger.info(f"✅ {algorithm} training completed - Accuracy: {model_result['metrics']['accuracy']:.4f}")
                
            except Exception as e:
                logger.error(f"❌ Error training {algorithm}: {str(e)}")
                results[algorithm] = {'error': str(e)}
        
        # Generate training report
        report = await self._generate_training_report(results, trading_pair)
        
        logger.info("🎉 Model training completed!")
        return results
    
    async def _train_single_model(self, algorithm: str, X_train: np.ndarray, X_test: np.ndarray,
                                y_train: pd.Series, y_test: pd.Series, 
                                feature_names: List[str], trading_pair: str) -> Dict:
        """Train a single ML model"""
        
        # Create model
        model = self.algorithms[algorithm]()
        
        # Train model
        model.fit(X_train, y_train)
        
        # Make predictions
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_test, y_pred, y_pred_proba)
        
        # Cross-validation
        cv_scores = cross_val_score(model, X_train, y_train, cv=self.cv_folds, scoring='accuracy')
        metrics['cv_mean'] = cv_scores.mean()
        metrics['cv_std'] = cv_scores.std()
        
        # Feature importance
        importance = self._get_feature_importance(model, feature_names)
        
        return {
            'model': model,
            'metrics': metrics,
            'feature_importance': importance,
            'algorithm': algorithm,
            'trading_pair': trading_pair,
            'trained_at': datetime.utcnow(),
            'samples_used': len(X_train) + len(X_test)
        }
    
    def _create_random_forest(self) -> RandomForestClassifier:
        """Create Random Forest model with optimized parameters"""
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=self.random_state,
            n_jobs=-1
        )
    
    def _create_xgboost(self) -> xgb.XGBClassifier:
        """Create XGBoost model with optimized parameters"""
        return xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=self.random_state,
            eval_metric='logloss'
        )
    
    def _create_lightgbm(self) -> lgb.LGBMClassifier:
        """Create LightGBM model with optimized parameters"""
        return lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=self.random_state,
            verbosity=-1
        )
    
    def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray, 
                          y_pred_proba: np.ndarray) -> Dict[str, float]:
        """Calculate comprehensive model metrics"""
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_true, y_pred, average='weighted', zero_division=0),
        }
        
        # AUC-ROC (only for binary classification)
        try:
            metrics['auc_roc'] = roc_auc_score(y_true, y_pred_proba)
        except:
            metrics['auc_roc'] = 0.0
        
        return metrics
    
    def _get_feature_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Extract feature importance from trained model"""
        
        importance_dict = {}
        
        if hasattr(model, 'feature_importances_'):
            # Tree-based models
            importances = model.feature_importances_
            for name, importance in zip(feature_names, importances):
                importance_dict[name] = float(importance)
        
        elif hasattr(model, 'coef_'):
            # Linear models
            coefficients = np.abs(model.coef_[0]) if model.coef_.ndim > 1 else np.abs(model.coef_)
            for name, coef in zip(feature_names, coefficients):
                importance_dict[name] = float(coef)
        
        # Sort by importance
        importance_dict = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
        
        return importance_dict
    
    async def _save_model(self, model: Any, scaler: StandardScaler, algorithm: str,
                         trading_pair: str, metrics: Dict[str, float]) -> str:
        """Save trained model and metadata"""
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        model_name = f"{algorithm}_{trading_pair.replace(' ', '_')}_{timestamp}"
        
        # Prepare model data (combine model and scaler)
        model_data = {
            'model': model,
            'scaler': scaler
        }
        
        # Prepare metadata
        metadata = {
            'algorithm': algorithm,
            'trading_pair': trading_pair,
            'trained_at': datetime.utcnow().isoformat(),
            'metrics': metrics,
            'version': '1.0.0'
        }
        
        if self.use_cloud_storage:
            # Save to cloud storage (R2)
            try:
                result = await self.storage_service.save_model(
                    model_data=model_data,
                    metadata=metadata,
                    model_id=model_name
                )
                logger.info(f"☁️ Model saved to cloud storage: {model_name}")
            except Exception as e:
                logger.error(f"❌ Error saving model to cloud storage: {str(e)}")
                raise
        else:
            # Legacy local storage path (only used if cloud storage is disabled)
            model_dir = self.models_dir / model_name
            model_dir.mkdir(exist_ok=True)
            
            # Save model
            model_path = model_dir / "model.pkl"
            joblib.dump(model, model_path)
            
            # Save scaler
            scaler_path = model_dir / "scaler.pkl"
            joblib.dump(scaler, scaler_path)
            
            # Update metadata with local paths
            metadata['model_path'] = str(model_path)
            metadata['scaler_path'] = str(scaler_path)
            
            # Save metadata
            metadata_path = model_dir / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"💾 Model saved locally: {model_name}")
        
        return model_name
    
    async def _generate_training_report(self, results: Dict[str, Dict], 
                                      trading_pair: str) -> Dict:
        """Generate comprehensive training report"""
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_id = f"training_report_{trading_pair.replace(' ', '_')}_{timestamp}"
        
        report = {
            'trading_pair': trading_pair,
            'trained_at': datetime.utcnow().isoformat(),
            'models_trained': len(results),
            'best_model': None,
            'best_accuracy': 0.0,
            'model_comparison': {}
        }
        
        # Find best model
        for algorithm, result in results.items():
            if 'metrics' in result:
                accuracy = result['metrics']['accuracy']
                report['model_comparison'][algorithm] = result['metrics']
                
                if accuracy > report['best_accuracy']:
                    report['best_accuracy'] = accuracy
                    report['best_model'] = algorithm
        
        if self.use_cloud_storage:
            # Save report to cloud storage
            try:
                # Convert report to bytes
                report_bytes = json.dumps(report, indent=2).encode('utf-8')
                report_stream = io.BytesIO(report_bytes)
                
                # Upload to R2
                report_key = f"reports/{report_id}.json"
                self.storage_service.r2_client.upload_fileobj(
                    report_stream,
                    self.storage_service.bucket_name,
                    report_key
                )
                
                logger.info(f"☁️ Training report saved to cloud storage: {report_id}")
            except Exception as e:
                logger.error(f"❌ Error saving training report to cloud storage: {str(e)}")
                # Continue execution even if cloud save fails
        else:
            # Legacy local storage path
            report_path = self.models_dir / f"{report_id}.json"
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"📊 Training report saved locally: {report_path}")
            
        return report
    
    async def check_model_exists(self, trading_pair: str, model_type: str = 'xgboost') -> bool:
        """Check if a trained model exists for a trading pair and model type"""
        try:
            if self.use_cloud_storage:
                # Check in cloud storage
                try:
                    # Get list of models from cloud storage
                    model_prefix = f"models/{model_type}_{trading_pair.replace('/', '_').replace('(', '_').replace(')', '_')}"
                    
                    # List objects with the prefix
                    response = self.storage_service.r2_client.list_objects_v2(
                        Bucket=self.storage_service.bucket_name,
                        Prefix=model_prefix
                    )
                    
                    # Check if any matching models exist
                    exists = 'Contents' in response and len(response['Contents']) > 0
                    
                    if exists:
                        model_key = response['Contents'][0]['Key']
                        model_name = model_key.split('/')[1]  # Extract model name from key
                        logger.info(f"☁️ Found model in cloud storage for {trading_pair} ({model_type}): {model_name}")
                    else:
                        logger.warning(f"⚠️ No model found in cloud storage for {trading_pair} ({model_type})")
                        
                    return exists
                    
                except Exception as e:
                    logger.error(f"❌ Error checking model existence in cloud storage: {str(e)}")
                    return False
            else:
                # Legacy local storage check
                model_pattern = f"{model_type}_{trading_pair.replace('/', '_').replace('(', '_').replace(')', '_')}*"
                
                # List all directories in the models directory
                model_dirs = list(self.models_dir.glob(model_pattern))
                
                # Check if any matching model directories exist
                exists = len(model_dirs) > 0
                
                if exists:
                    logger.info(f"✅ Found local model for {trading_pair} ({model_type}): {model_dirs[0].name}")
                else:
                    logger.warning(f"⚠️ No local model found for {trading_pair} ({model_type})")
                    
                return exists
                
        except Exception as e:
            logger.error(f"❌ Error checking model existence: {str(e)}")
            return False
    
    async def load_model(self, model_name: str) -> Dict:
        """Load a trained model with its metadata"""
        try:
            if self.use_cloud_storage:
                # Load from cloud storage
                try:
                    # Use storage service to load model
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
                    logger.error(f"❌ Error loading model from cloud storage {model_name}: {str(e)}")
                    return None
            else:
                # Legacy local storage path
                model_dir = self.models_dir / model_name
                
                if not model_dir.exists():
                    logger.error(f"❌ Model directory not found: {model_dir}")
                    return None
                
                # Load model
                model_path = model_dir / "model.pkl"
                if not model_path.exists():
                    logger.error(f"❌ Model file not found: {model_path}")
                    return None
                    
                model = joblib.load(model_path)
                
                # Load scaler
                scaler_path = model_dir / "scaler.pkl"
                if not scaler_path.exists():
                    logger.warning(f"⚠️ Scaler file not found: {scaler_path}")
                    scaler = None
                else:
                    scaler = joblib.load(scaler_path)
                
                # Load metadata
                metadata_path = model_dir / "metadata.json"
                if not metadata_path.exists():
                    logger.warning(f"⚠️ Metadata file not found: {metadata_path}")
                    metadata = {
                        'model_name': model_name,
                        'loaded_at': datetime.utcnow().isoformat()
                    }
                else:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                
                logger.info(f"📁 Model loaded from local storage: {model_name}")
                
                return {
                    'model': model,
                    'scaler': scaler,
                    'metadata': metadata
                }
                
        except Exception as e:
            logger.error(f"❌ Error loading model {model_name}: {str(e)}")
            return None
    
    async def hyperparameter_tuning(self, algorithm: str, trading_pair: str = "EURUSD OTC",
                                  data_limit: int = 2000) -> Dict:
        """Perform hyperparameter tuning for a specific algorithm"""
        
        logger.info(f"🔧 Starting hyperparameter tuning for {algorithm}")
        
        # Prepare data
        features_df, targets_df = await self.feature_engineer.prepare_training_data(
            trading_pair=trading_pair, limit=data_limit
        )
        
        if features_df.empty:
            return {'error': 'No training data available'}
        
        # Split and scale data
        X_train, X_test, y_train, y_test = train_test_split(
            features_df, targets_df['target'], 
            test_size=self.test_size, random_state=self.random_state
        )
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Define parameter grids
        param_grids = {
            'random_forest': {
                'n_estimators': [50, 100, 200],
                'max_depth': [5, 10, 15, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            },
            'xgboost': {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 6, 9],
                'learning_rate': [0.01, 0.1, 0.2],
                'subsample': [0.8, 0.9, 1.0]
            },
            'lightgbm': {
                'n_estimators': [50, 100, 200],
                'max_depth': [3, 6, 9],
                'learning_rate': [0.01, 0.1, 0.2],
                'subsample': [0.8, 0.9, 1.0]
            }
        }
        
        if algorithm not in param_grids:
            return {'error': f'Hyperparameter tuning not available for {algorithm}'}
        
        # Create base model
        base_model = self.algorithms[algorithm]()
        
        # Perform grid search
        grid_search = GridSearchCV(
            base_model, param_grids[algorithm], 
            cv=3, scoring='accuracy', n_jobs=-1, verbose=1
        )
        
        grid_search.fit(X_train_scaled, y_train)
        
        # Test best model
        best_model = grid_search.best_estimator_
        y_pred = best_model.predict(X_test_scaled)
        y_pred_proba = best_model.predict_proba(X_test_scaled)[:, 1] if hasattr(best_model, 'predict_proba') else y_pred
        
        metrics = self._calculate_metrics(y_test, y_pred, y_pred_proba)
        
        result = {
            'algorithm': algorithm,
            'best_params': grid_search.best_params_,
            'best_score': grid_search.best_score_,
            'test_metrics': metrics,
            'cv_results': grid_search.cv_results_
        }
        
        logger.info(f"✅ Hyperparameter tuning completed for {algorithm}")
        logger.info(f"   Best accuracy: {grid_search.best_score_:.4f}")
        logger.info(f"   Best params: {grid_search.best_params_}")
        
        return result
    
    def create_performance_visualization(self, results: Dict[str, Dict], 
                                       save_path: str = None) -> go.Figure:
        """Create performance comparison visualization"""
        
        algorithms = []
        accuracies = []
        precisions = []
        recalls = []
        f1_scores = []
        
        for algorithm, result in results.items():
            if 'metrics' in result:
                algorithms.append(algorithm)
                accuracies.append(result['metrics']['accuracy'])
                precisions.append(result['metrics']['precision'])
                recalls.append(result['metrics']['recall'])
                f1_scores.append(result['metrics']['f1'])
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Accuracy', 'Precision', 'Recall', 'F1 Score'),
            specs=[[{'type': 'bar'}, {'type': 'bar'}],
                   [{'type': 'bar'}, {'type': 'bar'}]]
        )
        
        # Add bar charts
        fig.add_trace(go.Bar(x=algorithms, y=accuracies, name='Accuracy'), row=1, col=1)
        fig.add_trace(go.Bar(x=algorithms, y=precisions, name='Precision'), row=1, col=2)
        fig.add_trace(go.Bar(x=algorithms, y=recalls, name='Recall'), row=2, col=1)
        fig.add_trace(go.Bar(x=algorithms, y=f1_scores, name='F1 Score'), row=2, col=2)
        
        fig.update_layout(
            title='Model Performance Comparison',
            showlegend=False,
            height=600
        )
        
        if save_path:
            fig.write_html(save_path)
            logger.info(f"📊 Performance visualization saved: {save_path}")
        
        return fig 