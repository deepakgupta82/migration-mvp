import logging
from fastapi import APIRouter, HTTPException
from app.core.project_service import get_project_service

logger = logging.getLogger("platform.platform_settings_router")

router = APIRouter(prefix="/api", tags=["platform-settings"])

@router.get("/platform-settings", summary="List platform settings (API keys, etc.)")
async def list_platform_settings():
    try:
        service = get_project_service()
        settings = service.get_platform_settings() or []
        return settings
    except Exception as e:
        logger.error(f"Error retrieving platform settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve platform settings")
