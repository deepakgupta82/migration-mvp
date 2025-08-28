"""
Shared Model Manager for AI Model Loading Optimization
Provides centralized model loading, caching, and background warm-up functionality
"""

import logging
import threading
import asyncio
import time
import os
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("model-manager")

class ModelType(Enum):
    SENTENCE_TRANSFORMER = "sentence_transformer"
    EMBEDDING_MODEL = "embedding_model"
    SEMANTIC_CHUNKING = "semantic_chunking"

@dataclass
class ModelConfig:
    model_type: ModelType
    model_name: str
    load_on_startup: bool = False
    cache_timeout: int = 3600  # seconds
    max_retries: int = 3

class ModelManager:
    """Centralized model management with lazy loading and background warming"""
    
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._model_configs: Dict[str, ModelConfig] = {}
        self._loading_locks: Dict[str, threading.Lock] = {}
        self._load_failures: Dict[str, int] = {}
        self._load_times: Dict[str, float] = {}
        self._background_tasks: Dict[str, threading.Thread] = {}
        
        # Default model configurations
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Setup default model configurations"""
        self.register_model(
            "sentence_transformer_default",
            ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"),
                load_on_startup=True
            )
        )
        
        self.register_model(
            "semantic_chunking_model",
            ModelConfig(
                model_type=ModelType.SEMANTIC_CHUNKING,
                model_name=os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"),
                load_on_startup=False
            )
        )
    
    def register_model(self, model_id: str, config: ModelConfig):
        """Register a model configuration"""
        self._model_configs[model_id] = config
        self._loading_locks[model_id] = threading.Lock()
        logger.info(f"Registered model: {model_id} ({config.model_name})")
    
    def start_background_warming(self):
        """Start background model loading for models marked for startup loading"""
        for model_id, config in self._model_configs.items():
            if config.load_on_startup and model_id not in self._background_tasks:
                thread = threading.Thread(
                    target=self._background_load_model,
                    args=(model_id,),
                    daemon=True,
                    name=f"ModelLoader-{model_id}"
                )
                thread.start()
                self._background_tasks[model_id] = thread
                logger.info(f"Started background loading for model: {model_id}")
    
    def _background_load_model(self, model_id: str):
        """Load model in background thread"""
        try:
            start_time = time.time()
            logger.info(f"Background loading model: {model_id}")
            
            model = self._load_model_sync(model_id)
            if model:
                load_time = time.time() - start_time
                self._load_times[model_id] = load_time
                logger.info(f"Background loaded model {model_id} in {load_time:.2f}s")
            else:
                logger.warning(f"Background loading failed for model: {model_id}")
                
        except Exception as e:
            logger.error(f"Background loading error for {model_id}: {e}")
    
    def _load_model_sync(self, model_id: str) -> Optional[Any]:
        """Load model synchronously"""
        if model_id not in self._model_configs:
            logger.error(f"Unknown model ID: {model_id}")
            return None
        
        config = self._model_configs[model_id]
        
        # Check if already loaded
        if model_id in self._models:
            return self._models[model_id]
        
        # Check failure count
        if self._load_failures.get(model_id, 0) >= config.max_retries:
            logger.warning(f"Model {model_id} has exceeded max retries, skipping load")
            return None
        
        try:
            with self._loading_locks[model_id]:
                # Double-check pattern
                if model_id in self._models:
                    return self._models[model_id]
                
                logger.info(f"Loading model: {model_id} ({config.model_name})")
                start_time = time.time()
                
                model = self._create_model(config)
                if model:
                    self._models[model_id] = model
                    load_time = time.time() - start_time
                    self._load_times[model_id] = load_time
                    logger.info(f"Model {model_id} loaded successfully in {load_time:.2f}s")
                    
                    # Reset failure count on success
                    self._load_failures.pop(model_id, None)
                    return model
                else:
                    raise Exception("Model creation returned None")
                    
        except Exception as e:
            self._load_failures[model_id] = self._load_failures.get(model_id, 0) + 1
            logger.error(f"Failed to load model {model_id} (attempt {self._load_failures[model_id]}): {e}")
            return None
    
    def _create_model(self, config: ModelConfig) -> Optional[Any]:
        """Create model instance based on configuration"""
        try:
            if config.model_type == ModelType.SENTENCE_TRANSFORMER:
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(config.model_name)
            
            elif config.model_type == ModelType.SEMANTIC_CHUNKING:
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(config.model_name)
            
            else:
                logger.error(f"Unsupported model type: {config.model_type}")
                return None
                
        except ImportError as e:
            logger.error(f"Missing dependency for {config.model_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating model {config.model_name}: {e}")
            return None
    
    async def get_model_async(self, model_id: str) -> Optional[Any]:
        """Get model asynchronously with background loading support"""
        # If model is already loaded, return immediately
        if model_id in self._models:
            return self._models[model_id]
        
        # If background task is running, wait for it
        if model_id in self._background_tasks:
            thread = self._background_tasks[model_id]
            if thread.is_alive():
                # Wait for background loading to complete
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, thread.join, 30)  # 30s timeout
        
        # If still not loaded, load synchronously in thread pool
        if model_id not in self._models:
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(None, self._load_model_sync, model_id)
            return model
        
        return self._models.get(model_id)
    
    def get_model_sync(self, model_id: str) -> Optional[Any]:
        """Get model synchronously"""
        return self._load_model_sync(model_id)
    
    def is_model_loaded(self, model_id: str) -> bool:
        """Check if model is already loaded"""
        return model_id in self._models
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get model loading statistics"""
        return {
            "loaded_models": list(self._models.keys()),
            "load_times": self._load_times.copy(),
            "load_failures": self._load_failures.copy(),
            "background_tasks": {
                model_id: thread.is_alive() 
                for model_id, thread in self._background_tasks.items()
            }
        }
    
    def preload_model(self, model_id: str):
        """Trigger immediate model loading"""
        if model_id not in self._background_tasks or not self._background_tasks[model_id].is_alive():
            thread = threading.Thread(
                target=self._background_load_model,
                args=(model_id,),
                daemon=True,
                name=f"PreLoader-{model_id}"
            )
            thread.start()
            self._background_tasks[model_id] = thread

# Global model manager instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get the global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

def start_background_model_loading():
    """Start background model loading for all services"""
    manager = get_model_manager()
    manager.start_background_warming()
    logger.info("Background model loading started")

async def get_sentence_transformer_async(model_name: str = None) -> Optional[Any]:
    """Get sentence transformer model asynchronously"""
    model_id = "sentence_transformer_default"
    if model_name:
        # Register custom model if needed
        custom_id = f"sentence_transformer_{hash(model_name)}"
        manager = get_model_manager()
        if custom_id not in manager._model_configs:
            manager.register_model(custom_id, ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=model_name
            ))
        model_id = custom_id
    
    manager = get_model_manager()
    return await manager.get_model_async(model_id)

def get_sentence_transformer_sync(model_name: str = None) -> Optional[Any]:
    """Get sentence transformer model synchronously"""
    model_id = "sentence_transformer_default"
    if model_name:
        custom_id = f"sentence_transformer_{hash(model_name)}"
        manager = get_model_manager()
        if custom_id not in manager._model_configs:
            manager.register_model(custom_id, ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=model_name
            ))
        model_id = custom_id
    
    manager = get_model_manager()
    return manager.get_model_sync(model_id)"""
Shared Model Manager for AI Model Loading Optimization
Provides centralized model loading, caching, and background warm-up functionality
"""

import logging
import threading
import asyncio
import time
import os
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("model-manager")

class ModelType(Enum):
    SENTENCE_TRANSFORMER = "sentence_transformer"
    EMBEDDING_MODEL = "embedding_model"
    SEMANTIC_CHUNKING = "semantic_chunking"

@dataclass
class ModelConfig:
    model_type: ModelType
    model_name: str
    load_on_startup: bool = False
    cache_timeout: int = 3600  # seconds
    max_retries: int = 3

class ModelManager:
    """Centralized model management with lazy loading and background warming"""
    
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._model_configs: Dict[str, ModelConfig] = {}
        self._loading_locks: Dict[str, threading.Lock] = {}
        self._load_failures: Dict[str, int] = {}
        self._load_times: Dict[str, float] = {}
        self._background_tasks: Dict[str, threading.Thread] = {}
        
        # Default model configurations
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Setup default model configurations"""
        self.register_model(
            "sentence_transformer_default",
            ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"),
                load_on_startup=True
            )
        )
        
        self.register_model(
            "semantic_chunking_model",
            ModelConfig(
                model_type=ModelType.SEMANTIC_CHUNKING,
                model_name=os.getenv("SEMANTIC_MODEL", "all-MiniLM-L6-v2"),
                load_on_startup=False
            )
        )
    
    def register_model(self, model_id: str, config: ModelConfig):
        """Register a model configuration"""
        self._model_configs[model_id] = config
        self._loading_locks[model_id] = threading.Lock()
        logger.info(f"Registered model: {model_id} ({config.model_name})")
    
    def start_background_warming(self):
        """Start background model loading for models marked for startup loading"""
        for model_id, config in self._model_configs.items():
            if config.load_on_startup and model_id not in self._background_tasks:
                thread = threading.Thread(
                    target=self._background_load_model,
                    args=(model_id,),
                    daemon=True,
                    name=f"ModelLoader-{model_id}"
                )
                thread.start()
                self._background_tasks[model_id] = thread
                logger.info(f"Started background loading for model: {model_id}")
    
    def _background_load_model(self, model_id: str):
        """Load model in background thread"""
        try:
            start_time = time.time()
            logger.info(f"Background loading model: {model_id}")
            
            model = self._load_model_sync(model_id)
            if model:
                load_time = time.time() - start_time
                self._load_times[model_id] = load_time
                logger.info(f"Background loaded model {model_id} in {load_time:.2f}s")
            else:
                logger.warning(f"Background loading failed for model: {model_id}")
                
        except Exception as e:
            logger.error(f"Background loading error for {model_id}: {e}")
    
    def _load_model_sync(self, model_id: str) -> Optional[Any]:
        """Load model synchronously"""
        if model_id not in self._model_configs:
            logger.error(f"Unknown model ID: {model_id}")
            return None
        
        config = self._model_configs[model_id]
        
        # Check if already loaded
        if model_id in self._models:
            return self._models[model_id]
        
        # Check failure count
        if self._load_failures.get(model_id, 0) >= config.max_retries:
            logger.warning(f"Model {model_id} has exceeded max retries, skipping load")
            return None
        
        try:
            with self._loading_locks[model_id]:
                # Double-check pattern
                if model_id in self._models:
                    return self._models[model_id]
                
                logger.info(f"Loading model: {model_id} ({config.model_name})")
                start_time = time.time()
                
                model = self._create_model(config)
                if model:
                    self._models[model_id] = model
                    load_time = time.time() - start_time
                    self._load_times[model_id] = load_time
                    logger.info(f"Model {model_id} loaded successfully in {load_time:.2f}s")
                    
                    # Reset failure count on success
                    self._load_failures.pop(model_id, None)
                    return model
                else:
                    raise Exception("Model creation returned None")
                    
        except Exception as e:
            self._load_failures[model_id] = self._load_failures.get(model_id, 0) + 1
            logger.error(f"Failed to load model {model_id} (attempt {self._load_failures[model_id]}): {e}")
            return None
    
    def _create_model(self, config: ModelConfig) -> Optional[Any]:
        """Create model instance based on configuration"""
        try:
            if config.model_type == ModelType.SENTENCE_TRANSFORMER:
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(config.model_name)
            
            elif config.model_type == ModelType.SEMANTIC_CHUNKING:
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(config.model_name)
            
            else:
                logger.error(f"Unsupported model type: {config.model_type}")
                return None
                
        except ImportError as e:
            logger.error(f"Missing dependency for {config.model_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating model {config.model_name}: {e}")
            return None
    
    async def get_model_async(self, model_id: str) -> Optional[Any]:
        """Get model asynchronously with background loading support"""
        # If model is already loaded, return immediately
        if model_id in self._models:
            return self._models[model_id]
        
        # If background task is running, wait for it
        if model_id in self._background_tasks:
            thread = self._background_tasks[model_id]
            if thread.is_alive():
                # Wait for background loading to complete
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, thread.join, 30)  # 30s timeout
        
        # If still not loaded, load synchronously in thread pool
        if model_id not in self._models:
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(None, self._load_model_sync, model_id)
            return model
        
        return self._models.get(model_id)
    
    def get_model_sync(self, model_id: str) -> Optional[Any]:
        """Get model synchronously"""
        return self._load_model_sync(model_id)
    
    def is_model_loaded(self, model_id: str) -> bool:
        """Check if model is already loaded"""
        return model_id in self._models
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get model loading statistics"""
        return {
            "loaded_models": list(self._models.keys()),
            "load_times": self._load_times.copy(),
            "load_failures": self._load_failures.copy(),
            "background_tasks": {
                model_id: thread.is_alive() 
                for model_id, thread in self._background_tasks.items()
            }
        }
    
    def preload_model(self, model_id: str):
        """Trigger immediate model loading"""
        if model_id not in self._background_tasks or not self._background_tasks[model_id].is_alive():
            thread = threading.Thread(
                target=self._background_load_model,
                args=(model_id,),
                daemon=True,
                name=f"PreLoader-{model_id}"
            )
            thread.start()
            self._background_tasks[model_id] = thread

# Global model manager instance
_model_manager = None

def get_model_manager() -> ModelManager:
    """Get the global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

def start_background_model_loading():
    """Start background model loading for all services"""
    manager = get_model_manager()
    manager.start_background_warming()
    logger.info("Background model loading started")

async def get_sentence_transformer_async(model_name: str = None) -> Optional[Any]:
    """Get sentence transformer model asynchronously"""
    model_id = "sentence_transformer_default"
    if model_name:
        # Register custom model if needed
        custom_id = f"sentence_transformer_{hash(model_name)}"
        manager = get_model_manager()
        if custom_id not in manager._model_configs:
            manager.register_model(custom_id, ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=model_name
            ))
        model_id = custom_id
    
    manager = get_model_manager()
    return await manager.get_model_async(model_id)

def get_sentence_transformer_sync(model_name: str = None) -> Optional[Any]:
    """Get sentence transformer model synchronously"""
    model_id = "sentence_transformer_default"
    if model_name:
        custom_id = f"sentence_transformer_{hash(model_name)}"
        manager = get_model_manager()
        if custom_id not in manager._model_configs:
            manager.register_model(custom_id, ModelConfig(
                model_type=ModelType.SENTENCE_TRANSFORMER,
                model_name=model_name
            ))
        model_id = custom_id
    
    manager = get_model_manager()
    return manager.get_model_sync(model_id)