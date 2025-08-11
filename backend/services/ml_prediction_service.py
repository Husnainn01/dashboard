"""
ML Prediction Service
Runs as a separate service on port 6008 to generate ML predictions
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
import os
import time
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from ml_models.model_trainer import ModelTrainer
from database.mongodb_models import MongoDBManager, PredictionData, CandleData
from config import DEFAULT_TRADING_PAIRS

# Setup logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="OTC Predictor ML Service",
    description="ML Prediction Service for OTC Markets",
    version="1.0.0"
)

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
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
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
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"❌ Error broadcasting WebSocket message: {str(e)}")

# Create connection manager
manager = ConnectionManager()

# MongoDB manager
mongodb_manager = MongoDBManager()

# ML model trainer
model_trainer = None

# Prediction service state
prediction_service_state = {
    "is_running": False,
    "started_at": None,
    "predictions_made": 0,
    "last_prediction": None,
    "active_models": {}
}

# Models for API requests
class PredictionRequest(BaseModel):
    trading_pair: str
    timeframe: int = 60  # Default to 1 minute
    model_type: str = "xgboost"  # Default model type

# API Routes
@app.get("/")
async def root():
    return {
        "service": "OTC Predictor ML Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "ml_prediction",
        "mongodb_connected": mongodb_manager.client is not None
    }

@app.get("/status")
async def get_status():
    """Get prediction service status"""
    global prediction_service_state
    
    # Add current time
    current_time = datetime.now()
    uptime = None
    
    if prediction_service_state["started_at"]:
        uptime = (current_time - prediction_service_state["started_at"]).total_seconds()
    
    return {
        **prediction_service_state,
        "current_time": current_time.isoformat(),
        "uptime_seconds": uptime
    }

@app.post("/train/{trading_pair:path}")
async def train_model(trading_pair: str, model_type: str = "xgboost", background_tasks: BackgroundTasks = None):
    """Train a new ML model for a specific trading pair (use URL encoded path)"""
    global model_trainer
    
    if not model_trainer:
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    try:
        # Check if we have enough data to train
        logger.info(f"🧠 Checking data for training model for {trading_pair}")
        
        # If background_tasks is provided, run training in background
        if background_tasks:
            background_tasks.add_task(model_trainer.train_model, trading_pair, model_type)
            return {"status": "training_started", "trading_pair": trading_pair, "model_type": model_type}
        else:
            # Train model synchronously
            result = await model_trainer.train_model(trading_pair, model_type=model_type)
            
            if not result:
                raise HTTPException(status_code=400, detail=f"Failed to train model for {trading_pair}")
            
            return {
                "status": "training_completed", 
                "trading_pair": trading_pair, 
                "model_type": model_type,
                "metrics": result.get("metrics", {})
            }
    except Exception as e:
        logger.error(f"❌ Training error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Training error: {str(e)}")

@app.post("/predict/{trading_pair:path}")
async def predict(trading_pair: str, model_type: str = "xgboost"):
    """Generate a prediction for a specific trading pair (use URL encoded path)"""
    global model_trainer
    
    if not model_trainer:
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    try:
        # Get prediction
        prediction = await model_trainer.predict_next_candle(trading_pair, model_type=model_type)
        
        if not prediction:
            raise HTTPException(status_code=404, detail=f"No prediction available for {trading_pair}")
        
        return prediction
    except Exception as e:
        logger.error(f"❌ Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.post("/train-all")
async def train_all_models(background_tasks: BackgroundTasks, model_type: str = "xgboost"):
    """Train models for all configured trading pairs"""
    global model_trainer
    
    if not model_trainer:
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    try:
        # Get all trading pairs from config
        from config import DEFAULT_TRADING_PAIRS
        
        # Start training for each pair
        for trading_pair in DEFAULT_TRADING_PAIRS:
            logger.info(f"🧠 Scheduling training for {trading_pair}")
            background_tasks.add_task(model_trainer.train_model, trading_pair, model_type)
        
        return {
            "status": "training_scheduled",
            "pairs": DEFAULT_TRADING_PAIRS,
            "model_type": model_type
        }
    except Exception as e:
        logger.error(f"❌ Error scheduling training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error scheduling training: {str(e)}")

@app.post("/start")
async def start_prediction_service(background_tasks: BackgroundTasks):
    """Start the continuous prediction service"""
    global prediction_service_state
    
    if prediction_service_state["is_running"]:
        return {"status": "already_running"}
    
    # Start prediction service in background
    background_tasks.add_task(run_continuous_predictions)
    
    return {"status": "starting"}

@app.post("/stop")
async def stop_prediction_service():
    """Stop the continuous prediction service"""
    global prediction_service_state
    
    if not prediction_service_state["is_running"]:
        return {"status": "not_running"}
    
    prediction_service_state["is_running"] = False
    
    return {"status": "stopping"}

# WebSocket endpoint for ML predictions
@app.websocket("/ws/ml-predictions")
async def websocket_ml_predictions(websocket: WebSocket):
    """WebSocket endpoint for ML predictions"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "subscribe":
                trading_pair = message.get("trading_pair")
                logger.info(f"📡 ML WebSocket subscription request for: {trading_pair}")
                
                if trading_pair and websocket in manager.subscriptions:
                    if trading_pair not in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].append(trading_pair)
                    logger.info(f"✅ Client subscribed to ML predictions for {trading_pair}")
                    
                    # Send latest prediction if available
                    await send_latest_prediction(websocket, trading_pair)
                else:
                    logger.warning(f"⚠️ Failed to subscribe to ML predictions for {trading_pair}")
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket ML predictions error: {str(e)}")
    finally:
        manager.disconnect(websocket)

async def send_latest_prediction(websocket: WebSocket, trading_pair: str):
    """Send the latest prediction for a trading pair"""
    try:
        # Get latest prediction from MongoDB
        latest_prediction = await mongodb_manager.get_latest_prediction(trading_pair)
        
        if latest_prediction:
            prediction_data = {
                "type": "ml_prediction",
                "trading_pair": trading_pair,
                "timestamp": latest_prediction.timestamp.isoformat(),
                "prediction": {
                    "direction": latest_prediction.direction,
                    "probability": latest_prediction.probability,
                    "expected_change": latest_prediction.expected_change,
                    "model_type": latest_prediction.model_type
                }
            }
            
            await manager.send_personal_message(prediction_data, websocket)
            logger.info(f"📡 Sent latest ML prediction for {trading_pair}")
        else:
            logger.warning(f"⚠️ No ML predictions found for {trading_pair}")
    except Exception as e:
        logger.error(f"❌ Error sending latest prediction: {str(e)}")

async def broadcast_prediction(prediction: PredictionData):
    """Broadcast a new prediction to all subscribed clients"""
    try:
        prediction_data = {
            "type": "ml_prediction",
            "trading_pair": prediction.trading_pair,
            "timestamp": prediction.timestamp.isoformat(),
            "prediction": {
                "direction": prediction.direction,
                "probability": prediction.probability,
                "expected_change": prediction.expected_change,
                "model_type": prediction.model_type
            }
        }
        
        # Send to subscribed clients
        for websocket, subscriptions in manager.subscriptions.items():
            if prediction.trading_pair in subscriptions:
                await manager.send_personal_message(prediction_data, websocket)
        
        logger.info(f"📡 Broadcasted ML prediction for {prediction.trading_pair}")
    except Exception as e:
        logger.error(f"❌ Error broadcasting prediction: {str(e)}")

async def initialize_service():
    """Initialize the ML prediction service"""
    global model_trainer
    
    logger.info("🚀 Initializing ML Prediction Service...")
    
    # Connect to MongoDB
    logger.info("🔌 Connecting to MongoDB...")
    if not await mongodb_manager.connect():
        logger.error("❌ Failed to connect to MongoDB")
        return False
    
    logger.info("✅ MongoDB connected successfully")
    
    # Initialize model trainer
    model_trainer = ModelTrainer(mongodb_manager)
    
    # Load existing models
    model_types = ["xgboost", "random_forest"]
    for trading_pair in DEFAULT_TRADING_PAIRS:
        for model_type in model_types:
            try:
                # Check if model exists
                model_exists = await model_trainer.check_model_exists(trading_pair, model_type)
                
                if model_exists:
                    logger.info(f"✅ Found existing {model_type} model for {trading_pair}")
                else:
                    logger.warning(f"⚠️ No {model_type} model found for {trading_pair}")
            except Exception as e:
                logger.error(f"❌ Error checking model for {trading_pair}: {str(e)}")
    
    return True

async def run_continuous_predictions():
    """Run continuous ML predictions"""
    global prediction_service_state
    
    logger.info("🚀 Starting continuous ML predictions...")
    
    prediction_service_state["is_running"] = True
    prediction_service_state["started_at"] = datetime.now()
    
    try:
        while prediction_service_state["is_running"]:
            # Generate predictions for all trading pairs
            for trading_pair in DEFAULT_TRADING_PAIRS:
                try:
                    logger.info(f"🔮 Generating prediction for {trading_pair}...")
                    
                    # Generate prediction
                    prediction = await model_trainer.predict_next_candle(trading_pair)
                    
                    if prediction:
                        # Store prediction in MongoDB
                        prediction_data = PredictionData(
                            timestamp=datetime.now(),
                            trading_pair=trading_pair,
                            direction=prediction["direction"],
                            probability=prediction["probability"],
                            expected_change=prediction["expected_change"],
                            model_type=prediction["model_type"]
                        )
                        
                        # Save to database
                        await mongodb_manager.save_prediction(prediction_data)
                        
                        # Broadcast prediction
                        await broadcast_prediction(prediction_data)
                        
                        # Update state
                        prediction_service_state["predictions_made"] += 1
                        prediction_service_state["last_prediction"] = datetime.now().isoformat()
                        
                        logger.info(f"✅ Generated prediction for {trading_pair}: {prediction['direction']} with {prediction['probability']:.2f} probability")
                    else:
                        logger.warning(f"⚠️ Could not generate prediction for {trading_pair}")
                
                except Exception as e:
                    logger.error(f"❌ Error generating prediction for {trading_pair}: {str(e)}")
            
            # Wait before next prediction cycle (30 seconds)
            await asyncio.sleep(30)
    
    except Exception as e:
        logger.error(f"❌ Continuous prediction error: {str(e)}")
    finally:
        prediction_service_state["is_running"] = False
        logger.info("🛑 Continuous ML predictions stopped")

def setup_logging():
    """Setup comprehensive logging"""
    
    # Create logs directory
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # File handler
    log_file = logs_dir / f"ml_service_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Configure logger
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

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
    setup_logging()
    setup_signal_handlers()
    await initialize_service()
    logger.info("✅ ML Prediction Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global prediction_service_state
    prediction_service_state["is_running"] = False
    
    # Disconnect from MongoDB
    await mongodb_manager.disconnect()
    
    logger.info("✅ ML Prediction Service shut down successfully")

def run_ml_service(host: str = "0.0.0.0", port: int = 6008, reload: bool = False):
    """Run the ML prediction service"""
    print("🔮 OTC Predictor - ML Prediction Service")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("services.ml_prediction_service:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    run_ml_service()
