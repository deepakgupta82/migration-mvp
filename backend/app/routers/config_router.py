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
        # Default configuration structure (UI-editable)
        # Mirrors env_var_summary.txt
        default_config = {
            "backend": {
                "stats_refresh_interval_sec": 300,
                "disable_ws_auth": 0,
                "service_auth_token": "service-backend-token",
                "port": 8000,
                "warmup_stats_concurrency": 6,
                "warmup_stats_limit": 50,
                "cors_origins": [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://localhost:30300",
                    "http://127.0.0.1:30300",
                    "http://frontend-service",
                    "http://frontend-service:80"
                ]
            },
            "project_service": {
                "database_url": "postgresql://projectuser:projectpass@localhost:5432/projectdb",
                "secret_key": "",
                "jwt_secret_key": "your-super-secret-jwt-key-change-in-production",
                "jwt_algorithm": "HS256",
                "jwt_access_token_expire_minutes": 30,
                "jwt_refresh_token_expire_days": 7,
                "jwt_service_token_expire_hours": 24,
                "service_auth_token": "service-backend-token"
            },
            "document_service": {
                "chunking_strategy": "paragraph",
                "semantic_max_chunk": 2000,
                "semantic_overlap": 200,
                "semantic_model": "all-MiniLM-L6-v2",
                "enable_llm_enrichment": False,
                "service_auth_token": "service-backend-token"
            },
            "vector_service": {
                "chroma_db_path": "../../data/chroma_db",
                "debug_vector_logs": False
            },
            "graph_service": {
                "neo4j_uri": "bolt://localhost:7687",
                "neo4j_user": "neo4j",
                "neo4j_password": "password",
                "redis_host": "localhost",
                "redis_port": 6379,
                "redis_db": 5,
                "llm_service_url": "http://localhost:8007",
                "service_auth_token": "service-backend-token"
            },
            "llm_service": {
                "openai_api_key": "",
                "anthropic_api_key": "",
                "azure_openai_endpoint": "",
                "azure_openai_api_key": "",
                "debug_llm_logs": False,
                "service_auth_token": "service-backend-token"
            },
            "ai_agent_service": {
                "project_service_url": "http://localhost:8002",
                "vector_service_url": "http://localhost:8005",
                "llm_service_url": "http://localhost:8007",
                "storage_service_url": "http://localhost:8010",
                "reporting_service_url": "http://localhost:8003",
                "service_auth_token": "service-backend-token"
            },
            "storage_service": {
                "storage_provider": "minio",
                "storage_bucket": "agentimigrate",
                "storage_endpoint": "localhost:9000",
                "storage_access_key": "minioadmin",
                "storage_secret_key": "minioadmin",
                "storage_secure": False,
                "upload_root_tmp": ""
            },
            "reporting_service": {
                "database_url": "postgresql://projectuser:projectpass@localhost:5432/projectdb",
                "project_service_url": "http://localhost:8002",
                "object_storage_endpoint": "localhost:9000",
                "object_storage_access_key": "minioadmin",
                "object_storage_secret_key": "minioadmin",
                "backend_service_url": "http://localhost:8000",
                "service_auth_token": "service-backend-token"
            },
            "frontend": {
                "react_app_api_url": ""
            },
            "shared": {
                "weaviate_url": "http://localhost:8080",
                "minio_endpoint": "localhost:9000",
                "minio_access_key": "minioadmin",
                "minio_secret_key": "minioadmin",
                "minio_bucket_name": "agentimigrate"
            },
            "processing": {
                "chunking_strategy": "semantic",
                "chunk_size": 3500,
                "embedding_model": "all-MiniLM-L6-v2"
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
