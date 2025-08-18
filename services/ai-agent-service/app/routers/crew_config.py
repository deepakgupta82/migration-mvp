from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Any, Dict
import logging

from ..core.crew_config_service import crew_config_service

logger = logging.getLogger("ai-agent-service.crew-config-router")
router = APIRouter(prefix="/api/crew-config", tags=["crew-config"]) 

@router.get("")
async def get_crew_configuration():
    try:
        cfg = crew_config_service.get_configuration()
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        return {
            "config": cfg,
            "statistics": stats,
            "validation": validation,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to fetch crew configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to load crew configuration")

@router.post("/reload")
async def reload_crew_configuration():
    try:
        cfg = crew_config_service.get_configuration(force_reload=True)
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        return {"status": "reloaded", "statistics": stats, "validation": validation}
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration")

@router.put("")
async def update_crew_configuration(new_config: Dict[str, Any]):
    try:
        ok = crew_config_service.update_configuration(new_config)
        if not ok:
            raise HTTPException(status_code=400, detail="Update failed; configuration restored from backup")
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        return {"status": "updated", "statistics": stats, "validation": validation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")
