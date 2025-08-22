import os
import time
import logging
import requests

logger = logging.getLogger("platform.llm_config")

llm_configurations_cache = {}
last_cache_update = None

def get_llm_configurations_from_db():
    """Get LLM configurations from project service database with caching"""
    global llm_configurations_cache, last_cache_update
    current_time = time.time()
    if last_cache_update and (current_time - last_cache_update) < 30:
        return llm_configurations_cache
    try:
        from app.core.project_service import get_project_service
        project_service = get_project_service()
        headers = project_service._get_auth_headers()
        try:
            from app.core.logging_config import correlation_id_ctx
            cid = correlation_id_ctx.get("-")
            if cid and cid != "-":
                headers["X-Correlation-ID"] = cid
        except Exception:
            pass
        response = requests.get(
            f"{project_service.base_url}/llm-configurations",
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            configs_list = response.json()
            llm_configurations_cache = {config['id']: config for config in configs_list}
            last_cache_update = current_time
            logger.info(f"Loaded {len(llm_configurations_cache)} LLM configurations from database")
        else:
            logger.error(f"Failed to load LLM configurations: {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise Exception("Database load failed, falling back to JSON")
    except Exception as e:
        logger.warning(f"Error loading LLM configurations from database: {e}")
        logger.info("Falling back to JSON file for LLM configurations")
        try:
            import json
            json_path = os.path.join(os.path.dirname(__file__), "../llm_configurations.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    llm_configurations_cache = json.load(f)
                last_cache_update = current_time
                logger.info(f"Loaded {len(llm_configurations_cache)} LLM configurations from JSON file")
            else:
                logger.error("No LLM configurations JSON file found")
        except Exception as json_error:
            logger.error(f"Error loading LLM configurations from JSON: {json_error}")
    return llm_configurations_cache

def invalidate_llm_cache():
    global last_cache_update, llm_configurations_cache
    last_cache_update = None
    llm_configurations_cache = {}
