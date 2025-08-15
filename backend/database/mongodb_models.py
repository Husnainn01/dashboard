"""
MongoDB Models and Manager for OTC Predictor
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import json
import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING, IndexModel
from bson import ObjectId
from bson.json_util import dumps
import dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

# MongoDB connection string from environment or default to Atlas
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb+srv://dash:JBuim9uQ8CbXPd1K@dashbaord.zsslbre.mongodb.net/otc-predictor")
MONGODB_DB = os.environ.get("MONGODB_DB", "otc_predictor")

class CandleData:
    """
    Candle data model for MongoDB
    """
    def __init__(self, 
                trading_pair: str, 
                timestamp: datetime,
                open_price: float,
                close_price: float,
                high_price: float,
                low_price: float,
                volume: float = 0,
                is_closed: bool = True,
                is_validated: bool = False,
                source: str = "pyquotex"):
        self.trading_pair = trading_pair
        self.timestamp = timestamp
        self.open_price = open_price
        self.close_price = close_price
        self.high_price = high_price
        self.low_price = low_price
        self.volume = volume
        self.is_closed = is_closed
        self.is_validated = is_validated
        self.source = source
        
    # Property getters for backward compatibility
    @property
    def open(self) -> float:
        return self.open_price
        
    @property
    def close(self) -> float:
        return self.close_price
        
    @property
    def high(self) -> float:
        return self.high_price
        
    @property
    def low(self) -> float:
        return self.low_price
        
    @property
    def direction(self) -> str:
        """Return the candle direction (up or down)"""
        return "up" if self.close_price >= self.open_price else "down"
        
    @property
    def change(self) -> float:
        """Return the absolute price change"""
        return abs(self.close_price - self.open_price)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        return {
            "trading_pair": self.trading_pair,
            "timestamp": self.timestamp,
            "open": self.open_price,
            "close": self.close_price,
            "high": self.high_price,
            "low": self.low_price,
            "volume": self.volume,
            "is_closed": self.is_closed,
            "is_validated": self.is_validated,
            "source": self.source
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CandleData':
        """Create from dictionary"""
        return cls(
            trading_pair=data.get("trading_pair"),
            timestamp=data.get("timestamp"),
            open_price=data.get("open"),
            close_price=data.get("close"),
            high_price=data.get("high"),
            low_price=data.get("low"),
            volume=data.get("volume", 0),
            is_closed=data.get("is_closed", True),
            is_validated=data.get("is_validated", False),
            source=data.get("source", "pyquotex")
        )

class PredictionData:
    """
    ML Prediction data model for MongoDB
    """
    def __init__(self,
                trading_pair: str,
                timestamp: datetime,
                model_type: str,
                model_version: str,
                prediction: str,  # "up" or "down"
                confidence: float,
                model_name: str = None,
                features: Dict[str, float] = None,
                actual_result: str = None,
                was_correct: bool = None):
        self.trading_pair = trading_pair
        self.timestamp = timestamp
        self.model_type = model_type
        self.model_version = model_version
        self.prediction = prediction
        self.confidence = confidence
        self.model_name = model_name
        self.features = features or {}
        self.actual_result = actual_result
        self.was_correct = was_correct
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MongoDB storage"""
        return {
            "trading_pair": self.trading_pair,
            "timestamp": self.timestamp,
            "model_type": self.model_type,
            "model_version": self.model_version,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "model_name": self.model_name,
            "features": self.features,
            "actual_result": self.actual_result,
            "was_correct": self.was_correct
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PredictionData':
        """Create from dictionary"""
        return cls(
            trading_pair=data.get("trading_pair"),
            timestamp=data.get("timestamp"),
            model_type=data.get("model_type"),
            model_version=data.get("model_version"),
            prediction=data.get("prediction"),
            confidence=data.get("confidence"),
            model_name=data.get("model_name"),
            features=data.get("features", {}),
            actual_result=data.get("actual_result"),
            was_correct=data.get("was_correct")
        )

class MongoDBManager:
    """
    MongoDB Database Manager for OTC Predictor
    """
    def __init__(self, uri: str = None, db_name: str = None):
        """Initialize MongoDB connection"""
        self.uri = uri or MONGODB_URI
        self.db_name = db_name or MONGODB_DB
        self.client = None
        self.db = None
        self.is_connected = False
        
    async def connect(self):
        """Connect to MongoDB"""
        if self.is_connected:
            return
            
        try:
            # Create client
            logger.info(f"Connecting to MongoDB at {self.uri}")
            self.client = motor.motor_asyncio.AsyncIOMotorClient(self.uri)
            
            # Get database
            self.db = self.client[self.db_name]
            
            # Create indexes
            await self._create_indexes()
            
            self.is_connected = True
            logger.info(f"✅ Connected to MongoDB: {self.db_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error connecting to MongoDB: {str(e)}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("✅ Disconnected from MongoDB")
    
    async def _create_indexes(self):
        """Create indexes for collections"""
        # Candles collection indexes
        await self.db.candles.create_index([("trading_pair", ASCENDING), ("timestamp", DESCENDING)])
        await self.db.candles.create_index([("timestamp", DESCENDING)])
        await self.db.candles.create_index([("trading_pair", ASCENDING), ("is_validated", ASCENDING)])
        
        # Predictions collection indexes
        await self.db.predictions.create_index([("trading_pair", ASCENDING), ("timestamp", DESCENDING)])
        await self.db.predictions.create_index([("timestamp", DESCENDING)])
        await self.db.predictions.create_index([("model_type", ASCENDING), ("trading_pair", ASCENDING)])
        
        logger.info("✅ MongoDB indexes created")
    
    async def create_ttl_index(self, collection_name: str, field: str, expiration_seconds: int):
        """
        Create a TTL index on a collection
        
        Args:
            collection_name: Name of the collection
            field: Field to index (usually timestamp)
            expiration_seconds: Time in seconds after which documents will be deleted
        """
        collection = self.db[collection_name]
        await collection.create_index([(field, ASCENDING)], expireAfterSeconds=expiration_seconds)
        logger.info(f"✅ TTL index created on {collection_name}.{field} ({expiration_seconds} seconds)")
    
    async def save_candle(self, candle: CandleData) -> str:
        """
        Save candle data to MongoDB
        
        Args:
            candle: CandleData object
            
        Returns:
            ID of the inserted document
        """
        if not self.is_connected:
            await self.connect()
        
        # Convert to dict
        candle_dict = candle.to_dict()
        
        # Check for existing candle with same trading_pair and timestamp
        existing = await self.db.candles.find_one({
            "trading_pair": candle.trading_pair,
            "timestamp": candle.timestamp
        })
        
        if existing:
            # Update existing candle
            result = await self.db.candles.update_one(
                {"_id": existing["_id"]},
                {"$set": candle_dict}
            )
            return str(existing["_id"])
        else:
            # Insert new candle
            result = await self.db.candles.insert_one(candle_dict)
            return str(result.inserted_id)
    
    async def save_prediction(self, prediction: PredictionData) -> str:
        """
        Save prediction data to MongoDB
        
        Args:
            prediction: PredictionData object
            
        Returns:
            ID of the inserted document
        """
        if not self.is_connected:
            await self.connect()
        
        # Convert to dict
        prediction_dict = prediction.to_dict()
        
        # Check for existing prediction with same trading_pair, timestamp, and model_type
        existing = await self.db.predictions.find_one({
            "trading_pair": prediction.trading_pair,
            "timestamp": prediction.timestamp,
            "model_type": prediction.model_type
        })
        
        if existing:
            # Update existing prediction
            result = await self.db.predictions.update_one(
                {"_id": existing["_id"]},
                {"$set": prediction_dict}
            )
            return str(existing["_id"])
        else:
            # Insert new prediction
            result = await self.db.predictions.insert_one(prediction_dict)
            return str(result.inserted_id)
    
    async def get_candles(self, 
                         trading_pair: str, 
                         limit: int = 1000, 
                         start_time: datetime = None, 
                         end_time: datetime = None,
                         validated_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get candles from MongoDB
        
        Args:
            trading_pair: Trading pair to get candles for
            limit: Maximum number of candles to return
            start_time: Start time for candles
            end_time: End time for candles
            validated_only: Only return validated candles
            
        Returns:
            List of candle dictionaries
        """
        if not self.is_connected:
            await self.connect()
        
        # Build query
        query = {"trading_pair": trading_pair}
        
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        
        if end_time:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_time
            else:
                query["timestamp"] = {"$lte": end_time}
        
        if validated_only:
            query["is_validated"] = True
        
        # Execute query
        cursor = self.db.candles.find(query).sort("timestamp", DESCENDING).limit(limit)
        
        # Convert to list
        candles = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for candle in candles:
            candle["_id"] = str(candle["_id"])
        
        return candles
    
    async def get_predictions(self, 
                            trading_pair: str, 
                            limit: int = 100, 
                            model_type: str = None,
                            model_name: str = None,
                            start_time: datetime = None, 
                            end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Get predictions from MongoDB
        
        Args:
            trading_pair: Trading pair to get predictions for
            limit: Maximum number of predictions to return
            model_type: Filter by model type
            start_time: Start time for predictions
            end_time: End time for predictions
            
        Returns:
            List of prediction dictionaries
        """
        if not self.is_connected:
            await self.connect()
        
        # Build query
        query = {"trading_pair": trading_pair}
        
        if model_type:
            query["model_type"] = model_type
            
        if model_name:
            query["model_name"] = model_name
        
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        
        if end_time:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_time
            else:
                query["timestamp"] = {"$lte": end_time}
        
        # Execute query
        cursor = self.db.predictions.find(query).sort("timestamp", DESCENDING).limit(limit)
        
        # Convert to list
        predictions = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for prediction in predictions:
            prediction["_id"] = str(prediction["_id"])
        
        return predictions
        
    async def get_latest_prediction(self, 
                                trading_pair: str,
                                model_name: str = None,
                                model_type: str = None) -> Optional[PredictionData]:
        """
        Get the latest prediction for a trading pair with optional model selection
        
        Args:
            trading_pair: Trading pair to get prediction for
            model_name: Filter by model name (optional)
            model_type: Filter by model type (optional)
            
        Returns:
            Latest PredictionData object or None if not found
        """
        if not self.is_connected:
            await self.connect()
        
        # Build query
        query = {"trading_pair": trading_pair}
        
        if model_type:
            query["model_type"] = model_type
            
        if model_name:
            query["model_name"] = model_name
        
        # Execute query to get the latest prediction
        cursor = self.db.predictions.find(query).sort("timestamp", DESCENDING).limit(1)
        predictions = await cursor.to_list(length=1)
        
        if predictions and len(predictions) > 0:
            # Convert ObjectId to string
            predictions[0]["_id"] = str(predictions[0]["_id"])
            # Convert to PredictionData object
            return PredictionData.from_dict(predictions[0])
        else:
            return None
    
    async def get_candles_for_training(self, 
                                     trading_pair: str, 
                                     limit: int = 2000, 
                                     validated_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get candles for ML training
        
        Args:
            trading_pair: Trading pair to get candles for
            limit: Maximum number of candles to return
            validated_only: Only return validated candles
            
        Returns:
            List of candle dictionaries
        """
        if not self.is_connected:
            await self.connect()
        
        # Try different formats of trading pair
        formats_to_try = [
            trading_pair,  # Original format (e.g., "USD/BRL(OTC)")
            trading_pair.replace("/", "").replace("(OTC)", " OTC"),  # "USDBRL OTC"
            trading_pair.replace("/", "").replace("(OTC)", "_OTC"),  # "USDBRL_OTC"
        ]
        
        # Get all available trading pairs in the database
        available_pairs = await self.get_available_trading_pairs()
        logger.info(f"Available trading pairs in database: {available_pairs}")
        
        # Try each format
        for pair_format in formats_to_try:
            # Build query
            query = {"trading_pair": pair_format}
            
            if validated_only:
                query["is_validated"] = True
            
            # Check if this format exists in the database
            count = await self.db.candles.count_documents(query)
            
            if count > 0:
                logger.info(f"Found {count} candles for {pair_format}")
                
                # Execute query
                cursor = self.db.candles.find(query).sort("timestamp", ASCENDING).limit(limit)
                
                # Convert to list
                candles = await cursor.to_list(length=limit)
                
                # Convert ObjectId to string
                for candle in candles:
                    candle["_id"] = str(candle["_id"])
                
                return candles
        
        # If no format matched, try to find a similar trading pair
        for available_pair in available_pairs:
            # Check if the available pair contains parts of the requested pair
            if (trading_pair.replace("/", "").replace("(OTC)", "").lower() in available_pair.lower() or
                available_pair.lower() in trading_pair.replace("/", "").replace("(OTC)", "").lower()):
                
                logger.info(f"Trying similar pair: {available_pair}")
                
                # Build query
                query = {"trading_pair": available_pair}
                
                if validated_only:
                    query["is_validated"] = True
                
                # Execute query
                cursor = self.db.candles.find(query).sort("timestamp", ASCENDING).limit(limit)
                
                # Convert to list
                candles = await cursor.to_list(length=limit)
                
                # Convert ObjectId to string
                for candle in candles:
                    candle["_id"] = str(candle["_id"])
                
                return candles
        
        # If no match found, return empty list
        logger.warning(f"No candles found for {trading_pair} (tried formats: {formats_to_try})")
        return []
    
    async def get_available_trading_pairs(self) -> List[str]:
        """
        Get all available trading pairs in the database
        
        Returns:
            List of trading pair strings
        """
        if not self.is_connected:
            await self.connect()
        
        # Get distinct trading pairs
        pairs = await self.db.candles.distinct("trading_pair")
        return pairs
    
    async def get_trading_pairs_with_counts(self) -> Dict[str, int]:
        """
        Get all trading pairs with their candle counts
        
        Returns:
            Dict mapping trading pair to candle count
        """
        if not self.is_connected:
            await self.connect()
        
        # Get distinct trading pairs
        pairs = await self.db.candles.distinct("trading_pair")
        
        # Get counts for each pair
        result = {}
        for pair in pairs:
            count = await self.db.candles.count_documents({"trading_pair": pair})
            result[pair] = count
        
        return result
    
    async def delete_old_candles(self, cutoff_date: datetime) -> Dict[str, Any]:
        """
        Delete candles older than cutoff date
        
        Args:
            cutoff_date: Delete candles older than this date
            
        Returns:
            Dict with deletion results
        """
        if not self.is_connected:
            await self.connect()
        
        # Delete old candles
        result = await self.db.candles.delete_many({"timestamp": {"$lt": cutoff_date}})
        
        return {
            "deleted_count": result.deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
    
    async def delete_old_predictions(self, cutoff_date: datetime) -> Dict[str, Any]:
        """
        Delete predictions older than cutoff date
        
        Args:
            cutoff_date: Delete predictions older than this date
            
        Returns:
            Dict with deletion results
        """
        if not self.is_connected:
            await self.connect()
        
        # Delete old predictions
        result = await self.db.predictions.delete_many({"timestamp": {"$lt": cutoff_date}})
        
        return {
            "deleted_count": result.deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
    
    async def count_documents(self, collection_name: str) -> int:
        """
        Count documents in a collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Number of documents
        """
        if not self.is_connected:
            await self.connect()
        
        collection = self.db[collection_name]
        return await collection.count_documents({})
    
    async def get_oldest_document(self, collection_name: str) -> Dict[str, Any]:
        """
        Get oldest document in a collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Oldest document or None
        """
        if not self.is_connected:
            await self.connect()
        
        collection = self.db[collection_name]
        cursor = collection.find().sort("timestamp", ASCENDING).limit(1)
        documents = await cursor.to_list(length=1)
        
        if documents:
            document = documents[0]
            document["_id"] = str(document["_id"])
            return document
        else:
            return None
    
    async def get_collection_size(self, collection_name: str) -> int:
        """
        Get size of a collection in bytes
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Size in bytes or None if error
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            stats = await self.db.command("collStats", collection_name)
            return stats.get("size", 0)
        except Exception as e:
            logger.error(f"❌ Error getting collection size: {str(e)}")
            return None
            
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with database statistics
        """
        if not self.is_connected:
            await self.connect()
            
        try:
            # Get collection counts
            candles_count = await self.count_documents("candles")
            predictions_count = await self.count_documents("predictions")
            
            # Get collection sizes
            candles_size = await self.get_collection_size("candles")
            predictions_size = await self.get_collection_size("predictions")
            
            # Get trading pairs with counts
            pairs_with_counts = await self.get_trading_pairs_with_counts()
            
            # Get oldest documents
            oldest_candle = await self.get_oldest_document("candles")
            oldest_prediction = await self.get_oldest_document("predictions")
            
            return {
                "candles": {
                    "count": candles_count,
                    "size_bytes": candles_size,
                    "size_mb": round(candles_size / (1024 * 1024), 2) if candles_size else 0,
                    "oldest": oldest_candle["timestamp"].isoformat() if oldest_candle else None
                },
                "predictions": {
                    "count": predictions_count,
                    "size_bytes": predictions_size,
                    "size_mb": round(predictions_size / (1024 * 1024), 2) if predictions_size else 0,
                    "oldest": oldest_prediction["timestamp"].isoformat() if oldest_prediction else None
                },
                "trading_pairs": pairs_with_counts,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting database stats: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }