"""
Monitoring utilities for OTC Predictor prediction service
Provides endpoints and utilities for monitoring service health and performance
"""

import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PredictionMetrics(BaseModel):
    """Metrics for prediction service monitoring"""
    total_predictions: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0
    timeout_count: int = 0
    retry_count: int = 0
    cache_hits: int = 0
    circuit_breaks: int = 0
    avg_prediction_time_ms: float = 0
    max_prediction_time_ms: float = 0
    min_prediction_time_ms: float = 0
    predictions_last_minute: int = 0
    predictions_last_hour: int = 0
    
    # Timing metrics
    p50_latency_ms: float = 0
    p90_latency_ms: float = 0
    p99_latency_ms: float = 0

class ServiceHealth(BaseModel):
    """Health status of the prediction service"""
    status: str = "healthy"  # healthy, degraded, unhealthy
    uptime_seconds: float = 0
    start_time: datetime = datetime.now()
    last_successful_prediction: Optional[datetime] = None
    memory_usage_mb: float = 0
    cpu_usage_percent: float = 0
    active_connections: int = 0
    
    # Circuit breaker status
    circuit_breaker_status: Dict[str, str] = {}

class MonitoringService:
    """Service for monitoring prediction service health and performance"""
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics = PredictionMetrics()
        self.health = ServiceHealth(start_time=self.start_time)
        self.prediction_times = []  # List of recent prediction times in ms
        self.prediction_history = []  # List of (timestamp, success) tuples
        self.max_history_size = 10000  # Maximum number of entries to keep
        
    def record_prediction(self, trading_pair: str, duration_ms: float, success: bool, 
                         timeout: bool = False, retry: bool = False, 
                         cache_hit: bool = False, circuit_break: bool = False):
        """Record a prediction attempt"""
        # Update basic counters
        self.metrics.total_predictions += 1
        
        if success:
            self.metrics.successful_predictions += 1
            self.health.last_successful_prediction = datetime.now()
        else:
            self.metrics.failed_predictions += 1
        
        if timeout:
            self.metrics.timeout_count += 1
        
        if retry:
            self.metrics.retry_count += 1
            
        if cache_hit:
            self.metrics.cache_hits += 1
            
        if circuit_break:
            self.metrics.circuit_breaks += 1
        
        # Record prediction time
        if duration_ms > 0:  # Only record valid times
            self.prediction_times.append(duration_ms)
            # Keep only the last 1000 prediction times
            if len(self.prediction_times) > 1000:
                self.prediction_times.pop(0)
            
            # Update min/max/avg
            self.metrics.min_prediction_time_ms = min(self.prediction_times) if self.prediction_times else 0
            self.metrics.max_prediction_time_ms = max(self.prediction_times) if self.prediction_times else 0
            self.metrics.avg_prediction_time_ms = sum(self.prediction_times) / len(self.prediction_times) if self.prediction_times else 0
            
            # Calculate percentiles
            if self.prediction_times:
                sorted_times = sorted(self.prediction_times)
                self.metrics.p50_latency_ms = sorted_times[int(len(sorted_times) * 0.5)]
                self.metrics.p90_latency_ms = sorted_times[int(len(sorted_times) * 0.9)]
                self.metrics.p99_latency_ms = sorted_times[int(len(sorted_times) * 0.99)]
        
        # Record in history
        self.prediction_history.append((datetime.now(), success))
        # Trim history if needed
        if len(self.prediction_history) > self.max_history_size:
            self.prediction_history = self.prediction_history[-self.max_history_size:]
    
    def update_health(self, prediction_manager=None, parallel_processor=None):
        """Update health metrics"""
        # Update uptime
        self.health.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        # Count recent predictions
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        one_hour_ago = now - timedelta(hours=1)
        
        self.metrics.predictions_last_minute = sum(1 for ts, success in self.prediction_history if ts >= one_minute_ago)
        self.metrics.predictions_last_hour = sum(1 for ts, success in self.prediction_history if ts >= one_hour_ago)
        
        # Update circuit breaker status if prediction manager is provided
        if prediction_manager:
            self.health.circuit_breaker_status = {
                pair: breaker.state 
                for pair, breaker in prediction_manager.circuit_breakers.items()
            }
        
        # Determine overall health status
        recent_failures = sum(1 for ts, success in self.prediction_history[-20:] if not success)
        if recent_failures >= 15:  # 75% or more of recent predictions failed
            self.health.status = "unhealthy"
        elif recent_failures >= 5:  # 25% or more of recent predictions failed
            self.health.status = "degraded"
        else:
            self.health.status = "healthy"
            
        # Try to get memory and CPU usage
        try:
            import psutil
            process = psutil.Process()
            self.health.memory_usage_mb = process.memory_info().rss / (1024 * 1024)
            self.health.cpu_usage_percent = process.cpu_percent()
        except:
            # If psutil is not available, just skip these metrics
            pass
    
    def get_metrics(self) -> PredictionMetrics:
        """Get current metrics"""
        return self.metrics
    
    def get_health(self) -> ServiceHealth:
        """Get current health status"""
        return self.health
    
    def reset_metrics(self):
        """Reset metrics counters"""
        self.metrics = PredictionMetrics()
        self.prediction_times = []
        # Don't reset health or history

# Create a singleton instance
monitoring_service = MonitoringService()

# Function to register with FastAPI
def setup_monitoring_routes(app, prediction_manager=None, parallel_processor=None):
    """Set up monitoring routes in the FastAPI app"""
    from fastapi import APIRouter
    
    router = APIRouter()
    
    @router.get("/metrics")
    async def get_metrics():
        """Get prediction service metrics"""
        monitoring_service.update_health(prediction_manager, parallel_processor)
        return monitoring_service.get_metrics()
    
    @router.get("/health")
    async def get_health():
        """Get prediction service health"""
        monitoring_service.update_health(prediction_manager, parallel_processor)
        return monitoring_service.get_health()
    
    @router.post("/reset-metrics")
    async def reset_metrics():
        """Reset metrics counters"""
        monitoring_service.reset_metrics()
        return {"status": "success", "message": "Metrics reset successfully"}
    
    app.include_router(router, prefix="/monitoring", tags=["monitoring"])
    
    return monitoring_service
