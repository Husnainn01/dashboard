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
import pytz
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

# Pair normalization helper (delegate to shared utility)
from shared.pairs import normalize_internal as _normalize_internal, to_api_asset

def normalize_trading_pair(raw: str) -> str:
    """Normalize trading pair to canonical internal form using shared utility.

    Canonical: 'USDBRL'. Accepts aliases like 'USD/BRL(OTC)', 'USD/BRL', 'USDBRL OTC', 'USDBRL_otc'.
    """
    return _normalize_internal(raw)

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
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[Dict[str, str]]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
    
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
model_selections = {}  # Track user-selected models per trading pair
model_storage_manager = None
service_ready = False

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
    model_name: Optional[str] = None

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
    mongodb_uri = os.environ.get("MONGODB_URI", "")
    if not mongodb_uri:
        logger.warning("⚠️ MONGODB_URI not set. Database features will be unavailable.")
    else:
        logger.info(f"Using MongoDB URI: {mongodb_uri[:30]}...")
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

    global service_ready
    service_ready = True
    return True

async def prepare_features_for_prediction(trading_pair: str, lookback_candles: int = 100):
    """Prepare features for prediction using fresh data every time"""
    global mongodb_manager, feature_engineer, prediction_service_state
    
    logger.info(f"🔄 Preparing fresh features for {trading_pair} with {lookback_candles} lookback candles")
    
    # Start timing
    start_time = time.time()
    
    try:
        # Get recent candles — convert canonical pair to API format (e.g. BRLUSD_otc)
        # because data collection stores candles with to_api_asset()
        api_pair = to_api_asset(trading_pair) or trading_pair
        candles = await mongodb_manager.get_candles_for_training(
            limit=lookback_candles, trading_pair=api_pair
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
        
        # Log information about the freshness of the data
        if candles and len(candles) > 0:
            latest_candle_time = candles[-1].get('timestamp')
            if latest_candle_time:
                from datetime import datetime
                import pytz
                
                # Ensure both datetimes are timezone-aware
                if hasattr(latest_candle_time, 'tzinfo') and latest_candle_time.tzinfo is None:
                    # Convert naive datetime to aware
                    latest_candle_time = latest_candle_time.replace(tzinfo=pytz.UTC)
                elif isinstance(latest_candle_time, str):
                    # Parse string to datetime with UTC timezone
                    latest_candle_time = datetime.fromisoformat(latest_candle_time.replace('Z', '+00:00'))
                    if latest_candle_time.tzinfo is None:
                        latest_candle_time = latest_candle_time.replace(tzinfo=pytz.UTC)
                
                # Now both are timezone-aware, safe to subtract
                time_diff = datetime.now(pytz.UTC) - latest_candle_time
                logger.info(f"⏰ Latest candle is from {time_diff.total_seconds() / 60:.1f} minutes ago")
                if time_diff.total_seconds() > 300:  # 5 minutes
                    logger.warning(f"⚠️ Using candle data from {time_diff.total_seconds() / 60:.1f} minutes ago")
        
        # Log performance
        end_time = time.time()
        logger.info(f"⏱️ Feature extraction took {(end_time - start_time) * 1000:.2f}ms for {trading_pair}")
        
        return latest_features, len(candles)
    except Exception as e:
        logger.error(f"❌ Error preparing features: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error preparing features: {str(e)}")

async def get_best_model(trading_pair: str, algorithm: str = None):
    """Get the best available model for a trading pair - always fetches the latest model"""
    global model_trainer, prediction_service_state
    
    logger.info(f"🔄 Getting latest model for {trading_pair} ({algorithm or 'default'})")
    
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
            filtered_models = [m for m in models if isinstance(m, dict) and m.get('trading_pair') == trading_pair]
        
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
        
        # Normalize metrics and ensure all models have required fields
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
                
            # Ensure timestamp exists for sorting
            if 'timestamp' not in m or not isinstance(m['timestamp'], (int, float)):
                # Try to extract timestamp from other fields
                if 'created_at' in m and isinstance(m['created_at'], str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(m['created_at'].replace('Z', '+00:00'))
                        m['timestamp'] = dt.timestamp()
                    except Exception:
                        m['timestamp'] = 0
                else:
                    m['timestamp'] = 0

        # Sort models by creation time (newest first) and then by accuracy
        # This ensures we get the most recent high-performing model
        sorted_models = sorted(
            filtered_models,
            key=lambda x: (
                # First sort by timestamp (newest first)
                -float(x.get('timestamp', 0) if isinstance(x.get('timestamp'), (int, float)) else 0),
                # Then by accuracy (highest first)
                x.get('metrics', {}).get('accuracy', 0.5)
            ),
            reverse=True
        )
        
        # Select the best model (newest high-performing model)
        best_model = sorted_models[0] if sorted_models else None
        if not best_model:
            raise HTTPException(status_code=404, detail=f"No suitable models found for {trading_pair}")
            
        model_id = best_model.get('model_id', 'unknown')
        logger.info(f"✅ Selected model: {model_id} for {trading_pair}")
        
        # Log model selection details
        if len(sorted_models) > 1:
            logger.info(f"📊 Selected from {len(sorted_models)} available models for {trading_pair}")
            # Log the top 3 models considered
            for i, model in enumerate(sorted_models[:3]):
                accuracy = model.get('metrics', {}).get('accuracy', 0.5)
                timestamp = model.get('timestamp', 'unknown')
                logger.info(f"📊 Model {i+1}: ID={model.get('model_id', 'unknown')}, Accuracy={accuracy:.4f}, Timestamp={timestamp}")
        
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
            
            # Check if model loading failed
            if model is None:
                logger.error(f"❌ Failed to load model {model_name}")
                raise HTTPException(status_code=500, detail=f"Failed to load model: {model_name}")
            
            # Ensure metadata is a dictionary
            if metadata is None:
                logger.warning(f"⚠️ Model {model_name} has no metadata, creating default")
                metadata = {}
            
            # Ensure metadata contains essential fields
            metadata.setdefault('algorithm', best_model.get('algorithm'))
            metadata.setdefault('trading_pair', best_model.get('trading_pair'))
            metadata.setdefault('model_name', model_name)
            metadata.setdefault('metrics', {'accuracy': best_model.get('metrics', {}).get('accuracy', 0.5)})
            
            # Log model details for debugging
            logger.info(f"📊 Using model {model_name} for {trading_pair}")
            if 'metrics' in metadata:
                logger.info(f"📊 Model metrics: {metadata['metrics']}")
            
            # Log when the model was trained (if available)
            if 'trained_at' in metadata:
                logger.info(f"📊 Model trained at: {metadata['trained_at']}")
            elif 'created_at' in best_model:
                logger.info(f"📊 Model created at: {best_model['created_at']}")
                # Add to metadata for future reference
                metadata.setdefault('trained_at', best_model['created_at'])
            elif 'timestamp' in best_model:
                logger.info(f"📊 Model timestamp: {best_model['timestamp']}")
            else:
                logger.info(f"📊 Model timestamp not available")
            
            # Log performance
            end_time = time.time()
            logger.info(f"⏱️ Model loading took {(end_time - start_time) * 1000:.2f}ms")
            logger.info(f"✅ Successfully loaded fresh model for {trading_pair}")
            
            return model, scaler, metadata
        except HTTPException:
            raise
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
    global mongodb_manager, service_ready

    if not service_ready:
        return {
            "status": "starting",
            "timestamp": datetime.now().isoformat(),
            "service": "prediction",
            "mongodb_connected": False
        }

    mongo_connected = mongodb_manager.is_connected if mongodb_manager else False
    status = "healthy" if mongo_connected else "unhealthy"

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "service": "prediction",
        "mongodb_connected": mongo_connected
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

@app.get("/predictions/accuracy")
async def get_prediction_accuracy():
    """Get prediction accuracy statistics by comparing predicted vs actual directions"""
    global mongodb_manager

    if not mongodb_manager or not mongodb_manager.is_connected:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        now = datetime.now(pytz.UTC)
        cutoff_7d = now - timedelta(days=7)
        cutoff_24h = now - timedelta(hours=24)

        # Fetch recent predictions (last 30 days max)
        cutoff_30d = now - timedelta(days=30)
        predictions_cursor = mongodb_manager.db.predictions.find(
            {"timestamp": {"$gte": cutoff_30d}},
            sort=[("timestamp", -1)]
        ).limit(1000)
        predictions = await predictions_cursor.to_list(length=1000)

        if not predictions:
            return {
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy": 0.0,
                "win_rate": 0.0,
                "recent_accuracy_7d": 0.0,
                "recent_accuracy_24h": 0.0,
                "by_model": {}
            }

        total = 0
        correct = 0
        correct_7d = 0
        total_7d = 0
        correct_24h = 0
        total_24h = 0
        by_model = {}

        for pred in predictions:
            pred_ts = pred.get("timestamp")
            if pred_ts and pred_ts.tzinfo is None:
                pred_ts = pred_ts.replace(tzinfo=pytz.UTC)

            predicted_direction = pred.get("prediction", "").lower()
            trading_pair = pred.get("trading_pair", "")
            model_type = pred.get("model_type", "unknown")

            if not predicted_direction or not trading_pair:
                continue

            # Find the candle that closed after this prediction to determine actual direction
            candle = await mongodb_manager.db.candles.find_one(
                {"trading_pair": trading_pair, "timestamp": {"$gt": pred_ts}},
                sort=[("timestamp", 1)]
            )

            if not candle:
                continue

            actual_direction = "up" if candle.get("close", 0) > candle.get("open", 0) else "down"
            is_correct = predicted_direction == actual_direction

            total += 1
            if is_correct:
                correct += 1

            # 7d window
            if pred_ts and pred_ts >= cutoff_7d:
                total_7d += 1
                if is_correct:
                    correct_7d += 1

            # 24h window
            if pred_ts and pred_ts >= cutoff_24h:
                total_24h += 1
                if is_correct:
                    correct_24h += 1

            # Per-model breakdown
            if model_type not in by_model:
                by_model[model_type] = {"total": 0, "correct": 0, "accuracy": 0.0}
            by_model[model_type]["total"] += 1
            if is_correct:
                by_model[model_type]["correct"] += 1

        # Compute accuracies
        accuracy = correct / total if total > 0 else 0.0
        accuracy_7d = correct_7d / total_7d if total_7d > 0 else 0.0
        accuracy_24h = correct_24h / total_24h if total_24h > 0 else 0.0

        for model_key in by_model:
            m = by_model[model_key]
            m["accuracy"] = round(m["correct"] / m["total"], 4) if m["total"] > 0 else 0.0

        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": round(accuracy, 4),
            "win_rate": round(accuracy, 4),
            "recent_accuracy_7d": round(accuracy_7d, 4),
            "recent_accuracy_24h": round(accuracy_24h, 4),
            "by_model": by_model
        }

    except Exception as e:
        logger.error(f"❌ Error computing prediction accuracy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error computing accuracy: {str(e)}")

@app.post("/predict", response_model=PredictionResponse)
async def make_prediction(request: PredictionRequest):
    """Generate a prediction for a trading pair"""
    # Start timing for monitoring
    start_time = time.time()
    global model_trainer, mongodb_manager, model_selections
    
    try:
        canonical = normalize_trading_pair(request.trading_pair)
        logger.info(f"🔮 Making prediction for {request.trading_pair} (canonical: {canonical})")
        
        # Store model selection for future use if provided
        if getattr(request, 'model_name', None) or getattr(request, 'model_type', None):
            model_selections[canonical] = {
                'model_name': getattr(request, 'model_name', None),
                'model_type': getattr(request, 'model_type', None)
            }
            logger.info(f"🔑 Stored model selection for {canonical}: {model_selections[canonical]}")
            
        
        # Load explicit model if provided, otherwise get best model
        if getattr(request, 'model_name', None):
            logger.info(f"🎛️ Explicit model selection: {request.model_name}")
            try:
                # First try to load the exact model by name
                model, scaler, metadata = await model_trainer.load_model(request.model_name)
                logger.info(f"✅ Successfully loaded requested model: {request.model_name}")
                
                # Ensure metadata is a dictionary and contains essential fields
                if metadata is None:
                    logger.warning(f"⚠️ Model {request.model_name} has no metadata, creating default")
                    metadata = {}
                    
                # Add essential fields to metadata
                metadata.setdefault('model_name', request.model_name)
                metadata.setdefault('trading_pair', request.trading_pair)
                metadata.setdefault('algorithm', getattr(request, 'model_type', 'unknown'))
                metadata.setdefault('metrics', {'accuracy': 0.5})
                    
                # Store this successful model selection for future use
                model_selections[canonical] = {'model_name': request.model_name, 'model_type': None}
            except Exception as e:
                logger.error(f"❌ Failed to load requested model {request.model_name}: {str(e)}")
                logger.info(f"⚠️ Falling back to best available model for {request.trading_pair}")
                # Fall back to best model
                model, scaler, metadata = await get_best_model(
                    canonical, getattr(request, 'model_type', None)
                )
        elif getattr(request, 'model_type', None):
            logger.info(f"🎛️ Explicit model type selection: {request.model_type}")
            # Get the best model of the specified type
            model, scaler, metadata = await get_best_model(
                canonical, request.model_type
            )
            # Store this model type selection for future use
            model_selections[canonical] = {'model_name': None, 'model_type': request.model_type}
        else:
            # Get the best model
            model, scaler, metadata = await get_best_model(
                canonical, None
            )
        
        # Prepare features
        try:
            features, candles_used = await prepare_features_for_prediction(canonical)
        except Exception as e:
            logger.error(f"❌ Error preparing features: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error preparing features: {str(e)}")
        
        # Ensure features match what the model was trained on
        try:
            # Get feature names from the model if available
            model_features = None
            
            # First, try to get feature names from the model
            if hasattr(model, 'feature_names_in_'):
                model_features = model.feature_names_in_
            elif hasattr(model, 'get_booster') and hasattr(model.get_booster(), 'feature_names'):
                model_features = model.get_booster().feature_names
            
            if model_features is not None:
                logger.info(f"🔍 Model expects {len(model_features)} features")
                
                # If we have a DataFrame, we can align features by name
                if isinstance(features, pd.DataFrame):
                    current_features = features.columns.tolist()
                    logger.info(f"🔍 Current features: {len(current_features)}")
                    
                    # Find missing features
                    missing_features = [f for f in model_features if f not in current_features]
                    if missing_features:
                        logger.warning(f"⚠️ Missing features in prediction data: {missing_features}")
                        # Add missing features with zeros (more efficiently)
                        missing_df = pd.DataFrame(0.0, index=features.index, columns=missing_features)
                        features = pd.concat([features, missing_df], axis=1)
                    
                    # Find extra features
                    extra_features = [f for f in current_features if f not in model_features]
                    if extra_features:
                        logger.warning(f"⚠️ Extra features in prediction data: {extra_features}")
                        # Remove extra features
                        features = features.drop(columns=extra_features)
                    
                    # Reorder columns to match model's expected order
                    features = features[model_features]
                    
                    logger.info(f"✅ Features aligned successfully: {features.shape}")
                # If we have a numpy array, we need to ensure the shape matches
                else:
                    expected_features = len(model_features)
                    actual_features = features.shape[1]
                    
                    if expected_features != actual_features:
                        logger.warning(f"⚠️ Feature shape mismatch, expected: {expected_features}, got {actual_features}")
                        
                        # Add missing features with zeros
                        if expected_features > actual_features:
                            missing_shape = (features.shape[0], expected_features - actual_features)
                            missing_features = np.zeros(missing_shape)
                            features = np.hstack((features, missing_features))
                            logger.info(f"✅ Added {expected_features - actual_features} missing features")
                            
                            # Log detailed information about the feature mismatch
                            if hasattr(model, 'feature_names_in_'):
                                logger.info(f"🔍 Model expects these features: {model.feature_names_in_}")
                                if hasattr(features, 'columns'):
                                    missing_feature_names = [f for f in model.feature_names_in_ if f not in features.columns]
                                    logger.info(f"🔍 Missing features: {missing_feature_names}")
                        
                        # If we have too many features, truncate
                        elif expected_features < actual_features:
                            features = features[:, :expected_features]
                            logger.info(f"✅ Removed {actual_features - expected_features} extra features")
            # Fallback to simple shape checking if feature names are not available
            elif hasattr(model, 'n_features_in_'):
                expected_features = model.n_features_in_
                actual_features = features.shape[1]
                
                if expected_features != actual_features:
                    logger.warning(f"⚠️ Feature shape mismatch, expected: {expected_features}, got {actual_features}")
                    
                    # Add missing features with zeros
                    if expected_features > actual_features:
                        if isinstance(features, pd.DataFrame):
                            # For DataFrame, add columns
                            missing_count = expected_features - actual_features
                            for i in range(missing_count):
                                col_name = f"missing_feature_{i}"
                                features[col_name] = 0.0
                        else:
                            # For numpy array, add columns with zeros
                            missing_shape = (features.shape[0], expected_features - actual_features)
                            missing_features = np.zeros(missing_shape)
                            features = np.hstack((features, missing_features))
                        
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
                        if isinstance(features, pd.DataFrame):
                            features = features.iloc[:, :expected_features]
                        else:
                            features = features[:, :expected_features]
                        
                        logger.info(f"✅ Removed {actual_features - expected_features} extra features")
            
            # Make the prediction with robust class/probability mapping
            predicted_class = None
            
            # Log feature values to help debug
            if isinstance(features, pd.DataFrame):
                logger.info(f"🔍 Feature sample for prediction: {features.iloc[0].head(5).to_dict()}")
            else:
                logger.info(f"🔍 Feature shape for prediction: {features.shape}")
            
            # Get prediction probabilities
            try:
                prediction_proba = model.predict_proba(features)[0] if hasattr(model, 'predict_proba') else [0.5, 0.5]
                logger.info(f"🔍 Raw prediction probabilities: {prediction_proba}")
            except Exception as e:
                logger.error(f"❌ Error getting prediction probabilities: {str(e)}")
                prediction_proba = [0.5, 0.5]
            
            # Get predicted class
            try:
                predicted_class = model.predict(features)[0]
                logger.info(f"🔍 Raw predicted class: {predicted_class}")
            except Exception as e:
                logger.error(f"❌ Error getting predicted class: {str(e)}")
                predicted_class = None
            
            # Get model classes
            classes = getattr(model, 'classes_', None)
            if classes is not None and hasattr(classes, '__len__') and len(classes) == len(prediction_proba):
                classes_list = list(classes)
            else:
                classes_list = None

            # Log mapping context (debug)
            try:
                logger.debug(f"Classes: {classes_list}, Probabilities: {prediction_proba}")
                if classes_list and len(classes_list) == len(prediction_proba):
                    logger.debug(f"Class 0 ({classes_list[0]}): {prediction_proba[0]:.4f}")
                    logger.debug(f"Class 1 ({classes_list[1]}): {prediction_proba[1]:.4f}")
            except Exception as e:
                logger.warning(f"Could not log class mapping: {str(e)}")

            # Resolve up_index reliably
            up_index = None
            if classes_list is not None:
                for i, c in enumerate(classes_list):
                    cs = str(c).lower()
                    if c == 1 or cs == 'up' or cs == '1' or c is True:
                        up_index = i
                        break
                if up_index is None:
                    # If numeric binary, assume larger value is 'up'
                    try:
                        if all(str(x).isdigit() for x in classes_list):
                            up_index = classes_list.index(max(classes_list))
                    except Exception:
                        pass

                if up_index is not None:
                    prob_up = float(prediction_proba[up_index])
                else:
                    # Fallback: assume index 1 is 'up' if binary
                    prob_up = float(prediction_proba[1]) if len(prediction_proba) > 1 else float(max(prediction_proba))

                # Determine binary direction using predicted_class first, then prob
                if predicted_class is not None:
                    pcs = str(predicted_class).lower()
                    if predicted_class == 1 or pcs == 'up' or pcs == '1' or predicted_class is True:
                        prediction_binary = 1
                    elif predicted_class == 0 or pcs == 'down' or pcs == '0' or predicted_class is False:
                        prediction_binary = 0
                    else:
                        prediction_binary = 1 if prob_up >= 0.5 else 0
                else:
                    prediction_binary = 1 if prob_up >= 0.5 else 0
            else:
                # No class info available — use raw probabilities
                prob_up = float(prediction_proba[1]) if len(prediction_proba) > 1 else 0.5
                if predicted_class is not None:
                    pcs = str(predicted_class).lower()
                    if predicted_class == 1 or pcs == 'up' or pcs == '1':
                        prediction_binary = 1
                    elif predicted_class == 0 or pcs == 'down' or pcs == '0':
                        prediction_binary = 0
                    else:
                        prediction_binary = 1 if prob_up >= 0.5 else 0
                else:
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
        
        # Calculate confidence based on probability distribution and market volatility
        # Get recent volatility from candles to make confidence market-aware
        recent_volatility = 0.001  # Default value if we can't calculate from candles
        
        try:
            # Get the candles used for this prediction
            recent_candles = candles_used[-10:]  # Use last 10 candles
            
            if len(recent_candles) > 1:
                # Calculate recent price changes as percentage
                price_changes = [abs(c['close'] - c['open']) / c['open'] for c in recent_candles]
                recent_volatility = sum(price_changes) / len(price_changes)
                logger.info(f"📊 Recent market volatility: {recent_volatility:.6f} ({len(recent_candles)} candles)")
        except Exception as e:
            logger.warning(f"⚠️ Could not calculate market volatility: {str(e)}")
        
        # The further from 0.5, the more confident the model is
        raw_confidence = abs(prob_up - 0.5) * 2  # Scale to [0, 1]
        
        # Apply sigmoid function with volatility adjustment
        # Higher volatility should reduce confidence unless signal is very strong
        import math
        volatility_factor = max(1.0, min(3.0, 1.0 + recent_volatility * 100))
        sigmoid_slope = 10 / volatility_factor  # Reduce slope when volatility is high
        
        sigmoid_confidence = 1 / (1 + math.exp(-sigmoid_slope * (raw_confidence - 0.5)))
        
        # Cap confidence based on volatility - more volatile markets should have lower max confidence
        max_confidence = min(0.95, 1.0 / (1.0 + recent_volatility * 50))
        confidence = min(max_confidence, sigmoid_confidence)
        
        logger.info(f"📊 Confidence calculation: raw={raw_confidence:.4f}, sigmoid={sigmoid_confidence:.4f}, final={confidence:.4f}")
        
        # Store probability of 'up' for reference
        probability = float(prob_up)
        
        # Calculate expected change based on recent market volatility
        # Higher volatility means potentially larger price movements
        expected_change = (probability - 0.5) * 2 * max(0.001, recent_volatility)
        logger.info(f"📊 Expected change calculation: {expected_change:.6f} based on volatility {recent_volatility:.6f}")
        
        # Check confidence threshold
        if confidence < PREDICTION_CONFIDENCE_THRESHOLD:
            logger.warning(f"⚠️ Low confidence prediction: {confidence:.3f}")
            logger.info(f"🔍 Confidence threshold: {PREDICTION_CONFIDENCE_THRESHOLD}")
            model_name = metadata.get('model_name', 'unknown')
            logger.info(f"🔍 Model used: {model_name}, algo: {metadata.get('algorithm') if isinstance(metadata, dict) else 'unknown'}, pair: {request.trading_pair}, Probability: {probability:.3f}, Direction: {'up' if probability > 0.5 else 'down'}")
        
        # Create prediction object with market-synced CURRENT market time
        # Use timezone-aware UTC timestamp so frontend can convert reliably
        try:
            from timezone_utils import get_current_market_time
            market_now = get_current_market_time()
            # Convert market time (Asia/Bangkok) to UTC
            timestamp_utc = market_now.astimezone(pytz.UTC)
        except Exception:
            # Fallback to aware UTC now
            timestamp_utc = datetime.now(pytz.UTC)

        # Ensure metadata has required fields before creating PredictionData
        if metadata is None:
            metadata = {}
        
        # Use safe access for metadata fields with fallbacks
        algorithm = metadata.get('algorithm', 'unknown')
        model_version = metadata.get('version', '1.0.0')
        
        prediction_data = PredictionData(
            timestamp=timestamp_utc,
            trading_pair=canonical,
            prediction=prediction_direction,
            model_type=algorithm,
            model_version=model_version,
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
        
        # Return prediction response with the same market-synced UTC timestamp
        # Determine model name with proper fallbacks
        model_name = None
        if isinstance(metadata, dict):
            model_name = metadata.get('algorithm')
        
        if not model_name and model is not None:
            model_name = type(model).__name__
        
        if not model_name:
            model_name = "unknown"
            
        return PredictionResponse(
            trading_pair=canonical,
            timestamp=timestamp_utc,
            prediction=prediction_direction,  
            probability=float(probability),
            confidence=float(confidence),
            expected_change=float(expected_change),
            model_used=model_name
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

@app.post("/select_model", response_model=Dict)
async def select_model(request: PredictionRequest):
    """Select a model for a specific trading pair without starting predictions"""
    global model_selections

    if not request.trading_pair:
        return {"status": "error", "message": "Trading pair is required"}

    canonical = normalize_trading_pair(request.trading_pair)
    # Store model selection for future use
    model_selections[canonical] = {
        'model_name': getattr(request, 'model_name', None),
        'model_type': getattr(request, 'model_type', None)
    }
    
    # Add the trading pair to active pairs
    if canonical not in prediction_service_state["active_pairs"]:
        prediction_service_state["active_pairs"].add(canonical)

    logger.info(f"🔑 Model selected for {canonical}: {model_selections[canonical]}")

    return {
        "status": "success", 
        "message": f"Model selected for {canonical}",
        "model_selection": model_selections[canonical]
    }

# Alias routes to handle potential API gateway/service path prefixes in production
@app.post("/predictions/select_model", response_model=Dict)
async def select_model_prefixed(request: PredictionRequest):
    """Alias for selecting a model when service is mounted with a /predictions prefix"""
    return await select_model(request)

@app.post("/api/select_model", response_model=Dict)
async def select_model_api_prefix(request: PredictionRequest):
    """Alias for selecting a model when service is mounted with an /api prefix"""
    return await select_model(request)

@app.get("/predict-by-query")
async def predict_by_query(trading_pair: str, model_type: str = None, model_name: str = None):
    """GET-based prediction endpoint using query params (called by API gateway)"""
    request = PredictionRequest(
        trading_pair=trading_pair,
        model_type=model_type or "xgboost",
        model_name=model_name
    )
    return await make_prediction(request)

@app.post("/subscribe")
async def subscribe_pair(trading_pair: str):
    """Subscribe a trading pair for active predictions"""
    global prediction_service_state

    canonical = normalize_trading_pair(trading_pair)
    prediction_service_state["active_pairs"].add(canonical)
    logger.info(f"📡 Subscribed to {canonical} (active pairs: {len(prediction_service_state['active_pairs'])})")

    return {"status": "subscribed", "trading_pair": canonical}

@app.post("/unsubscribe")
async def unsubscribe_pair(trading_pair: str):
    """Unsubscribe a trading pair from active predictions"""
    global prediction_service_state

    canonical = normalize_trading_pair(trading_pair)
    prediction_service_state["active_pairs"].discard(canonical)
    logger.info(f"📡 Unsubscribed from {canonical} (active pairs: {len(prediction_service_state['active_pairs'])})")

    return {"status": "unsubscribed", "trading_pair": canonical}

@app.post("/set-priority")
async def set_priority_pair(trading_pair: str):
    """Set a trading pair as the priority for predictions"""
    global prediction_service_state

    canonical = normalize_trading_pair(trading_pair)
    prediction_service_state["priority_pair"] = canonical
    logger.info(f"⭐ Priority pair set to {canonical}")

    return {"status": "priority_set", "trading_pair": canonical}

@app.post("/start")
async def start_prediction_service():
    """Start continuous prediction service"""
    global prediction_service_state

    if prediction_service_state["is_running"]:
        return {"status": "already_running"}

    prediction_service_state["is_running"] = True
    asyncio.create_task(run_continuous_predictions())
    logger.info("🔮 Prediction service started via /start endpoint")

    return {"status": "started"}

@app.post("/stop")
async def stop_prediction_service():
    """Stop continuous prediction service"""
    global prediction_service_state


    if not prediction_service_state["is_running"]:
        return {"status": "not_running"}

    prediction_service_state["is_running"] = False

    return {"status": "stopping"}

@app.post("/reset-circuit-breaker")
async def reset_circuit_breaker(trading_pair: str = None):
    """Reset circuit breaker for a specific trading pair or all pairs"""
    if trading_pair:
        canonical = normalize_trading_pair(trading_pair)
        cb = prediction_mgr.get_circuit_breaker(canonical)
        cb.reset()
        return {"status": "reset", "trading_pair": canonical}
    else:
        for cb in prediction_mgr.circuit_breakers.values():
            cb.reset()
        return {"status": "all_reset"}

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
                model_name = message.get("model_name")
                model_type = message.get("model_type")
                
                logger.info(f"📡 WebSocket subscription request for: {trading_pair} with model_name={model_name}, model_type={model_type}")
                
                if trading_pair and websocket in manager.subscriptions:
                    # Create subscription with model info
                    subscription = {
                        "trading_pair": trading_pair,
                        "model_name": model_name,
                        "model_type": model_type
                    }
                    
                    # Check if this exact subscription already exists
                    subscription_exists = False
                    for sub in manager.subscriptions[websocket]:
                        if (sub.get("trading_pair") == trading_pair and 
                            sub.get("model_name") == model_name and 
                            sub.get("model_type") == model_type):
                            subscription_exists = True
                            break
                    
                    if not subscription_exists:
                        manager.subscriptions[websocket].append(subscription)
                    
                    logger.info(f"✅ Client subscribed to predictions for {trading_pair} with model_name={model_name}, model_type={model_type}")
                    
                    # Store this model selection for future predictions
                    if model_name or model_type:
                        model_selections[trading_pair] = {'model_name': model_name, 'model_type': model_type}
                        logger.info(f"💾 Stored model selection for {trading_pair}: {model_name or model_type}")
                    
                    # Send latest prediction if available
                    await send_latest_prediction(websocket, trading_pair, model_name, model_type)
                else:
                    logger.warning(f"⚠️ Failed to subscribe to predictions for {trading_pair}")
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket predictions error: {str(e)}")
    finally:
        manager.disconnect(websocket)

async def get_latest_prediction(trading_pair: str, model_name=None, model_type=None):
    """Get the latest prediction for a trading pair with optional model selection"""
    global mongodb_manager
    
    try:
        canonical = normalize_trading_pair(trading_pair)
        # Get latest prediction from MongoDB with model filters
        latest_prediction = await mongodb_manager.get_latest_prediction(
            canonical, 
            model_name=model_name, 
            model_type=model_type
        )
        return latest_prediction
    except Exception as e:
        logger.error(f"❌ Error getting latest prediction: {str(e)}")
        return None

async def send_latest_prediction(websocket: WebSocket, trading_pair: str, model_name=None, model_type=None):
    """Send the latest prediction for a trading pair with optional model selection"""
    global mongodb_manager
    
    try:
        # Get latest prediction with model selection
        latest_prediction = await get_latest_prediction(trading_pair, model_name, model_type)
        
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

async def broadcast_prediction(prediction_data: PredictionData):
    """Broadcast a prediction to all subscribed clients"""
    trading_pair = prediction_data.trading_pair
    model_type = prediction_data.model_type
    
    # Get probability and expected_change from features if available
    probability = 0.5
    expected_change = 0.0
    if hasattr(prediction_data, 'features') and prediction_data.features:
        probability = prediction_data.features.get("probability", 0.5)
        expected_change = prediction_data.features.get("expected_change", 0.0)
    
    # Create message
    message = {
        "type": "prediction",
        "trading_pair": trading_pair,
        "timestamp": prediction_data.timestamp.isoformat(),
        "prediction": prediction_data.prediction,  # Use 'prediction' instead of 'direction'
        "probability": probability,
        "confidence": prediction_data.confidence,
        "expected_change": expected_change,
        "model_used": model_type
    }
    
    # Send to all clients subscribed to this trading pair and model
    for websocket, subscriptions in manager.subscriptions.items():
        for subscription in subscriptions:
            # Check if this is a dict-based subscription (new format)
            if isinstance(subscription, dict):
                sub_pair = subscription.get("trading_pair")
                sub_model_name = subscription.get("model_name")
                sub_model_type = subscription.get("model_type")
                
                # Match trading pair and optionally model name/type if specified
                if sub_pair == trading_pair:
                    # If client specified a model name or type, only send if it matches
                    if (sub_model_name and hasattr(prediction_data, 'model_name') and 
                        prediction_data.model_name != sub_model_name):
                        continue
                    if (sub_model_type and model_type and 
                        model_type != sub_model_type):
                        continue
                    
                    try:
                        await manager.send_personal_message(message, websocket)
                    except Exception as e:
                        logger.error(f"❌ WebSocket broadcast error: {e}")
            # Handle legacy string-based subscriptions
            elif subscription == trading_pair:
                try:
                    await manager.send_personal_message(message, websocket)
                except Exception as e:
                    logger.error(f"❌ WebSocket broadcast error: {e}")

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
    
    # Track model selections per trading pair
    model_selections = {}  # Format: {trading_pair: {'model_name': name, 'model_type': type}}
    
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
                
                # Get active trading pairs - don't use defaults
                active_pairs = prediction_service_state["active_pairs"]
                priority_pair = prediction_service_state["priority_pair"]
                
                # Only predict for pairs that have explicit model selections
                # This ensures we only predict when the user has selected a model
                pairs_to_predict = set()
                for pair in active_pairs:
                    if pair in model_selections:
                        pairs_to_predict.add(pair)
                        logger.info(f"🔑 Using selected model for {pair}: {model_selections[pair]}")
                
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
                                # Check if there are any active subscriptions for this trading pair
                                # that specify a particular model to use
                                model_name = None
                                model_type = None
                                
                                # First check if we have a stored model selection for this pair
                                if trading_pair in model_selections:
                                    stored_selection = model_selections[trading_pair]
                                    model_name = stored_selection.get('model_name')
                                    model_type = stored_selection.get('model_type')
                                    logger.info(f"📌 Using stored model selection: {model_name or model_type} for {trading_pair}")
                                
                                # Then check active subscriptions which may override the stored selection
                                for ws, subscriptions in manager.subscriptions.items():
                                    for sub in subscriptions:
                                        if isinstance(sub, dict) and sub.get("trading_pair") == trading_pair:
                                            # If we find a subscription with a specific model, use that
                                            if sub.get("model_name"):
                                                model_name = sub.get("model_name")
                                                logger.info(f"🎯 Using specifically requested model: {model_name} for {trading_pair}")
                                                # Store this selection for future predictions
                                                model_selections[trading_pair] = {'model_name': model_name, 'model_type': None}
                                                break
                                            elif sub.get("model_type") and not model_name:  # model_name takes precedence
                                                model_type = sub.get("model_type")
                                                logger.info(f"🎯 Using specifically requested model type: {model_type} for {trading_pair}")
                                                # Store this selection for future predictions
                                                model_selections[trading_pair] = {'model_name': None, 'model_type': model_type}
                                
                                # Create request with model selection if specified
                                request = PredictionRequest(
                                    trading_pair=trading_pair,
                                    model_name=model_name,
                                    model_type=model_type
                                )
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
    asyncio.create_task(initialize_service())
    
    # Auto-start prediction service
    global prediction_service_state
    # Don't automatically start continuous predictions
    # User will explicitly start predictions when they select a model
    
    logger.info("✅ Prediction Service initialized successfully - waiting for user model selection")

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
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '5003')), help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)
