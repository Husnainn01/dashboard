"""
ML Training Service for OTC Predictor
Handles model training, storage, and management
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
from ml_models.model_trainer import ModelTrainer
from ml_models.feature_engineering import FeatureEngineer
from ml_models.xgboost_trainer import XGBoostTrainer
from ml_models.lightgbm_trainer import LightGBMTrainer
from ml_models.random_forest_trainer import RandomForestTrainer
from config import DEFAULT_TRADING_PAIRS
from shared.pairs import normalize_internal, to_api_asset

# Import storage and data retention services
import os
import sys
# Add the current directory to the path so we can import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from storage import ModelStorageService
from model_storage import ModelStorageManager
from data_retention import DataRetentionService
from config import STORAGE_CONFIG, DATA_RETENTION, AUTO_TRAINING

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="OTC Predictor ML Training Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
mongodb_manager = None
model_trainer = None
feature_engineer = None
model_storage_manager = None
data_retention_service = None
training_queue = asyncio.Queue()
training_jobs = {}
is_training_worker_running = False
service_ready = False
trainer_helpers = {}

# Pydantic models
class TrainingRequest(BaseModel):
    """Request model for training a new ML model"""
    trading_pair: str
    model_type: str = "xgboost"
    force_retrain: bool = False
    
class TrainingResponse(BaseModel):
    """Response model for training requests"""
    job_id: str
    trading_pair: str
    model_type: str
    status: str
    submitted_at: datetime

class StorageConfigRequest(BaseModel):
    """Request model for updating storage configuration"""
    storage_type: str
    r2_config: Optional[Dict[str, Any]] = None
    local_dir: Optional[str] = None

class RetentionConfigRequest(BaseModel):
    """Request model for updating data retention configuration"""
    retention_days: int
    enable_auto_cleanup: bool = True
    cleanup_interval_hours: int = 24
    
class AutoTrainingConfigRequest(BaseModel):
    """Request model for updating auto-training configuration"""
    enabled: bool
    schedule_interval_hours: int = 24
    min_new_samples: int = 50
    trading_pairs: List[str] = None
    model_types: List[str] = None
    max_concurrent_jobs: int = 2

# Initialization functions
async def initialize_service():
    """Initialize the ML training service"""
    global mongodb_manager, model_trainer, feature_engineer
    global model_storage_manager, data_retention_service, training_queue
    global trainer_helpers
    
    logger.info("🚀 Initializing ML Training Service...")
    
    # Initialize MongoDB connection
    logger.info("🔌 Connecting to MongoDB...")
    mongodb_uri = os.environ.get("MONGODB_URI", "")
    if not mongodb_uri:
        logger.warning("⚠️ MONGODB_URI not set. Database features will be unavailable.")
    else:
        logger.info(f"Using MongoDB URI: {mongodb_uri[:30]}...")
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
                logger.info("Retrying in 2 seconds...")
                await asyncio.sleep(2)
            else:
                logger.error("❌ All MongoDB connection attempts failed")
                # Continue without MongoDB for now
                break
    # MongoDB connection attempts completed
    
    # Initialize feature engineer
    feature_engineer = FeatureEngineer(mongodb_manager)
    
    # Initialize model trainer
    model_trainer = ModelTrainer(mongodb_manager)
    
    # Initialize specialized trainer helpers
    try:
        trainer_helpers = {
            "xgboost": XGBoostTrainer(mongodb_manager),
            "lightgbm": LightGBMTrainer(mongodb_manager),
            "random_forest": RandomForestTrainer(mongodb_manager),
        }
        logger.info("✅ Specialized trainer helpers initialized: xgboost, lightgbm, random_forest")
    except Exception as e:
        logger.error(f"❌ Error initializing trainer helpers: {str(e)}")
        trainer_helpers = {}
    
    # Initialize model storage manager
    model_storage_manager = ModelStorageManager()
    
    # Initialize data retention service
    data_retention_service = DataRetentionService(mongodb_manager)
    
    # Setup TTL indexes for data retention
    try:
        await data_retention_service.setup_ttl_indexes()
    except Exception as e:
        logger.error(f"❌ Error setting up TTL indexes: {str(e)}")
        # Continue without TTL indexes
    
    logger.info("✅ ML components initialized")

    # Start training worker
    start_training_worker()

    # Start data retention service if enabled
    if DATA_RETENTION.get("enable_auto_cleanup", True):
        await data_retention_service.start_auto_cleanup()

    global service_ready
    service_ready = True
    return True

def start_training_worker():
    """Start the background training worker"""
    global is_training_worker_running
    
    if not is_training_worker_running:
        asyncio.create_task(run_training_worker())
        is_training_worker_running = True
        logger.info("✅ Training worker started")

async def run_training_worker():
    """Background worker to process training jobs from the queue"""
    global training_jobs, training_queue, is_training_worker_running
    
    logger.info("🧠 Training worker running")
    
    try:
        while True:
            # Get next job from queue
            job_id = await training_queue.get()
            job = training_jobs.get(job_id)
            
            if not job:
                logger.warning(f"⚠️ Job {job_id} not found in training jobs")
                training_queue.task_done()
                continue
            
            # Update job status
            job["status"] = "training"
            job["started_at"] = datetime.now()
            
            logger.info(f"🧠 Training model for {job['trading_pair']} ({job_id})")
            
            try:
                # Dispatch to specialized trainer helper if available, else fallback to ModelTrainer
                model_type = job["model_type"]
                helper = trainer_helpers.get(model_type)
                if helper:
                    result = await helper.train_model(
                        trading_pair=job["trading_pair"]
                    )
                else:
                    result = await model_trainer.train_model(
                        trading_pair=job["trading_pair"],
                        model_type=model_type
                    )
                
                # Update job with result
                job["completed_at"] = datetime.now()
                job["result"] = result

                # Check if trainer returned an error (e.g., insufficient data)
                if result and result.get("error"):
                    job["status"] = "failed"
                    job["error"] = result["error"]
                    logger.warning(f"⚠️ Training returned error for {job['trading_pair']} ({job_id}): {result['error']}")
                else:
                    job["status"] = "completed"
                
                # Store model in cloud storage if configured
                # If specialized helper already saved to cloud (detected via 'model_info'), skip duplicate save
                if job["status"] == "completed" and STORAGE_CONFIG.get("type") == "r2" and result and "model" in result and "model_info" not in result:
                    try:
                        # Extract metadata from result
                        import math
                        def _safe_float(v):
                            if v is None:
                                return None
                            try:
                                f = float(v)
                                return None if (math.isnan(f) or math.isinf(f)) else f
                            except (TypeError, ValueError):
                                return None

                        metadata = {
                            "trading_pair": job["trading_pair"],
                            "algorithm": job["model_type"],
                            "accuracy": _safe_float(result.get("metrics", {}).get("accuracy")),
                            "precision": _safe_float(result.get("metrics", {}).get("precision")),
                            "recall": _safe_float(result.get("metrics", {}).get("recall")),
                            "f1_score": _safe_float(result.get("metrics", {}).get("f1_score")),
                            "training_date": datetime.now().isoformat(),
                            "samples_count": result.get("samples_count"),
                            "features_count": result.get("features_count")
                        }
                        
                        # Save model to cloud storage
                        storage_result = await model_storage_manager.save_model(
                            model_data=result["model"], 
                            metadata=metadata
                        )
                        
                        # Add storage info to job result
                        job["result"]["storage"] = {
                            "type": STORAGE_CONFIG.get("type"),
                            "model_id": storage_result.get("model_id"),
                            "version": storage_result.get("version")
                        }
                        
                        logger.info(f"✅ Model saved to {STORAGE_CONFIG.get('type')} storage: {storage_result.get('model_id')}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error saving model to cloud storage: {str(e)}")
                        job["result"]["storage_error"] = str(e)
                
                if job["status"] == "failed":
                    logger.info(f"❌ Training failed for {job['trading_pair']} ({job_id}): {job.get('error')}")
                else:
                    logger.info(f"✅ Training completed for {job['trading_pair']} ({job_id})")
                
            except Exception as e:
                logger.error(f"❌ Training error for {job['trading_pair']} ({job_id}): {str(e)}")
                job["status"] = "failed"
                job["error"] = str(e)
                job["completed_at"] = datetime.now()
            
            # Mark task as done
            training_queue.task_done()
            
            # Clean up old completed jobs
            clean_old_jobs()
    
    except Exception as e:
        logger.error(f"❌ Training worker error: {str(e)}")
    finally:
        is_training_worker_running = False
        logger.info("🛑 Training worker stopped")

def clean_old_jobs():
    """Clean up old completed jobs"""
    global training_jobs
    
    # Keep only jobs from the last 24 hours
    now = datetime.now()
    old_jobs = []
    
    for job_id, job in training_jobs.items():
        if job["status"] in ["completed", "failed"]:
            completed_at = job.get("completed_at")
            if completed_at and (now - completed_at).total_seconds() > 86400:  # 24 hours
                old_jobs.append(job_id)
    
    # Remove old jobs
    for job_id in old_jobs:
        del training_jobs[job_id]
    
    if old_jobs:
        logger.info(f"🧹 Cleaned up {len(old_jobs)} old training jobs")

# API routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OTC Predictor ML Training Service",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/status")
async def get_status():
    """Get detailed service status"""
    global training_jobs, training_queue, is_training_worker_running
    
    # Count jobs by status
    job_counts = {}
    for job in training_jobs.values():
        status = job["status"]
        job_counts[status] = job_counts.get(status, 0) + 1
    
    # Get cloud models only
    cloud_models = []
    if model_storage_manager:
        try:
            cloud_models = await model_storage_manager.list_latest_models()
        except Exception as e:
            logger.error(f"❌ Error listing cloud models: {str(e)}")
    
    # Calculate uptime
    uptime_seconds = 0
    if hasattr(app, "start_time"):
        uptime_seconds = (datetime.now() - app.start_time).total_seconds()
    
    return {
        "status": "running",
        "uptime_seconds": uptime_seconds,
        "worker_running": is_training_worker_running,
        "queue_size": training_queue.qsize(),
        "active_jobs": job_counts.get("processing", 0),
        "total_jobs": len(training_jobs),
        "job_counts": job_counts,
        "models_count": {"cloud": len(cloud_models)},
        "auto_training": {
            "enabled": AUTO_TRAINING["enabled"],
            "interval_hours": AUTO_TRAINING["schedule_interval_hours"]
        },
        "mongodb_connected": mongodb_manager.is_connected if mongodb_manager else False,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global mongodb_manager, service_ready

    if not service_ready:
        return {
            "status": "starting",
            "timestamp": datetime.now().isoformat(),
            "service": "ml_training",
            "mongodb_connected": False
        }

    mongo_connected = mongodb_manager.is_connected if mongodb_manager else False
    status = "healthy" if mongo_connected else "unhealthy"

    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "service": "ml_training",
        "mongodb_connected": mongo_connected
    }

@app.get("/models")
async def get_models():
    """Get list of trained models"""
    global model_trainer, model_storage_manager
    
    if not model_trainer:
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    # Get models from cloud storage only
    cloud_models = []
    if model_storage_manager:
        try:
            cloud_models = await model_storage_manager.list_latest_models()
        except Exception as e:
            logger.error(f"❌ Error listing models from cloud storage: {str(e)}")
    
    return {
        "cloud_models": cloud_models,
        "cloud_count": len(cloud_models)
    }

@app.get("/models/{trading_pair:path}")
async def get_models_for_pair(trading_pair: str = PathParam(...)):
    """Get trained models for a specific trading pair"""
    global model_trainer, model_storage_manager
    
    logger.info(f"🔍 Received request for models with trading_pair: '{trading_pair}'")
    # Normalize to internal canonical for model metadata matching
    canonical_pair = normalize_internal(trading_pair)
    
    if not model_trainer:
        logger.error("❌ ML service not initialized")
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    # Get cloud models
    cloud_models = []
    if model_storage_manager:
        try:
            logger.info(f"☁️ Fetching cloud models for trading_pair: '{canonical_pair}'")
            cloud_models = await model_storage_manager.list_models(trading_pair=canonical_pair)
            logger.info(f"📊 Found {len(cloud_models)} cloud models matching trading_pair: '{trading_pair}'")
            
            # Log cloud model details for debugging
            if cloud_models:
                for i, model in enumerate(cloud_models):
                    logger.info(f"☁️ Cloud model {i+1}: id={model.get('model_id')}, pair={model.get('trading_pair')}, algorithm={model.get('algorithm')}")
            else:
                logger.warning(f"⚠️ No cloud models found for trading_pair: '{trading_pair}'")
                
        except Exception as e:
            logger.error(f"❌ Error listing models from cloud storage: {str(e)}")
    else:
        logger.warning("⚠️ model_storage_manager not initialized, skipping cloud models")
    
    # Sanitize NaN/Inf floats that aren't JSON-serializable
    import math
    def _sanitize(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    cloud_models = _sanitize(cloud_models)

    response = {
        "trading_pair": canonical_pair,
        "cloud_models": cloud_models,
        "cloud_count": len(cloud_models)
    }

    logger.info(f"✅ Returning response with {len(cloud_models)} cloud models")
    return response

@app.post("/train", response_model=TrainingResponse)
async def train_model(request: TrainingRequest):
    """Train a new model for a trading pair"""
    global training_jobs, training_queue, model_trainer
    
    if not model_trainer:
        raise HTTPException(status_code=503, detail="ML service not initialized")
    
    # Normalize trading pair to canonical for consistency
    canonical_pair = normalize_internal(request.trading_pair)
    # Check if we already have a model for this pair and type
    if not request.force_retrain:
        models = model_trainer.list_trained_models()
        # Use safe access; ignore entries without required keys
        existing_models = [
            m for m in models
            if isinstance(m, dict)
            and m.get("trading_pair") == canonical_pair
            and m.get("algorithm") == request.model_type
        ]
        
        if existing_models:
            logger.info(f"ℹ️ Model already exists for {canonical_pair} ({request.model_type})")
    
    # Create job ID
    job_id = f"{canonical_pair}_{request.model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Create job
    job = {
        "job_id": job_id,
        "trading_pair": canonical_pair,
        "model_type": request.model_type,
        "status": "queued",
        "submitted_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    # Add job to queue
    training_jobs[job_id] = job
    await training_queue.put(job_id)
    
    logger.info(f"📋 Training job queued for {canonical_pair} ({job_id})")
    
    return TrainingResponse(
        job_id=job_id,
        trading_pair=canonical_pair,
        model_type=request.model_type,
        status="queued",
        submitted_at=job["submitted_at"]
    )

@app.get("/train/status/{job_id}")
async def get_training_status(job_id: str):
    """Get status of a training job"""
    global training_jobs
    
    job = training_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} not found")
    
    return job

@app.post("/train-all")
async def train_all_models(model_type: str = "xgboost", force_retrain: bool = False):
    """Train models for all configured trading pairs"""
    global training_jobs, training_queue
    
    jobs = []
    
    for trading_pair in DEFAULT_TRADING_PAIRS:
        canonical_pair = normalize_internal(trading_pair)
        # Create job ID
        job_id = f"{canonical_pair}_{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create job
        job = {
            "job_id": job_id,
            "trading_pair": canonical_pair,
            "model_type": model_type,
            "status": "queued",
            "submitted_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None
        }
        
        # Add job to queue
        training_jobs[job_id] = job
        await training_queue.put(job_id)
        
        jobs.append({
            "job_id": job_id,
            "trading_pair": canonical_pair,
            "status": "queued"
        })
    
    logger.info(f"📋 Scheduled training for {len(DEFAULT_TRADING_PAIRS)} trading pairs")
    
    return {
        "status": "training_scheduled",
        "jobs": jobs,
        "count": len(jobs)
    }

@app.get("/queue/status")
async def get_queue_status():
    """Get status of the training queue"""
    global training_queue, training_jobs
    
    # Count jobs by status
    status_counts = {}
    for job in training_jobs.values():
        status = job["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "queue_size": training_queue.qsize(),
        "is_worker_running": is_training_worker_running,
        "job_counts": status_counts,
        "total_jobs": len(training_jobs)
    }

@app.get("/storage/config")
async def get_storage_config():
    """Get current storage configuration"""
    # Remove sensitive information
    config = dict(STORAGE_CONFIG)
    if "r2" in config:
        r2_config = dict(config["r2"])
        if "secret_key" in r2_config:
            r2_config["secret_key"] = "***REDACTED***"
        config["r2"] = r2_config
    
    return config

@app.post("/storage/config")
async def update_storage_config(config: StorageConfigRequest):
    """Update storage configuration"""
    global model_storage_manager
    
    # Update configuration
    STORAGE_CONFIG["type"] = config.storage_type
    
    if config.r2_config:
        STORAGE_CONFIG["r2"].update(config.r2_config)
    
    if config.local_dir:
        STORAGE_CONFIG["local_dir"] = config.local_dir
    
    # Reinitialize storage manager
    model_storage_manager = ModelStorageManager()
    
    return {
        "status": "updated",
        "config": await get_storage_config()
    }

@app.get("/retention/config")
async def get_retention_config():
    """Get current data retention configuration"""
    return DATA_RETENTION

@app.post("/retention/config")
async def update_retention_config(config: RetentionConfigRequest):
    """Update data retention configuration"""
    global data_retention_service
    
    # Update configuration
    DATA_RETENTION["retention_days"] = config.retention_days
    DATA_RETENTION["enable_auto_cleanup"] = config.enable_auto_cleanup
    DATA_RETENTION["cleanup_interval_hours"] = config.cleanup_interval_hours
    
    # Update service
    if data_retention_service:
        data_retention_service.retention_days = config.retention_days
        data_retention_service.enable_auto_cleanup = config.enable_auto_cleanup
        data_retention_service.cleanup_interval = config.cleanup_interval_hours * 3600
        
        # Restart auto cleanup if enabled
        await data_retention_service.stop_auto_cleanup()
        if config.enable_auto_cleanup:
            await data_retention_service.start_auto_cleanup()
    
    return {
        "status": "updated",
        "config": DATA_RETENTION
    }

@app.post("/retention/cleanup")
async def run_manual_cleanup():
    """Run manual data cleanup"""
    global data_retention_service
    
    if not data_retention_service:
        raise HTTPException(status_code=503, detail="Data retention service not initialized")
    
    result = await data_retention_service.clean_old_data()
    return result

@app.get("/retention/status")
async def get_retention_status():
    """Get data retention status"""
    global data_retention_service
    
    if not data_retention_service:
        raise HTTPException(status_code=503, detail="Data retention service not initialized")
    
    status = await data_retention_service.get_status()
    return status
    
# Auto-training endpoints
@app.get("/auto-training/config")
async def get_auto_training_config():
    """Get current auto-training configuration"""
    return AUTO_TRAINING

@app.post("/auto-training/config")
async def update_auto_training_config(config: AutoTrainingConfigRequest):
    """Update auto-training configuration"""
    # Update configuration
    AUTO_TRAINING["enabled"] = config.enabled
    AUTO_TRAINING["schedule_interval_hours"] = config.schedule_interval_hours
    AUTO_TRAINING["min_new_samples"] = config.min_new_samples
    
    if config.trading_pairs:
        AUTO_TRAINING["trading_pairs"] = config.trading_pairs
    
    if config.model_types:
        AUTO_TRAINING["model_types"] = config.model_types
    
    AUTO_TRAINING["max_concurrent_jobs"] = config.max_concurrent_jobs
    
    # Apply new configuration immediately
    if config.enabled:
        # Schedule auto-training
        asyncio.create_task(schedule_auto_training())
        logger.info(f"🤖 Auto-training enabled with interval of {config.schedule_interval_hours} hours")
    else:
        logger.info("🤖 Auto-training disabled")
    
    return {
        "status": "updated",
        "config": AUTO_TRAINING
    }

async def schedule_auto_training():
    """Schedule automatic training based on configuration"""
    global training_queue, mongodb_manager
    
    while AUTO_TRAINING["enabled"]:
        try:
            logger.info("🤖 Running scheduled auto-training check")
            
            # Check if we have enough new samples for each pair
            for trading_pair in AUTO_TRAINING["trading_pairs"]:
                canonical_pair = normalize_internal(trading_pair)
                # Get count of new samples since last training
                last_training_time = await get_last_training_time(canonical_pair)
                new_samples = await count_new_samples(canonical_pair, last_training_time)
                
                logger.info(f"🤖 {canonical_pair}: {new_samples} new samples since last training")
                
                if new_samples >= AUTO_TRAINING["min_new_samples"]:
                    # Schedule training for this pair
                    for model_type in AUTO_TRAINING["model_types"]:
                        # Create job ID
                        job_id = f"{canonical_pair}_{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        
                        # Create job
                        job = {
                            "job_id": job_id,
                            "trading_pair": canonical_pair,
                            "model_type": model_type,
                            "status": "queued",
                            "submitted_at": datetime.now(),
                            "started_at": None,
                            "completed_at": None,
                            "result": None,
                            "error": None,
                            "auto_scheduled": True
                        }
                        
                        # Add job to queue
                        training_jobs[job_id] = job
                        await training_queue.put(job_id)
                        
                        logger.info(f"🤖 Auto-scheduled training for {canonical_pair} ({model_type})")
            
            # Sleep until next check
            await asyncio.sleep(AUTO_TRAINING["schedule_interval_hours"] * 3600)
        except Exception as e:
            logger.error(f"❌ Error in auto-training scheduler: {str(e)}")
            await asyncio.sleep(300)  # Sleep for 5 minutes before retrying

async def get_last_training_time(trading_pair: str) -> datetime:
    """Get the timestamp of the last training for a trading pair (cloud-only)."""
    canonical_pair = normalize_internal(trading_pair)
    try:
        # List cloud models for this pair
        models = await model_storage_manager.list_models(trading_pair=canonical_pair)
    except Exception as e:
        logger.error(f"❌ Error listing cloud models for last training time: {str(e)}")
        models = []
    
    if not models:
        return datetime.now() - timedelta(days=365)
    
    # Determine timestamp field with fallbacks
    def parse_ts(m: dict) -> datetime:
        for key in ("saved_at", "trained_at", "created_at", "r2_upload_time"):
            v = m.get(key)
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(v)
                except Exception:
                    continue
        return datetime.min
    
    latest_model = max(models, key=parse_ts)
    return parse_ts(latest_model)

async def count_new_samples(trading_pair: str, since: datetime) -> int:
    """Count the number of new candle samples for a trading pair since a given time"""
    if not mongodb_manager or not mongodb_manager.is_connected:
        return 0
    
    try:
        # Count documents newer than the given timestamp
        # Use API asset format to match stored candle trading_pair values
        api_pair = to_api_asset(trading_pair)
        count = await mongodb_manager.db.candles.count_documents({
            "trading_pair": api_pair,
            "timestamp": {"$gt": since}
        })
        return count
    except Exception as e:
        logger.error(f"❌ Error counting new samples: {str(e)}")
        return 0

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
    asyncio.create_task(initialize_service())
    
    # Auto-start training worker
    global is_training_worker_running
    if not is_training_worker_running:
        is_training_worker_running = True
        asyncio.create_task(run_training_worker())
        logger.info("🧠 Training worker started automatically")
    
    # Start auto-training scheduler if enabled
    if AUTO_TRAINING["enabled"]:
        asyncio.create_task(schedule_auto_training())
        logger.info(f"🤖 Auto-training scheduler started (interval: {AUTO_TRAINING['schedule_interval_hours']} hours)")
        
    logger.info("✅ ML Training Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global mongodb_manager, is_training_worker_running, data_retention_service
    
    # Stop training worker
    is_training_worker_running = False
    
    # Disable auto-training
    AUTO_TRAINING["enabled"] = False
    
    # Stop data retention service
    if data_retention_service:
        await data_retention_service.stop_auto_cleanup()
    
    # Disconnect from MongoDB
    if mongodb_manager:
        await mongodb_manager.disconnect()
    
    logger.info("✅ ML Training Service shut down successfully")

def run_service(host: str = "0.0.0.0", port: int = 5002, reload: bool = False):
    """Run the ML training service"""
    print("🚀 OTC Predictor - ML Training Service")
    print("=" * 50)
    print(f"🌐 API: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print("-" * 50)
    
    uvicorn.run("main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OTC Predictor ML Training Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '5002')), help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    run_service(host=args.host, port=args.port, reload=args.reload)