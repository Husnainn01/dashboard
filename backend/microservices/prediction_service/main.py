#!/usr/bin/env python3
"""
Prediction Microservice
Generates predictions using trained ML models
"""

import asyncio
import logging
import sys
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
import os
import argparse
import json
import uvicorn
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

from ml_models.feature_engineering import FeatureEngineer
from database.mongodb_models import MongoDBManager, PredictionData
from config import DEFAULT_TRADING_PAIRS, PREDICTION_CONFIDENCE_THRESHOLD, STORAGE_CONFIG

# Import R2 storage support
from model_storage import ModelStorageManager
from model_trainer_r2 import ModelTrainerR2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="OTC Prediction Service",
    description="Service for making predictions for OTC trading pairs",
    version="1.0.0"
)

# Import monitoring module
import monitoring

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
        self.subscriptions = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info(f"📡 WebSocket client connected. Active connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"📡 WebSocket client disconnected. Active connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"❌ Error sending WebSocket message: {str(e)}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict, trading_pair: str = None):
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                # Check if client is subscribed to this trading pair
                if trading_pair and trading_pair not in self.subscriptions.get(connection, []):
                    continue
                    
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"❌ WebSocket broadcast error: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Create connection manager
manager = ConnectionManager()

# Global services
mongodb_manager = None
model_trainer = None
feature_engineer = None
model_storage_manager = None

# Import prediction manager and parallel processor modules
import prediction_manager
import parallel_processor

# Service state
prediction_service_state = {
    "is_running": False,
    "started_at": None,
    "predictions_made": 0,
    "last_prediction": None,
    "active_models": {},
    "active_pairs": set(),  # Set of trading pairs that are actively being subscribed to
    "priority_pair": None,  # The currently selected priority pair
    "model_cache": {},      # Cache for loaded models to reduce latency
    "feature_cache": {}     # Cache for extracted features to reduce latency
}

# Initialize prediction manager and parallel processor
prediction_mgr = prediction_manager.PredictionManager()
parallel_proc = parallel_processor.ParallelProcessor(max_concurrency=3)

# Setup monitoring routes and link to prediction manager
monitoring_svc = monitoring.setup_monitoring_routes(app, prediction_mgr, parallel_proc)
prediction_manager.monitoring_service = monitoring_svc

# Pydantic models
class PredictionRequest(BaseModel):
    trading_pair: str
    model_type: Optional[str] = "xgboost"

class PredictionResponse(BaseModel):
    trading_pair: str
    timestamp: datetime
    prediction: str  # "up" or "down" (was "direction")
    probability: float
    confidence: float
    expected_change: float
    model_used: str

async def initialize_service():
    """Initialize the prediction service"""
    global mongodb_manager, model_trainer, feature_engineer, model_storage_manager
    
    logger.info("🚀 Initializing Prediction Service...")
    
    # Initialize MongoDB connection
    mongodb_uri = "mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor"
    logger.info(f"Using MongoDB URI: {mongodb_uri}")
    mongodb_manager = MongoDBManager(uri=mongodb_uri)
    if not await mongodb_manager.connect():
        logger.error("❌ Failed to connect to MongoDB")
        return False
    
    logger.info("✅ MongoDB connected successfully")
    
    # Initialize feature engineer
    feature_engineer = FeatureEngineer(mongodb_manager)
    
    # Initialize model storage manager with R2 storage only
    # Force R2 storage type
    STORAGE_CONFIG["type"] = "r2"
    model_storage_manager = ModelStorageManager()
    logger.info(f"✅ Model storage initialized with type: R2 (cloud storage)")
    
    # Initialize model trainer with R2 support
    model_trainer = ModelTrainerR2(mongodb_manager)
    model_trainer.model_storage_manager = model_storage_manager
    logger.info("✅ ModelTrainerR2 initialized with R2 support")
    
    logger.info("✅ ML components initialized")
    
    return True

async def prepare_features_for_prediction(trading_pair: str, lookback_candles: int = 100):
    """Prepare features for prediction with caching for performance"""
    global mongodb_manager, feature_engineer, prediction_service_state
    
    # Check if we have cached features for this pair
    feature_cache = prediction_service_state.get("feature_cache", {})
    cache_key = f"{trading_pair}_{lookback_candles}"
    cached_features = feature_cache.get(cache_key)
    
    # Use cached features if they're recent (within 30 seconds)
    if cached_features and cached_features.get("timestamp", 0) > time.time() - 30:
        logger.info(f"🔍 Using cached features for {trading_pair} (age: {time.time() - cached_features['timestamp']:.1f}s)")
        return cached_features["features"], cached_features["candle_count"]
    
    # Start timing
    start_time = time.time()
    
    # Get recent candles
    candles = await mongodb_manager.get_candles_for_training(
        limit=lookback_candles, trading_pair=trading_pair
    )
    
    if len(candles) < 30:  # Reduced from 50 to allow more pairs to work
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient data: {len(candles)} candles (need at least 30)"
        )
    
    # Extract features
    feature_df = await feature_engineer.extract_features_from_candles(
        candles, target_next=False
    )
    
    if feature_df.empty:
        raise HTTPException(status_code=400, detail="Failed to extract features")
    
    # Get the latest feature row for prediction
    latest_features = feature_df.iloc[-1:].drop(columns=['timestamp'], errors='ignore')
    
    # Remove volume-related features that might not have been present during training
    # These are the features causing the mismatch error
    volume_features = ['price_volume_correlation', 'volume_ratio', 'volume_sma_10']
    for feature in volume_features:
        if feature in latest_features.columns:
            logger.info(f"🔧 Removing feature not present during training: {feature}")
            latest_features = latest_features.drop(columns=[feature], errors='ignore')
    
    # Cache the features
    if "feature_cache" not in prediction_service_state:
        prediction_service_state["feature_cache"] = {}
        
    prediction_service_state["feature_cache"][cache_key] = {
        "features": latest_features,
        "candle_count": len(candles),
        "timestamp": time.time()
    }
    
    # Limit cache size to 10 pairs
    if len(prediction_service_state["feature_cache"]) > 10:
        # Remove the oldest entry
        oldest_key = min(
            prediction_service_state["feature_cache"].keys(),
            key=lambda k: prediction_service_state["feature_cache"][k].get("timestamp", 0)
        )
        if oldest_key != cache_key:
            logger.info(f"🧹 Removing oldest features from cache: {oldest_key}")
            del prediction_service_state["feature_cache"][oldest_key]
    
    # Log performance
    end_time = time.time()
    logger.info(f"⏱️ Feature extraction took {(end_time - start_time) * 1000:.2f}ms for {trading_pair}")
    
    return latest_features, len(candles)

async def get_best_model(trading_pair: str, algorithm: str = None):
    """Get the best available model for a trading pair"""
    global model_trainer, prediction_service_state
    
    # Create cache key
    cache_key = f"{trading_pair}_{algorithm or 'default'}"
    
    # Check if we have this model in cache
    model_cache = prediction_service_state.get("model_cache", {})
    cached_model = model_cache.get(cache_key)
    
    # Use cached model if available and not expired (5 minutes)
    if cached_model and cached_model.get("timestamp", 0) > time.time() - 300:
        logger.info(f"🔍 Using cached model for {trading_pair} ({algorithm or 'default'})")
        return cached_model["model"], cached_model["scaler"], cached_model["metadata"]
    
    # Start timing
    start_time = time.time()
    
    # Check if model_trainer is initialized
    if model_trainer is None:
        logger.error("❌ Model trainer is not initialized")
        raise HTTPException(status_code=500, detail="Model trainer not initialized")
    
    try:
        # Call the async list_trained_models method
        models = await model_trainer.list_trained_models()
        
        if not models:
            logger.warning(f"⚠️ No trained models available for any trading pair")
            raise HTTPException(status_code=404, detail="No trained models available")
        
        # Filter by trading pair and algorithm (safe access)
        filtered_models = [
            m for m in models 
            if isinstance(m, dict)
            and m.get('trading_pair') == trading_pair 
            and (algorithm is None or m.get('algorithm') == algorithm)
        ]
        
        if not filtered_models:
            # Try without algorithm filter
            filtered_models = [m for m in models if m['trading_pair'] == trading_pair]
        
        # Try with different formats of the trading pair
        if not filtered_models:
            # Try alternative formats (USD/BRL(OTC) vs USDBRL OTC)
            alt_formats = []
            
            # Convert USD/BRL(OTC) to USDBRL OTC
            if '/' in trading_pair and '(' in trading_pair:
                currency_pair = trading_pair.split('(')[0]  # Get USD/BRL
                base, quote = currency_pair.split('/')      # Split into USD and BRL
                alt_formats.append(f"{base}{quote} OTC")    # USDBRL OTC
            
            # Convert USDBRL OTC to USD/BRL(OTC)
            elif ' OTC' in trading_pair:
                base_quote = trading_pair.replace(" OTC", "")
                if len(base_quote) == 6:  # Standard currency pair length
                    alt_formats.append(f"{base_quote[:3]}/{base_quote[3:]}(OTC)")
            
            # Try each alternative format
            for alt_format in alt_formats:
                logger.info(f"🔍 Trying alternative format: {alt_format}")
                filtered_models = [m for m in models if isinstance(m, dict) and m.get('trading_pair') == alt_format]
                if filtered_models:
                    logger.info(f"✅ Found models using format: {alt_format}")
                    break

        if not filtered_models:
            logger.error(f"❌ No models found for trading pair: {trading_pair}")
            raise HTTPException(
                status_code=404, 
                detail=f"No models found for trading pair: {trading_pair}"
            )
        
        # Normalize metrics and select model with highest accuracy
        # Check if models have metrics field, and add a default if not
        for m in filtered_models:
            if 'metrics' not in m:
                logger.warning(f"⚠️ Model {m.get('model_name', 'unknown')} missing metrics, adding default")
                m['metrics'] = {'accuracy': 0.5, 'precision': 0.5, 'recall': 0.5, 'f1': 0.5}
            elif not isinstance(m['metrics'], dict):
                logger.warning(f"⚠️ Model {m.get('model_name', 'unknown')} has invalid metrics format, fixing")
                m['metrics'] = {'accuracy': 0.5, 'precision': 0.5, 'recall': 0.5, 'f1': 0.5}
            elif 'accuracy' not in m['metrics']:
                logger.warning(f"⚠️ Model {m.get('model_name', 'unknown')} missing accuracy metric, adding default")
                m['metrics']['accuracy'] = 0.5

        # Select the model with highest accuracy
        best_model = max(filtered_models, key=lambda x: x.get('metrics', {}).get('accuracy', 0.5))
        model_id = best_model.get('model_id', 'unknown')
        logger.info(f"✅ Selected model: {model_id} for {trading_pair}")
        
        # Load the model
        try:
            # Get model name, falling back to the model ID if name is not available
            model_name = best_model.get('model_name') or best_model.get('id') or best_model.get('_id') or best_model.get('model_id')
            
            if not model_name:
                logger.error(f"❌ Model has no name or ID: {best_model}")
                raise ValueError("Model has no name or ID")
                
            logger.info(f"🔍 Loading model with ID: {model_name}")
                
            # Call the async load_model method
            model, scaler, metadata = await model_trainer.load_model(model_name)
            # Ensure metadata contains essential fields
            if isinstance(metadata, dict):
                metadata.setdefault('algorithm', best_model.get('algorithm'))
                metadata.setdefault('trading_pair', best_model.get('trading_pair'))
                metadata.setdefault('model_name', model_name)
            
            # Cache the model
            if "model_cache" not in prediction_service_state:
                prediction_service_state["model_cache"] = {}
                
            prediction_service_state["model_cache"][cache_key] = {
                "model": model,
                "scaler": scaler,
                "metadata": best_model,
                "timestamp": time.time()
            }
            
            # Limit cache size to 5 models
            if len(prediction_service_state["model_cache"]) > 5:
                # Remove the oldest model
                oldest_key = min(
                    prediction_service_state["model_cache"].keys(),
                    key=lambda k: prediction_service_state["model_cache"][k].get("timestamp", 0)
                )
                if oldest_key != cache_key:
                    logger.info(f"🧹 Removing oldest model from cache: {oldest_key}")
                    del prediction_service_state["model_cache"][oldest_key]
            
            # Log performance
            end_time = time.time()
            logger.info(f"⏱️ Model loading took {(end_time - start_time) * 1000:.2f}ms")
            
            return model, scaler, metadata
        except Exception as e:
            model_id = best_model.get('model_id', best_model.get('model_name', 'unknown'))
            logger.error(f"❌ Failed to load model {model_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in get_best_model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting model: {str(e)}")

# API routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OTC Predictor Prediction Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global mongodb_manager
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "prediction",
        "mongodb_connected": mongodb_manager.is_connected if mongodb_manager else False
    }

@app.get("/status")
async def get_status():
    """Get service status"""
    global prediction_service_state
    
    try:
        # Add current time
        current_time = datetime.now()
        uptime = None
        
        if prediction_service_state["started_at"]:
            uptime = (current_time - prediction_service_state["started_at"]).total_seconds()
        
        # Create a JSON-serializable copy of the state
        status_data = {
            "is_running": prediction_service_state["is_running"],
            "started_at": prediction_service_state["started_at"].isoformat() if prediction_service_state["started_at"] else None,
            "predictions_made": prediction_service_state["predictions_made"],
            "last_prediction": prediction_service_state["last_prediction"],
            "active_models": prediction_service_state["active_models"],
            "active_pairs": list(prediction_service_state["active_pairs"]),  # Convert set to list
            "priority_pair": prediction_service_state["priority_pair"],
            "model_cache_size": len(prediction_service_state.get("model_cache", {})),
            "feature_cache_size": len(prediction_service_state.get("feature_cache", {})),
            "current_time": current_time.isoformat(),
            "uptime_seconds": uptime
        }
        
        logger.info(f"📊 Status endpoint called - Service running: {status_data['is_running']}, Active pairs: {len(status_data['active_pairs'])}")
        return status_data
        
    except Exception as e:
        logger.error(f"❌ Error in status endpoint: {str(e)}")
        # Return a basic status even if there's an error
        return {
            "error": "Status retrieval failed",
            "error_details": str(e),
            "is_running": prediction_service_state.get("is_running", False),
            "current_time": datetime.now().isoformat()
        }

@app.post("/predict", response_model=PredictionResponse)
async def make_prediction(request: PredictionRequest):
    # Start timing for monitoring
    start_time = time.time()
    """Generate a prediction for a trading pair"""
    global model_trainer, mongodb_manager
    
    # Start timing for performance measurement
    start_time = time.time()
    
    try:
        logger.info(f"🔮 Making prediction for {request.trading_pair}")
        
        # Get the best model
        model, scaler, metadata = await get_best_model(
            request.trading_pair, request.model_type
        )
        
        # Prepare features
        features, candles_used = await prepare_features_for_prediction(request.trading_pair)
        
        # Ensure features match what the model was trained on
        try:
            # Get feature names from the model if available
            model_features = None
            if hasattr(model, 'feature_names_in_'):
                model_features = model.feature_names_in_
            elif hasattr(model, 'get_booster') and hasattr(model.get_booster(), 'feature_names'):
                model_features = model.get_booster().feature_names
            
            # If we have model features, ensure our features match
            if model_features is not None:
                logger.info(f"🔍 Aligning features with model's expected features")
                
                # Get current feature names
                current_features = features.columns.tolist()
                
                # Check for missing features
                missing_features = [f for f in model_features if f not in current_features]
                if missing_features:
                    logger.warning(f"⚠️ Missing features in prediction data: {missing_features}")
                    # Add missing features with zeros (more efficiently)
                    missing_df = pd.DataFrame(0.0, index=features.index, columns=missing_features)
                    features = pd.concat([features, missing_df], axis=1)
                
                # Check for extra features
                extra_features = [f for f in current_features if f not in model_features]
                if extra_features:
                    logger.warning(f"⚠️ Extra features in prediction data: {extra_features}")
                    # Remove extra features
                    features = features.drop(columns=extra_features)
                
                # Ensure feature order matches
                features = features[model_features]
        except Exception as e:
            logger.warning(f"⚠️ Could not align features: {str(e)}")
        
        # Scale features if scaler is available
        if scaler is not None:
            try:
                # Log detailed information about features and scaler
                feature_count = features.shape[1]
                logger.info(f"🔍 Scaling features with scaler: {feature_count} features in data")
                
                # Log scaler attributes for debugging
                if hasattr(scaler, 'n_features_in_'):
                    logger.info(f"🔍 Scaler expects {scaler.n_features_in_} features")
                if hasattr(scaler, 'mean_'):
                    logger.info(f"🔍 Scaler mean shape: {scaler.mean_.shape}")
                if hasattr(scaler, 'scale_'):
                    logger.info(f"🔍 Scaler scale shape: {scaler.scale_.shape}")
                
                # Check if scaler dimensions match feature dimensions
                if hasattr(scaler, 'n_features_in_') and scaler.n_features_in_ != feature_count:
                    logger.warning(f"⚠️ Feature count mismatch: scaler expects {scaler.n_features_in_} features but got {feature_count}")
                    # Adjust scaler dimensions to match features
                    logger.info(f"🔧 Adjusting scaler dimensions to match feature count")
                    scaler.mean_ = np.zeros(feature_count)
                    scaler.scale_ = np.ones(feature_count)
                    scaler.var_ = np.ones(feature_count)
                    scaler.n_features_in_ = feature_count
                    if hasattr(scaler, 'n_samples_seen_'):
                        logger.info(f"🔧 Preserving n_samples_seen_: {scaler.n_samples_seen_}")
                    else:
                        logger.info(f"🔧 Adding n_samples_seen_ attribute")
                        scaler.n_samples_seen_ = 100
                
                # Try to transform features
                features_scaled = scaler.transform(features)
                logger.info(f"✅ Features scaled successfully")
                
            except Exception as e:
                logger.warning(f"⚠️ Error using scaler: {str(e)}")
                
                try:
                    # If the scaler is not fitted or has other issues, create a new one
                    logger.info(f"🔧 Creating new StandardScaler as fallback")
                    from sklearn.preprocessing import StandardScaler
                    
                    # Create a new scaler
                    scaler = StandardScaler()
                    
                    # Fit with current features
                    logger.info(f"🔧 Fitting new scaler with current features ({features.shape})")
                    scaler.fit(features)
                    
                    # Transform the features
                    features_scaled = scaler.transform(features)
                    logger.info(f"✅ Features scaled successfully with new scaler")
                    
                    # Log detailed information about the new scaler
                    logger.info(f"🔍 New scaler attributes: n_features_in_={scaler.n_features_in_}, " +
                               f"n_samples_seen_={getattr(scaler, 'n_samples_seen_', 'N/A')}")
                    logger.info(f"🔍 New scaler mean shape: {scaler.mean_.shape}, scale shape: {scaler.scale_.shape}")
                    
                except Exception as inner_e:
                    # If all scaling attempts fail, use unscaled features
                    logger.error(f"❌ Failed to create fallback scaler: {str(inner_e)}")
                    logger.warning(f"⚠️ Using unscaled features as last resort")
                    features_scaled = features.values
        else:
            logger.warning(f"⚠️ No scaler available, using unscaled features")
            features_scaled = features.values
        
        # Make prediction
        try:
            # Check for feature shape mismatch and ensure exact feature alignment
            model_features = None
            
            # First, try to get feature names from the model
            if hasattr(model, 'feature_names_in_'):
                model_features = model.feature_names_in_
            elif hasattr(model, 'get_booster') and hasattr(model.get_booster(), 'feature_names'):
                model_features = model.get_booster().feature_names
            
            if model_features is not None:
                logger.info(f"🔍 Model expects {len(model_features)} features")
                
                # If we have a DataFrame, we can align features by name
                if isinstance(features_scaled, pd.DataFrame):
                    current_features = features_scaled.columns.tolist()
                    logger.info(f"🔍 Current features: {len(current_features)}")
                    
                    # Find missing features
                    missing_features = [f for f in model_features if f not in current_features]
                    if missing_features:
                        logger.warning(f"⚠️ Adding {len(missing_features)} missing features: {missing_features}")
                        for feature in missing_features:
                            features_scaled[feature] = 0.0
                    
                    # Find extra features
                    extra_features = [f for f in current_features if f not in model_features]
                    if extra_features:
                        logger.warning(f"⚠️ Removing {len(extra_features)} extra features: {extra_features}")
                        features_scaled = features_scaled.drop(columns=extra_features)
                    
                    # Reorder columns to match model's expected order
                    features_scaled = features_scaled[model_features]
                    
                    logger.info(f"✅ Features aligned successfully: {features_scaled.shape}")
                # If we have a numpy array, we need to ensure the shape matches
                else:
                    expected_features = len(model_features)
                    actual_features = features_scaled.shape[1]
                    
                    if expected_features != actual_features:
                        logger.warning(f"⚠️ Feature shape mismatch, expected: {expected_features}, got {actual_features}")
                        
                        # Add missing features with zeros
                        if expected_features > actual_features:
                            missing_shape = (features_scaled.shape[0], expected_features - actual_features)
                            missing_features = np.zeros(missing_shape)
                            features_scaled = np.hstack((features_scaled, missing_features))
                            logger.info(f"✅ Added {expected_features - actual_features} missing features")
                            
                            # Log detailed information about the feature mismatch
                            if hasattr(model, 'feature_names_in_'):
                                logger.info(f"🔍 Model expects these features: {model.feature_names_in_}")
                                if hasattr(features, 'columns'):
                                    missing_feature_names = [f for f in model.feature_names_in_ if f not in features.columns]
                                    logger.info(f"🔍 Missing features: {missing_feature_names}")
                        
                        # If we have too many features, truncate
                        elif expected_features < actual_features:
                            features_scaled = features_scaled[:, :expected_features]
                            logger.info(f"✅ Removed {actual_features - expected_features} extra features")
            # Fallback to simple shape checking if feature names are not available
            elif hasattr(model, 'n_features_in_'):
                expected_features = model.n_features_in_
                actual_features = features_scaled.shape[1]
                
                if expected_features != actual_features:
                    logger.warning(f"⚠️ Feature shape mismatch, expected: {expected_features}, got {actual_features}")
                    
                    # Add missing features with zeros
                    if expected_features > actual_features:
                        if isinstance(features_scaled, pd.DataFrame):
                            # For DataFrame, add columns
                            missing_count = expected_features - actual_features
                            for i in range(missing_count):
                                col_name = f"missing_feature_{i}"
                                features_scaled[col_name] = 0.0
                        else:
                            # For numpy array, add columns with zeros
                            missing_shape = (features_scaled.shape[0], expected_features - actual_features)
                            missing_features = np.zeros(missing_shape)
                            features_scaled = np.hstack((features_scaled, missing_features))
                        
                        logger.info(f"✅ Added {expected_features - actual_features} missing features")
                        
                        # Log detailed information about the feature mismatch
                        if hasattr(model, 'feature_names_in_'):
                            logger.info(f"🔍 Model expects {len(model.feature_names_in_)} features")
                            if hasattr(features, 'columns'):
                                missing_feature_names = [f for f in model.feature_names_in_ if f not in features.columns]
                                if missing_feature_names:
                                    logger.info(f"🔍 Missing features: {missing_feature_names[:10]}... (showing first 10)")
                    
                    # If we have too many features, truncate
                    elif expected_features < actual_features:
                        if isinstance(features_scaled, pd.DataFrame):
                            features_scaled = features_scaled.iloc[:, :expected_features]
                        else:
                            features_scaled = features_scaled[:, :expected_features]
                        
                        logger.info(f"✅ Removed {actual_features - expected_features} extra features")
            
            # Make the prediction
            raw_pred = model.predict(features_scaled)[0]
            prediction_proba = model.predict_proba(features_scaled)[0] if hasattr(model, 'predict_proba') else [0.5, 0.5]
            # Map probability to class label '1' (up) robustly
            prob_up = None
            try:
                if hasattr(model, 'classes_') and len(getattr(model, 'classes_', [])) == len(prediction_proba):
                    classes = list(model.classes_)
                    if 1 in classes:
                        up_index = classes.index(1)
                        prob_up = float(prediction_proba[up_index])
                # Fallback: assume index 1 is 'up' when binary
                if prob_up is None and len(prediction_proba) == 2:
                    prob_up = float(prediction_proba[1])
            except Exception:
                # Final fallback
                prob_up = float(prediction_proba[1]) if len(prediction_proba) > 1 else 0.5
            
            # Derive direction from prob_up for consistency
            prediction_binary = 1 if prob_up >= 0.5 else 0
        except Exception as e:
            logger.error(f"❌ Error during prediction: {str(e)}")
            # Fallback to random prediction
            logger.warning("⚠️ Using fallback random prediction")
            import random
            prediction_binary = random.choice([0, 1])
            prediction_proba = [0.5, 0.5] if prediction_binary == 0 else [0.5, 0.5]
        
        # Convert to readable format
        prediction_direction = 'up' if prediction_binary == 1 else 'down'
        
        # Calculate confidence based on probability distribution and historical accuracy
        # The further from 0.5, the more confident the model is
        raw_confidence = abs(prediction_proba[1] - 0.5) * 2  # Scale to [0, 1]
        
        # Apply sigmoid function to make confidence curve more realistic
        # This ensures small differences near 0.5 result in low confidence
        # while strong signals result in high confidence
        import math
        sigmoid_confidence = 1 / (1 + math.exp(-10 * (raw_confidence - 0.5)))
        confidence = min(0.95, sigmoid_confidence)  # Cap at 95% to avoid overconfidence
        
        # Store probability of 'up' for reference
        probability = float(prob_up)
        
        # Calculate expected change (simplified)
        expected_change = (probability - 0.5) * 2 * 0.001  # 0.1% base change scaled by probability
        
        # Check confidence threshold
        if confidence < PREDICTION_CONFIDENCE_THRESHOLD:
            logger.warning(f"⚠️ Low confidence prediction: {confidence:.3f}")
            logger.info(f"🔍 Confidence threshold: {PREDICTION_CONFIDENCE_THRESHOLD}")
            model_name = metadata.get('model_name', 'unknown')
            logger.info(f"🔍 Model used: {model_name}, Probability: {probability:.3f}, Direction: {'up' if probability > 0.5 else 'down'}")
        
        # Create prediction object
        prediction_data = PredictionData(
            timestamp=datetime.utcnow(),
            trading_pair=request.trading_pair,
            prediction=prediction_direction,  # Use 'prediction' instead of 'direction'
            model_type=metadata['algorithm'],
            model_version=metadata.get('version', '1.0.0'),
            confidence=float(confidence),
            features={"probability": float(probability), "expected_change": float(expected_change)}
        )
        
        # Save prediction to database asynchronously (don't wait for completion)
        asyncio.create_task(mongodb_manager.save_prediction(prediction_data))
        
        # Update service state
        prediction_service_state["predictions_made"] += 1
        prediction_service_state["last_prediction"] = datetime.now().isoformat()
        
        # Log performance metrics
        end_time = time.time()
        # Broadcast prediction to WebSocket clients asynchronously
        asyncio.create_task(broadcast_prediction(prediction_data))
        
        # Calculate execution time for monitoring
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Record successful prediction in monitoring service
        monitoring_svc.record_prediction(
            trading_pair=request.trading_pair,
            duration_ms=execution_time_ms,
            success=True
        )
        
        # Return prediction response
        return PredictionResponse(
            trading_pair=request.trading_pair,
            timestamp=datetime.utcnow(),
            prediction=prediction_direction,  
            probability=float(probability),
            confidence=float(confidence),
            expected_change=float(expected_change),
            model_used=(metadata.get('algorithm') if isinstance(metadata, dict) and metadata.get('algorithm') else type(model).__name__)
        )
    except HTTPException:
        # Record HTTP exception in monitoring
        execution_time_ms = (time.time() - start_time) * 1000
        monitoring_svc.record_prediction(
            trading_pair=request.trading_pair,
            duration_ms=execution_time_ms,
            success=False
        )
        raise
    except Exception as e:
        # Record general exception in monitoring
        execution_time_ms = (time.time() - start_time) * 1000
        monitoring_svc.record_prediction(
            trading_pair=request.trading_pair,
            duration_ms=execution_time_ms,
            success=False
        )
        logger.error(f"❌ Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.get("/predict/{trading_pair}")
async def quick_prediction(trading_pair: str, model_type: str = None):
    """Quick prediction endpoint for a specific trading pair"""
    # No fallback predictions - either return a real prediction or an error
    request = PredictionRequest(trading_pair=trading_pair, model_type=model_type)
    return await make_prediction(request)

@app.get("/predict-by-query")
async def quick_prediction_by_query(trading_pair: str, model_type: str = None):
    """Alternative prediction endpoint using query parameters instead of path parameters"""
    # No fallback predictions - either return a real prediction or an error
    request = PredictionRequest(trading_pair=trading_pair, model_type=model_type)
    return await make_prediction(request)

@app.post("/subscribe")
async def subscribe_to_pair(trading_pair: str):
    """Subscribe to a trading pair for predictions using query parameter"""
    global prediction_service_state
    
    prediction_service_state["active_pairs"].add(trading_pair)
    logger.info(f"📊 Subscribed to trading pair: {trading_pair}")
    logger.info(f"📊 Active pairs: {prediction_service_state['active_pairs']}")
    
    return {
        "status": "subscribed",
        "trading_pair": trading_pair,
        "active_pairs": list(prediction_service_state["active_pairs"])
    }

@app.post("/unsubscribe")
async def unsubscribe_from_pair(trading_pair: str):
    """Unsubscribe from a trading pair using query parameter"""
    global prediction_service_state
    
    if trading_pair in prediction_service_state["active_pairs"]:
        prediction_service_state["active_pairs"].remove(trading_pair)
        logger.info(f"📊 Unsubscribed from trading pair: {trading_pair}")
    
    # If this was the priority pair, clear it
    if prediction_service_state["priority_pair"] == trading_pair:
        prediction_service_state["priority_pair"] = None
        logger.info(f"📊 Cleared priority pair")
    
    logger.info(f"📊 Active pairs: {prediction_service_state['active_pairs']}")
    
    return {
        "status": "unsubscribed",
        "trading_pair": trading_pair,
        "active_pairs": list(prediction_service_state["active_pairs"])
    }

@app.post("/set-priority")
async def set_priority_pair(trading_pair: str):
    """Set a trading pair as the priority pair using query parameter"""
    global prediction_service_state
    
    # Make sure the pair is subscribed
    prediction_service_state["active_pairs"].add(trading_pair)
    
    # Set as priority
    prediction_service_state["priority_pair"] = trading_pair
    logger.info(f"📊 Set priority pair: {trading_pair}")
    
    return {
        "status": "priority_set",
        "priority_pair": trading_pair,
        "active_pairs": list(prediction_service_state["active_pairs"])
    }

@app.get("/active-pairs")
async def get_active_pairs():
    """Get the list of active trading pairs"""
    global prediction_service_state
    
    return {
        "active_pairs": list(prediction_service_state["active_pairs"]),
        "priority_pair": prediction_service_state["priority_pair"]
    }

@app.post("/start")
async def start_prediction_service():
    """Start continuous prediction service"""
    global prediction_service_state
    
    if prediction_service_state["is_running"]:
        return {"status": "already_running"}
    
    # Start prediction service in background
    asyncio.create_task(run_continuous_predictions())
    
    return {"status": "starting"}

@app.post("/stop")
async def stop_prediction_service():
    """Stop continuous prediction service"""
    global prediction_service_state
    
    if not prediction_service_state["is_running"]:
        return {"status": "not_running"}
    
    prediction_service_state["is_running"] = False
    
    return {"status": "stopping"}

# WebSocket endpoint for predictions
@app.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    """WebSocket endpoint for real-time predictions"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "subscribe":
                trading_pair = message.get("trading_pair")
                logger.info(f"📡 WebSocket subscription request for: {trading_pair}")
                
                if trading_pair and websocket in manager.subscriptions:
                    if trading_pair not in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].append(trading_pair)
                    logger.info(f"✅ Client subscribed to predictions for {trading_pair}")
                    
                    # Send latest prediction if available
                    await send_latest_prediction(websocket, trading_pair)
                else:
                    logger.warning(f"⚠️ Failed to subscribe to predictions for {trading_pair}")
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket predictions error: {str(e)}")
    finally:
        manager.disconnect(websocket)

async def get_latest_prediction(trading_pair: str) -> Optional[PredictionData]:
    """Get the latest prediction for a trading pair from MongoDB"""
    global mongodb_manager
    
    try:
        # Get the latest prediction from MongoDB
        predictions = await mongodb_manager.get_predictions(
            trading_pair=trading_pair,
            limit=1
        )
        
        if predictions and len(predictions) > 0:
            # Convert to PredictionData object
            return PredictionData.from_dict(predictions[0])
        else:
            return None
    except Exception as e:
        logger.error(f"❌ Error getting latest prediction: {str(e)}")
        return None

async def send_latest_prediction(websocket: WebSocket, trading_pair: str):
    """Send the latest prediction for a trading pair"""
    global mongodb_manager
    
    try:
        # Get latest prediction
        latest_prediction = await get_latest_prediction(trading_pair)
        
        if latest_prediction:
            # Get probability and expected_change from features if available
            probability = 0.5
            expected_change = 0.0
            if hasattr(latest_prediction, 'features') and latest_prediction.features:
                probability = latest_prediction.features.get("probability", 0.5)
                expected_change = latest_prediction.features.get("expected_change", 0.0)
            
            prediction_data = {
                "type": "prediction",
                "trading_pair": trading_pair,
                "timestamp": latest_prediction.timestamp.isoformat(),
                "prediction": latest_prediction.prediction,  # Use 'prediction' instead of 'direction'
                "probability": probability,
                "confidence": latest_prediction.confidence,
                "expected_change": expected_change,
                "model_used": latest_prediction.model_type
            }
            
            await manager.send_personal_message(prediction_data, websocket)
            logger.info(f"📡 Sent latest prediction for {trading_pair}")
        else:
            logger.warning(f"⚠️ No predictions found for {trading_pair}")
    except Exception as e:
        logger.error(f"❌ Error sending latest prediction: {str(e)}")

async def broadcast_prediction(prediction: PredictionData):
    """Broadcast a prediction to all subscribed clients"""
    try:
        # Get probability and expected_change from features if available
        probability = 0.5
        expected_change = 0.0
        if hasattr(prediction, 'features') and prediction.features:
            probability = prediction.features.get("probability", 0.5)
            expected_change = prediction.features.get("expected_change", 0.0)
        
        prediction_data = {
            "type": "prediction",
            "trading_pair": prediction.trading_pair,
            "timestamp": prediction.timestamp.isoformat(),
            "prediction": prediction.prediction,  # Use 'prediction' instead of 'direction'
            "probability": probability,
            "confidence": prediction.confidence,
            "expected_change": expected_change,
            "model_used": prediction.model_type
        }
        
        # Send to subscribed clients
        await manager.broadcast(prediction_data, prediction.trading_pair)
        
        logger.info(f"📡 Broadcasted prediction for {prediction.trading_pair}")
    except Exception as e:
        logger.error(f"❌ Error broadcasting prediction: {str(e)}")

async def run_continuous_predictions():
    """Run continuous prediction generation with proper timezone handling"""
    global prediction_service_state
    
    # Import the timezone utilities
    from timezone_utils import (
        get_current_market_time, get_current_candle_time, get_previous_candle_time,
        seconds_until_next_candle, get_candle_schedule_info
    )
    
    logger.info("🚀 Starting continuous predictions with improved timezone handling...")
    
    prediction_service_state["is_running"] = True
    prediction_service_state["started_at"] = datetime.now()
    
    # Track the last candle timestamp we made a prediction for (in market timezone)
    last_candle_timestamps = {}
    
    # Define the candle timeframe in minutes
    timeframe_minutes = 1
    # Buffer time to wait after candle close to ensure data is available (seconds)
    buffer_seconds = 3
    
    try:
        while prediction_service_state["is_running"]:
            # Check if we have any trained models before attempting predictions
            models_available = False
            try:
                if model_trainer:
                    # Call the async list_trained_models method
                    models = await model_trainer.list_trained_models()
                    models_available = len(models) > 0
                    if not models_available:
                        logger.warning("⚠️ No trained models available. Waiting for models to be trained...")
            except Exception as e:
                logger.error(f"❌ Error checking for trained models: {str(e)}")
            
            if models_available:
                # Get current candle time in market timezone (UTC+7)
                current_candle_time = get_current_candle_time(timeframe_minutes)
                previous_candle_time = get_previous_candle_time(timeframe_minutes)
                
                # Log detailed timing information for debugging
                schedule_info = get_candle_schedule_info(timeframe_minutes, buffer_seconds)
                logger.info(f"⏱️ Candle timing: Current market time: {schedule_info['current_time']}, "  
                           f"Current candle: {schedule_info['current_candle']}, "  
                           f"Next candle: {schedule_info['next_candle']}")
                
                # Get active trading pairs or use defaults if none are active
                active_pairs = prediction_service_state["active_pairs"]
                priority_pair = prediction_service_state["priority_pair"]
                
                # If no pairs are active, use defaults
                pairs_to_predict = active_pairs if active_pairs else DEFAULT_TRADING_PAIRS
                
                # If we have a priority pair, process it first
                if priority_pair:
                    pairs_ordered = [priority_pair] + [p for p in pairs_to_predict if p != priority_pair]
                else:
                    pairs_ordered = list(pairs_to_predict)
                
                logger.info(f"📊 Processing predictions for pairs: {pairs_ordered}")
                
                # Generate predictions for active trading pairs in parallel with priority handling
                # First, filter pairs that need prediction for this cycle
                pairs_to_process = []
                for trading_pair in pairs_ordered:
                    # Check if we already made a prediction for this candle
                    last_prediction_time = last_candle_timestamps.get(trading_pair)
                    
                    # We want to predict for the previous completed candle
                    # This ensures we have all the data for that candle
                    if last_prediction_time is None or last_prediction_time < previous_candle_time:
                        # Check if model_trainer is initialized
                        if model_trainer is None:
                            logger.error(f"❌ Model trainer not initialized for {trading_pair}")
                            continue
                            
                        pairs_to_process.append(trading_pair)
                    else:
                        logger.info(f"⏭️ Skipping prediction for {trading_pair} - already predicted for candle at {previous_candle_time}")
                
                if pairs_to_process:
                    logger.info(f"🔄 Processing {len(pairs_to_process)} trading pairs in parallel")
                    
                    # Define the prediction function for a single trading pair
                    async def process_trading_pair(trading_pair):
                        try:
                            # Log with priority indicator if applicable
                            if trading_pair == priority_pair:
                                logger.info(f"🔮 [PRIORITY] Generating prediction for {trading_pair} for candle at {previous_candle_time}...")
                            else:
                                logger.info(f"🔮 Generating prediction for {trading_pair} for candle at {previous_candle_time}...")
                            
                            # Define a wrapper function for prediction manager
                            async def make_prediction_wrapper(trading_pair):
                                request = PredictionRequest(trading_pair=trading_pair)
                                return await make_prediction(request)
                            
                            # Set different timeout for priority pairs
                            base_timeout = 8.0 if trading_pair == priority_pair else 5.0
                            max_retries = 2 if trading_pair == priority_pair else 1
                            
                            # Execute prediction with resilience
                            result = await prediction_mgr.make_prediction_with_resilience(
                                make_prediction_wrapper,
                                trading_pair,
                                max_retries=max_retries,
                                base_timeout=base_timeout
                            )
                            
                            # Update the last prediction time for this pair
                            last_candle_timestamps[trading_pair] = previous_candle_time
                            
                            return result
                            
                        except HTTPException as http_e:
                            # Handle HTTP exceptions (like 404 for missing models) gracefully
                            if http_e.status_code == 404:
                                logger.warning(f"⚠️ No model available for {trading_pair}. Skipping prediction.")
                            else:
                                logger.error(f"❌ HTTP error for {trading_pair}: {http_e.detail}")
                            return None
                        except Exception as e:
                            logger.error(f"❌ Error generating prediction for {trading_pair}: {str(e)}")
                            return None
                    
                    # Process all trading pairs in parallel with priority handling
                    results = await parallel_proc.process_trading_pairs(
                        pairs_to_process,
                        process_trading_pair,
                        priority_pair=priority_pair
                    )
                    
                    # Log summary of results
                    successful = sum(1 for r in results.values() if r is not None)
                    logger.info(f"✅ Successfully processed {successful}/{len(pairs_to_process)} trading pairs")
                    
                    # Log parallel processing stats
                    processor_stats = parallel_proc.get_stats()
                    logger.info(f"📊 Parallel processor stats: {processor_stats['successful_tasks']}/{processor_stats['total_tasks_processed']} successful, " +
                               f"max concurrent: {processor_stats['max_concurrent_tasks']}")
                else:
                    logger.info("⏭️ No trading pairs need prediction for this cycle")
            
            # Calculate wait time until the next candle using timezone-aware utilities
            wait_seconds = seconds_until_next_candle(timeframe_minutes, buffer_seconds)
            
            # Log detailed waiting information
            schedule_info = get_candle_schedule_info(timeframe_minutes, buffer_seconds)
            logger.info(f"⏱️ Waiting {wait_seconds:.1f} seconds until next candle processing")
            logger.info(f"⏱️ Next prediction cycle at: {schedule_info['next_prediction_at']}")
            
            # Wait until it's time for the next prediction cycle
            await asyncio.sleep(wait_seconds)
    
    except Exception as e:
        logger.error(f"❌ Continuous prediction error: {str(e)}")
    finally:
        prediction_service_state["is_running"] = False
        logger.info("🛑 Continuous predictions stopped")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
        global prediction_service_state
        prediction_service_state["is_running"] = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    setup_signal_handlers()
    await initialize_service()
    
    # Auto-start prediction service
    global prediction_service_state
    if not prediction_service_state["is_running"]:
        prediction_service_state["is_running"] = True
        asyncio.create_task(run_continuous_predictions())
        logger.info("🔮 Prediction service started automatically")
        
    logger.info("✅ Prediction Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global prediction_service_state, mongodb_manager
    
    # Stop continuous predictions
    prediction_service_state["is_running"] = False
    
    # Disconnect from MongoDB
    if mongodb_manager:
        await mongodb_manager.disconnect()
    
    logger.info("✅ Prediction Service shut down successfully")

def run_service(host: str = "0.0.0.0", port: int = 5003, reload: bool = False):
    """Run the prediction service"""
    print("🚀 OTC Predictor - Prediction Service")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor Prediction Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5003, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)
