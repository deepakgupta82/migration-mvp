"""
Configuration router - for accessing local configuration files
"""
from fastapi import APIRouter, HTTPException
import logging
import os
import json
from typing import Dict, Any

router = APIRouter(prefix="/config", tags=["config"])
logger = logging.getLogger(__name__)

@router.get("/config.local.json", summary="Get local configuration")
async def get_local_config() -> Dict[str, Any]:
    """Get local configuration settings"""
    try:
        # Default configuration structure
        default_config = {
            "processing": {
                "chunking_strategy": "semantic",
                "chunk_size": 3500,
                "embedding_model": "all-MiniLM-L6-v2"
            },
            "database": {
                "host": "localhost",
                "port": 5432
            },
            "logging": {
                "level": "INFO"
            }
        }
        
        # Try to read from actual config file if it exists
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.local.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config
            except Exception as e:
                logger.warning(f"Failed to read config file: {e}")
        
        # Return default config if file doesn't exist
        return default_config
        
    except Exception as e:
        logger.error(f"Error getting local config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")

@router.put("/config.local.json", summary="Update local configuration")
async def update_local_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Update local configuration settings"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.local.json")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Write updated config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Updated local configuration at {config_path}")
        return config
        
    except Exception as e:
        logger.error(f"Error updating local config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")
