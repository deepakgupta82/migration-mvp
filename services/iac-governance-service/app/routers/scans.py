"""
Scan Router

FastAPI endpoints for policy scan management and execution.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Header, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repository import ScanRepository
from app.services import ScanExecutor
from app.models import ScanStatus, PolicySeverity

logger = logging.getLogger("scan-router")

router = APIRouter(prefix="/scans", tags=["scans"])


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class ScanCreate(BaseModel):
    """Request model for creating scan."""
    project_id: UUID = Field(..., description="Project UUID")
    scan_name: str = Field(..., description="Name of the scan", min_length=1)
    scan_description: Optional[str] = Field(None, description="Description of the scan")
    iac_framework: str = Field(..., description="IaC framework (terraform, cloudformation, etc.)")
    iac_version: Optional[str] = Field(None, description="IaC version")
    source_type: str = Field(..., description="Source type (git, local, etc.)")
    source_location: str = Field(..., description="Source location/path")
    source_branch: Optional[str] = Field(None, description="Git branch")
    source_commit: Optional[str] = Field(None, description="Git commit")
    template_id: Optional[UUID] = Field(None, description="Policy template ID to use")
    scan_config: Dict[str, Any] = Field(default_factory=dict, description="Scan configuration")
    auto_execute: bool = Field(default=True, description="Automatically execute scan after creation")


class ScanResponse(BaseModel):
    """Response model for scan."""
    scan_id: UUID
    template_id: Optional[UUID]
    project_id: UUID
    scan_name: str
    scan_description: Optional[str]
    iac_framework: str
    iac_version: Optional[str]
    source_type: str
    source_location: str
    source_branch: Optional[str]
    source_commit: Optional[str]
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    total_resources: int
    passed_checks: int
    failed_checks: int
    violations_critical: int
    violations_high: int
    violations_medium: int
    violations_low: int
    violations_info: int
    error_message: Optional[str]
    correlation_id: Optional[str]
    triggered_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ViolationResponse(BaseModel):
    """Response model for violation."""
    violation_id: UUID
    scan_id: UUID
    template_id: Optional[UUID]
    violation_rule: str
    severity: str
    resource_type: str
    resource_name: str
    resource_identifier: str
    file_path: Optional[str]
    line_number: Optional[int]
    violation_message: str
    violation_details: Dict[str, Any]
    recommended_fix: Optional[str]
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ViolationListResponse(BaseModel):
    """Response model for violation list."""
    scan_id: UUID
    violations: List[ViolationResponse]
    total: int
    by_severity: Dict[str, int]


# ============================================================================
# Dependency Injection
# ============================================================================

def get_scan_repository(db: Session = Depends(get_db_session)) -> ScanRepository:
    """Get scan repository instance."""
    return ScanRepository(db)


def get_scan_executor(db: Session = Depends(get_db_session)) -> ScanExecutor:
    """Get scan executor instance."""
    return ScanExecutor(db)


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("", response_model=ScanResponse, status_code=201)
async def create_scan(
    request: ScanCreate,
    background_tasks: BackgroundTasks,
    x_correlation_id: Optional[str] = Header(None),
    triggered_by: Optional[str] = Header(None, alias="X-User-ID"),
    repo: ScanRepository = Depends(get_scan_repository),
    executor: ScanExecutor = Depends(get_scan_executor),
):
    """
    Create new policy scan.
    
    Creates a scan and optionally executes it in the background.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Creating scan: {request.scan_name} (correlation={correlation_id})")
    
    try:
        # Create scan record
        scan = repo.create_scan(
            project_id=request.project_id,
            scan_name=request.scan_name,
            scan_description=request.scan_description,
            iac_framework=request.iac_framework,
            iac_version=request.iac_version,
            source_type=request.source_type,
            source_location=request.source_location,
            source_branch=request.source_branch,
            source_commit=request.source_commit,
            template_id=request.template_id,
            scan_config=request.scan_config,
            correlation_id=correlation_id,
            triggered_by=triggered_by,
        )
        
        # Execute scan in background if requested
        if request.auto_execute:
            background_tasks.add_task(
                executor.execute_scan,
                scan.scan_id,
                correlation_id
            )
            logger.info(f"Scan {scan.scan_id} queued for background execution")
        
        return ScanResponse.from_orm(scan)
        
    except Exception as e:
        logger.error(f"Error creating scan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create scan: {str(e)}")


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    repo: ScanRepository = Depends(get_scan_repository),
):
    """
    Get scan by ID.
    
    Returns details of a specific scan.
    """
    logger.info(f"Getting scan: {scan_id}")
    
    try:
        scan = repo.get_scan(scan_id)
        
        if not scan:
            raise HTTPException(
                status_code=404,
                detail=f"Scan {scan_id} not found"
            )
        
        return ScanResponse.from_orm(scan)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get scan: {str(e)}")


@router.get("/{scan_id}/violations", response_model=ViolationListResponse)
async def list_violations(
    scan_id: UUID,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    is_resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    repo: ScanRepository = Depends(get_scan_repository),
):
    """
    List violations for a scan.
    
    Returns violations with optional filters.
    """
    logger.info(f"Listing violations for scan: {scan_id}")
    
    try:
        # Verify scan exists
        scan = repo.get_scan(scan_id)
        if not scan:
            raise HTTPException(
                status_code=404,
                detail=f"Scan {scan_id} not found"
            )
        
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
        
        # Get violations
        violations = repo.get_violations_by_scan(
            scan_id,
            severity=severity_enum,
            is_resolved=is_resolved,
            limit=limit,
            offset=offset,
        )
        
        # Get severity counts
        severity_counts = repo.count_violations_by_severity(scan_id)
        
        return ViolationListResponse(
            scan_id=scan_id,
            violations=[ViolationResponse.from_orm(v) for v in violations],
            total=len(violations),
            by_severity=severity_counts,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing violations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list violations: {str(e)}")


@router.post("/{scan_id}/execute")
async def execute_scan(
    scan_id: UUID,
    background_tasks: BackgroundTasks,
    x_correlation_id: Optional[str] = Header(None),
    repo: ScanRepository = Depends(get_scan_repository),
    executor: ScanExecutor = Depends(get_scan_executor),
):
    """
    Execute an existing scan.
    
    Queues scan for execution in the background.
    """
    correlation_id = x_correlation_id or str(uuid4())
    
    logger.info(f"Executing scan: {scan_id} (correlation={correlation_id})")
    
    try:
        # Verify scan exists
        scan = repo.get_scan(scan_id)
        if not scan:
            raise HTTPException(
                status_code=404,
                detail=f"Scan {scan_id} not found"
            )
        
        # Check if scan is already running
        if scan.status == ScanStatus.RUNNING:
            raise HTTPException(
                status_code=409,
                detail=f"Scan {scan_id} is already running"
            )
        
        # Queue scan for execution
        background_tasks.add_task(
            executor.execute_scan,
            scan_id,
            correlation_id
        )
        
        # Update scan status to pending
        repo.update_scan_status(scan_id, ScanStatus.PENDING)
        
        return {
            "scan_id": str(scan_id),
            "status": "queued",
            "message": "Scan queued for execution",
            "correlation_id": correlation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing scan: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to execute scan: {str(e)}")


@router.get("/project/{project_id}", response_model=List[ScanResponse])
async def list_scans_by_project(
    project_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    repo: ScanRepository = Depends(get_scan_repository),
):
    """
    List scans for a project.
    
    Returns paginated list of scans with optional status filter.
    """
    logger.info(f"Listing scans for project: {project_id}")
    
    try:
        # Parse status if provided
        status_enum = None
        if status:
            try:
                status_enum = ScanStatus[status.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {[s.name for s in ScanStatus]}"
                )
        
        # Get scans
        scans = repo.list_scans_by_project(
            project_id,
            status=status_enum,
            limit=limit,
            offset=offset,
        )
        
        return [ScanResponse.from_orm(s) for s in scans]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing scans: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list scans: {str(e)}")
