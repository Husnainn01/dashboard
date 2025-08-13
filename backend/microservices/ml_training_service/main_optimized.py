"""
Optimized ML Training Service for OTC Predictor
Uses XGBoost as the primary model with advanced feature engineering
"""

import os
import sys
import argparse
import asyncio
import logging
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import local modules
from database.mongodb_models import MongoDBManager
from ml_models.xgboost_trainer import XGBoostTrainer
from ml_models.feature_engineering import FeatureEngineer
from config import DEFAULT_TRADING_PAIRS

# Import the optimized ML service
from ml_service import OptimizedMLService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="OTC Predictor Optimized ML Training Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
mongodb_manager = None
ml_service = None
training_queue = asyncio.Queue()
training_jobs = {}
is_training_worker_running = False

# Pydantic models
class TrainingRequest(BaseModel):
    """Request model for training a new ML model"""
    trading_pair: str
    force_retrain: bool = False
    
class TrainingResponse(BaseModel):
    """Response model for training requests"""
    job_id: str
    trading_pair: str
    status: str
    submitted_at: datetime

class ConfigRequest(BaseModel):
    """Request model for updating service configuration"""
    retraining_enabled: Optional[bool] = None
    retraining_interval_hours: Optional[int] = None
    min_samples_for_retraining: Optional[int] = None
    volatility_threshold: Optional[float] = None
    data_limit: Optional[int] = None
    auto_training_enabled: Optional[bool] = None
    trading_pairs: Optional[List[str]] = None

# Initialization functions
async def initialize_service():
    """Initialize the ML training service"""
    global mongodb_manager, ml_service
    
    logger.info("🚀 Initializing Optimized ML Training Service...")
    
    # Initialize MongoDB connection
    logger.info("🔌 Connecting to MongoDB...")
    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor")
    logger.info(f"Using MongoDB URI: {mongodb_uri}")
    mongodb_manager = MongoDBManager(uri=mongodb_uri)
    
    # Try to connect to MongoDB with retries
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        logger.info(f"MongoDB connection attempt {attempt}/{max_retries}")
        if await mongodb_manager.connect():
            logger.info("✅ MongoDB connected successfully")
            break
        else:
            logger.warning(f"⚠️ MongoDB connection attempt {attempt} failed")
            if attempt < max_retries:
                await asyncio.sleep(5)  # Wait before retrying
    
    if not mongodb_manager.is_connected:
        logger.error("❌ Failed to connect to MongoDB after multiple attempts")
        return False
    
    # Initialize ML service
    logger.info("🧠 Initializing Optimized ML Service...")
    ml_service = OptimizedMLService(mongodb_manager)
    await ml_service.start()
    
    # Store start time for uptime calculation
    ml_service._start_time = datetime.now()
    
    logger.info("✅ Optimized ML Training Service initialized successfully")
    return True

async def start_training_worker():
    """Start the background training worker"""
    global is_training_worker_running
    
    if not is_training_worker_running:
        is_training_worker_running = True
        asyncio.create_task(run_training_worker())
        logger.info("🧠 Training worker started")

async def run_training_worker():
    """Background worker to process training jobs from the queue"""
    global training_jobs, is_training_worker_running
    
    logger.info("🔄 Training worker running")
    
    while is_training_worker_running:
        try:
            # Get job from queue with timeout
            try:
                job = await asyncio.wait_for(training_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # No job available, continue loop
                continue
            
            job_id = job["job_id"]
            trading_pair = job["trading_pair"]
            force_retrain = job.get("force_retrain", False)
            
            logger.info(f"🏋️ Processing training job {job_id} for {trading_pair}")
            
            # Update job status
            training_jobs[job_id]["status"] = "training"
            training_jobs[job_id]["progress"] = 10
            
            try:
                # Train model
                result = await ml_service.train_model(
                    trading_pair=trading_pair,
                    background=False  # Run synchronously in this worker
                )
                
                # Update job with results
                training_jobs[job_id]["status"] = "completed"
                training_jobs[job_id]["progress"] = 100
                training_jobs[job_id]["result"] = result
                training_jobs[job_id]["completed_at"] = datetime.now()
                
                logger.info(f"✅ Training job {job_id} completed successfully")
                
            except Exception as e:
                logger.error(f"❌ Error in training job {job_id}: {str(e)}")
                training_jobs[job_id]["status"] = "failed"
                training_jobs[job_id]["error"] = str(e)
                training_jobs[job_id]["completed_at"] = datetime.now()
            
            # Mark task as done
            training_queue.task_done()
            
            # Clean up old jobs periodically
            if training_queue.qsize() == 0:
                await clean_old_jobs()
                
        except Exception as e:
            logger.error(f"❌ Error in training worker: {str(e)}")
            await asyncio.sleep(5)  # Wait before continuing
    
    logger.info("🛑 Training worker stopped")

async def clean_old_jobs():
    """Clean up old completed jobs"""
    global training_jobs
    
    # Keep jobs for 24 hours
    retention_period = timedelta(hours=24)
    current_time = datetime.now()
    
    jobs_to_remove = []
    
    for job_id, job in training_jobs.items():
        if job["status"] in ["completed", "failed"]:
            completed_at = job.get("completed_at")
            if completed_at and (current_time - completed_at) > retention_period:
                jobs_to_remove.append(job_id)
    
    # Remove old jobs
    for job_id in jobs_to_remove:
        del training_jobs[job_id]
    
    if jobs_to_remove:
        logger.info(f"🧹 Cleaned up {len(jobs_to_remove)} old training jobs")

# API routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OTC Predictor Optimized ML Training Service",
        "version": "2.0.0",
        "status": "running",
        "docs_url": "/docs"
    }

@app.get("/status")
async def get_status():
    """Get detailed service status"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    status = await ml_service.get_service_status()
    
    # Add queue information
    status["queue"] = {
        "size": training_queue.qsize(),
        "active_jobs": len([j for j in training_jobs.values() if j["status"] == "training"]),
        "pending_jobs": len([j for j in training_jobs.values() if j["status"] == "pending"]),
        "completed_jobs": len([j for j in training_jobs.values() if j["status"] == "completed"]),
        "failed_jobs": len([j for j in training_jobs.values() if j["status"] == "failed"])
    }
    
    return status

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not ml_service:
        return {"status": "initializing"}
    
    mongodb_status = "connected" if mongodb_manager and mongodb_manager.is_connected else "disconnected"
    
    return {
        "status": "healthy",
        "mongodb": mongodb_status,
        "training_worker": "running" if is_training_worker_running else "stopped"
    }

@app.get("/models")
async def get_models():
    """Get list of trained models"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        models = await ml_service.list_models()
        return models
    except Exception as e:
        logger.error(f"❌ Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")

@app.get("/models/pair/{trading_pair}")
async def get_models_for_pair(trading_pair: str = PathParam(...)):
    """Get trained models for a specific trading pair"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        models = await ml_service.list_models(trading_pair=trading_pair)
        return models
    except Exception as e:
        logger.error(f"❌ Error listing models for {trading_pair}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")

@app.post("/train", response_model=TrainingResponse)
async def train_model(request: TrainingRequest):
    """Train a new model for a trading pair"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Create job ID
    job_id = f"train_{request.trading_pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create job
    job = {
        "job_id": job_id,
        "trading_pair": request.trading_pair,
        "force_retrain": request.force_retrain,
        "status": "pending",
        "progress": 0,
        "submitted_at": datetime.now()
    }
    
    # Store job
    training_jobs[job_id] = job
    
    # Add to queue
    await training_queue.put(job)
    
    # Make sure worker is running
    if not is_training_worker_running:
        await start_training_worker()
    
    logger.info(f"📋 Training job {job_id} queued for {request.trading_pair}")
    
    # Return response
    return TrainingResponse(
        job_id=job_id,
        trading_pair=request.trading_pair,
        status="pending",
        submitted_at=job["submitted_at"]
    )

@app.get("/train/status/{job_id}")
async def get_training_status(job_id: str):
    """Get status of a training job"""
    if job_id in training_jobs:
        return training_jobs[job_id]
    else:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} not found")

@app.post("/train/all")
async def train_all_models(force_retrain: bool = False):
    """Train models for all configured trading pairs"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        results = await ml_service.train_all_models(force_retrain=force_retrain)
        return results
    except Exception as e:
        logger.error(f"❌ Error training all models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error training all models: {str(e)}")

@app.get("/queue")
async def get_queue_status():
    """Get status of the training queue"""
    queue_size = training_queue.qsize()
    
    active_jobs = [j for j in training_jobs.values() if j["status"] == "training"]
    pending_jobs = [j for j in training_jobs.values() if j["status"] == "pending"]
    
    return {
        "queue_size": queue_size,
        "active_jobs": len(active_jobs),
        "pending_jobs": len(pending_jobs),
        "active_job_details": active_jobs,
        "pending_job_details": pending_jobs
    }

@app.get("/config")
async def get_config():
    """Get current service configuration"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        config = await ml_service.get_config()
        return config
    except Exception as e:
        logger.error(f"❌ Error getting config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")

@app.put("/config")
async def update_config(config: ConfigRequest):
    """Update service configuration"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Convert Pydantic model to dict, excluding None values
        config_updates = {k: v for k, v in config.dict().items() if v is not None}
        
        if not config_updates:
            return await ml_service.get_config()
        
        updated_config = await ml_service.update_config(config_updates)
        return updated_config
    except Exception as e:
        logger.error(f"❌ Error updating config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")

@app.get("/models/{model_name}")
async def get_model_details(model_name: str):
    """Get detailed information about a specific model"""
    if not ml_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        model_details = await ml_service.get_model_details(model_name)
        
        if 'error' in model_details:
            raise HTTPException(status_code=404, detail=model_details['error'])
            
        return model_details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting model details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting model details: {str(e)}")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}. Initiating graceful shutdown...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    # Record start time for uptime calculation
    app.start_time = datetime.now()
    
    setup_signal_handlers()
    success = await initialize_service()
    
    if not success:
        logger.error("❌ Failed to initialize service")
        return
    
    # Auto-start training worker
    global is_training_worker_running
    if not is_training_worker_running:
        is_training_worker_running = True
        asyncio.create_task(run_training_worker())
        logger.info("🧠 Training worker started automatically")
        
    logger.info("✅ Optimized ML Training Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global mongodb_manager, ml_service, is_training_worker_running
    
    # Stop training worker
    is_training_worker_running = False
    
    # Stop ML service
    if ml_service:
        await ml_service.stop()
    
    # Disconnect from MongoDB
    if mongodb_manager:
        await mongodb_manager.disconnect()
    
    logger.info("✅ Optimized ML Training Service shut down successfully")

def run_service(host: str = "0.0.0.0", port: int = 5002, reload: bool = False):
    """Run the ML training service"""
    print("🚀 OTC Predictor - Optimized ML Training Service")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("main_optimized:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor Optimized ML Training Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5002, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)
