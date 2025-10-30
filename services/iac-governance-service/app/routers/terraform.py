"""
Terraform Router

FastAPI endpoints for Terraform operations through MCP integration.
Provides plan, apply, validate, destroy, workspace, and state management.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.adapters import TerraformMCPAdapter
from app.repository import TerraformRepository
from app.models import TerraformExecutionType, TerraformExecutionStatus

logger = logging.getLogger("terraform-router")

router = APIRouter(prefix="/terraform", tags=["terraform"])


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class TerraformPlanRequest(BaseModel):
    """Request model for Terraform plan operation."""
    project_id: UUID = Field(..., description="Project UUID")
    workspace_path: str = Field(..., description="Path to Terraform workspace")
    workspace_name: Optional[str] = Field(None, description="Terraform workspace name")
    var_file: Optional[str] = Field(None, description="Path to variables file")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variable overrides")
    target_resources: Optional[List[str]] = Field(default_factory=list, description="Target resource addresses")
    destroy: bool = Field(default=False, description="Generate destroy plan")
    scan_id: Optional[UUID] = Field(None, description="Associated policy scan ID")
    triggered_by: Optional[str] = Field(None, description="User or service triggering the plan")


class TerraformApplyRequest(BaseModel):
    """Request model for Terraform apply operation."""
    project_id: UUID = Field(..., description="Project UUID")
    workspace_path: str = Field(..., description="Path to Terraform workspace")
    workspace_name: Optional[str] = Field(None, description="Terraform workspace name")
    plan_file: Optional[str] = Field(None, description="Path to plan file to apply")
    var_file: Optional[str] = Field(None, description="Path to variables file")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variable overrides")
    target_resources: Optional[List[str]] = Field(default_factory=list, description="Target resource addresses")
    auto_approve: bool = Field(default=False, description="Skip approval prompts")
    scan_id: Optional[UUID] = Field(None, description="Associated policy scan ID")
    triggered_by: Optional[str] = Field(None, description="User or service triggering the apply")


class TerraformValidateRequest(BaseModel):
    """Request model for Terraform validate operation."""
    project_id: UUID = Field(..., description="Project UUID")
    workspace_path: str = Field(..., description="Path to Terraform workspace")
    workspace_name: Optional[str] = Field(None, description="Terraform workspace name")
    triggered_by: Optional[str] = Field(None, description="User or service triggering the validation")


class TerraformDestroyRequest(BaseModel):
    """Request model for Terraform destroy operation."""
    project_id: UUID = Field(..., description="Project UUID")
    workspace_path: str = Field(..., description="Path to Terraform workspace")
    workspace_name: Optional[str] = Field(None, description="Terraform workspace name")
    var_file: Optional[str] = Field(None, description="Path to variables file")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variable overrides")
    target_resources: Optional[List[str]] = Field(default_factory=list, description="Target resource addresses")
    auto_approve: bool = Field(default=False, description="Skip approval prompts")
    scan_id: Optional[UUID] = Field(None, description="Associated policy scan ID")
    triggered_by: Optional[str] = Field(None, description="User or service triggering the destroy")


class WorkspaceListRequest(BaseModel):
    """Request model for workspace list operation."""
    workspace_path: str = Field(..., description="Path to Terraform workspace")


class StateShowRequest(BaseModel):
    """Request model for state show operation."""
    workspace_path: str = Field(..., description="Path to Terraform workspace")
    workspace_name: Optional[str] = Field(None, description="Terraform workspace name")
    resource_address: Optional[str] = Field(None, description="Specific resource address to show")


class TerraformExecutionResponse(BaseModel):
    """Response model for Terraform execution."""
    execution_id: UUID
    project_id: UUID
    execution_type: str
    status: str
    workspace_path: str
    workspace_name: Optional[str]
    plan_id: Optional[str]
    changes_summary: Optional[Dict[str, int]]
    resources_affected: Optional[List[str]]
    is_valid: Optional[bool]
    error_count: Optional[int]
    warning_count: Optional[int]
    duration_seconds: Optional[int]
    error_message: Optional[str]
    correlation_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Dependency Injection
# ============================================================================

def get_terraform_adapter() -> TerraformMCPAdapter:
    """Get Terraform MCP adapter instance."""
    return TerraformMCPAdapter()


def get_repository(db: Session = Depends(get_db_session)) -> TerraformRepository:
    """Get Terraform repository instance."""
    return TerraformRepository(db)


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/plan", response_model=TerraformExecutionResponse)
async def terraform_plan(
    request: TerraformPlanRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
    repo: TerraformRepository = Depends(get_repository),
):
    """
    Generate Terraform execution plan.
    
    Creates an execution record, generates plan via MCP, and stores results.
    Returns execution details with plan summary.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Starting Terraform plan for project {request.project_id} (correlation={correlation_id})")
    
    # Create execution record
    execution = repo.create_execution(
        project_id=request.project_id,
        scan_id=request.scan_id,
        execution_type=TerraformExecutionType.PLAN,
        workspace_path=request.workspace_path,
        workspace_name=request.workspace_name,
        var_file=request.var_file,
        variables=request.variables,
        target_resources=request.target_resources,
        correlation_id=correlation_id,
        triggered_by=request.triggered_by,
    )
    
    try:
        # Update status to in_progress
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        # Execute plan via MCP adapter
        plan_result = await adapter.plan(
            workspace_path=request.workspace_path,
            workspace_name=request.workspace_name,
            var_file=request.var_file,
            variables=request.variables,
            target_resources=request.target_resources,
            destroy=request.destroy,
            correlation_id=correlation_id,
        )
        
        # Update execution with results
        repo.update_execution_results(
            execution.execution_id,
            plan_id=plan_result.get("plan_id"),
            changes_summary=plan_result.get("changes_summary"),
            resources_affected=plan_result.get("resources"),
            output_text=plan_result.get("output"),
        )
        
        # Update status to completed
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            duration_seconds=plan_result.get("duration_seconds"),
        )
        
        # Create resource records if resources present
        if plan_result.get("resource_changes"):
            resource_data = [
                {
                    "resource_address": rc.get("address"),
                    "resource_type": rc.get("type"),
                    "resource_name": rc.get("name"),
                    "module_path": rc.get("module"),
                    "action": rc.get("action"),
                    "change_details": rc.get("change", {}),
                    "previous_state": rc.get("before"),
                    "new_state": rc.get("after"),
                    "provider": rc.get("provider_name"),
                }
                for rc in plan_result.get("resource_changes", [])
            ]
            repo.bulk_create_resources(execution.execution_id, resource_data)
        
        # Refresh and return
        execution = repo.get_execution(execution.execution_id)
        return TerraformExecutionResponse.from_orm(execution)
        
    except Exception as e:
        logger.error(f"Terraform plan failed: {str(e)}", exc_info=True)
        
        # Update execution with error
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=str(e),
            error_details={"exception": type(e).__name__},
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Terraform plan failed: {str(e)}"
        )


@router.post("/apply", response_model=TerraformExecutionResponse)
async def terraform_apply(
    request: TerraformApplyRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
    repo: TerraformRepository = Depends(get_repository),
):
    """
    Apply Terraform changes.
    
    Creates an execution record, applies changes via MCP, and stores results.
    Returns execution details with apply summary.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Starting Terraform apply for project {request.project_id} (correlation={correlation_id})")
    
    # Create execution record
    execution = repo.create_execution(
        project_id=request.project_id,
        scan_id=request.scan_id,
        execution_type=TerraformExecutionType.APPLY,
        workspace_path=request.workspace_path,
        workspace_name=request.workspace_name,
        var_file=request.var_file,
        variables=request.variables,
        target_resources=request.target_resources,
        auto_approve=request.auto_approve,
        correlation_id=correlation_id,
        triggered_by=request.triggered_by,
    )
    
    try:
        # Update status to in_progress
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        # Execute apply via MCP adapter
        apply_result = await adapter.apply(
            workspace_path=request.workspace_path,
            workspace_name=request.workspace_name,
            plan_file=request.plan_file,
            var_file=request.var_file,
            variables=request.variables,
            target_resources=request.target_resources,
            auto_approve=request.auto_approve,
            correlation_id=correlation_id,
        )
        
        # Update execution with results
        repo.update_execution_results(
            execution.execution_id,
            changes_summary=apply_result.get("changes_summary"),
            resources_affected=apply_result.get("resources"),
            output_text=apply_result.get("output"),
        )
        
        # Update status to completed
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            duration_seconds=apply_result.get("duration_seconds"),
        )
        
        # Create resource records if resources present
        if apply_result.get("resource_changes"):
            resource_data = [
                {
                    "resource_address": rc.get("address"),
                    "resource_type": rc.get("type"),
                    "resource_name": rc.get("name"),
                    "module_path": rc.get("module"),
                    "action": rc.get("action"),
                    "change_details": rc.get("change", {}),
                    "previous_state": rc.get("before"),
                    "new_state": rc.get("after"),
                    "provider": rc.get("provider_name"),
                }
                for rc in apply_result.get("resource_changes", [])
            ]
            repo.bulk_create_resources(execution.execution_id, resource_data)
        
        # Refresh and return
        execution = repo.get_execution(execution.execution_id)
        return TerraformExecutionResponse.from_orm(execution)
        
    except Exception as e:
        logger.error(f"Terraform apply failed: {str(e)}", exc_info=True)
        
        # Update execution with error
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=str(e),
            error_details={"exception": type(e).__name__},
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Terraform apply failed: {str(e)}"
        )


@router.post("/validate", response_model=TerraformExecutionResponse)
async def terraform_validate(
    request: TerraformValidateRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
    repo: TerraformRepository = Depends(get_repository),
):
    """
    Validate Terraform configuration.
    
    Creates an execution record, validates configuration via MCP, and stores results.
    Returns execution details with validation diagnostics.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Starting Terraform validate for project {request.project_id} (correlation={correlation_id})")
    
    # Create execution record
    execution = repo.create_execution(
        project_id=request.project_id,
        execution_type=TerraformExecutionType.VALIDATE,
        workspace_path=request.workspace_path,
        workspace_name=request.workspace_name,
        correlation_id=correlation_id,
        triggered_by=request.triggered_by,
    )
    
    try:
        # Update status to in_progress
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        # Execute validate via MCP adapter
        validate_result = await adapter.validate(
            workspace_path=request.workspace_path,
            workspace_name=request.workspace_name,
            correlation_id=correlation_id,
        )
        
        # Update execution with validation results
        repo.update_execution_results(
            execution.execution_id,
            is_valid=validate_result.get("valid", False),
            diagnostics=validate_result.get("diagnostics", []),
            error_count=validate_result.get("error_count", 0),
            warning_count=validate_result.get("warning_count", 0),
            output_text=validate_result.get("output"),
        )
        
        # Update status to completed
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
        
        # Refresh and return
        execution = repo.get_execution(execution.execution_id)
        return TerraformExecutionResponse.from_orm(execution)
        
    except Exception as e:
        logger.error(f"Terraform validate failed: {str(e)}", exc_info=True)
        
        # Update execution with error
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=str(e),
            error_details={"exception": type(e).__name__},
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Terraform validate failed: {str(e)}"
        )


@router.post("/destroy", response_model=TerraformExecutionResponse)
async def terraform_destroy(
    request: TerraformDestroyRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
    repo: TerraformRepository = Depends(get_repository),
):
    """
    Destroy Terraform infrastructure.
    
    Creates an execution record, destroys infrastructure via MCP, and stores results.
    Returns execution details with destroy summary.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Starting Terraform destroy for project {request.project_id} (correlation={correlation_id})")
    
    # Create execution record
    execution = repo.create_execution(
        project_id=request.project_id,
        scan_id=request.scan_id,
        execution_type=TerraformExecutionType.DESTROY,
        workspace_path=request.workspace_path,
        workspace_name=request.workspace_name,
        var_file=request.var_file,
        variables=request.variables,
        target_resources=request.target_resources,
        auto_approve=request.auto_approve,
        correlation_id=correlation_id,
        triggered_by=request.triggered_by,
    )
    
    try:
        # Update status to in_progress
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )
        
        # Execute destroy via MCP adapter
        destroy_result = await adapter.destroy(
            workspace_path=request.workspace_path,
            workspace_name=request.workspace_name,
            var_file=request.var_file,
            variables=request.variables,
            target_resources=request.target_resources,
            auto_approve=request.auto_approve,
            correlation_id=correlation_id,
        )
        
        # Update execution with results
        repo.update_execution_results(
            execution.execution_id,
            changes_summary=destroy_result.get("changes_summary"),
            resources_affected=destroy_result.get("resources"),
            output_text=destroy_result.get("output"),
        )
        
        # Update status to completed
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            duration_seconds=destroy_result.get("duration_seconds"),
        )
        
        # Create resource records if resources present
        if destroy_result.get("resource_changes"):
            resource_data = [
                {
                    "resource_address": rc.get("address"),
                    "resource_type": rc.get("type"),
                    "resource_name": rc.get("name"),
                    "module_path": rc.get("module"),
                    "action": "delete",  # All resources destroyed
                    "change_details": rc.get("change", {}),
                    "previous_state": rc.get("before"),
                    "provider": rc.get("provider_name"),
                }
                for rc in destroy_result.get("resource_changes", [])
            ]
            repo.bulk_create_resources(execution.execution_id, resource_data)
        
        # Refresh and return
        execution = repo.get_execution(execution.execution_id)
        return TerraformExecutionResponse.from_orm(execution)
        
    except Exception as e:
        logger.error(f"Terraform destroy failed: {str(e)}", exc_info=True)
        
        # Update execution with error
        repo.update_execution_status(
            execution.execution_id,
            TerraformExecutionStatus.FAILED,
            completed_at=datetime.utcnow(),
            error_message=str(e),
            error_details={"exception": type(e).__name__},
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Terraform destroy failed: {str(e)}"
        )


@router.post("/workspace/list")
async def list_workspaces(
    request: WorkspaceListRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
):
    """
    List Terraform workspaces.
    
    Returns list of workspaces and current workspace.
    Does not create execution record (read-only operation).
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Listing Terraform workspaces for {request.workspace_path} (correlation={correlation_id})")
    
    try:
        result = await adapter.list_workspaces(
            workspace_path=request.workspace_path,
            correlation_id=correlation_id,
        )
        
        return {
            "workspaces": result.get("workspaces", []),
            "current_workspace": result.get("current_workspace"),
        }
        
    except Exception as e:
        logger.error(f"List workspaces failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"List workspaces failed: {str(e)}"
        )


@router.post("/state/show")
async def show_state(
    request: StateShowRequest,
    x_correlation_id: Optional[str] = Header(None),
    adapter: TerraformMCPAdapter = Depends(get_terraform_adapter),
):
    """
    Show Terraform state.
    
    Returns state information for entire workspace or specific resource.
    Does not create execution record (read-only operation).
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Showing Terraform state for {request.workspace_path} (correlation={correlation_id})")
    
    try:
        result = await adapter.show_state(
            workspace_path=request.workspace_path,
            workspace_name=request.workspace_name,
            resource_address=request.resource_address,
            correlation_id=correlation_id,
        )
        
        return {
            "resources": result.get("resources", []),
            "outputs": result.get("outputs", {}),
            "resource_count": result.get("resource_count", 0),
        }
        
    except Exception as e:
        logger.error(f"Show state failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Show state failed: {str(e)}"
        )


@router.get("/executions/{project_id}")
async def list_executions(
    project_id: UUID,
    execution_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    repo: TerraformRepository = Depends(get_repository),
):
    """
    List Terraform executions for a project.
    
    Returns paginated list of executions with optional filters.
    """
    try:
        # Convert string parameters to enums if provided
        type_filter = None
        if execution_type:
            type_filter = TerraformExecutionType[execution_type.upper()]
        
        status_filter = None
        if status:
            status_filter = TerraformExecutionStatus[status.upper()]
        
        executions = repo.list_executions_by_project(
            project_id=project_id,
            execution_type=type_filter,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        
        return {
            "executions": [TerraformExecutionResponse.from_orm(e) for e in executions],
            "total": len(executions),
            "limit": limit,
            "offset": offset,
        }
        
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filter value: {str(e)}"
        )
    except Exception as e:
        logger.error(f"List executions failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"List executions failed: {str(e)}"
        )


@router.get("/executions/{execution_id}/resources")
async def list_execution_resources(
    execution_id: UUID,
    repo: TerraformRepository = Depends(get_repository),
):
    """
    List resources for a Terraform execution.
    
    Returns all resources affected by the execution with change details.
    """
    try:
        resources = repo.get_resources_by_execution(execution_id)
        
        return {
            "execution_id": execution_id,
            "resources": [
                {
                    "resource_id": r.resource_id,
                    "resource_address": r.resource_address,
                    "resource_type": r.resource_type,
                    "resource_name": r.resource_name,
                    "module_path": r.module_path,
                    "action": r.action,
                    "provider": r.provider,
                    "change_details": r.change_details,
                    "created_at": r.created_at,
                }
                for r in resources
            ],
            "total": len(resources),
        }
        
    except Exception as e:
        logger.error(f"List execution resources failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"List execution resources failed: {str(e)}"
        )
