#!/usr/bin/env python3
"""
LLM Router - Clean API endpoints for LLM orchestration
Handles process-specific LLM requests, configuration, and provider management
"""

from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

from ..core.llm_processor import LLMProcessor, LLMProcessType

logger = logging.getLogger("llm-service")
router = APIRouter()

# Initialize clean processor
llm_processor = LLMProcessor()

# Request/Response Models
class ProcessLLMRequest(BaseModel):
    process_type: str = Field(..., description="Process type requiring LLM")
    prompt: str = Field(..., description="Prompt to process")
    project_id: Optional[str] = Field(None, description="Optional project ID")

class ProcessLLMResponse(BaseModel):
    process_type: str
    response: str
    success: bool
    error: Optional[str] = None

class HealthResponse(BaseModel):
    service: str
    status: str
    langchain_available: bool
    supported_providers: List[str]
    process_types: List[str]
    cache_status: Dict[str, Any]

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Clean health check endpoint"""
    try:
        health_data = await llm_processor.health_check()
        return HealthResponse(
            service="llm-service",
            status=health_data["status"],
            langchain_available=health_data["langchain_available"],
            supported_providers=list(health_data.get("supported_providers", [])),
            process_types=health_data["process_types"],
            cache_status=health_data["cache_status"]
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/providers")
async def list_providers():
    """List available LLM providers"""
    try:
        providers = await llm_processor.list_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/providers/status")
async def get_provider_status():
    """Get status and configuration info for all providers"""
    try:
        status = await llm_processor.get_provider_status()
        return {"provider_status": status}
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/process-types")
async def list_process_types():
    """List supported LLM process types"""
    try:
        process_types = await llm_processor.list_process_types()
        return {"process_types": process_types}
    except Exception as e:
        logger.error(f"Error listing process types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{process_type}")
async def get_model_recommendations(process_type: str):
    """Get model recommendations for specific process type"""
    try:
        recommendations = llm_processor.get_model_recommendations(process_type)
        return {
            "process_type": process_type,
            "recommendations": recommendations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process", response_model=ProcessLLMResponse)
async def process_llm_request(request: ProcessLLMRequest):
    """Process LLM request for specific process type"""
    try:
        response_text = await llm_processor.process_llm_request(
            process_type=request.process_type,
            prompt=request.prompt,
            project_id=request.project_id
        )
        
        return ProcessLLMResponse(
            process_type=request.process_type,
            response=response_text,
            success=True
        )
        
    except ValueError as e:
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=f"Invalid process type: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing LLM request: {e}")
        return ProcessLLMResponse(
            process_type=request.process_type,
            response="",
            success=False,
            error=str(e)
        )

@router.get("/configurations")
async def get_configurations():
    """Get LLM configurations"""
    try:
        configurations = await llm_processor.get_configurations()
        return {"configurations": configurations}
    except Exception as e:
        logger.error(f"Error getting configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/invalidate")
async def invalidate_cache():
    """Invalidate configuration cache"""
    try:
        llm_processor.invalidate_cache()
        return {"message": "Cache invalidated successfully"}
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Legacy compatibility endpoints
@router.get("/entity-extraction/{project_id}")
async def get_entity_extraction_llm(project_id: str):
    """Legacy endpoint: Get LLM for entity extraction"""
    try:
        llm = await llm_processor.get_llm_for_entity_extraction(project_id)
        return {
            "project_id": project_id,
            "process_type": "entity_extraction", 
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting entity extraction LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-assessment/{project_id}")
async def get_crew_assessment_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew assessment"""
    try:
        llm = await llm_processor.get_llm_for_crew_assessment(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_assessment",
            "llm_available": llm is not None,
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew assessment LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/crew-documentation/{project_id}")
async def get_crew_documentation_llm(project_id: str):
    """Legacy endpoint: Get LLM for crew documentation"""
    try:
        llm = await llm_processor.get_llm_for_crew_documentation(project_id)
        return {
            "project_id": project_id,
            "process_type": "crew_documentation",
            "llm_available": llm is not None, 
            "llm_type": str(type(llm).__name__) if llm else None
        }
    except Exception as e:
        logger.error(f"Error getting crew documentation LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
