"""
Prediction API Service
FastAPI REST API for real-time trading predictions using trained ML models
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

# FastAPI imports
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from database.mongodb_models import MongoDBManager, PredictionData, CandleData
from ml_models.model_trainer import ModelTrainer
from ml_models.feature_engineering import FeatureEngineer
from services.data_service import ContinuousDataService
from config import DEFAULT_TRADING_PAIRS, PREDICTION_CONFIDENCE_THRESHOLD

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="OTC Predictor API",
    description="Real-time trading predictions API using ML models",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
mongodb_manager = MongoDBManager()
model_trainer = ModelTrainer(mongodb_manager)
feature_engineer = FeatureEngineer(mongodb_manager)
data_service: Optional[ContinuousDataService] = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info(f"📡 WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info(f"📡 WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"❌ Failed to send WebSocket message: {e}")
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
                    
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"❌ WebSocket broadcast error: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# Pydantic models for API
class PredictionRequest(BaseModel):
    trading_pair: str = Field(..., description="Trading pair (e.g., 'EURUSD OTC')")
    timeframe: int = Field(60, description="Timeframe in seconds")
    model_algorithm: Optional[str] = Field(None, description="Specific algorithm to use")

class PredictionResponse(BaseModel):
    trading_pair: str
    prediction: str  # 'up' or 'down'
    confidence: float
    probability: float
    model_used: str
    timestamp: datetime
    features_used: int
    model_accuracy: Optional[float] = None

class ServiceStatus(BaseModel):
    api_status: str
    database_connected: bool
    data_service_running: bool
    available_models: int
    last_prediction: Optional[datetime] = None

class ModelInfo(BaseModel):
    model_name: str
    algorithm: str
    trading_pair: str
    accuracy: float
    trained_at: datetime
    samples_used: int

class DatabaseStats(BaseModel):
    candle_count: int
    prediction_count: int
    accuracy_rate: float
    total_processed_predictions: int
    correct_predictions: int

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global mongodb_manager, model_trainer, feature_engineer, data_service
    
    logger.info("🚀 Starting OTC Predictor API...")
    
    try:
        # Initialize MongoDB
        mongodb_manager = MongoDBManager()
        await mongodb_manager.connect()
        logger.info("✅ MongoDB connected")
        
        # Initialize ML components (non-critical for WebSocket functionality)
        try:
            feature_engineer = FeatureEngineer(mongodb_manager)
            model_trainer = ModelTrainer(mongodb_manager)
            logger.info("✅ ML components initialized")
        except Exception as ml_error:
            logger.warning(f"⚠️ ML components failed to initialize: {ml_error}")
            logger.info("🔄 API will continue without ML features")
        
        # Initialize data service for shared data access (non-critical)
        try:
            from services.data_service import ContinuousDataService
            data_service = ContinuousDataService()
            await data_service.initialize()
            
            # Connect WebSocket broadcaster to data service
            data_service.set_websocket_broadcaster(broadcast_market_update)
            logger.info("✅ Data service initialized with WebSocket broadcasting")
        except Exception as data_error:
            logger.warning(f"⚠️ Data service initialization failed: {data_error}")
            logger.info("🔄 WebSocket will work with database data only")
        
        logger.info("✅ API startup completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Critical startup error: {str(e)}")
        # Don't raise the error - let the API start even with limited functionality
        logger.info("🔄 API starting with limited functionality")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down OTC Predictor API...")
    
    # Disconnect from MongoDB
    await mongodb_manager.disconnect()
    
    # Shutdown data service
    if data_service:
        await data_service.shutdown()

# Helper functions
async def get_best_model(trading_pair: str, algorithm: str = None) -> tuple:
    """Get the best available model for a trading pair"""
    
    models = model_trainer.list_trained_models()
    
    if not models:
        raise HTTPException(status_code=404, detail="No trained models available")
    
    # Filter by trading pair and algorithm
    filtered_models = [
        m for m in models 
        if m['trading_pair'] == trading_pair and 
        (algorithm is None or m['algorithm'] == algorithm)
    ]
    
    if not filtered_models:
        # Try without algorithm filter
        filtered_models = [m for m in models if m['trading_pair'] == trading_pair]
    
    if not filtered_models:
        raise HTTPException(
            status_code=404, 
            detail=f"No models found for trading pair: {trading_pair}"
        )
    
    # Get the best model (highest accuracy)
    best_model = max(filtered_models, key=lambda x: x['metrics']['accuracy'])
    
    # Load the model
    try:
        model, scaler, metadata = model_trainer.load_model(best_model['model_name'])
        return model, scaler, metadata
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")

async def prepare_features_for_prediction(trading_pair: str, lookback_candles: int = 100):
    """Prepare features for prediction"""
    
    # Get recent candles
    candles = await mongodb_manager.get_candles_for_training(
        limit=lookback_candles, trading_pair=trading_pair
    )
    
    if len(candles) < 50:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient data: {len(candles)} candles (need at least 50)"
        )
    
    # Extract features
    feature_df = await feature_engineer.extract_features_from_candles(
        candles, target_next=False
    )
    
    if feature_df.empty:
        raise HTTPException(status_code=400, detail="Failed to extract features")
    
    # Get the latest feature row for prediction
    latest_features = feature_df.iloc[-1:].drop(columns=['timestamp'], errors='ignore')
    
    return latest_features, len(candles)

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """API root endpoint"""
    return {
        "message": "OTC Predictor API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/status", response_model=ServiceStatus)
async def get_status():
    """Get API and service status"""
    
    models = model_trainer.list_trained_models()
    
    return ServiceStatus(
        api_status="running",
        database_connected=mongodb_manager.is_connected,
        data_service_running=data_service.is_running if data_service else False,
        available_models=len(models),
        last_prediction=None  # TODO: Track last prediction
    )

@app.get("/models", response_model=List[ModelInfo])
async def get_models():
    """Get list of available trained models"""
    
    models = model_trainer.list_trained_models()
    
    return [
        ModelInfo(
            model_name=model['model_name'],
            algorithm=model['algorithm'],
            trading_pair=model['trading_pair'],
            accuracy=model['metrics']['accuracy'],
            trained_at=datetime.fromisoformat(model['trained_at']),
            samples_used=0  # TODO: Add samples_used to metadata
        )
        for model in models
    ]

@app.get("/database/stats", response_model=DatabaseStats)
async def get_database_stats():
    """Get database statistics"""
    
    stats = await mongodb_manager.get_stats()
    
    return DatabaseStats(
        candle_count=stats['candle_count'],
        prediction_count=stats['prediction_count'],
        accuracy_rate=stats['accuracy_rate'],
        total_processed_predictions=stats['total_processed_predictions'],
        correct_predictions=stats['correct_predictions']
    )

@app.post("/predict", response_model=PredictionResponse)
async def make_prediction(request: PredictionRequest):
    """Make a trading prediction"""
    
    try:
        logger.info(f"🔮 Making prediction for {request.trading_pair}")
        
        # Get the best model
        model, scaler, metadata = await get_best_model(
            request.trading_pair, request.model_algorithm
        )
        
        # Prepare features
        features, candles_used = await prepare_features_for_prediction(request.trading_pair)
        
        # Scale features
        features_scaled = scaler.transform(features)
        
        # Make prediction
        prediction_binary = model.predict(features_scaled)[0]
        prediction_proba = model.predict_proba(features_scaled)[0] if hasattr(model, 'predict_proba') else [0.5, 0.5]
        
        # Convert to readable format
        prediction_direction = 'up' if prediction_binary == 1 else 'down'
        confidence = max(prediction_proba)
        probability = prediction_proba[1]  # Probability of 'up'
        
        # Check confidence threshold
        if confidence < PREDICTION_CONFIDENCE_THRESHOLD:
            logger.warning(f"⚠️ Low confidence prediction: {confidence:.3f}")
        
        # Save prediction to database
        prediction_data = PredictionData(
            timestamp=datetime.utcnow(),
            trading_pair=request.trading_pair,
            direction=prediction_direction,
            confidence=float(confidence),
            algorithm_used=metadata['algorithm'],
            model_version=metadata.get('version', '1.0.0'),
            features={'candles_used': candles_used}
        )
        
        prediction_id = await mongodb_manager.save_prediction(prediction_data)
        
        logger.info(f"✅ Prediction made: {prediction_direction} ({confidence:.3f} confidence)")
        
        return PredictionResponse(
            trading_pair=request.trading_pair,
            prediction=prediction_direction,
            confidence=float(confidence),
            probability=float(probability),
            model_used=metadata['algorithm'],
            timestamp=datetime.utcnow(),
            features_used=features.shape[1],
            model_accuracy=metadata['metrics']['accuracy']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.get("/predict/{trading_pair}", response_model=PredictionResponse)
async def quick_prediction(trading_pair: str):
    """Quick prediction endpoint for a specific trading pair"""
    
    request = PredictionRequest(trading_pair=trading_pair)
    return await make_prediction(request)

@app.get("/trading-pairs", response_model=List[str])
async def get_trading_pairs():
    """Get available trading pairs from configuration"""
    return DEFAULT_TRADING_PAIRS

@app.get("/db-trading-pairs")
async def get_db_trading_pairs():
    """Get trading pairs available in the database"""
    try:
        # Get distinct trading pairs from database
        all_pairs = await mongodb_manager.db.candle_data.distinct("trading_pair")
        
        # Get count for each pair
        pair_counts = {}
        for pair in all_pairs:
            count = await mongodb_manager.db.candle_data.count_documents({"trading_pair": pair})
            pair_counts[pair] = count
        
        return {
            "available_pairs": all_pairs,
            "pair_counts": pair_counts,
            "total_pairs": len(all_pairs),
            "total_candles": sum(pair_counts.values())
        }
    except Exception as e:
        logger.error(f"❌ Error getting trading pairs from database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving trading pairs: {str(e)}")

@app.get("/candles/{trading_pair:path}")
async def get_candles_for_pair(trading_pair: str, limit: int = 50):
    """Get latest candles for a trading pair (for debugging)"""
    try:
        logger.info(f"🔍 Fetching {limit} candles for {trading_pair}")
        
        # Try to get candles with the exact trading pair format
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=limit)
        
        # If no candles found, try to get all trading pairs from the database to help debugging
        if not candles:
            logger.warning(f"⚠️ No candles found for {trading_pair}, checking alternative formats")
            
            # Get all available trading pairs
            all_pairs = await mongodb_manager.db.candle_data.distinct("trading_pair")
            logger.info(f"📊 Available trading pairs: {all_pairs}")
            
            # Try to find a similar trading pair
            for pair in all_pairs:
                # Clean both strings for comparison
                clean_requested = trading_pair.replace(" OTC", "").replace("/", "").replace("(OTC)", "").upper()
                clean_available = pair.replace(" OTC", "").replace("/", "").replace("(OTC)", "").upper()
                
                if clean_requested == clean_available:
                    logger.info(f"📊 Found matching pair format: {pair}")
                    candles = await mongodb_manager.get_latest_candles(trading_pair=pair, limit=limit)
                    if candles:
                        trading_pair = pair  # Update trading_pair to the found format
                        break
        
        if not candles:
            return {
                "trading_pair": trading_pair,
                "candles": [],
                "count": 0,
                "message": "No candles found for this trading pair",
                "available_pairs": await mongodb_manager.db.candle_data.distinct("trading_pair")
            }
        
        candle_data = []
        for candle in candles:
            candle_data.append({
                "timestamp": candle.timestamp.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": getattr(candle, 'volume', 0),
                "direction": candle.direction
            })
        
        return {
            "trading_pair": trading_pair,
            "candles": candle_data,
            "count": len(candle_data)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting candles for {trading_pair}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving candles: {str(e)}")

@app.post("/retrain/{trading_pair}")
async def retrain_model(trading_pair: str, background_tasks: BackgroundTasks):
    """Trigger model retraining for a trading pair"""
    
    async def retrain_task():
        try:
            logger.info(f"🔄 Starting retraining for {trading_pair}")
            results = await model_trainer.train_models(
                trading_pair=trading_pair,
                algorithms=['random_forest', 'xgboost', 'lightgbm'],
                data_limit=2000
            )
            logger.info(f"✅ Retraining completed for {trading_pair}: {len(results)} models")
        except Exception as e:
            logger.error(f"❌ Retraining failed for {trading_pair}: {str(e)}")
    
    background_tasks.add_task(retrain_task)
    
    return {"message": f"Retraining initiated for {trading_pair}", "status": "started"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    try:
        # Check MongoDB connection
        db_status = await mongodb_manager.get_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "database": "connected",
            "candles": db_status['candle_count']
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# WebSocket endpoint for real-time predictions (optional)
@app.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    """WebSocket endpoint for real-time predictions"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            
            # Parse request
            request = json.loads(data)
            trading_pair = request.get("trading_pair", "EURUSD OTC")
            timeframe = request.get("timeframe", 60)
            
            # Generate prediction
            prediction = await make_prediction(PredictionRequest(trading_pair=trading_pair, timeframe=timeframe))
            
            # Send response
            await manager.send_personal_message(prediction.dict(), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        manager.disconnect(websocket)

# Main WebSocket endpoint for live market data
@app.websocket("/ws/live-quotex")
async def websocket_live_quotex(websocket: WebSocket):
    """WebSocket endpoint for live PyQuotex market data"""
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
                    logger.info(f"✅ Client subscribed to {trading_pair}")
                    
                    # Send current market data for this pair
                    await send_current_market_data(websocket, trading_pair)
                else:
                    logger.warning(f"⚠️ Failed to subscribe to {trading_pair} - websocket not in manager")
                    
            elif message.get("action") == "get_historical":
                trading_pair = message.get("trading_pair")
                limit = message.get("limit", 50)
                logger.info(f"📚 WebSocket historical data request: {trading_pair}, limit: {limit}")
                await send_historical_data(websocket, trading_pair, limit)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket live-quotex error: {e}")
    finally:
        manager.disconnect(websocket)

# WebSocket endpoint for general live data
@app.websocket("/ws/live-data")
async def websocket_live_data(websocket: WebSocket):
    """WebSocket endpoint for live data (alternative endpoint)"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "subscribe":
                trading_pair = message.get("trading_pair")
                if trading_pair and websocket in manager.subscriptions:
                    if trading_pair not in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].append(trading_pair)
                    logger.info(f"📡 Client subscribed to {trading_pair}")
                    
                    # Send current market data
                    await send_current_market_data(websocket, trading_pair)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"❌ WebSocket live-data error: {e}")
    finally:
        manager.disconnect(websocket)

# Helper functions for WebSocket data
async def send_current_market_data(websocket: WebSocket, trading_pair: str):
    """Send current market data for a trading pair"""
    try:
        # Get latest candle from database
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=1)
        
        if candles:
            candle = candles[0]
            
            # Send market data
            market_data = {
                "type": "market_data",
                "trading_pair": trading_pair,
                "price": candle.close,
                "change": candle.change,
                "changePercent": (candle.change / candle.open) * 100 if candle.open else 0,
                "direction": "up" if candle.change >= 0 else "down",
                "timestamp": candle.timestamp.isoformat(),
                "volume": getattr(candle, 'volume', 0)
            }
            
            await manager.send_personal_message(market_data, websocket)
            
            # Also send as candle data
            candle_data = {
                "type": "candle_data",
                "trading_pair": trading_pair,
                "timestamp": candle.timestamp.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": getattr(candle, 'volume', 0)
            }
            
            await manager.send_personal_message(candle_data, websocket)
            
    except Exception as e:
        logger.error(f"❌ Error sending current market data: {e}")

async def send_historical_data(websocket: WebSocket, trading_pair: str, limit: int = 50):
    """Send historical candle data"""
    try:
        logger.info(f"📚 Requesting historical data for {trading_pair}, limit: {limit}")
        
        # Get historical candles
        candles = await mongodb_manager.get_latest_candles(trading_pair=trading_pair, limit=limit)
        
        logger.info(f"📊 Found {len(candles) if candles else 0} candles for {trading_pair}")
        
        if candles:
            historical_data = {
                "type": "historical_data",
                "trading_pair": trading_pair,
                "candles": [
                    {
                        "timestamp": candle.timestamp.isoformat(),
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": getattr(candle, 'volume', 0)
                    }
                    for candle in reversed(candles)  # Reverse to get chronological order
                ]
            }
            
            logger.info(f"📡 Sending historical data to WebSocket: {len(historical_data['candles'])} candles")
            await manager.send_personal_message(historical_data, websocket)
        else:
            logger.warning(f"⚠️ No historical data found for {trading_pair}")
            # Send empty data response
            empty_data = {
                "type": "historical_data",
                "trading_pair": trading_pair,
                "candles": []
            }
            await manager.send_personal_message(empty_data, websocket)
            
    except Exception as e:
        logger.error(f"❌ Error sending historical data: {e}")
        logger.error(f"Stack trace: {e.__class__.__name__}: {str(e)}")

# Function to broadcast new market data (called by data service)
async def broadcast_market_update(candle_data: CandleData):
    """Broadcast new market data to all connected WebSocket clients"""
    try:
        trading_pair = candle_data.trading_pair
        
        # Market data message
        market_data = {
            "type": "market_data",
            "trading_pair": trading_pair,
            "price": candle_data.close,
            "change": candle_data.change,
            "changePercent": (candle_data.change / candle_data.open) * 100 if candle_data.open else 0,
            "direction": "up" if candle_data.change >= 0 else "down",
            "timestamp": candle_data.timestamp.isoformat(),
            "volume": getattr(candle_data, 'volume', 0)
        }
        
        # Candle data message
        candle_message = {
            "type": "candle_data",
            "trading_pair": trading_pair,
            "timestamp": candle_data.timestamp.isoformat(),
            "open": candle_data.open,
            "high": candle_data.high,
            "low": candle_data.low,
            "close": candle_data.close,
            "volume": getattr(candle_data, 'volume', 0)
        }
        
        # Broadcast to subscribed clients
        await manager.broadcast(market_data, trading_pair)
        await manager.broadcast(candle_message, trading_pair)
        
        logger.info(f"📡 Broadcasted {trading_pair} update to {len(manager.active_connections)} clients")
        
    except Exception as e:
        logger.error(f"❌ Error broadcasting market update: {e}")

def run_api_server(host: str = "0.0.0.0", port: int = 5001, reload: bool = False):
    """Run the API server"""
    
    print("🚀 Starting OTC Predictor API Server")
    print("=" * 50)
    print(f"📡 Server: http://{host}:{port}")
    print(f"📚 Docs: http://{host}:{port}/docs")
    print(f"🔄 Reload: {reload}")
    print("-" * 50)
    
    uvicorn.run(
        "services.prediction_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    run_api_server(reload=True) 