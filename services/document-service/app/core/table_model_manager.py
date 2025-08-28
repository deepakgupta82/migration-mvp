"""
Table Model Manager for Unstructured.io Optimization
Reduces the 2-minute table agent loading delay by implementing lazy loading and caching
"""

import os
import logging
import threading
import time
import asyncio
from typing import Optional, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("document-service.table-model-manager")

class TableModelManager:
    """Manages table detection models for unstructured.io with optimization"""
    
    def __init__(self):
        self._table_agent = None
        self._table_model = None
        self._loading_lock = threading.Lock()
        self._model_loading = False
        self._load_failure_count = 0
        self._max_retries = 3
        self._background_loading_enabled = os.getenv("ENABLE_TABLE_MODEL_BACKGROUND_LOADING", "true").lower() == "true"
        self._cache_models = os.getenv("ENABLE_TABLE_MODEL_CACHING", "true").lower() == "true"
        
        # Thread pool for background loading
        self._thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TableModelLoader")
        
        logger.info("Table Model Manager initialized with background loading and caching optimizations")
    
    def start_background_loading(self):
        """Start background loading of table models after service startup"""
        if not self._background_loading_enabled:
            logger.info("Background table model loading disabled")
            return
            
        # Start loading in background after a delay
        delay = int(os.getenv("TABLE_MODEL_LOADING_DELAY", "10"))  # 10 seconds delay
        
        def delayed_load():
            time.sleep(delay)
            self._load_table_models_sync()
        
        self._thread_pool.submit(delayed_load)
        logger.info(f"Scheduled background table model loading in {delay} seconds")
    
    def _load_table_models_sync(self):
        """Load table models synchronously in background thread"""
        try:
            with self._loading_lock:
                if self._table_agent is not None and self._table_model is not None:
                    logger.info("Table models already loaded, skipping background load")
                    return
                
                logger.info("Background loading table detection models...")
                start_time = time.time()
                
                # Import and load table agent
                try:
                    from unstructured_inference.inference.layout import DocumentLayout
                    from unstructured_inference.models.tables import UnstructuredTableTransformerModel
                    
                    # Load table transformer model
                    self._table_model = UnstructuredTableTransformerModel()
                    load_time = time.time() - start_time
                    
                    logger.info(f"Table models loaded successfully in background: {load_time:.2f}s")
                    self._load_failure_count = 0
                    
                except ImportError as e:
                    logger.warning(f"Table model dependencies not available: {e}")
                    self._load_failure_count += 1
                except Exception as e:
                    logger.error(f"Background table model loading failed: {e}")
                    self._load_failure_count += 1
                    
        except Exception as e:
            logger.error(f"Error in background table model loading: {e}")
            self._load_failure_count += 1
    
    async def get_table_models_async(self) -> tuple[Optional[Any], Optional[Any]]:
        """Get table models asynchronously with fallback to on-demand loading"""
        # If models are already loaded, return immediately
        if self._cache_models and self._table_agent is not None and self._table_model is not None:
            return self._table_agent, self._table_model
        
        # Check if background loading is in progress
        if self._model_loading:
            logger.info("Table models loading in progress, waiting...")
            # Wait for background loading to complete
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._wait_for_loading)
            return self._table_agent, self._table_model
        
        # Load models on-demand if not available and not loading
        if self._table_agent is None or self._table_model is None:
            if self._load_failure_count >= self._max_retries:
                logger.warning(f"Table model loading has failed {self._load_failure_count} times, skipping")
                return None, None
            
            logger.info("Loading table models on-demand...")
            self._model_loading = True
            
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._load_table_models_sync)
            finally:
                self._model_loading = False
        
        return self._table_agent, self._table_model
    
    def _wait_for_loading(self, timeout: int = 120):
        """Wait for model loading to complete with timeout"""
        start_time = time.time()
        while self._model_loading and (time.time() - start_time) < timeout:
            time.sleep(0.5)
        
        if self._model_loading:
            logger.warning("Timeout waiting for table model loading")
    
    def get_models_sync(self) -> tuple[Optional[Any], Optional[Any]]:
        """Get table models synchronously (for compatibility)"""
        if self._cache_models and self._table_agent is not None and self._table_model is not None:
            return self._table_agent, self._table_model
        
        if self._load_failure_count >= self._max_retries:
            logger.warning(f"Table model loading has failed {self._load_failure_count} times, skipping")
            return None, None
        
        self._load_table_models_sync()
        return self._table_agent, self._table_model
    
    def is_models_loaded(self) -> bool:
        """Check if table models are loaded"""
        return self._table_agent is not None and self._table_model is not None
    
    def get_load_status(self) -> dict:
        """Get current loading status"""
        return {
            "models_loaded": self.is_models_loaded(),
            "loading_in_progress": self._model_loading,
            "load_failure_count": self._load_failure_count,
            "background_loading_enabled": self._background_loading_enabled,
            "caching_enabled": self._cache_models
        }
    
    def clear_cache(self):
        """Clear cached models to force reload"""
        with self._loading_lock:
            self._table_agent = None
            self._table_model = None
            self._load_failure_count = 0
            logger.info("Table model cache cleared")
    
    def shutdown(self):
        """Shutdown the table model manager"""
        self._thread_pool.shutdown(wait=False)
        logger.info("Table Model Manager shutdown")

# Global instance
_table_model_manager = None

def get_table_model_manager() -> TableModelManager:
    """Get the global table model manager instance"""
    global _table_model_manager
    if _table_model_manager is None:
        _table_model_manager = TableModelManager()
    return _table_model_manager

def init_table_model_optimization():
    """Initialize table model optimization (call during service startup)"""
    manager = get_table_model_manager()
    manager.start_background_loading()
    logger.info("Table model optimization initialized")

def get_table_model_status():
    """Get table model loading status for health checks"""
    manager = get_table_model_manager()
    return manager.get_load_status()