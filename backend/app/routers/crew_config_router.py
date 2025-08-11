from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from app.core.crew_config_service import crew_config_service
from app.main import crew_config_ws_manager  # reuse websocket manager for broadcast
import logging
from datetime import datetime

logger = logging.getLogger("platform.crew_config_router")

router = APIRouter(prefix="/api/crew-config", tags=["crew-config"])

@router.get("", summary="Get current crew configuration with statistics & validation")
async def get_crew_configuration():
    try:
        config = crew_config_service.get_configuration()
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        return {
            "config": config,
            "statistics": stats,
            "validation": validation,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to fetch crew configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to load crew configuration")

@router.post("/reload", summary="Reload crew configuration from YAML file and broadcast")
async def reload_crew_configuration():
    try:
        config = crew_config_service.get_configuration(force_reload=True)
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        # Broadcast update on websocket
        try:
            await crew_config_ws_manager.broadcast({
                "type": "crew_config_update",
                "timestamp": datetime.utcnow().isoformat(),
                "config": config,
                "stats": stats,
                "validation": validation
            })
        except Exception as be:
            logger.warning(f"Broadcast failed during reload: {be}")
        return {"status": "reloaded", "statistics": stats, "validation": validation}
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration")

@router.put("", summary="Update crew configuration (overwrite YAML)")
async def update_crew_configuration(new_config: Dict[str, Any]):
    try:
        ok = crew_config_service.update_configuration(new_config)
        if not ok:
            raise HTTPException(status_code=400, detail="Update failed; configuration restored from backup")
        stats = crew_config_service.get_statistics()
        validation = crew_config_service.validate_references()
        try:
            await crew_config_ws_manager.broadcast({
                "type": "crew_config_update",
                "timestamp": datetime.utcnow().isoformat(),
                "config": crew_config_service.get_configuration(),
                "stats": stats,
                "validation": validation
            })
        except Exception as be:
            logger.warning(f"Broadcast failed after update: {be}")
        return {"status": "updated", "statistics": stats, "validation": validation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")
