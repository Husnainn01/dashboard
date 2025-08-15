"""
Model Storage Service for OTC Predictor
Handles storing and retrieving ML models from different storage backends
"""

import os
import json
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import pickle
import io
from typing import Dict, Any, Optional, BinaryIO, Union, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelStorageService:
    """
    Service for storing and retrieving ML models from different storage backends
    Supports local filesystem and Cloudflare R2 (S3-compatible) storage
    """
    
    def __init__(self, storage_type: str = "local", config: Dict[str, Any] = None):
        """
        Initialize the storage service
        
        Args:
            storage_type: Type of storage to use ('local' or 'r2')
            config: Configuration for the storage backend
        """
        self.storage_type = storage_type.lower()
        self.config = config or {}
        
        # Set up local storage
        if self.storage_type == "local":
            self.local_dir = Path(self.config.get("local_dir", Path(__file__).parent.parent.parent / "trained_models"))
            self.local_dir.mkdir(exist_ok=True, parents=True)
            logger.info(f"📁 Using local storage at {self.local_dir}")
            
        # Set up R2 storage
        elif self.storage_type == "r2":
            self._setup_r2_client()
            logger.info(f"☁️ Using Cloudflare R2 storage with bucket {self.config.get('bucket_name', 'quotex')}")
            
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
    
    def _setup_r2_client(self):
        """Set up the R2 client using boto3"""
        try:
            # Get credentials from config or environment variables
            access_key = self.config.get("access_key") or os.environ.get("R2_ACCESS_KEY")
            secret_key = self.config.get("secret_key") or os.environ.get("R2_SECRET_KEY")
            endpoint_url = self.config.get("endpoint_url") or os.environ.get("R2_ENDPOINT_URL")
            self.bucket_name = self.config.get("bucket_name") or os.environ.get("R2_BUCKET_NAME") or "quotex"
            
            # Log configuration (with redacted secret key)
            logger.info(f"☁️ Setting up R2 client with endpoint: {endpoint_url}")
            logger.info(f"☁️ Using bucket: {self.bucket_name}")
            
            if not access_key:
                logger.error("❌ Missing R2 access key")
                raise ValueError("Missing R2 access key")
                
            if not secret_key:
                logger.error("❌ Missing R2 secret key")
                raise ValueError("Missing R2 secret key")
                
            if not endpoint_url:
                logger.error("❌ Missing R2 endpoint URL")
                raise ValueError("Missing R2 endpoint URL")
            
            # Create S3 client for R2
            logger.info("🔌 Creating boto3 S3 client for R2...")
            self.r2_client = boto3.client(
                service_name='s3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="auto"  # R2 doesn't use regions but boto3 requires this
            )
            
            # Ensure bucket exists
            try:
                logger.info(f"🔍 Checking if bucket exists: {self.bucket_name}")
                self.r2_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ Connected to R2 bucket: {self.bucket_name}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                logger.warning(f"⚠️ Bucket check error: {error_code}")
                
                if error_code == '404':
                    # Create bucket if it doesn't exist
                    logger.info(f"🔧 Creating bucket: {self.bucket_name}")
                    self.r2_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"✅ Created R2 bucket: {self.bucket_name}")
                else:
                    logger.error(f"❌ R2 client error: {str(e)}")
                    raise
                    
        except ImportError as e:
            logger.error(f"❌ Failed to import boto3. Please install it with 'pip install boto3': {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize R2 client: {str(e)}")
            raise
    
    async def save_model(self, 
                        model_data: Any, 
                        metadata: Dict[str, Any], 
                        model_id: str = None) -> Dict[str, Any]:
        """
        Save a model to storage
        
        Args:
            model_data: The model object to save
            metadata: Metadata about the model
            model_id: Optional ID for the model, if None a new ID will be generated
            
        Returns:
            Dict with model information including storage location
        """
        # Generate model ID if not provided
        if model_id is None:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            trading_pair = metadata.get("trading_pair", "unknown").replace("/", "_").replace(" ", "_")
            algorithm = metadata.get("algorithm", "model")
            model_id = f"{algorithm}_{trading_pair}_{timestamp}"
        
        # Add storage info to metadata
        metadata["model_id"] = model_id
        metadata["storage_type"] = self.storage_type
        metadata["saved_at"] = datetime.now().isoformat()
        
        # Save to appropriate storage
        if self.storage_type == "local":
            return await self._save_local(model_data, metadata, model_id)
        elif self.storage_type == "r2":
            return await self._save_r2(model_data, metadata, model_id)
    
    async def _save_local(self, 
                         model_data: Any, 
                         metadata: Dict[str, Any], 
                         model_id: str) -> Dict[str, Any]:
        """Save model to local filesystem"""
        try:
            # Create directory for this model
            model_dir = self.local_dir / model_id
            model_dir.mkdir(exist_ok=True)
            
            # Save model
            model_path = model_dir / "model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model_data, f)
            
            # Save metadata
            metadata_path = model_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Add paths to metadata
            metadata["model_path"] = str(model_path)
            metadata["metadata_path"] = str(metadata_path)
            
            logger.info(f"✅ Model saved to local storage: {model_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error saving model to local storage: {str(e)}")
            raise
    
    async def _save_r2(self, 
                      model_data: Any, 
                      metadata: Dict[str, Any], 
                      model_id: str) -> Dict[str, Any]:
        """Save model to Cloudflare R2"""
        try:
            # Create model key
            model_key = f"models/{model_id}/model.pkl"
            metadata_key = f"models/{model_id}/metadata.json"
            
            logger.info(f"🔄 Saving model to R2: {model_id}")
            logger.info(f"📄 Model key: {model_key}")
            logger.info(f"📄 Metadata key: {metadata_key}")
            
            # Serialize model to bytes
            try:
                model_bytes = io.BytesIO()
                pickle.dump(model_data, model_bytes)
                model_bytes.seek(0)
                model_size = model_bytes.getbuffer().nbytes
                logger.info(f"📦 Model serialized: {model_size} bytes")
            except Exception as e:
                logger.error(f"❌ Error serializing model: {str(e)}")
                raise
            
            # Upload model
            try:
                logger.info(f"📤 Uploading model to R2...")
                self.r2_client.upload_fileobj(
                    model_bytes, 
                    self.bucket_name, 
                    model_key
                )
                logger.info(f"✅ Model uploaded successfully")
            except ClientError as e:
                logger.error(f"❌ Error uploading model to R2: {str(e)}")
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                logger.error(f"❌ Error code: {error_code}")
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error uploading model: {str(e)}")
                raise
            
            # Add R2 info to metadata
            metadata["r2_bucket"] = self.bucket_name
            metadata["r2_model_key"] = model_key
            metadata["r2_metadata_key"] = metadata_key
            metadata["r2_upload_time"] = datetime.now().isoformat()
            
            # Upload metadata
            try:
                logger.info(f"📤 Uploading metadata to R2...")
                metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
                metadata_stream = io.BytesIO(metadata_bytes)
                self.r2_client.upload_fileobj(
                    metadata_stream,
                    self.bucket_name,
                    metadata_key
                )
                logger.info(f"✅ Metadata uploaded successfully")
            except Exception as e:
                logger.error(f"❌ Error uploading metadata to R2: {str(e)}")
                raise
            
            # Verify upload by checking if files exist
            try:
                logger.info(f"🔍 Verifying model upload...")
                self.r2_client.head_object(Bucket=self.bucket_name, Key=model_key)
                self.r2_client.head_object(Bucket=self.bucket_name, Key=metadata_key)
                logger.info(f"✅ Upload verification successful")
            except Exception as e:
                logger.warning(f"⚠️ Could not verify upload: {str(e)}")
                # Continue anyway, don't raise exception
            
            logger.info(f"✅ Model saved to R2 storage: {model_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error saving model to R2: {str(e)}")
            raise
    
    async def load_model(self, model_id: str, version: str = None) -> Tuple[Any, Dict[str, Any]]:
        """
        Load a model from storage
        
        Args:
            model_id: ID of the model to load
            version: Optional version of the model to load
            
        Returns:
            Tuple of (model_data, metadata)
        """
        if self.storage_type == "local":
            return await self._load_local(model_id, version)
        elif self.storage_type == "r2":
            return await self._load_r2(model_id, version)
    
    async def _load_local(self, model_id: str, version: str = None) -> Tuple[Any, Dict[str, Any]]:
        """Load model from local filesystem"""
        try:
            # Find model directory
            model_dir = self.local_dir / model_id
            if not model_dir.exists():
                raise FileNotFoundError(f"Model not found: {model_id}")
            
            # Load metadata
            metadata_path = model_dir / "metadata.json"
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            # Load model
            model_path = model_dir / "model.pkl"
            with open(model_path, "rb") as f:
                model_data = pickle.load(f)
            
            logger.info(f"✅ Model loaded from local storage: {model_id}")
            return model_data, metadata
            
        except Exception as e:
            logger.error(f"❌ Error loading model from local storage: {str(e)}")
            raise
    
    async def _load_r2(self, model_id: str, version: str = None) -> Tuple[Any, Dict[str, Any]]:
        """Load model from Cloudflare R2"""
        try:
            # Create model key
            model_key = f"models/{model_id}/model.pkl"
            metadata_key = f"models/{model_id}/metadata.json"
            
            # Download metadata
            metadata_obj = self.r2_client.get_object(
                Bucket=self.bucket_name,
                Key=metadata_key
            )
            metadata_bytes = metadata_obj['Body'].read()
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            
            # Download model
            model_obj = self.r2_client.get_object(
                Bucket=self.bucket_name,
                Key=model_key
            )
            model_bytes = model_obj['Body'].read()
            model_data = pickle.loads(model_bytes)
            
            logger.info(f"✅ Model loaded from R2 storage: {model_id}")
            return model_data, metadata
            
        except Exception as e:
            logger.error(f"❌ Error loading model from R2: {str(e)}")
            raise
    
    async def list_models(self, trading_pair: str = None, algorithm: str = None) -> list:
        """
        List available models
        
        Args:
            trading_pair: Optional filter by trading pair
            algorithm: Optional filter by algorithm
            
        Returns:
            List of model metadata
        """
        if self.storage_type == "local":
            return await self._list_local_models(trading_pair, algorithm)
        elif self.storage_type == "r2":
            return await self._list_r2_models(trading_pair, algorithm)
            
    async def get_model_metadata(self, model_id: str) -> dict:
        """
        Get metadata for a specific model
        
        Args:
            model_id: Model ID to get metadata for
            
        Returns:
            Model metadata dictionary
        """
        logger.info(f"🔍 Getting metadata for model: {model_id}")
        
        if self.storage_type == "local":
            return await self._get_local_model_metadata(model_id)
        elif self.storage_type == "r2":
            return await self._get_r2_model_metadata(model_id)
            
    async def _get_local_model_metadata(self, model_id: str) -> dict:
        """Get model metadata from local storage"""
        try:
            # Construct path to metadata file
            metadata_path = Path(self.local_dir) / model_id / "metadata.json"
            
            if not metadata_path.exists():
                raise FileNotFoundError(f"Metadata file not found for model {model_id}")
                
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                
            logger.info(f"✅ Loaded metadata for model {model_id} from local storage")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error loading metadata for model {model_id} from local storage: {str(e)}")
            raise
            
    async def _get_r2_model_metadata(self, model_id: str) -> dict:
        """Get model metadata from Cloudflare R2"""
        try:
            # Construct key for metadata file
            metadata_key = f"models/{model_id}/metadata.json"
            
            # Get metadata object
            try:
                metadata_obj = self.r2_client.get_object(
                    Bucket=self.bucket_name,
                    Key=metadata_key
                )
            except self.r2_client.exceptions.NoSuchKey:
                raise FileNotFoundError(f"Metadata file not found for model {model_id} in R2 storage")
                
            # Read and parse metadata
            metadata_bytes = metadata_obj['Body'].read()
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            
            logger.info(f"✅ Loaded metadata for model {model_id} from R2 storage")
            return metadata
            
        except FileNotFoundError:
            # Re-raise file not found errors
            raise
        except Exception as e:
            logger.error(f"❌ Error loading metadata for model {model_id} from R2 storage: {str(e)}")
            raise
    
    async def _list_local_models(self, trading_pair: str = None, algorithm: str = None) -> list:
        """List models in local filesystem"""
        models = []
        
        # Iterate through model directories
        for model_dir in self.local_dir.iterdir():
            if not model_dir.is_dir():
                continue
                
            # Check for metadata file
            metadata_path = model_dir / "metadata.json"
            if not metadata_path.exists():
                continue
                
            # Load metadata
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    
                # Apply filters
                if trading_pair and metadata.get("trading_pair") != trading_pair:
                    continue
                if algorithm and metadata.get("algorithm") != algorithm:
                    continue
                    
                models.append(metadata)
            except Exception as e:
                logger.warning(f"⚠️ Error loading metadata from {metadata_path}: {str(e)}")
        
        # Sort by saved_at (newest first)
        models.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return models
    
    async def _list_r2_models(self, trading_pair: str = None, algorithm: str = None) -> list:
        """List models in Cloudflare R2"""
        models = []
        
        try:
            logger.info(f"🔍 Listing R2 models with filters - trading_pair: {trading_pair}, algorithm: {algorithm}")
            
            # List all metadata files
            logger.info(f"📋 Listing objects in bucket: {self.bucket_name} with prefix: models/")
            response = self.r2_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="models/",
                Delimiter="/"
            )
            
            # Log the response structure
            logger.info(f"📊 R2 list response keys: {list(response.keys())}")
            common_prefixes_count = len(response.get('CommonPrefixes', []))
            logger.info(f"📊 Found {common_prefixes_count} common prefixes (model directories)")
            
            # Process common prefixes (directories)
            for prefix in response.get('CommonPrefixes', []):
                model_prefix = prefix.get('Prefix')
                if not model_prefix:
                    logger.warning("⚠️ Found empty prefix in R2 response")
                    continue
                
                logger.info(f"📁 Processing model directory: {model_prefix}")
                
                # Get metadata file
                metadata_key = f"{model_prefix}metadata.json"
                try:
                    logger.info(f"📄 Fetching metadata file: {metadata_key}")
                    metadata_obj = self.r2_client.get_object(
                        Bucket=self.bucket_name,
                        Key=metadata_key
                    )
                    metadata_bytes = metadata_obj['Body'].read()
                    metadata = json.loads(metadata_bytes.decode('utf-8'))
                    
                    # Log metadata keys for debugging
                    logger.info(f"📋 Metadata keys: {list(metadata.keys())}")
                    logger.info(f"📋 Model trading_pair: {metadata.get('trading_pair')}, algorithm: {metadata.get('algorithm')}")
                    
                    # Apply filters
                    if trading_pair and metadata.get("trading_pair") != trading_pair:
                        logger.info(f"🔍 Filtering out model: trading_pair mismatch - requested: {trading_pair}, found: {metadata.get('trading_pair')}")
                        continue
                    if algorithm and metadata.get("algorithm") != algorithm:
                        logger.info(f"🔍 Filtering out model: algorithm mismatch - requested: {algorithm}, found: {metadata.get('algorithm')}")
                        continue
                        
                    logger.info(f"✅ Adding model to results: {metadata.get('model_id')}")
                    models.append(metadata)
                except Exception as e:
                    logger.warning(f"⚠️ Error loading metadata from {metadata_key}: {str(e)}")
            
            # Sort by saved_at (newest first)
            models.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
            logger.info(f"📊 Returning {len(models)} models after filtering")
            return models
            
        except Exception as e:
            logger.error(f"❌ Error listing models from R2: {str(e)}")
            raise
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Delete a model from storage
        
        Args:
            model_id: ID of the model to delete
            
        Returns:
            True if successful, False otherwise
        """
        if self.storage_type == "local":
            return await self._delete_local_model(model_id)
        elif self.storage_type == "r2":
            return await self._delete_r2_model(model_id)
    
    async def _delete_local_model(self, model_id: str) -> bool:
        """Delete model from local filesystem"""
        try:
            # Find model directory
            model_dir = self.local_dir / model_id
            if not model_dir.exists():
                logger.warning(f"⚠️ Model not found: {model_id}")
                return False
            
            # Delete files
            for file_path in model_dir.iterdir():
                file_path.unlink()
            
            # Delete directory
            model_dir.rmdir()
            
            logger.info(f"✅ Model deleted from local storage: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting model from local storage: {str(e)}")
            return False
    
    async def _delete_r2_model(self, model_id: str) -> bool:
        """Delete model from Cloudflare R2"""
        try:
            # Create model keys
            model_key = f"models/{model_id}/model.pkl"
            metadata_key = f"models/{model_id}/metadata.json"
            
            # Delete model and metadata
            self.r2_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={
                    'Objects': [
                        {'Key': model_key},
                        {'Key': metadata_key}
                    ]
                }
            )
            
            logger.info(f"✅ Model deleted from R2 storage: {model_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting model from R2: {str(e)}")
            return False
