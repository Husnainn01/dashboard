#!/usr/bin/env python3
"""
API Gateway Microservice
Provides a unified API for the frontend and handles WebSocket connections
"""

import asyncio
import logging
import sys
import signal
from datetime import datetime, timedelta
from pathlib import Path
import os
import argparse
import json
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

from config import DEFAULT_TRADING_PAIRS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="OTC Predictor API Gateway",
    description="Unified API for OTC Predictor microservices",
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

# Service configuration
service_config = {
    "data_collection": {
        # Using the public domain provided for data collection service
        "host": os.getenv("DATA_SERVICE_HOST", "datacollection-service-production.up.railway.app"),
        "port": int(os.getenv("DATA_SERVICE_PORT", "5008")),
        "ws_path": "/ws/market-data"
    },
    "ml_training": {
        # Using the public domain provided for ML training service
        "host": os.getenv("ML_SERVICE_HOST", "ml-traning-service-production.up.railway.app"),
        "port": int(os.getenv("ML_SERVICE_PORT", "5002"))
    },
    "prediction": {
        # Using the public domain provided for prediction service
        "host": os.getenv("PREDICTION_SERVICE_HOST", "prediction-service-production.up.railway.app"),
        "port": int(os.getenv("PREDICTION_SERVICE_PORT", "5003")),
        "ws_path": "/ws/predictions"
    }
}

# Gateway state
gateway_state = {
    "started_at": datetime.now(),
    "is_running": True,
    "prediction_polling_task": None,
    "last_predictions": {}  # Store the last prediction for each trading pair
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
        self.subscriptions = {}
        self.service_connections = {}
    
    def get_subscribed_pairs(self) -> set:
        """Get all unique trading pairs that have active subscriptions"""
        unique_pairs = set()
        for client_subs in self.subscriptions.values():
            unique_pairs.update(client_subs)
        return unique_pairs
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info(f"📡 WebSocket client connected. Active connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        # Get the client's subscriptions before removing them
        client_pairs = []
        if websocket in self.subscriptions:
            client_pairs = self.subscriptions[websocket].copy()
        
        # Remove from active connections and subscriptions
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
            
        logger.info(f"📡 WebSocket client disconnected. Active connections: {len(self.active_connections)}")
        
        # Check if any pairs need to be unsubscribed from prediction service
        if client_pairs:
            all_subscribed_pairs = self.get_subscribed_pairs()
            for pair in client_pairs:
                if pair not in all_subscribed_pairs:
                    # No one is subscribed to this pair anymore
                    try:
                        unsubscribe_url = get_service_url("prediction", "/unsubscribe")
                        
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(unsubscribe_url, params={"trading_pair": pair})
                            if response.status_code == 200:
                                logger.info(f"✅ Unsubscribed from {pair} in prediction service after client disconnect")
                            else:
                                logger.error(f"❌ Failed to unsubscribe from {pair} in prediction service: {response.status_code}")
                    except Exception as e:
                        logger.error(f"❌ Error unsubscribing from prediction service: {str(e)}")
                        logger.error(f"❌ Error type: {type(e).__name__}")
            
            # If there are still other pairs, set one as priority
            if all_subscribed_pairs:
                try:
                    config = service_config["prediction"]
                    new_priority = next(iter(all_subscribed_pairs))
                    # Use HTTPS for public domains (Railway), HTTP for localhost
                    protocol = "https" if "localhost" not in config['host'] else "http"
                    priority_url = get_service_url("prediction", "/set-priority")
                    
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        priority_response = await client.post(priority_url, params={"trading_pair": new_priority})
                        if priority_response.status_code == 200:
                            logger.info(f"✅ Set {new_priority} as new priority pair in prediction service after client disconnect")
                        else:
                            logger.error(f"❌ Failed to set priority pair {new_priority}: {priority_response.status_code}")
                except Exception as e:
                    logger.error(f"❌ Error setting priority pair: {str(e)}")
                    logger.error(f"❌ Error type: {type(e).__name__}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"❌ Error sending WebSocket message: {str(e)}")
            await self.disconnect(websocket)
    
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
            await self.disconnect(connection)

# Create connection manager
manager = ConnectionManager()

# HTTP client for service communication
http_client = None

# Service status cache
service_status_cache = {
    "data_collection": {"status": "unknown", "last_check": None},
    "ml_training": {"status": "unknown", "last_check": None},
    "prediction": {"status": "unknown", "last_check": None}
}

# Helper functions
def get_service_url(service_name: str, path: str = ""):
    """Get the URL for a microservice"""
    config = service_config.get(service_name)
    if not config:
        raise ValueError(f"Unknown service: {service_name}")
    
    # Use HTTPS for public domains (Railway) without explicit port; HTTP+port for localhost
    if "localhost" in config['host']:
        return f"http://{config['host']}:{config['port']}{path}"
    else:
        return f"https://{config['host']}{path}"

def get_service_ws_url(service_name: str, path: str = ""):
    """Get the WebSocket URL for a microservice"""
    config = service_config.get(service_name)
    if not config:
        raise ValueError(f"Unknown service: {service_name}")
    
    # Use WSS for public domains (Railway) without explicit port; WS+port for localhost
    if "localhost" in config['host']:
        return f"ws://{config['host']}:{config['port']}{path}"
    else:
        return f"wss://{config['host']}{path}"

def get_protocol(host: str, secure: bool = True):
    """Get the appropriate protocol based on host"""
    if "localhost" in host:
        return "https" if secure else "http"
    else:
        return "https" if secure else "http"

async def check_service_health(service_name: str):
    """Check if a service is healthy"""
    global http_client, service_status_cache
    
    # Check cache first (valid for 30 seconds)
    cache = service_status_cache.get(service_name, {})
    last_check = cache.get("last_check")
    if last_check and (datetime.now() - last_check).total_seconds() < 30:
        return cache.get("status") == "healthy"
    
    try:
        url = get_service_url(service_name, "/health")
        logger.info(f"🔎 Health check -> {service_name}: {url}")
        response = await http_client.get(url, timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            is_healthy = data.get("status") == "healthy"
            
            # Update cache
            service_status_cache[service_name] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "last_check": datetime.now()
            }
            
            logger.info(f"✅ {service_name} health check successful")
            return is_healthy
        else:
            # Update cache
            service_status_cache[service_name] = {
                "status": "unhealthy",
                "last_check": datetime.now()
            }
            return False
    except Exception as e:
        # Log type and full error for better diagnosis
        logger.error(f"❌ Error checking {service_name} health: {str(e)}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        
        # Update cache
        service_status_cache[service_name] = {
            "status": "unhealthy",
            "last_check": datetime.now()
        }
        
        return False

async def forward_request(request_or_service: Union[Request, str], service_name_or_path: str, path: str = "", method: str = None):
    """Forward a request to a microservice
    
    Can be called in two ways:
    1. forward_request(request, service_name, path) - Forward a request object
    2. forward_request(service_name, path, method="GET") - Create and forward a new request
    """
    global http_client
    
    # Handle both calling patterns
    if isinstance(request_or_service, Request):
        # Called with (request, service_name, path)
        request = request_or_service
        service_name = service_name_or_path
        request_method = request.method
        request_headers = request.headers
        request_body = await request.body()
    else:
        # Called with (service_name, path, method)
        service_name = request_or_service
        path = service_name_or_path
        request_method = method or "GET"
        request_headers = {}
        request_body = b""
    
    # Log request details
    logger.info(f"📬 Forward request - Method: {request_method}, Service: {service_name}, Path: '{path}'")
    
    # Get the target URL
    try:
        target_url = get_service_url(service_name, path)
        logger.info(f"📬 Target URL constructed: {target_url}")
        
        # Log service configuration
        config = service_config.get(service_name)
        logger.info(f"📬 Service config for {service_name}: host={config['host']}, port={config['port']}")
    except ValueError as e:
        logger.error(f"❌ Error constructing URL: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    
    # Log request body preview if available
    if request_body:
        body_preview = request_body[:100].decode('utf-8', errors='replace')
        logger.info(f"📬 Request body preview: {body_preview}...")
    
    # Forward the request
    try:
        logger.info(f"📬 Forwarding {request_method} request to {target_url}")
        response = await http_client.request(
            method=request_method,
            url=target_url,
            headers=request_headers,
            content=request_body,
        )
        
        # Log response details
        logger.info(f"📬 Received response from {target_url} - Status: {response.status_code}")
        logger.info(f"📬 Response headers: {dict(response.headers)}")
        
        # Get the response content
        content = await response.aread()
        content_preview = content[:100].decode('utf-8', errors='replace') if content else "<empty>"
        logger.info(f"📬 Response content preview: {content_preview}...")
        
        # Return the response
        return Response(
            content=content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
    except httpx.RequestError as e:
        logger.error(f"❌ Request error forwarding to {service_name}: {str(e)}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        raise HTTPException(status_code=503, detail=f"Error communicating with {service_name} service: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error forwarding request to {target_url}: {str(e)}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=f"Error forwarding request: {str(e)}")

# API routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OTC Predictor API Gateway",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    
    # Check all services
    data_service_healthy = await check_service_health("data_collection")
    ml_service_healthy = await check_service_health("ml_training")
    prediction_service_healthy = await check_service_health("prediction")
    
    # Gateway is healthy if at least one service is healthy
    gateway_healthy = data_service_healthy or ml_service_healthy or prediction_service_healthy
    
    return {
        "status": "healthy" if gateway_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "data_collection": "healthy" if data_service_healthy else "unhealthy",
            "ml_training": "healthy" if ml_service_healthy else "unhealthy",
            "prediction": "healthy" if prediction_service_healthy else "unhealthy"
        }
    }

@app.get("/status")
async def get_status():
    """Get status of all services"""
    
    status = {
        "gateway": {
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # Get status from each service
    for service_name in ["data_collection", "ml_training", "prediction"]:
        try:
            service_status = await forward_request(service_name, "/status")
            status[service_name] = service_status
        except Exception as e:
            status[service_name] = {
                "status": "error",
                "error": str(e)
            }
    
    return status

@app.get("/trading-pairs")
async def get_trading_pairs():
    """Get configured trading pairs"""
    return {
        "trading_pairs": DEFAULT_TRADING_PAIRS,
        "count": len(DEFAULT_TRADING_PAIRS)
    }

# Data service routes
@app.get("/data/candles/{trading_pair:path}")
async def get_candles(trading_pair: str, limit: int = 50):
    """Get latest candles for a trading pair"""
    return await forward_request(
        "data_collection", 
        f"/candles/{trading_pair}?limit={limit}"
    )

# ML service routes
@app.get("/ml/models")
async def get_models():
    """Get list of trained models"""
    return await forward_request("ml_training", "/models")

@app.get("/ml/models/{trading_pair:path}")
async def get_models_for_pair(trading_pair: str):
    """Get trained models for a specific trading pair"""
    logger.info(f"🔍 Received request for models with trading_pair: '{trading_pair}'")
    return await forward_request(
        "ml_training", 
        f"/models/{trading_pair}"
    )

@app.post("/ml/train")
async def train_model(request: Request):
    """Train a new model for a trading pair"""
    # Forward the request directly
    return await forward_request(
        request,
        "ml_training", 
        "/train"
    )

@app.post("/ml/train-all")
async def train_all_models(request: Request):
    """Train models for all configured trading pairs"""
    # Forward the request directly
    return await forward_request(
        request,
        "ml_training", 
        "/train-all"
    )

# Prediction service routes
@app.post("/predict")
async def make_prediction(request: Request):
    """Generate a prediction for a trading pair"""
    try:
        data = await request.json()
        trading_pair = data.get("trading_pair")
        logger.info(f"🔮 POST prediction request for trading pair: {trading_pair}")
        
        # Forward the request directly
        result = await forward_request(
            request,
            "prediction", 
            "/predict"
        )
        logger.info(f"✅ POST prediction successful for {trading_pair}")
        return result
    except Exception as e:
        logger.error(f"❌ Error in POST prediction endpoint: {str(e)}")
        # Try direct request to prediction service as fallback
        try:
            config = service_config["prediction"]
            # Use HTTPS for public domains (Railway), HTTP for localhost
            protocol = "https" if "localhost" not in config['host'] else "http"
            prediction_url = f"{protocol}://{config['host']}:{config['port']}/predict"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(prediction_url, json=data)
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Fallback POST prediction successful")
                    return result
                else:
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"Prediction service error: {response.text}"
                    )
        except Exception as fallback_error:
            logger.error(f"❌ Fallback POST prediction failed: {str(fallback_error)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get prediction: {str(e)}"
            )

@app.get("/predict/{trading_pair}")
async def quick_prediction(trading_pair: str, model_type: str = None, model_name: str = None):
    """Quick prediction endpoint for a specific trading pair"""
    try:
        logger.info(f"🔮 Prediction request for trading pair: {trading_pair}")
        
        # Use query parameters instead of path parameters to avoid URL encoding issues
        path = f"/predict-by-query?trading_pair={trading_pair}"
        if model_type:
            path += f"&model_type={model_type}"
        if model_name:
            path += f"&model_name={model_name}"
        
        result = await forward_request("prediction", path)
        logger.info(f"✅ Prediction successful for {trading_pair}")
        return result
    except Exception as e:
        logger.error(f"❌ Error in prediction endpoint for {trading_pair}: {str(e)}")
        # Try direct request to prediction service
        try:
            prediction_url = get_service_url("prediction", "/predict-by-query")
            
            async with httpx.AsyncClient() as client:
                params = {"trading_pair": trading_pair}
                if model_type:
                    params["model_type"] = model_type
                if model_name:
                    params["model_name"] = model_name
                response = await client.get(prediction_url, params=params)
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ Direct prediction successful for {trading_pair}")
                    return result
                else:
                    # Return a clear error message instead of a random prediction
                    logger.warning(f"⚠️ No prediction available for {trading_pair}")
                    
                    raise HTTPException(
                        status_code=404,
                        detail=f"No prediction available for {trading_pair}. Please try again later."
                    )
        except Exception as direct_error:
            logger.error(f"❌ Direct prediction request failed: {str(direct_error)}")
            
            # Return a clear error message
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get prediction for {trading_pair}. Please try again later."
            )

@app.post("/predictions/start")
async def start_prediction_service():
    """Start continuous prediction service"""
    return await forward_request(
        "prediction", 
        "/start", 
        method="POST"
    )

@app.post("/predictions/stop")
async def stop_prediction_service():
    """Stop continuous prediction service"""
    return await forward_request(
        "prediction", 
        "/stop", 
        method="POST"
    )

@app.post("/predictions/select_model")
async def select_prediction_model(request: Request):
    """Select a model for a specific trading pair without starting predictions"""
    return await forward_request(
        request,
        "prediction", 
        "/select_model"
    )

# WebSocket proxy for market data
@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    """WebSocket proxy for market data"""
    await manager.connect(websocket)
    
    # Connect to data service WebSocket
    data_service_ws = None
    
    try:
        # Get data service WebSocket URL
        config = service_config["data_collection"]
        # Use WSS for public domains (Railway), WS for localhost
        ws_protocol = "wss" if "localhost" not in config['host'] else "ws"
        ws_url = f"{ws_protocol}://{config['host']}:{config['port']}{config['ws_path']}"
        
        # Connect to data service WebSocket
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.websocket_connect(ws_url) as data_service_ws:
                # Forward client messages to data service
                client_task = asyncio.create_task(forward_client_messages(websocket, data_service_ws))
                
                # Forward data service messages to client
                async for message in data_service_ws:
                    if message.type == "text":
                        await websocket.send_text(message.text)
                    elif message.type == "bytes":
                        await websocket.send_bytes(message.bytes)
                
                # Cancel client task when data service disconnects
                client_task.cancel()
    
    except WebSocketDisconnect:
        logger.info("📡 Client disconnected from market data WebSocket")
    except Exception as e:
        logger.error(f"❌ Market data WebSocket error: {str(e)}")
    finally:
        await manager.disconnect(websocket)

# Direct WebSocket handler for predictions
@app.websocket("/ws/predictions")
async def websocket_predictions(websocket: WebSocket):
    """WebSocket handler for predictions - directly managed by API gateway"""
    await manager.connect(websocket)
    
    try:
        # Send welcome message
        await manager.send_personal_message({
            "type": "connection_status",
            "status": "connected",
            "message": "Connected to prediction service"
        }, websocket)
        
        # Listen for messages from the client
        while True:
            message = await websocket.receive_json()
            logger.info(f"📡 Received message from client: {message}")
            
            # Handle subscription requests
            if message.get("action") == "subscribe":
                trading_pair = message.get("trading_pair")
                if trading_pair:
                    # Add to subscriptions
                    if websocket not in manager.subscriptions:
                        manager.subscriptions[websocket] = []
                    
                    if trading_pair not in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].append(trading_pair)
                        
                    logger.info(f"📡 Client subscribed to {trading_pair}")
                    
                    # Also subscribe in the prediction service
                    try:
                        config = service_config["prediction"]
                        # Use HTTPS for public domains (Railway), HTTP for localhost
                        protocol = "https" if "localhost" not in config['host'] else "http"
                        subscribe_url = get_service_url("prediction", "/subscribe")
                        
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(subscribe_url, params={"trading_pair": trading_pair})
                            if response.status_code == 200:
                                logger.info(f"✅ Subscribed to {trading_pair} in prediction service")
                                
                                # If this is the only active subscription, also set it as priority
                                active_pairs = len(manager.get_subscribed_pairs())
                                if active_pairs == 1:
                                    # Use HTTPS for public domains (Railway), HTTP for localhost
                                    protocol = "https" if "localhost" not in config['host'] else "http"
                                    priority_url = get_service_url("prediction", "/set-priority")
                                    priority_response = await client.post(priority_url, params={"trading_pair": trading_pair})
                                    if priority_response.status_code == 200:
                                        logger.info(f"✅ Set {trading_pair} as priority pair in prediction service")
                            else:
                                logger.error(f"❌ Failed to subscribe to {trading_pair} in prediction service: {response.status_code}")
                                logger.error(f"❌ Response: {response.text}")
                    except Exception as e:
                        logger.error(f"❌ Error subscribing to prediction service: {str(e)}")
                        logger.error(f"❌ Error type: {type(e).__name__}")
                        logger.error(f"❌ Full error details: {repr(e)}")
                    
                    # Send confirmation
                    await manager.send_personal_message({
                        "type": "subscription_status",
                        "status": "subscribed",
                        "trading_pair": trading_pair
                    }, websocket)
                    
                    # Fetch and send latest prediction
                    try:
                        prediction_url = get_service_url("prediction", "/predict-by-query")
                        logger.info(f"📡 Fetching initial prediction from: {prediction_url}?trading_pair={trading_pair}")
                        
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                response = await client.get(prediction_url, params={"trading_pair": trading_pair})
                                if response.status_code == 200:
                                    prediction_data = response.json()
                                    
                                    # Format as WebSocket message
                                    ws_message = {
                                        "type": "prediction",
                                        "trading_pair": trading_pair,
                                        "timestamp": prediction_data.get("timestamp"),
                                        "prediction": prediction_data.get("prediction"),
                                        "probability": prediction_data.get("probability"),
                                        "confidence": prediction_data.get("confidence"),
                                        "expected_change": prediction_data.get("expected_change"),
                                        "model_used": prediction_data.get("model_used")
                                    }
                                    
                                    # Send to client
                                    await manager.send_personal_message(ws_message, websocket)
                                    logger.info(f"📡 Sent latest prediction for {trading_pair}")
                                else:
                                    logger.error(f"❌ Error fetching latest prediction: Status code {response.status_code}")
                                    logger.error(f"❌ Response: {response.text}")
                                    
                                    # Send no prediction message
                                    await send_no_prediction_message(websocket, trading_pair)
                        except httpx.HTTPError as http_err:
                            logger.error(f"❌ HTTP error fetching latest prediction: {str(http_err)}")
                            await send_no_prediction_message(websocket, trading_pair)
                        except asyncio.TimeoutError:
                            logger.error(f"❌ Timeout fetching latest prediction for {trading_pair}")
                            await send_no_prediction_message(websocket, trading_pair)
                    except Exception as e:
                        if str(e):
                            logger.error(f"❌ Error fetching latest prediction: {str(e)}")
                        else:
                            logger.error(f"❌ Error fetching latest prediction: Unknown error (empty exception message)")
                            logger.error(f"❌ Error type: {type(e).__name__}")
                        
                        # Send no prediction message
                        await send_no_prediction_message(websocket, trading_pair)
            
            # Handle unsubscribe requests
            elif message.get("action") == "unsubscribe":
                trading_pair = message.get("trading_pair")
                if trading_pair and websocket in manager.subscriptions:
                    if trading_pair in manager.subscriptions[websocket]:
                        manager.subscriptions[websocket].remove(trading_pair)
                        
                    logger.info(f"📡 Client unsubscribed from {trading_pair}")
                    
                    # Check if any other clients are still subscribed to this pair
                    all_subscribed_pairs = manager.get_subscribed_pairs()
                    if trading_pair not in all_subscribed_pairs:
                        # No one is subscribed to this pair anymore, unsubscribe from prediction service
                        try:
                            config = service_config["prediction"]
                            # Use HTTPS for public domains (Railway), HTTP for localhost
                            protocol = "https" if "localhost" not in config['host'] else "http"
                            unsubscribe_url = get_service_url("prediction", "/unsubscribe")
                            
                            async with httpx.AsyncClient(timeout=30.0) as client:
                                response = await client.post(unsubscribe_url, params={"trading_pair": trading_pair})
                                if response.status_code == 200:
                                    logger.info(f"✅ Unsubscribed from {trading_pair} in prediction service")
                                else:
                                    logger.error(f"❌ Failed to unsubscribe from {trading_pair} in prediction service: {response.status_code}")
                                    logger.error(f"❌ Response: {response.text}")
                                    
                            # If there are other pairs, set one as priority
                            if all_subscribed_pairs:
                                new_priority = next(iter(all_subscribed_pairs))
                                # Use HTTPS for public domains (Railway), HTTP for localhost
                                protocol = "https" if "localhost" not in config['host'] else "http"
                                priority_url = f"{protocol}://{config['host']}:{config['port']}/set-priority"
                                async with httpx.AsyncClient(timeout=30.0) as priority_client:
                                    priority_response = await priority_client.post(priority_url, params={"trading_pair": new_priority})
                                    if priority_response.status_code == 200:
                                        logger.info(f"✅ Set {new_priority} as new priority pair in prediction service")
                        except Exception as e:
                            logger.error(f"❌ Error unsubscribing from prediction service: {str(e)}")
                    
                    # Send confirmation
                    await manager.send_personal_message({
                        "type": "subscription_status",
                        "status": "unsubscribed",
                        "trading_pair": trading_pair
                    }, websocket)
    
    except WebSocketDisconnect:
        logger.info("📡 Client disconnected from predictions WebSocket")
    except Exception as e:
        logger.error(f"❌ Predictions WebSocket error: {str(e)}")
    finally:
        await manager.disconnect(websocket)

async def forward_client_messages(client_ws: WebSocket, service_ws):
    """Forward messages from client to service"""
    try:
        while True:
            # Wait for client message
            message = await client_ws.receive()
            
            # Forward to service
            if message.get("type") == "websocket.receive":
                if "text" in message:
                    await service_ws.send_text(message["text"])
                elif "bytes" in message:
                    await service_ws.send_bytes(message["bytes"])
    
    except WebSocketDisconnect:
        logger.info("📡 Client disconnected while forwarding messages")
    except Exception as e:
        logger.error(f"❌ Error forwarding client messages: {str(e)}")

# Unified WebSocket endpoint
@app.websocket("/ws")
async def websocket_unified(websocket: WebSocket):
    """Unified WebSocket endpoint for all data"""
    await manager.connect(websocket)
    
    # Track active service connections
    service_connections = {}
    
    try:
        # Process client messages
        while True:
            # Wait for client message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            service = message.get("service")
            trading_pair = message.get("trading_pair")
            
            if action == "subscribe":
                # Subscribe to a service
                if service == "market_data":
                    # Connect to data service if not already connected
                    if "data_collection" not in service_connections:
                        await connect_to_service(websocket, "data_collection", service_connections)
                    
                    # Forward subscription to data service
                    if "data_collection" in service_connections:
                        await service_connections["data_collection"].send_text(json.dumps({
                            "action": "subscribe",
                            "trading_pair": trading_pair
                        }))
                
                elif service == "predictions":
                    # Connect to prediction service if not already connected
                    if "prediction" not in service_connections:
                        await connect_to_service(websocket, "prediction", service_connections)
                    
                    # Forward subscription to prediction service
                    if "prediction" in service_connections:
                        await service_connections["prediction"].send_text(json.dumps({
                            "action": "subscribe",
                            "trading_pair": trading_pair
                        }))
            
            elif action == "get_historical":
                # Get historical data
                if service == "market_data":
                    # Connect to data service if not already connected
                    if "data_collection" not in service_connections:
                        await connect_to_service(websocket, "data_collection", service_connections)
                    
                    # Forward request to data service
                    if "data_collection" in service_connections:
                        await service_connections["data_collection"].send_text(json.dumps({
                            "action": "get_historical",
                            "trading_pair": trading_pair,
                            "limit": message.get("limit", 50)
                        }))
    
    except WebSocketDisconnect:
        logger.info("📡 Client disconnected from unified WebSocket")
    except Exception as e:
        logger.error(f"❌ Unified WebSocket error: {str(e)}")
    finally:
        # Disconnect from all services
        for service_name, connection in service_connections.items():
            try:
                await connection.close()
            except Exception:
                pass
        
        await manager.disconnect(websocket)

async def connect_to_service(client_ws: WebSocket, service_name: str, connections: dict):
    """Connect to a service WebSocket"""
    try:
        # Get service WebSocket URL
        config = service_config[service_name]
        # Use WSS for public domains (Railway), WS for localhost
        ws_protocol = "wss" if "localhost" not in config['host'] else "ws"
        ws_url = f"{ws_protocol}://{config['host']}:{config['port']}{config['ws_path']}"
        
        # Connect to service WebSocket
        async with httpx.AsyncClient(timeout=None) as client:
            service_ws = await client.websocket_connect(ws_url)
            
            # Store connection
            connections[service_name] = service_ws
            
            # Start task to forward messages from service to client
            asyncio.create_task(forward_service_messages(service_ws, client_ws, service_name, connections))
            
            return True
    
    except Exception as e:
        logger.error(f"❌ Error connecting to {service_name} WebSocket: {str(e)}")
        return False

async def forward_service_messages(service_ws, client_ws: WebSocket, service_name: str, connections: dict):
    """Forward messages from service to client"""
    try:
        async for message in service_ws:
            if message.type == "text":
                # Parse message and add service name
                data = json.loads(message.text)
                data["service"] = service_name
                
                # Forward to client
                await client_ws.send_json(data)
            elif message.type == "bytes":
                await client_ws.send_bytes(message.bytes)
    
    except Exception as e:
        logger.error(f"❌ Error forwarding {service_name} messages: {str(e)}")
    finally:
        # Remove connection from tracking
        if service_name in connections:
            del connections[service_name]

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def broadcast_no_prediction_message(trading_pair: str):
    """Broadcast a message to all subscribed clients indicating that no prediction is available"""
    # Create no prediction message
    ws_message = {
        "type": "no_prediction", 
        "trading_pair": trading_pair, 
        "timestamp": datetime.now().isoformat(),
        "message": "No prediction available. Please try again later."
    }
    
    # Broadcast to all subscribed clients
    await manager.broadcast(ws_message, trading_pair)
    logger.info(f"📡 Broadcasted no prediction message for {trading_pair}")

async def send_no_prediction_message(websocket: WebSocket, trading_pair: str):
    """Send a message to the client indicating that no prediction is available"""
    # Create no prediction message
    ws_message = {
        "type": "no_prediction", 
        "trading_pair": trading_pair, 
        "timestamp": datetime.now().isoformat(),
        "message": "No prediction available. Please try again later."
    }
    
    # Send to the specific client
    await manager.send_personal_message(ws_message, websocket)
    logger.info(f"📡 Sent no prediction message for {trading_pair}")

async def poll_predictions():
    """Background task to poll for new predictions"""
    global gateway_state, manager
    
    # Track the last candle timestamp we polled for each trading pair
    last_candle_timestamps = {}
    
    try:
        while gateway_state["is_running"]:
            # Get current time and round down to the nearest minute
            # This represents the timestamp of the candle that just completed
            now = datetime.now()
            current_candle_time = now.replace(second=0, microsecond=0)
            
            # Get all unique trading pairs from subscriptions
            trading_pairs = set()
            for subs in manager.subscriptions.values():
                trading_pairs.update(subs)
            
            # If we have subscriptions, poll for predictions
            if trading_pairs:
                for trading_pair in trading_pairs:
                    try:
                        # Check if we already polled for this candle
                        last_poll_time = last_candle_timestamps.get(trading_pair)
                        
                        if last_poll_time is None or last_poll_time < current_candle_time:
                            logger.info(f"🔍 Polling prediction for {trading_pair} for candle at {current_candle_time.isoformat()}")
                            
                            # Get prediction from prediction service
                            prediction_url = get_service_url("prediction", "/predict-by-query")
                            logger.info(f"🔍 Polling prediction from: {prediction_url}?trading_pair={trading_pair}")
                            
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    response = await client.get(prediction_url, params={"trading_pair": trading_pair})
                                    if response.status_code == 200:
                                        prediction_data = response.json()
                                        
                                        # Check if this is a new prediction
                                        last_prediction = gateway_state["last_predictions"].get(trading_pair)
                                        current_timestamp = prediction_data.get("timestamp")
                                        
                                        if not last_prediction or last_prediction.get("timestamp") != current_timestamp:
                                            # Store the new prediction
                                            gateway_state["last_predictions"][trading_pair] = prediction_data
                                            
                                            # Format as WebSocket message
                                            ws_message = {
                                                "type": "prediction",
                                                "trading_pair": trading_pair,
                                                "timestamp": prediction_data.get("timestamp"),
                                                "prediction": prediction_data.get("prediction"),
                                                "probability": prediction_data.get("probability"),
                                                "confidence": prediction_data.get("confidence"),
                                                "expected_change": prediction_data.get("expected_change"),
                                                "model_used": prediction_data.get("model_used")
                                            }
                                            
                                            # Broadcast to subscribed clients
                                            await manager.broadcast(ws_message, trading_pair)
                                            logger.info(f"📡 Broadcasted new prediction for {trading_pair}")
                                        
                                        # Update the last poll time for this pair
                                        last_candle_timestamps[trading_pair] = current_candle_time
                                    else:
                                        logger.error(f"❌ Error polling prediction: Status code {response.status_code}")
                                        logger.error(f"❌ Response: {response.text}")
                                        
                                        # Broadcast no prediction message
                                        await broadcast_no_prediction_message(trading_pair)
                            except httpx.HTTPError as http_err:
                                logger.error(f"❌ HTTP error polling prediction: {str(http_err)}")
                                await broadcast_no_prediction_message(trading_pair)
                            except asyncio.TimeoutError:
                                logger.error(f"❌ Timeout polling prediction for {trading_pair}")
                                await broadcast_no_prediction_message(trading_pair)
                        else:
                            logger.info(f"⏭️ Skipping poll for {trading_pair} - already polled for candle at {current_candle_time.isoformat()}")
                    except Exception as e:
                        if str(e):
                            logger.error(f"❌ Error polling prediction for {trading_pair}: {str(e)}")
                        else:
                            logger.error(f"❌ Error polling prediction for {trading_pair}: Unknown error (empty exception message)")
                            logger.error(f"❌ Error type: {type(e).__name__}")
            
            # Sleep until the next minute starts (to match 1-minute candlestick timeframe)
            now = datetime.now()
            
            # For 1-minute candles, we want to poll for predictions right after they're generated
            # Example: For 10:01:00 candle, prediction service generates at 10:02:03, we poll at 10:02:05
            seconds_to_next_minute = 60 - now.second
            if seconds_to_next_minute < 5:  # If we're very close to the next minute, wait for the minute after
                seconds_to_next_minute += 60
            
            # Add buffer to ensure prediction is available (5 seconds after the minute)
            seconds_to_next_minute += 5
            
            logger.info(f"⏱️ Waiting {seconds_to_next_minute} seconds until next candle (1-minute timeframe)")
            logger.info(f"⏱️ Next polling at: {(now + timedelta(seconds=seconds_to_next_minute)).strftime('%H:%M:%S')}")
            
            await asyncio.sleep(seconds_to_next_minute)
    except asyncio.CancelledError:
        logger.info("🛑 Prediction polling task cancelled")
    except Exception as e:
        logger.error(f"❌ Error in prediction polling task: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    global http_client, gateway_state
    
    setup_signal_handlers()
    
    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=10.0)
    
    # Start prediction polling task
    gateway_state["prediction_polling_task"] = asyncio.create_task(poll_predictions())
    logger.info("✅ Prediction polling task started")
    
    logger.info("✅ API Gateway started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global http_client, gateway_state
    
    # Set running flag to false
    gateway_state["is_running"] = False
    
    # Cancel prediction polling task
    if gateway_state["prediction_polling_task"]:
        gateway_state["prediction_polling_task"].cancel()
        try:
            await gateway_state["prediction_polling_task"]
        except asyncio.CancelledError:
            pass
        logger.info("🛑 Prediction polling task cancelled")
    
    # Close HTTP client
    if http_client:
        await http_client.aclose()
    
    logger.info("✅ API Gateway shut down successfully")

def run_service(host: str = "0.0.0.0", port: int = 5001, reload: bool = False):
    """Run the API gateway"""
    print("🚀 OTC Predictor - API Gateway")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor API Gateway')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5001, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)
