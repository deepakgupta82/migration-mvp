"""
Global template usage router - for platform-wide template statistics
"""
from fastapi import APIRouter, HTTPException
import logging
import requests
from ..core.project_service import get_project_service

router = APIRouter(prefix="/api/template-usage", tags=["templates"])
logger = logging.getLogger(__name__)

@router.get("/global", summary="Get global template usage across all projects")
async def get_global_template_usage():
    """Get aggregated template usage statistics across all projects"""
    try:
        service = get_project_service()
        headers = service._get_auth_headers()
        
        response = requests.get(
            f"{service.base_url}/template-usage/global", 
            headers=headers, 
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Upstream template usage service returned {response.status_code}")
            # Return empty response if service is not available
            return {
                "total_templates": 0,
                "total_generations": 0,
                "templates": []
            }
    except requests.RequestException as e:
        logger.warning(f"Template usage service unavailable: {e}")
        # Return default response when service is down
        return {
            "total_templates": 0,
            "total_generations": 0,
            "templates": []
        }
    except Exception as e:
        logger.error(f"Error fetching global template usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch template usage data")
