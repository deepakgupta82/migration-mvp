"""Remediation API router for managing remediation actions."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.database import RemediationStatus
from app.repository.remediation_repository import RemediationRepository
from app.repository.scan_repository import ScanRepository
from app.services.remediation_executor import RemediationExecutor, RemediationExecutionError
from app.adapters.terraform_mcp_adapter import TerraformMCPAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remediations", tags=["Remediation"])


# Pydantic Models

class RemediationActionCreate(BaseModel):
    """Request model for creating a remediation action."""
    violation_id: UUID = Field(..., description="ID of the violation to remediate")
    action_type: str = Field(..., description="Type of action (auto_fix, manual_fix, suppress, ignore)")
    action_name: str = Field(..., description="Name of the remediation action")
    action_description: Optional[str] = Field(None, description="Description of the action")
    remediation_method: str = Field(..., description="Method to apply remediation")
    remediation_code: Optional[str] = Field(None, description="Code/script to apply fix")
    remediation_params: Optional[dict] = Field(default_factory=dict, description="Parameters for remediation")
    requires_approval: bool = Field(False, description="Whether action requires approval")


class RemediationActionResponse(BaseModel):
    """Response model for remediation action."""
    action_id: UUID
    violation_id: UUID
    action_type: str
    action_name: str
    action_description: Optional[str]
    remediation_method: str
    remediation_code: Optional[str]
    remediation_params: dict
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[int]
    is_successful: Optional[bool]
    result: Optional[dict]
    error_message: Optional[str]
    requires_approval: bool
    approved_by: Optional[str]
    approved_at: Optional[str]
    approval_notes: Optional[str]
    triggered_by: Optional[str]
    correlation_id: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class RemediationActionListResponse(BaseModel):
    """Response model for list of remediation actions."""
    actions: List[RemediationActionResponse]
    total: int
    limit: int
    offset: int


class RemediationExecutionRequest(BaseModel):
    """Request model for executing a remediation action."""
    pass  # No additional fields needed


class RemediationApprovalRequest(BaseModel):
    """Request model for approving a remediation action."""
    approval_notes: Optional[str] = Field(None, description="Notes for the approval")


class AutoRemediationRequest(BaseModel):
    """Request model for auto-remediation."""
    violation_id: UUID = Field(..., description="ID of the violation to remediate")


class RemediationStatisticsResponse(BaseModel):
    """Response model for remediation statistics."""
    total_actions: int
    pending: int
    in_progress: int
    completed: int
    failed: int
    successful: int
    success_rate: float
    pending_approvals: int


# Dependency injection

def get_remediation_repo(db: AsyncSession = Depends(get_db)) -> RemediationRepository:
    """Get remediation repository instance."""
    return RemediationRepository(db)


def get_scan_repo(db: AsyncSession = Depends(get_db)) -> ScanRepository:
    """Get scan repository instance."""
    return ScanRepository(db)


def get_terraform_adapter() -> TerraformMCPAdapter:
    """Get Terraform MCP adapter instance."""
    return TerraformMCPAdapter()


def get_remediation_executor(
    remediation_repo: RemediationRepository = Depends(get_remediation_repo),
    scan_repo: ScanRepository = Depends(get_scan_repo),
    terraform_adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
) -> RemediationExecutor:
    """Get remediation executor instance."""
    return RemediationExecutor(remediation_repo, scan_repo, terraform_adapter)


# API Endpoints

@router.post("", response_model=RemediationActionResponse, status_code=201)
async def create_remediation_action(
    request: RemediationActionCreate,
    repo: RemediationRepository = Depends(get_remediation_repo),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Create a new remediation action.
    
    Args:
        request: Remediation action creation request
        repo: Remediation repository
        x_correlation_id: Correlation ID for tracing
        x_user_id: User ID from header
        
    Returns:
        Created remediation action
    """
    logger.info(f"Creating remediation action for violation {request.violation_id}")
    
    try:
        action = await repo.create_action(
            violation_id=request.violation_id,
            action_type=request.action_type,
            action_name=request.action_name,
            action_description=request.action_description,
            remediation_method=request.remediation_method,
            remediation_code=request.remediation_code,
            remediation_params=request.remediation_params,
            requires_approval=request.requires_approval,
            triggered_by=x_user_id,
            correlation_id=x_correlation_id,
        )
        
        return action
        
    except Exception as e:
        logger.error(f"Failed to create remediation action: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create remediation action: {str(e)}")


@router.get("/{action_id}", response_model=RemediationActionResponse)
async def get_remediation_action(
    action_id: UUID,
    repo: RemediationRepository = Depends(get_remediation_repo),
):
    """
    Get a remediation action by ID.
    
    Args:
        action_id: UUID of the remediation action
        repo: Remediation repository
        
    Returns:
        Remediation action details
    """
    action = await repo.get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Remediation action {action_id} not found")
    
    return action


@router.get("", response_model=RemediationActionListResponse)
async def list_remediation_actions(
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    requires_approval: Optional[bool] = None,
    is_successful: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    repo: RemediationRepository = Depends(get_remediation_repo),
):
    """
    List remediation actions with optional filters.
    
    Args:
        status: Filter by status
        action_type: Filter by action type
        requires_approval: Filter by approval requirement
        is_successful: Filter by success status
        limit: Maximum number of results
        offset: Number of results to skip
        repo: Remediation repository
        
    Returns:
        List of remediation actions
    """
    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = RemediationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    actions = await repo.list_actions(
        status=status_enum,
        action_type=action_type,
        requires_approval=requires_approval,
        is_successful=is_successful,
        limit=limit,
        offset=offset,
    )
    
    total = await repo.count_actions(
        status=status_enum,
        action_type=action_type,
        requires_approval=requires_approval,
        is_successful=is_successful,
    )
    
    return RemediationActionListResponse(
        actions=actions,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{action_id}/execute", response_model=dict)
async def execute_remediation_action(
    action_id: UUID,
    background_tasks: BackgroundTasks,
    executor: RemediationExecutor = Depends(get_remediation_executor),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Execute a remediation action.
    
    Args:
        action_id: UUID of the remediation action
        background_tasks: FastAPI background tasks
        executor: Remediation executor
        x_correlation_id: Correlation ID for tracing
        
    Returns:
        Execution status
    """
    logger.info(f"Queuing remediation action {action_id} for execution")
    
    # Execute in background
    background_tasks.add_task(
        executor.execute_remediation,
        action_id=action_id,
        correlation_id=x_correlation_id,
    )
    
    return {
        "action_id": str(action_id),
        "status": "queued",
        "message": "Remediation action queued for execution",
    }


@router.post("/{action_id}/approve", response_model=RemediationActionResponse)
async def approve_remediation_action(
    action_id: UUID,
    request: RemediationApprovalRequest,
    repo: RemediationRepository = Depends(get_remediation_repo),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Approve a remediation action.
    
    Args:
        action_id: UUID of the remediation action
        request: Approval request
        repo: Remediation repository
        x_user_id: User ID from header
        
    Returns:
        Updated remediation action
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required for approval")
    
    action = await repo.approve_action(
        action_id=action_id,
        approved_by=x_user_id,
        approval_notes=request.approval_notes,
    )
    
    if not action:
        raise HTTPException(status_code=404, detail=f"Remediation action {action_id} not found")
    
    return action


@router.get("/violation/{violation_id}", response_model=RemediationActionListResponse)
async def get_remediation_actions_by_violation(
    violation_id: UUID,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    repo: RemediationRepository = Depends(get_remediation_repo),
):
    """
    Get remediation actions for a specific violation.
    
    Args:
        violation_id: UUID of the violation
        status: Optional status filter
        limit: Maximum number of results
        offset: Number of results to skip
        repo: Remediation repository
        
    Returns:
        List of remediation actions
    """
    # Convert status string to enum if provided
    status_enum = None
    if status:
        try:
            status_enum = RemediationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    actions = await repo.get_actions_by_violation(
        violation_id=violation_id,
        status=status_enum,
        limit=limit,
        offset=offset,
    )
    
    total = len(actions)  # Simple count for now
    
    return RemediationActionListResponse(
        actions=actions,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/auto-remediate", response_model=dict)
async def create_auto_remediation(
    request: AutoRemediationRequest,
    background_tasks: BackgroundTasks,
    executor: RemediationExecutor = Depends(get_remediation_executor),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Create and execute auto-remediation for a violation.
    
    Args:
        request: Auto-remediation request
        background_tasks: FastAPI background tasks
        executor: Remediation executor
        x_correlation_id: Correlation ID for tracing
        x_user_id: User ID from header
        
    Returns:
        Auto-remediation result
    """
    logger.info(f"Creating auto-remediation for violation {request.violation_id}")
    
    try:
        # Execute auto-remediation in background
        background_tasks.add_task(
            executor.create_auto_remediation,
            violation_id=request.violation_id,
            triggered_by=x_user_id or "system",
            correlation_id=x_correlation_id,
        )
        
        return {
            "violation_id": str(request.violation_id),
            "status": "queued",
            "message": "Auto-remediation queued for execution",
        }
        
    except RemediationExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create auto-remediation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create auto-remediation: {str(e)}")


@router.get("/stats/summary", response_model=RemediationStatisticsResponse)
async def get_remediation_statistics(
    repo: RemediationRepository = Depends(get_remediation_repo),
):
    """
    Get remediation statistics.
    
    Args:
        repo: Remediation repository
        
    Returns:
        Remediation statistics
    """
    stats = await repo.get_statistics()
    return RemediationStatisticsResponse(**stats)


@router.get("/approvals/pending", response_model=RemediationActionListResponse)
async def get_pending_approvals(
    limit: int = 100,
    offset: int = 0,
    repo: RemediationRepository = Depends(get_remediation_repo),
):
    """
    Get remediation actions pending approval.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        repo: Remediation repository
        
    Returns:
        List of actions pending approval
    """
    actions = await repo.get_pending_approvals(limit=limit, offset=offset)
    total = len(actions)  # Simple count for now
    
    return RemediationActionListResponse(
        actions=actions,
        total=total,
        limit=limit,
        offset=offset,
    )
