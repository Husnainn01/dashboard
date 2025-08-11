"""
Extended ModelTrainer with R2 support
"""

import logging
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import sys

# Add parent directories to path
current_dir = Path(__file__).parent
backend_dir = current_dir.parent.parent
sys.path.append(str(backend_dir))

from ml_models.model_trainer import ModelTrainer as BaseModelTrainer
from model_storage import ModelStorageManager

logger = logging.getLogger(__name__)

class ModelTrainerR2(BaseModelTrainer):
    """
    Extended ModelTrainer with R2 support
    """
    
    def __init__(self, mongodb_manager=None):
        super().__init__(mongodb_manager)
        self.model_storage_manager = None
        
    async def list_trained_models(self) -> List[Dict]:
        """List all trained models with their metadata"""
        if self.model_storage_manager:
            try:
                # Use model_storage_manager to list models (async)
                models = await self.model_storage_manager.list_models()
                logger.info(f"✅ Listed {len(models)} models from storage")
                return models
            except Exception as e:
                logger.error(f"❌ Error listing models from storage: {str(e)}")
                # Fall back to local listing if there's an error
                return super().list_trained_models()
        else:
            # Fall back to local listing if model_storage_manager is not set
            return super().list_trained_models()
    
    async def load_model(self, model_id: str) -> Tuple[Any, Any, Dict]:
        """Load a trained model with its scaler and metadata"""
        if self.model_storage_manager:
            try:
                # Use model_storage_manager to load model (async)
                model, scaler, metadata = await self.model_storage_manager.load_model_by_id(model_id)
                logger.info(f"✅ Loaded model {model_id} from storage")
                return model, scaler, metadata
            except Exception as e:
                logger.error(f"❌ Error loading model from storage: {str(e)}")
                # Fall back to local loading if there's an error
                return super().load_model(model_id)
        else:
            # Fall back to local loading if model_storage_manager is not set
            return super().load_model(model_id)
