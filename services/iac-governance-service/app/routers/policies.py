"""
Policy Router

FastAPI endpoints for policy template management.
Provides CRUD operations for policy templates.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repository import PolicyRepository
from app.models import PolicySeverity

logger = logging.getLogger("policy-router")

router = APIRouter(prefix="/policies", tags=["policies"])


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class PolicyTemplateCreate(BaseModel):
    """Request model for creating policy template."""
    template_name: str = Field(..., description="Name of the policy template", min_length=1, max_length=255)
    template_description: Optional[str] = Field(None, description="Description of the policy")
    policy_category: str = Field(..., description="Category (security, compliance, cost, etc.)", min_length=1)
    severity: str = Field(..., description="Severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO)")
    engine_type: str = Field(default="opa", description="Policy engine type")
    policy_code: str = Field(..., description="Policy code (Rego for OPA)", min_length=1)
    supported_frameworks: List[str] = Field(..., description="Supported IaC frameworks", min_items=1)
    cloud_providers: List[str] = Field(..., description="Supported cloud providers", min_items=1)
    is_active: bool = Field(default=True, description="Whether policy is active")
    is_blocking: bool = Field(default=False, description="Whether policy blocks deployments")
    auto_remediate: bool = Field(default=False, description="Whether to auto-remediate violations")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    policy_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('severity')
    def validate_severity(cls, v):
        """Validate severity is a valid enum value."""
        try:
            PolicySeverity[v.upper()]
            return v.upper()
        except KeyError:
            raise ValueError(f"Invalid severity. Must be one of: {[s.name for s in PolicySeverity]}")


class PolicyTemplateUpdate(BaseModel):
    """Request model for updating policy template."""
    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    template_description: Optional[str] = None
    policy_category: Optional[str] = Field(None, min_length=1)
    severity: Optional[str] = None
    policy_code: Optional[str] = Field(None, min_length=1)
    supported_frameworks: Optional[List[str]] = Field(None, min_items=1)
    cloud_providers: Optional[List[str]] = Field(None, min_items=1)
    is_active: Optional[bool] = None
    is_blocking: Optional[bool] = None
    auto_remediate: Optional[bool] = None
    tags: Optional[List[str]] = None
    policy_metadata: Optional[Dict[str, Any]] = None
    
    @validator('severity')
    def validate_severity(cls, v):
        """Validate severity is a valid enum value."""
        if v is None:
            return v
        try:
            PolicySeverity[v.upper()]
            return v.upper()
        except KeyError:
            raise ValueError(f"Invalid severity. Must be one of: {[s.name for s in PolicySeverity]}")


class PolicyTemplateResponse(BaseModel):
    """Response model for policy template."""
    template_id: UUID
    template_name: str
    template_description: Optional[str]
    policy_category: str
    severity: str
    engine_type: str
    policy_code: str
    supported_frameworks: List[str]
    cloud_providers: List[str]
    is_active: bool
    is_blocking: bool
    auto_remediate: bool
    tags: List[str]
    policy_metadata: Dict[str, Any]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PolicyListResponse(BaseModel):
    """Response model for policy list."""
    policies: List[PolicyTemplateResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Dependency Injection
# ============================================================================

def get_repository(db: Session = Depends(get_db_session)) -> PolicyRepository:
    """Get policy repository instance."""
    return PolicyRepository(db)


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("", response_model=PolicyTemplateResponse, status_code=201)
async def create_policy(
    request: PolicyTemplateCreate,
    x_correlation_id: Optional[str] = Header(None),
    triggered_by: Optional[str] = Header(None, alias="X-User-ID"),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Create new policy template.
    
    Creates a policy template that can be used for IAC scanning.
    """
    logger.info(f"Creating policy template: {request.template_name}")
    
    try:
        # Check if policy with same name exists
        existing = repo.get_policy_by_name(request.template_name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Policy template with name '{request.template_name}' already exists"
            )
        
        # Create policy
        policy = repo.create_policy(
            template_name=request.template_name,
            template_description=request.template_description,
            policy_category=request.policy_category,
            severity=PolicySeverity[request.severity],
            engine_type=request.engine_type,
            policy_code=request.policy_code,
            supported_frameworks=request.supported_frameworks,
            cloud_providers=request.cloud_providers,
            is_active=request.is_active,
            is_blocking=request.is_blocking,
            auto_remediate=request.auto_remediate,
            tags=request.tags,
            policy_metadata=request.policy_metadata,
            created_by=triggered_by,
        )
        
        return PolicyTemplateResponse.from_orm(policy)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create policy: {str(e)}")


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    category: Optional[str] = Query(None, description="Filter by policy category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_blocking: Optional[bool] = Query(None, description="Filter by blocking status"),
    cloud_provider: Optional[str] = Query(None, description="Filter by cloud provider"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    List policy templates with optional filters.
    
    Returns paginated list of policy templates.
    """
    logger.info(f"Listing policies (limit={limit}, offset={offset})")
    
    try:
        # Parse severity if provided
        severity_enum = None
        if severity:
            try:
                severity_enum = PolicySeverity[severity.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid severity. Must be one of: {[s.name for s in PolicySeverity]}"
                )
        
        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        
        # Get policies
        policies = repo.list_policies(
            policy_category=category,
            severity=severity_enum,
            is_active=is_active,
            is_blocking=is_blocking,
            cloud_provider=cloud_provider,
            framework=framework,
            tags=tag_list,
            limit=limit,
            offset=offset,
        )
        
        return PolicyListResponse(
            policies=[PolicyTemplateResponse.from_orm(p) for p in policies],
            total=len(policies),
            limit=limit,
            offset=offset,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing policies: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list policies: {str(e)}")


@router.get("/{template_id}", response_model=PolicyTemplateResponse)
async def get_policy(
    template_id: UUID,
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Get policy template by ID.
    
    Returns details of a specific policy template.
    """
    logger.info(f"Getting policy template: {template_id}")
    
    try:
        policy = repo.get_policy(template_id)
        
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy template {template_id} not found"
            )
        
        return PolicyTemplateResponse.from_orm(policy)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get policy: {str(e)}")


@router.put("/{template_id}", response_model=PolicyTemplateResponse)
async def update_policy(
    template_id: UUID,
    request: PolicyTemplateUpdate,
    x_correlation_id: Optional[str] = Header(None),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Update policy template.
    
    Updates specified fields of a policy template.
    """
    logger.info(f"Updating policy template: {template_id}")
    
    try:
        # Convert severity if provided
        update_data = request.dict(exclude_unset=True)
        if 'severity' in update_data and update_data['severity']:
            update_data['severity'] = PolicySeverity[update_data['severity']]
        
        # Update policy
        policy = repo.update_policy(template_id, **update_data)
        
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy template {template_id} not found"
            )
        
        return PolicyTemplateResponse.from_orm(policy)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update policy: {str(e)}")


@router.delete("/{template_id}", status_code=204)
async def delete_policy(
    template_id: UUID,
    x_correlation_id: Optional[str] = Header(None),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Delete policy template.
    
    Permanently deletes a policy template.
    """
    logger.info(f"Deleting policy template: {template_id}")
    
    try:
        success = repo.delete_policy(template_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Policy template {template_id} not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete policy: {str(e)}")


@router.post("/{template_id}/activate", response_model=PolicyTemplateResponse)
async def activate_policy(
    template_id: UUID,
    x_correlation_id: Optional[str] = Header(None),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Activate policy template.
    
    Makes a policy active for use in scans.
    """
    logger.info(f"Activating policy template: {template_id}")
    
    try:
        policy = repo.activate_policy(template_id)
        
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy template {template_id} not found"
            )
        
        return PolicyTemplateResponse.from_orm(policy)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to activate policy: {str(e)}")


@router.post("/{template_id}/deactivate", response_model=PolicyTemplateResponse)
async def deactivate_policy(
    template_id: UUID,
    x_correlation_id: Optional[str] = Header(None),
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Deactivate policy template.
    
    Makes a policy inactive, excluding it from scans.
    """
    logger.info(f"Deactivating policy template: {template_id}")
    
    try:
        policy = repo.deactivate_policy(template_id)
        
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy template {template_id} not found"
            )
        
        return PolicyTemplateResponse.from_orm(policy)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating policy: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to deactivate policy: {str(e)}")


@router.get("/stats/summary")
async def get_policy_stats(
    repo: PolicyRepository = Depends(get_repository),
):
    """
    Get policy statistics summary.
    
    Returns counts and metrics about policies.
    """
    logger.info("Getting policy statistics")
    
    try:
        total = repo.count_policies()
        active = repo.count_policies(is_active=True)
        inactive = repo.count_policies(is_active=False)
        
        return {
            "total_policies": total,
            "active_policies": active,
            "inactive_policies": inactive,
        }
        
    except Exception as e:
        logger.error(f"Error getting policy stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get policy stats: {str(e)}")
