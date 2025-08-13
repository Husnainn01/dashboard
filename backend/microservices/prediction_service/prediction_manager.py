"""
Prediction Manager for OTC Predictor
Handles robust prediction processing with timeouts, retries, and circuit breaking
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import traceback

from fastapi import HTTPException

# Monitoring service will be set by main.py
monitoring_service = None

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent repeated failures
    """
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold  # Number of failures before opening circuit
        self.reset_timeout = reset_timeout  # Time in seconds before trying to close circuit
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_failure(self):
        """Record a failure and potentially open the circuit"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == "CLOSED" and self.failure_count >= self.failure_threshold:
            logger.warning(f"🔌 Circuit breaker opened after {self.failure_count} failures")
            self.state = "OPEN"
        elif self.state == "HALF_OPEN":
            logger.warning(f"🔌 Circuit breaker re-opened after failure in HALF_OPEN state")
            self.state = "OPEN"
    
    def record_success(self):
        """Record a success and potentially close the circuit"""
        if self.state == "HALF_OPEN":
            logger.info("🔌 Circuit breaker closed after successful operation")
            self.reset()
    
    def reset(self):
        """Reset the circuit breaker to closed state"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
    
    def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit state"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if reset timeout has elapsed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.reset_timeout:
                logger.info("🔌 Circuit breaker entering HALF_OPEN state")
                self.state = "HALF_OPEN"
                return True
            return False
        
        # In HALF_OPEN state, allow one request through
        return True

class PredictionManager:
    """
    Manages prediction requests with robust error handling, timeouts, and retries
    """
    def __init__(self):
        self.circuit_breakers = {}  # Trading pair -> CircuitBreaker
        self.prediction_cache = {}  # Trading pair -> (timestamp, prediction)
        self.prediction_stats = {
            "total_requests": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "timeout_count": 0,
            "retry_count": 0,
            "circuit_breaks": 0,
            "cache_hits": 0
        }
    
    def get_circuit_breaker(self, trading_pair: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a trading pair"""
        if trading_pair not in self.circuit_breakers:
            self.circuit_breakers[trading_pair] = CircuitBreaker()
        return self.circuit_breakers[trading_pair]
    
    async def execute_with_timeout(self, func, *args, timeout_seconds: float = 10.0, **kwargs):
        """Execute a function with timeout"""
        try:
            # Create a task and wait for it with timeout
            task = asyncio.create_task(func(*args, **kwargs))
            result = await asyncio.wait_for(task, timeout=timeout_seconds)
            return result, None
        except asyncio.TimeoutError:
            # Cancel the task if it timed out
            task.cancel()
            self.prediction_stats["timeout_count"] += 1
            return None, "timeout"
        except Exception as e:
            return None, str(e)
    
    async def make_prediction_with_resilience(
        self, 
        prediction_func, 
        trading_pair: str,
        *args,
        max_retries: int = 2,
        base_timeout: float = 5.0,
        **kwargs
    ):
        """
        Make a prediction with resilience features:
        - Timeout handling
        - Retries with exponential backoff
        - Circuit breaking
        - Result caching
        """
        self.prediction_stats["total_requests"] += 1
        circuit_breaker = self.get_circuit_breaker(trading_pair)
        
        # Record start time for monitoring
        overall_start_time = time.time()
        
        # Check if circuit is open
        if not circuit_breaker.can_execute():
            self.prediction_stats["circuit_breaks"] += 1
            logger.warning(f"🔌 Circuit breaker open for {trading_pair}, skipping prediction")
            
            # Return cached prediction if available
            if trading_pair in self.prediction_cache:
                cached_timestamp, cached_prediction = self.prediction_cache[trading_pair]
                age_seconds = (datetime.now() - cached_timestamp).total_seconds()
                
                if age_seconds < 300:  # Cache valid for 5 minutes
                    self.prediction_stats["cache_hits"] += 1
                    logger.info(f"📦 Using cached prediction for {trading_pair} ({age_seconds:.1f}s old)")
                    return cached_prediction
            
            # No valid cache, raise exception
            raise HTTPException(status_code=503, detail=f"Service temporarily unavailable for {trading_pair}")
        
        # Try to make prediction with retries
        retry_count = 0
        current_timeout = base_timeout
        
        while retry_count <= max_retries:
            if retry_count > 0:
                self.prediction_stats["retry_count"] += 1
                # Exponential backoff
                await asyncio.sleep(0.5 * (2 ** (retry_count - 1)))
                # Increase timeout for retries
                current_timeout = base_timeout * (1.5 ** retry_count)
                logger.info(f"🔄 Retry {retry_count}/{max_retries} for {trading_pair} with timeout {current_timeout:.1f}s")
            
            start_time = time.time()
            result, error = await self.execute_with_timeout(
                prediction_func, 
                trading_pair=trading_pair,
                *args,
                timeout_seconds=current_timeout,
                **kwargs
            )
            
            execution_time = (time.time() - start_time) * 1000  # ms
            
            if error is None:
                # Success
                circuit_breaker.record_success()
                self.prediction_stats["successful_predictions"] += 1
                
                # Cache the successful prediction
                self.prediction_cache[trading_pair] = (datetime.now(), result)
                
                # Record in monitoring service if available
                if monitoring_service:
                    overall_execution_time = (time.time() - overall_start_time) * 1000
                    monitoring_service.record_prediction(
                        trading_pair=trading_pair,
                        duration_ms=overall_execution_time,
                        success=True,
                        retry=(retry_count > 0)
                    )
                
                logger.info(f"✅ Prediction for {trading_pair} succeeded in {execution_time:.1f}ms")
                return result
            
            # Handle specific errors
            if error == "timeout":
                logger.warning(f"⏱️ Prediction for {trading_pair} timed out after {current_timeout:.1f}s")
                # Don't record circuit breaker failure for timeouts on first try
                if retry_count > 0:
                    circuit_breaker.record_failure()
            else:
                logger.error(f"❌ Prediction for {trading_pair} failed: {error}")
                circuit_breaker.record_failure()
            
            retry_count += 1
        
        # All retries failed
        self.prediction_stats["failed_predictions"] += 1
        
        # Record in monitoring service if available
        if monitoring_service:
            overall_execution_time = (time.time() - overall_start_time) * 1000
            monitoring_service.record_prediction(
                trading_pair=trading_pair,
                duration_ms=overall_execution_time,
                success=False,
                retry=(retry_count > 0),
                timeout=(error == "timeout")
            )
        
        # Return cached prediction if available
        if trading_pair in self.prediction_cache:
            cached_timestamp, cached_prediction = self.prediction_cache[trading_pair]
            age_seconds = (datetime.now() - cached_timestamp).total_seconds()
            
            if age_seconds < 300:  # Cache valid for 5 minutes
                self.prediction_stats["cache_hits"] += 1
                logger.warning(f"📦 Using cached prediction for {trading_pair} after failures ({age_seconds:.1f}s old)")
                
                # Record cache hit in monitoring
                if monitoring_service:
                    monitoring_service.record_prediction(
                        trading_pair=trading_pair,
                        duration_ms=overall_execution_time,
                        success=True,
                        cache_hit=True
                    )
                    
                return cached_prediction
        
        # No cache, raise exception
        raise HTTPException(status_code=500, detail=f"Failed to generate prediction for {trading_pair} after {max_retries} retries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get prediction statistics"""
        return {
            **self.prediction_stats,
            "circuit_breaker_states": {
                pair: breaker.state for pair, breaker in self.circuit_breakers.items()
            }
        }
