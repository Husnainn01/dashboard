"""
Model Storage Manager for ML Training Service
Integrates with the ModelStorageService to manage model storage and versioning
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from storage import ModelStorageService
from config import STORAGE_CONFIG, MODEL_VERSIONING

logger = logging.getLogger(__name__)

class ModelStorageManager:
    """
    Manager for model storage and versioning
    Integrates with ModelStorageService to provide a higher-level API
    """
    
    def __init__(self):
        """Initialize the model storage manager"""
        # Always use R2 storage - no local storage fallback
        self.storage_type = "r2"
        
        logger.info(f"🔧 Initializing ModelStorageManager with storage type: {self.storage_type}")
        
        # Configure R2 storage service
        r2_config = STORAGE_CONFIG.get("r2", {})
        logger.info(f"☁️ Using R2 storage with bucket {r2_config.get('bucket_name')}")
        # Redact sensitive information in logs
        safe_config = r2_config.copy()
        if 'secret_key' in safe_config:
            safe_config['secret_key'] = '***REDACTED***'
        logger.info(f"☁️ R2 config: {safe_config}")
        
        self.storage_service = ModelStorageService(
            storage_type="r2",
            config=r2_config
        )
        
        # Versioning settings
        self.enable_versioning = MODEL_VERSIONING.get("enable_versioning", True)
        self.max_versions = MODEL_VERSIONING.get("max_versions_per_model", 5)
        self.version_naming = MODEL_VERSIONING.get("version_naming", "timestamp")
        
        logger.info(f"✅ Model Storage Manager initialized with {self.storage_type} storage")
        logger.info(f"✅ Versioning: {'enabled' if self.enable_versioning else 'disabled'}, max versions: {self.max_versions}")
    
    async def save_model(self, model_data: Any, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a model with versioning
        
        Args:
            model_data: The model object to save
            metadata: Metadata about the model
            
        Returns:
            Dict with model information including storage location
        """
        # Generate model ID based on trading pair and algorithm
        trading_pair = metadata.get("trading_pair", "unknown").replace("/", "_").replace(" ", "_")
        algorithm = metadata.get("algorithm", "model")
        
        # Add version information
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        version = metadata.get("version", "1.0.0") if self.version_naming == "semantic" else timestamp
        
        # Create model ID
        model_id = f"{algorithm}_{trading_pair}_{timestamp}"
        
        # Add version info to metadata
        metadata["version"] = version
        metadata["created_at"] = datetime.now().isoformat()
        
        # Save model
        result = await self.storage_service.save_model(model_data, metadata, model_id)
        
        # Clean up old versions if versioning is enabled
        if self.enable_versioning:
            await self._cleanup_old_versions(trading_pair, algorithm)
        
        logger.info(f"✅ Model saved with ID: {model_id}, version: {version}")
        return result
    
    async def _cleanup_old_versions(self, trading_pair: str, algorithm: str):
        """
        Clean up old versions of a model
        
        Args:
            trading_pair: Trading pair of the model
            algorithm: Algorithm of the model
        """
        # Get all versions of this model
        models = await self.storage_service.list_models(trading_pair, algorithm)
        
        # Sort by created_at (newest first)
        models.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Delete old versions
        if len(models) > self.max_versions:
            for old_model in models[self.max_versions:]:
                model_id = old_model.get("model_id")
                if model_id:
                    logger.info(f"🧹 Cleaning up old model version: {model_id}")
                    await self.storage_service.delete_model(model_id)
    
    async def load_latest_model(self, trading_pair: str, algorithm: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Load the latest version of a model
        
        Args:
            trading_pair: Trading pair of the model
            algorithm: Algorithm of the model
            
        Returns:
            Tuple of (model_data, metadata)
        """
        # Format trading pair for search
        formatted_pair = trading_pair.replace("/", "_").replace(" ", "_")
        
        # Get all versions of this model
        models = await self.storage_service.list_models(trading_pair, algorithm)
        
        if not models:
            raise FileNotFoundError(f"No models found for {trading_pair} ({algorithm})")
        
        # Sort by created_at (newest first)
        models.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Load the latest model
        latest_model = models[0]
        model_id = latest_model.get("model_id")
        
        if not model_id:
            raise ValueError(f"Invalid model metadata: {latest_model}")
        
        logger.info(f"📂 Loading latest model: {model_id}")
        return await self.storage_service.load_model(model_id)
    
    async def load_model_by_id(self, model_id: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Load a specific model by ID
        
        Args:
            model_id: ID of the model to load
            
        Returns:
            Tuple of (model, scaler, metadata)
        """
        try:
            model, scaler, metadata = await self.storage_service.load_model(model_id)
            return model, scaler, metadata
        except ValueError as e:
            logger.error(f"❌ Error loading model {model_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error loading model {model_id}: {str(e)}")
            raise
    
    async def list_models(self, trading_pair: str = None, algorithm: str = None) -> List[Dict[str, Any]]:
        """
        List available models
        
        Args:
            trading_pair: Optional filter by trading pair
            algorithm: Optional filter by algorithm
            
        Returns:
            List of model metadata
        """
        return await self.storage_service.list_models(trading_pair, algorithm)
    
    async def list_latest_models(self) -> List[Dict[str, Any]]:
        """
        List the latest version of each model
        
        Returns:
            List of model metadata for the latest version of each model
        """
        # Get all models
        all_models = await self.storage_service.list_models()
        
        # Group by trading_pair and algorithm
        model_groups = {}
        for model in all_models:
            trading_pair = model.get("trading_pair", "unknown")
            algorithm = model.get("algorithm", "unknown")
            key = f"{trading_pair}_{algorithm}"
            
            if key not in model_groups:
                model_groups[key] = []
            
            model_groups[key].append(model)
        
        # Get the latest version from each group
        latest_models = []
        for group in model_groups.values():
            # Sort by created_at (newest first)
            group.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            latest_models.append(group[0])
        
        return latest_models
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Delete a model
        
        Args:
            model_id: ID of the model to delete
            
        Returns:
            True if successful, False otherwise
        """
        return await self.storage_service.delete_model(model_id)
