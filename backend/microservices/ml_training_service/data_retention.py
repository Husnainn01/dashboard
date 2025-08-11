"""
Data Retention Service for ML Training Service
Handles cleanup of old data in MongoDB
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from database.mongodb_models import MongoDBManager
from config import DEFAULT_TRADING_PAIRS

from config import DATA_RETENTION

logger = logging.getLogger(__name__)

class DataRetentionService:
    """
    Service for managing data retention in MongoDB
    Handles cleanup of old candle data and aggregation
    """
    
    def __init__(self, mongodb_manager: MongoDBManager = None):
        """
        Initialize the data retention service
        
        Args:
            mongodb_manager: MongoDB manager instance
        """
        self.mongodb = mongodb_manager or MongoDBManager()
        self.retention_days = DATA_RETENTION.get("retention_days", 90)
        self.enable_auto_cleanup = DATA_RETENTION.get("enable_auto_cleanup", True)
        self.cleanup_interval = DATA_RETENTION.get("cleanup_interval_hours", 24) * 3600  # Convert to seconds
        self._cleanup_task = None
        
        logger.info(f"✅ Data Retention Service initialized with {self.retention_days} days retention")
    
    async def setup_ttl_indexes(self):
        """Set up TTL indexes on collections"""
        try:
            # Set up TTL index on candles collection
            await self.mongodb.create_ttl_index(
                collection_name="candles",
                field="timestamp",
                expiration_seconds=self.retention_days * 86400  # Convert days to seconds
            )
            
            # Set up TTL index on predictions collection
            await self.mongodb.create_ttl_index(
                collection_name="predictions",
                field="timestamp",
                expiration_seconds=self.retention_days * 86400  # Convert days to seconds
            )
            
            logger.info(f"✅ TTL indexes created for data retention ({self.retention_days} days)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up TTL indexes: {str(e)}")
            return False
    
    async def clean_old_data(self):
        """
        Manually clean up data older than retention period
        
        Returns:
            Dict with cleanup results
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Delete old candles
            candles_result = await self.mongodb.delete_old_candles(cutoff_date)
            
            # Delete old predictions
            predictions_result = await self.mongodb.delete_old_predictions(cutoff_date)
            
            result = {
                "candles_deleted": candles_result.get("deleted_count", 0),
                "predictions_deleted": predictions_result.get("deleted_count", 0),
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": self.retention_days
            }
            
            logger.info(f"🧹 Cleaned up old data: {result['candles_deleted']} candles, {result['predictions_deleted']} predictions")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error cleaning old data: {str(e)}")
            return {"error": str(e)}
    
    async def aggregate_old_data(self):
        """
        Create aggregated summaries before deletion
        Stores hourly and daily aggregated data
        
        Returns:
            Dict with aggregation results
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Get data to aggregate
            aggregation_results = {}
            
            # Aggregate for each trading pair
            for trading_pair in DEFAULT_TRADING_PAIRS:
                # Create hourly aggregations
                hourly_result = await self._create_hourly_aggregations(trading_pair, cutoff_date)
                
                # Create daily aggregations
                daily_result = await self._create_daily_aggregations(trading_pair, cutoff_date)
                
                aggregation_results[trading_pair] = {
                    "hourly": hourly_result,
                    "daily": daily_result
                }
            
            logger.info(f"📊 Created aggregated data for old candles")
            return aggregation_results
            
        except Exception as e:
            logger.error(f"❌ Error aggregating old data: {str(e)}")
            return {"error": str(e)}
    
    async def _create_hourly_aggregations(self, trading_pair: str, cutoff_date: datetime):
        """Create hourly aggregations for old data"""
        # Implementation depends on MongoDB aggregation pipeline
        # This is a placeholder for the actual implementation
        return {"status": "not_implemented"}
    
    async def _create_daily_aggregations(self, trading_pair: str, cutoff_date: datetime):
        """Create daily aggregations for old data"""
        # Implementation depends on MongoDB aggregation pipeline
        # This is a placeholder for the actual implementation
        return {"status": "not_implemented"}
    
    async def start_auto_cleanup(self):
        """Start automatic cleanup task"""
        if self.enable_auto_cleanup:
            if self._cleanup_task:
                self._cleanup_task.cancel()
                
            self._cleanup_task = asyncio.create_task(self._run_auto_cleanup())
            logger.info(f"✅ Automatic data cleanup started (interval: {self.cleanup_interval // 3600} hours)")
            return True
        else:
            logger.info("⚠️ Automatic data cleanup is disabled")
            return False
    
    async def stop_auto_cleanup(self):
        """Stop automatic cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("✅ Automatic data cleanup stopped")
            return True
        else:
            logger.info("⚠️ Automatic data cleanup was not running")
            return False
    
    async def _run_auto_cleanup(self):
        """Run automatic cleanup task"""
        try:
            while True:
                # Run initial cleanup
                await self.clean_old_data()
                
                # Wait for next cleanup
                await asyncio.sleep(self.cleanup_interval)
                
        except asyncio.CancelledError:
            logger.info("🛑 Automatic data cleanup task cancelled")
        except Exception as e:
            logger.error(f"❌ Error in automatic data cleanup: {str(e)}")
    
    async def get_status(self):
        """Get status of data retention service"""
        # Get collection stats
        candles_count = await self.mongodb.count_documents("candles")
        predictions_count = await self.mongodb.count_documents("predictions")
        
        # Get oldest document date
        oldest_candle = await self.mongodb.get_oldest_document("candles")
        oldest_prediction = await self.mongodb.get_oldest_document("predictions")
        
        # Calculate storage usage
        candles_size = await self.mongodb.get_collection_size("candles")
        predictions_size = await self.mongodb.get_collection_size("predictions")
        
        return {
            "retention_days": self.retention_days,
            "auto_cleanup_enabled": self.enable_auto_cleanup,
            "auto_cleanup_running": self._cleanup_task is not None,
            "cleanup_interval_hours": self.cleanup_interval // 3600,
            "stats": {
                "candles": {
                    "count": candles_count,
                    "oldest": oldest_candle.get("timestamp") if oldest_candle else None,
                    "size_mb": round(candles_size / (1024 * 1024), 2) if candles_size else 0
                },
                "predictions": {
                    "count": predictions_count,
                    "oldest": oldest_prediction.get("timestamp") if oldest_prediction else None,
                    "size_mb": round(predictions_size / (1024 * 1024), 2) if predictions_size else 0
                },
                "total_size_mb": round((candles_size + predictions_size) / (1024 * 1024), 2) if candles_size and predictions_size else 0
            }
        }
