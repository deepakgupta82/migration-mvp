"""
Wave Management API Router
Endpoints for migration wave CRUD operations and execution.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repository.wave_repository import WaveRepository
from app.services.migration_executor import MigrationExecutor
from app.adapters.aws_mcp_adapter import AWSMCPAdapter
from common.mcp import MCPClient
from app.core.config import config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/waves",
    tags=["Migration Waves"]
)


# ============================================================================
# Request/Response Models
# ============================================================================

class WaveCreateRequest(BaseModel):
    """Request to create migration wave."""
    project_id: UUID = Field(..., description="Project UUID")
    wave_name: str = Field(..., min_length=1, max_length=255, description="Wave name")
    wave_description: Optional[str] = Field(None, description="Wave description")
    target_cloud: str = Field("aws", pattern="^(aws|azure|gcp)$", description="Target cloud provider")
    target_region: str = Field(..., description="Target cloud region")
    wave_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class WaveUpdateRequest(BaseModel):
    """Request to update migration wave."""
    wave_name: Optional[str] = Field(None, min_length=1, max_length=255)
    wave_description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|validated|invalid|running|completed|failed)$")
    target_region: Optional[str] = None
    wave_metadata: Optional[Dict[str, Any]] = None


class WaveResponse(BaseModel):
    """Migration wave response."""
    wave_id: UUID
    project_id: UUID
    wave_name: str
    wave_description: Optional[str]
    target_cloud: str
    target_region: str
    status: str
    wave_metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class ResourceCreateRequest(BaseModel):
    """Request to add resource to wave."""
    resource_name: str = Field(..., min_length=1, max_length=255)
    resource_type: str = Field(..., pattern="^(server|database|storage|application)$")
    source_config: Dict[str, Any] = Field(..., description="Source resource configuration")
    target_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Target configuration")
    resource_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ResourceResponse(BaseModel):
    """Migration resource response."""
    resource_id: UUID
    wave_id: UUID
    resource_name: str
    resource_type: str
    source_config: Dict[str, Any]
    target_config: Dict[str, Any]
    status: str
    error_message: Optional[str]
    resource_metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class WaveExecuteRequest(BaseModel):
    """Request to execute migration wave."""
    execution_mode: str = Field("sequential", pattern="^(sequential|parallel)$")


class WaveExecuteResponse(BaseModel):
    """Wave execution response."""
    wave_id: str
    wave_name: str
    status: str
    total_resources: int
    successful: int
    failed: int
    execution_mode: str
    results: List[Dict[str, Any]]


class ValidationResponse(BaseModel):
    """Wave validation response."""
    wave_id: str
    wave_name: str
    is_valid: bool
    total_resources: int
    errors: List[str]
    warnings: List[str]


# ============================================================================
# Dependency Injection
# ============================================================================

def get_correlation_id(
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID")
) -> Optional[str]:
    """Extract correlation ID from request headers."""
    return x_correlation_id


def get_wave_repository(db: Session = Depends(get_db_session)) -> WaveRepository:
    """Get wave repository instance."""
    return WaveRepository(db)


def get_mcp_client() -> MCPClient:
    """Get MCP client instance."""
    return MCPClient(
        base_url=config.MCP_CONTROL_PLANE_URL,
        auth_token=config.MCP_SERVICE_TOKEN
    )


def get_aws_adapter(
    mcp_client: MCPClient = Depends(get_mcp_client)
) -> AWSMCPAdapter:
    """Get AWS MCP adapter instance."""
    return AWSMCPAdapter(mcp_client=mcp_client)


def get_migration_executor(
    db: Session = Depends(get_db_session),
    aws_adapter: AWSMCPAdapter = Depends(get_aws_adapter),
    correlation_id: Optional[str] = Depends(get_correlation_id)
) -> MigrationExecutor:
    """Get migration executor instance."""
    return MigrationExecutor(
        db_session=db,
        aws_adapter=aws_adapter,
        correlation_id=correlation_id
    )


# ============================================================================
# Wave CRUD Endpoints
# ============================================================================

@router.post("", response_model=WaveResponse, status_code=status.HTTP_201_CREATED)
async def create_wave(
    request: WaveCreateRequest,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Create a new migration wave.
    
    - **project_id**: Project UUID
    - **wave_name**: Descriptive name for the wave
    - **target_cloud**: Target cloud provider (aws, azure, gcp)
    - **target_region**: Target cloud region
    """
    try:
        logger.info(
            f"Creating migration wave: {request.wave_name}",
            extra={"correlation_id": correlation_id}
        )
        
        wave = repository.create_wave(
            project_id=request.project_id,
            wave_name=request.wave_name,
            wave_description=request.wave_description,
            target_cloud=request.target_cloud,
            target_region=request.target_region,
            wave_metadata=request.wave_metadata
        )
        
        return WaveResponse.model_validate(wave)
        
    except ValueError as e:
        logger.error(f"Wave creation failed: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating wave: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=List[WaveResponse])
async def list_waves(
    project_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    target_cloud: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    List migration waves with optional filters.
    
    - **project_id**: Filter by project UUID
    - **status_filter**: Filter by wave status
    - **target_cloud**: Filter by target cloud provider
    - **limit**: Maximum results (default 100)
    - **offset**: Pagination offset (default 0)
    """
    try:
        logger.debug(
            f"Listing waves: project_id={project_id}, status={status_filter}",
            extra={"correlation_id": correlation_id}
        )
        
        waves = repository.list_waves(
            project_id=project_id,
            status=status_filter,
            target_cloud=target_cloud,
            limit=limit,
            offset=offset
        )
        
        return [WaveResponse.model_validate(wave) for wave in waves]
        
    except Exception as e:
        logger.error(f"Failed to list waves: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{wave_id}", response_model=WaveResponse)
async def get_wave(
    wave_id: UUID,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Get migration wave by ID.
    
    - **wave_id**: Wave UUID
    """
    try:
        logger.debug(f"Getting wave: {wave_id}", extra={"correlation_id": correlation_id})
        
        wave = repository.get_wave(wave_id)
        if not wave:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wave not found: {wave_id}"
            )
        
        return WaveResponse.model_validate(wave)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wave {wave_id}: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{wave_id}", response_model=WaveResponse)
async def update_wave(
    wave_id: UUID,
    request: WaveUpdateRequest,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Update migration wave.
    
    - **wave_id**: Wave UUID
    - **wave_name**: New wave name (optional)
    - **status**: New status (optional)
    - **wave_description**: New description (optional)
    """
    try:
        logger.info(f"Updating wave: {wave_id}", extra={"correlation_id": correlation_id})
        
        wave = repository.update_wave(
            wave_id=wave_id,
            wave_name=request.wave_name,
            wave_description=request.wave_description,
            status=request.status,
            target_region=request.target_region,
            wave_metadata=request.wave_metadata
        )
        
        if not wave:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wave not found: {wave_id}"
            )
        
        return WaveResponse.model_validate(wave)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update wave {wave_id}: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{wave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wave(
    wave_id: UUID,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Delete migration wave and all associated resources/tasks.
    
    - **wave_id**: Wave UUID
    """
    try:
        logger.info(f"Deleting wave: {wave_id}", extra={"correlation_id": correlation_id})
        
        deleted = repository.delete_wave(wave_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wave not found: {wave_id}"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete wave {wave_id}: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# Resource Management Endpoints
# ============================================================================

@router.post("/{wave_id}/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def add_resource_to_wave(
    wave_id: UUID,
    request: ResourceCreateRequest,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Add migration resource to wave.
    
    - **wave_id**: Wave UUID
    - **resource_name**: Resource name
    - **resource_type**: Resource type (server, database, storage, application)
    - **source_config**: Source configuration JSON
    - **target_config**: Target configuration JSON (optional)
    """
    try:
        logger.info(
            f"Adding resource to wave {wave_id}: {request.resource_name}",
            extra={"correlation_id": correlation_id}
        )
        
        resource = repository.add_resource_to_wave(
            wave_id=wave_id,
            resource_name=request.resource_name,
            resource_type=request.resource_type,
            source_config=request.source_config,
            target_config=request.target_config,
            resource_metadata=request.resource_metadata
        )
        
        return ResourceResponse.model_validate(resource)
        
    except ValueError as e:
        logger.error(f"Resource creation failed: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error adding resource: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{wave_id}/resources", response_model=List[ResourceResponse])
async def list_wave_resources(
    wave_id: UUID,
    resource_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    repository: WaveRepository = Depends(get_wave_repository),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    List resources in a wave.
    
    - **wave_id**: Wave UUID
    - **resource_type**: Filter by resource type (optional)
    - **status_filter**: Filter by status (optional)
    """
    try:
        logger.debug(
            f"Listing resources for wave {wave_id}",
            extra={"correlation_id": correlation_id}
        )
        
        resources = repository.list_wave_resources(
            wave_id=wave_id,
            resource_type=resource_type,
            status=status_filter
        )
        
        return [ResourceResponse.model_validate(resource) for resource in resources]
        
    except Exception as e:
        logger.error(f"Failed to list resources: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ============================================================================
# Wave Execution Endpoints
# ============================================================================

@router.post("/{wave_id}/validate", response_model=ValidationResponse)
async def validate_wave(
    wave_id: UUID,
    executor: MigrationExecutor = Depends(get_migration_executor),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Validate wave is ready for execution.
    
    - **wave_id**: Wave UUID
    
    Returns validation errors and warnings.
    """
    try:
        logger.info(f"Validating wave: {wave_id}", extra={"correlation_id": correlation_id})
        
        result = await executor.validate_wave(wave_id)
        
        return ValidationResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation failed: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error validating wave: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{wave_id}/execute", response_model=WaveExecuteResponse)
async def execute_wave(
    wave_id: UUID,
    request: WaveExecuteRequest,
    executor: MigrationExecutor = Depends(get_migration_executor),
    correlation_id: Optional[str] = Depends(get_correlation_id)
):
    """
    Execute migration wave.
    
    - **wave_id**: Wave UUID
    - **execution_mode**: Execution mode (sequential or parallel)
    
    Executes all resources in the wave using configured MCP adapters.
    """
    try:
        logger.info(
            f"Executing wave {wave_id} in {request.execution_mode} mode",
            extra={"correlation_id": correlation_id}
        )
        
        result = await executor.execute_wave(
            wave_id=wave_id,
            execution_mode=request.execution_mode
        )
        
        return WaveExecuteResponse(**result)
        
    except ValueError as e:
        logger.error(f"Execution failed: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error executing wave: {e}", extra={"correlation_id": correlation_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
