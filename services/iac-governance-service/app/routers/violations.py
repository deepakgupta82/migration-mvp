"""Violations API router for managing policy violations."""

import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.database import PolicySeverity
from app.repository.scan_repository import ScanRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/violations", tags=["Violations"])


# Pydantic Models

class ViolationResponse(BaseModel):
    """Response model for policy violation."""
    violation_id: UUID
    scan_id: UUID
    template_id: Optional[UUID]
    resource_type: str
    resource_name: str
    resource_address: Optional[str]
    violation_rule: str
    severity: str
    violation_message: str
    violation_details: Optional[dict]
    recommended_fix: Optional[str]
    is_resolved: bool
    resolved_at: Optional[str]
    resolved_by: Optional[str]
    resolution_notes: Optional[str]
    is_suppressed: bool
    suppressed_reason: Optional[str]
    suppressed_until: Optional[str]
    violation_metadata: dict
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ViolationListResponse(BaseModel):
    """Response model for list of violations."""
    violations: List[ViolationResponse]
    total: int
    limit: int
    offset: int
    severity_counts: dict


class ResolveViolationRequest(BaseModel):
    """Request model for resolving a violation."""
    resolution_notes: Optional[str] = Field(None, description="Notes about how the violation was resolved")


class SuppressViolationRequest(BaseModel):
    """Request model for suppressing a violation."""
    suppressed_reason: str = Field(..., description="Reason for suppressing the violation")
    suppressed_until: Optional[datetime] = Field(None, description="Optional expiration date for suppression")


class ViolationCommentRequest(BaseModel):
    """Request model for adding a comment to a violation."""
    comment: str = Field(..., description="Comment text")


class ViolationStatisticsResponse(BaseModel):
    """Response model for violation statistics."""
    total: int
    unresolved: int
    resolved: int
    suppressed: int
    by_severity: dict
    resolution_rate: float


# Dependency injection

def get_scan_repo(db: AsyncSession = Depends(get_db)) -> ScanRepository:
    """Get scan repository instance."""
    return ScanRepository(db)


# API Endpoints

@router.get("", response_model=ViolationListResponse)
async def list_violations(
    scan_id: Optional[UUID] = None,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    is_suppressed: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    List policy violations with optional filters.
    
    Args:
        scan_id: Optional filter by scan ID
        severity: Optional filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
        is_resolved: Optional filter by resolved status
        is_suppressed: Optional filter by suppressed status
        limit: Maximum number of results
        offset: Number of results to skip
        repo: Scan repository
        
    Returns:
        List of violations with metadata
    """
    # Convert severity string to enum if provided
    severity_enum = None
    if severity:
        try:
            severity_enum = PolicySeverity(severity.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    
    if scan_id:
        # Get violations for specific scan
        violations = await repo.get_violations_by_scan(
            scan_id=scan_id,
            severity=severity_enum,
            is_resolved=is_resolved,
            limit=limit,
            offset=offset,
        )
        
        # Get severity counts for the scan
        severity_counts = await repo.count_violations_by_severity(scan_id)
        
        total = len(violations)  # Simple count for now
    else:
        # TODO: Implement global violation query across all scans
        # For now, return error asking for scan_id
        raise HTTPException(
            status_code=400,
            detail="scan_id parameter is required for listing violations"
        )
    
    return ViolationListResponse(
        violations=violations,
        total=total,
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
    )


@router.get("/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: UUID,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Get a violation by ID.
    
    Args:
        violation_id: UUID of the violation
        repo: Scan repository
        
    Returns:
        Violation details
    """
    violation = await repo.get_violation(violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    return violation


@router.post("/{violation_id}/resolve", response_model=ViolationResponse)
async def resolve_violation(
    violation_id: UUID,
    request: ResolveViolationRequest,
    repo: ScanRepository = Depends(get_scan_repo),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Mark a violation as resolved.
    
    Args:
        violation_id: UUID of the violation
        request: Resolution request
        repo: Scan repository
        x_user_id: User ID from header
        
    Returns:
        Updated violation
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required for resolving violations")
    
    violation = await repo.resolve_violation(
        violation_id=violation_id,
        resolved_by=x_user_id,
        resolution_notes=request.resolution_notes,
    )
    
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    logger.info(f"Violation {violation_id} resolved by {x_user_id}")
    return violation


@router.delete("/{violation_id}/resolve", response_model=ViolationResponse)
async def unresolve_violation(
    violation_id: UUID,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Mark a resolved violation as unresolved.
    
    Args:
        violation_id: UUID of the violation
        repo: Scan repository
        
    Returns:
        Updated violation
    """
    violation = await repo.get_violation(violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    if not violation.is_resolved:
        raise HTTPException(status_code=400, detail="Violation is not resolved")
    
    # Unresolve the violation
    violation.is_resolved = False
    violation.resolved_at = None
    violation.resolved_by = None
    violation.resolution_notes = None
    violation.updated_at = datetime.utcnow()
    
    await repo.db.commit()
    await repo.db.refresh(violation)
    
    logger.info(f"Violation {violation_id} marked as unresolved")
    return violation


@router.post("/{violation_id}/suppress", response_model=ViolationResponse)
async def suppress_violation(
    violation_id: UUID,
    request: SuppressViolationRequest,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Suppress a violation.
    
    Args:
        violation_id: UUID of the violation
        request: Suppression request
        repo: Scan repository
        
    Returns:
        Updated violation
    """
    violation = await repo.suppress_violation(
        violation_id=violation_id,
        suppressed_reason=request.suppressed_reason,
        suppressed_until=request.suppressed_until,
    )
    
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    logger.info(f"Violation {violation_id} suppressed")
    return violation


@router.delete("/{violation_id}/suppress", response_model=ViolationResponse)
async def unsuppress_violation(
    violation_id: UUID,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Remove suppression from a violation.
    
    Args:
        violation_id: UUID of the violation
        repo: Scan repository
        
    Returns:
        Updated violation
    """
    violation = await repo.get_violation(violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    if not violation.is_suppressed:
        raise HTTPException(status_code=400, detail="Violation is not suppressed")
    
    # Unsuppress the violation
    violation.is_suppressed = False
    violation.suppressed_reason = None
    violation.suppressed_until = None
    violation.updated_at = datetime.utcnow()
    
    await repo.db.commit()
    await repo.db.refresh(violation)
    
    logger.info(f"Violation {violation_id} suppression removed")
    return violation


@router.post("/{violation_id}/comment", response_model=ViolationResponse)
async def add_violation_comment(
    violation_id: UUID,
    request: ViolationCommentRequest,
    repo: ScanRepository = Depends(get_scan_repo),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """
    Add a comment to a violation.
    
    Args:
        violation_id: UUID of the violation
        request: Comment request
        repo: Scan repository
        x_user_id: User ID from header
        
    Returns:
        Updated violation
    """
    violation = await repo.get_violation(violation_id)
    if not violation:
        raise HTTPException(status_code=404, detail=f"Violation {violation_id} not found")
    
    # Add comment to metadata
    metadata = violation.violation_metadata or {}
    comments = metadata.get("comments", [])
    
    comment_entry = {
        "user_id": x_user_id,
        "comment": request.comment,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    comments.append(comment_entry)
    metadata["comments"] = comments
    
    violation.violation_metadata = metadata
    violation.updated_at = datetime.utcnow()
    
    await repo.db.commit()
    await repo.db.refresh(violation)
    
    logger.info(f"Comment added to violation {violation_id} by {x_user_id}")
    return violation


@router.get("/scan/{scan_id}/stats", response_model=ViolationStatisticsResponse)
async def get_scan_violation_statistics(
    scan_id: UUID,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Get violation statistics for a scan.
    
    Args:
        scan_id: UUID of the scan
        repo: Scan repository
        
    Returns:
        Violation statistics
    """
    # Get all violations for the scan
    violations = await repo.get_violations_by_scan(scan_id=scan_id, limit=10000)
    
    total = len(violations)
    unresolved = sum(1 for v in violations if not v.is_resolved)
    resolved = sum(1 for v in violations if v.is_resolved)
    suppressed = sum(1 for v in violations if v.is_suppressed)
    
    # Count by severity
    by_severity = {
        "CRITICAL": sum(1 for v in violations if v.severity == PolicySeverity.CRITICAL),
        "HIGH": sum(1 for v in violations if v.severity == PolicySeverity.HIGH),
        "MEDIUM": sum(1 for v in violations if v.severity == PolicySeverity.MEDIUM),
        "LOW": sum(1 for v in violations if v.severity == PolicySeverity.LOW),
        "INFO": sum(1 for v in violations if v.severity == PolicySeverity.INFO),
    }
    
    # Calculate resolution rate
    resolution_rate = (resolved / total * 100) if total > 0 else 0.0
    
    return ViolationStatisticsResponse(
        total=total,
        unresolved=unresolved,
        resolved=resolved,
        suppressed=suppressed,
        by_severity=by_severity,
        resolution_rate=round(resolution_rate, 2),
    )


@router.get("/project/{project_id}/stats", response_model=ViolationStatisticsResponse)
async def get_project_violation_statistics(
    project_id: UUID,
    repo: ScanRepository = Depends(get_scan_repo),
):
    """
    Get violation statistics for all scans in a project.
    
    Args:
        project_id: UUID of the project
        repo: Scan repository
        
    Returns:
        Violation statistics across all project scans
    """
    # Get all scans for the project
    scans = await repo.list_scans_by_project(project_id=project_id, limit=1000)
    
    # Aggregate violations from all scans
    all_violations = []
    for scan in scans:
        violations = await repo.get_violations_by_scan(scan_id=scan.scan_id, limit=10000)
        all_violations.extend(violations)
    
    total = len(all_violations)
    unresolved = sum(1 for v in all_violations if not v.is_resolved)
    resolved = sum(1 for v in all_violations if v.is_resolved)
    suppressed = sum(1 for v in all_violations if v.is_suppressed)
    
    # Count by severity
    by_severity = {
        "CRITICAL": sum(1 for v in all_violations if v.severity == PolicySeverity.CRITICAL),
        "HIGH": sum(1 for v in all_violations if v.severity == PolicySeverity.HIGH),
        "MEDIUM": sum(1 for v in all_violations if v.severity == PolicySeverity.MEDIUM),
        "LOW": sum(1 for v in all_violations if v.severity == PolicySeverity.LOW),
        "INFO": sum(1 for v in all_violations if v.severity == PolicySeverity.INFO),
    }
    
    # Calculate resolution rate
    resolution_rate = (resolved / total * 100) if total > 0 else 0.0
    
    return ViolationStatisticsResponse(
        total=total,
        unresolved=unresolved,
        resolved=resolved,
        suppressed=suppressed,
        by_severity=by_severity,
        resolution_rate=round(resolution_rate, 2),
    )
