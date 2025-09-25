"""Fusion API Router

Runs the fusion orchestrator to consolidate entities & relationships.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
import logging

from ..core.fusion_orchestrator import get_fusion_orchestrator

logger = logging.getLogger("document-service.router.fusion")

router = APIRouter(prefix="/fusion", tags=["fusion"])


class FusionRunRequest(BaseModel):
    similarity_threshold: float = Field(0.82, ge=0.5, le=0.99)
    max_cards: int = Field(3000, ge=50, le=20000)
    include_singletons: bool = True


class FusionRunResponse(BaseModel):
    status: str
    fusion_run_id: Optional[str] = None
    project_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    persistence: Optional[Dict[str, Any]] = None
    vector_upsert: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[float] = None
    # Previews
    canonical_entities: Optional[list] = None
    canonical_relationships: Optional[list] = None
    entity_mapping_preview: Optional[Dict[str, str]] = None
    relationship_mapping_preview: Optional[Dict[str, str]] = None


@router.post("/projects/{project_id}/run", response_model=FusionRunResponse)
async def run_fusion(project_id: str, request: FusionRunRequest):
    if os.getenv("FUSION_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Fusion feature disabled. Set FUSION_ENABLED=true to enable.")
    try:
        orchestrator = get_fusion_orchestrator()
        result = await orchestrator.run_fusion(
            project_id=project_id,
            threshold=request.similarity_threshold,
            max_cards=request.max_cards,
            include_singletons=request.include_singletons,
        )
        return FusionRunResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fusion run failed for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Fusion run failed: {str(e)}")
