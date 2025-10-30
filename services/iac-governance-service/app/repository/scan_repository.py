"""
Scan Repository Layer

Database operations for policy scan and violation management.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models import (
    PolicyScan,
    PolicyViolation,
    ScanStatus,
    PolicySeverity
)

logger = logging.getLogger("scan-repository")


class ScanRepository:
    """Repository for policy scan data access."""
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    # ============================================================================
    # PolicyScan CRUD Operations
    # ============================================================================
    
    def create_scan(
        self,
        *,
        project_id: UUID,
        scan_name: str,
        iac_framework: str,
        source_type: str,
        source_location: str,
        template_id: Optional[UUID] = None,
        scan_description: Optional[str] = None,
        iac_version: Optional[str] = None,
        source_branch: Optional[str] = None,
        source_commit: Optional[str] = None,
        scan_config: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> PolicyScan:
        """
        Create new policy scan.
        
        Args:
            project_id: Project UUID
            scan_name: Name of the scan
            iac_framework: IaC framework (terraform, cloudformation, etc.)
            source_type: Source type (git, local, etc.)
            source_location: Source location/path
            template_id: Optional policy template ID
            scan_description: Optional description
            iac_version: Optional IaC version
            source_branch: Optional git branch
            source_commit: Optional git commit
            scan_config: Optional scan configuration
            correlation_id: Optional correlation ID
            triggered_by: User or service that triggered scan
            
        Returns:
            Created PolicyScan instance
        """
        scan = PolicyScan(
            template_id=template_id,
            project_id=project_id,
            scan_name=scan_name,
            scan_description=scan_description,
            iac_framework=iac_framework,
            iac_version=iac_version,
            source_type=source_type,
            source_location=source_location,
            source_branch=source_branch,
            source_commit=source_commit,
            status=ScanStatus.PENDING,
            scan_config=scan_config or {},
            correlation_id=correlation_id,
            triggered_by=triggered_by,
        )
        
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        
        logger.info(f"Created policy scan {scan.scan_id} for project {project_id}")
        return scan
    
    def get_scan(self, scan_id: UUID) -> Optional[PolicyScan]:
        """
        Get policy scan by ID.
        
        Args:
            scan_id: Scan UUID
            
        Returns:
            PolicyScan instance or None
        """
        return self.db.query(PolicyScan).filter(
            PolicyScan.scan_id == scan_id
        ).first()
    
    def update_scan_status(
        self,
        scan_id: UUID,
        status: ScanStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[PolicyScan]:
        """
        Update scan status and timing.
        
        Args:
            scan_id: Scan UUID
            status: New status
            started_at: Scan start time
            completed_at: Scan completion time
            duration_seconds: Scan duration
            error_message: Error message if failed
            error_details: Detailed error information
            
        Returns:
            Updated PolicyScan or None
        """
        scan = self.get_scan(scan_id)
        if not scan:
            logger.warning(f"Scan {scan_id} not found for status update")
            return None
        
        scan.status = status
        
        if started_at:
            scan.started_at = started_at
        if completed_at:
            scan.completed_at = completed_at
        if duration_seconds is not None:
            scan.duration_seconds = duration_seconds
        if error_message:
            scan.error_message = error_message
        if error_details:
            scan.error_details = error_details
        
        scan.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(scan)
        
        logger.info(f"Updated scan {scan_id} status to {status.value}")
        return scan
    
    def update_scan_results(
        self,
        scan_id: UUID,
        *,
        total_resources: Optional[int] = None,
        passed_checks: Optional[int] = None,
        failed_checks: Optional[int] = None,
        violations_critical: Optional[int] = None,
        violations_high: Optional[int] = None,
        violations_medium: Optional[int] = None,
        violations_low: Optional[int] = None,
        violations_info: Optional[int] = None,
    ) -> Optional[PolicyScan]:
        """
        Update scan results metrics.
        
        Args:
            scan_id: Scan UUID
            total_resources: Total resources scanned
            passed_checks: Number of passed checks
            failed_checks: Number of failed checks
            violations_critical: Count of critical violations
            violations_high: Count of high violations
            violations_medium: Count of medium violations
            violations_low: Count of low violations
            violations_info: Count of info violations
            
        Returns:
            Updated PolicyScan or None
        """
        scan = self.get_scan(scan_id)
        if not scan:
            logger.warning(f"Scan {scan_id} not found for results update")
            return None
        
        if total_resources is not None:
            scan.total_resources = total_resources
        if passed_checks is not None:
            scan.passed_checks = passed_checks
        if failed_checks is not None:
            scan.failed_checks = failed_checks
        if violations_critical is not None:
            scan.violations_critical = violations_critical
        if violations_high is not None:
            scan.violations_high = violations_high
        if violations_medium is not None:
            scan.violations_medium = violations_medium
        if violations_low is not None:
            scan.violations_low = violations_low
        if violations_info is not None:
            scan.violations_info = violations_info
        
        scan.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(scan)
        
        logger.info(f"Updated scan {scan_id} results")
        return scan
    
    def list_scans_by_project(
        self,
        project_id: UUID,
        *,
        status: Optional[ScanStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PolicyScan]:
        """
        List scans for a project.
        
        Args:
            project_id: Project UUID
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of PolicyScan instances
        """
        query = self.db.query(PolicyScan).filter(
            PolicyScan.project_id == project_id
        )
        
        if status:
            query = query.filter(PolicyScan.status == status)
        
        query = query.order_by(desc(PolicyScan.created_at))
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    # ============================================================================
    # PolicyViolation CRUD Operations
    # ============================================================================
    
    def create_violation(
        self,
        *,
        scan_id: UUID,
        template_id: Optional[UUID],
        violation_rule: str,
        severity: PolicySeverity,
        resource_type: str,
        resource_name: str,
        resource_identifier: str,
        violation_message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        violation_details: Optional[Dict[str, Any]] = None,
        recommended_fix: Optional[str] = None,
    ) -> PolicyViolation:
        """
        Create policy violation record.
        
        Args:
            scan_id: Associated scan UUID
            template_id: Optional policy template ID
            violation_rule: Rule that was violated
            severity: Violation severity
            resource_type: Type of resource
            resource_name: Name of resource
            resource_identifier: Unique identifier
            violation_message: Violation message
            file_path: Optional file path
            line_number: Optional line number
            violation_details: Optional details
            recommended_fix: Optional fix recommendation
            
        Returns:
            Created PolicyViolation instance
        """
        violation = PolicyViolation(
            scan_id=scan_id,
            template_id=template_id,
            violation_rule=violation_rule,
            severity=severity,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_identifier=resource_identifier,
            file_path=file_path,
            line_number=line_number,
            violation_message=violation_message,
            violation_details=violation_details or {},
            recommended_fix=recommended_fix,
        )
        
        self.db.add(violation)
        self.db.commit()
        self.db.refresh(violation)
        
        logger.debug(f"Created violation {violation.violation_id} for scan {scan_id}")
        return violation
    
    def bulk_create_violations(
        self,
        scan_id: UUID,
        violations: List[Dict[str, Any]]
    ) -> List[PolicyViolation]:
        """
        Bulk create violations for a scan.
        
        Args:
            scan_id: Associated scan UUID
            violations: List of violation dictionaries
            
        Returns:
            List of created PolicyViolation instances
        """
        violation_objs = []
        
        for viol_data in violations:
            violation = PolicyViolation(
                scan_id=scan_id,
                template_id=viol_data.get("template_id"),
                violation_rule=viol_data.get("violation_rule"),
                severity=viol_data.get("severity"),
                resource_type=viol_data.get("resource_type"),
                resource_name=viol_data.get("resource_name"),
                resource_identifier=viol_data.get("resource_identifier", ""),
                file_path=viol_data.get("file_path"),
                line_number=viol_data.get("line_number"),
                violation_message=viol_data.get("violation_message"),
                violation_details=viol_data.get("violation_details", {}),
                recommended_fix=viol_data.get("recommended_fix"),
            )
            violation_objs.append(violation)
        
        self.db.bulk_save_objects(violation_objs, return_defaults=True)
        self.db.commit()
        
        logger.info(f"Bulk created {len(violation_objs)} violations for scan {scan_id}")
        return violation_objs
    
    def get_violations_by_scan(
        self,
        scan_id: UUID,
        *,
        severity: Optional[PolicySeverity] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[PolicyViolation]:
        """
        Get violations for a scan.
        
        Args:
            scan_id: Scan UUID
            severity: Optional severity filter
            is_resolved: Optional resolved status filter
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of PolicyViolation instances
        """
        query = self.db.query(PolicyViolation).filter(
            PolicyViolation.scan_id == scan_id
        )
        
        if severity:
            query = query.filter(PolicyViolation.severity == severity)
        if is_resolved is not None:
            query = query.filter(PolicyViolation.is_resolved == is_resolved)
        
        query = query.order_by(desc(PolicyViolation.severity))
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def count_violations_by_severity(
        self,
        scan_id: UUID
    ) -> Dict[str, int]:
        """
        Count violations by severity for a scan.
        
        Args:
            scan_id: Scan UUID
            
        Returns:
            Dictionary with counts by severity
        """
        violations = self.get_violations_by_scan(scan_id, limit=10000)
        
        counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        
        for viol in violations:
            counts[viol.severity.value] += 1
        
        return counts

    def get_violation(self, violation_id: UUID) -> Optional[PolicyViolation]:
        """
        Get a violation by ID.
        
        Args:
            violation_id: Violation UUID
            
        Returns:
            PolicyViolation instance or None
        """
        return self.db.query(PolicyViolation).filter(
            PolicyViolation.violation_id == violation_id
        ).first()

    def resolve_violation(
        self,
        violation_id: UUID,
        resolved_by: str,
        resolution_notes: Optional[str] = None,
    ) -> Optional[PolicyViolation]:
        """
        Mark a violation as resolved.
        
        Args:
            violation_id: Violation UUID
            resolved_by: User who resolved the violation
            resolution_notes: Optional notes about resolution
            
        Returns:
            Updated PolicyViolation instance or None
        """
        violation = self.get_violation(violation_id)
        if not violation:
            return None
        
        violation.is_resolved = True
        violation.resolved_at = datetime.utcnow()
        violation.resolved_by = resolved_by
        violation.resolution_notes = resolution_notes
        violation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(violation)
        return violation

    def suppress_violation(
        self,
        violation_id: UUID,
        suppressed_reason: str,
        suppressed_until: Optional[datetime] = None,
    ) -> Optional[PolicyViolation]:
        """
        Suppress a violation.
        
        Args:
            violation_id: Violation UUID
            suppressed_reason: Reason for suppression
            suppressed_until: Optional expiration date for suppression
            
        Returns:
            Updated PolicyViolation instance or None
        """
        violation = self.get_violation(violation_id)
        if not violation:
            return None
        
        violation.is_suppressed = True
        violation.suppressed_reason = suppressed_reason
        violation.suppressed_until = suppressed_until
        violation.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(violation)
        return violation

