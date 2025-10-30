"""
Terraform Repository Layer

Database operations for Terraform execution tracking and resource management.
Provides CRUD operations and queries for Terraform operations audit trail.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from app.models import (
    TerraformExecution,
    TerraformResource,
    TerraformExecutionStatus,
    TerraformExecutionType
)

logger = logging.getLogger("terraform-repository")


class TerraformRepository:
    """Repository for Terraform execution and resource data access."""
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    # ============================================================================
    # Terraform Execution CRUD Operations
    # ============================================================================
    
    def create_execution(
        self,
        *,
        project_id: UUID,
        execution_type: TerraformExecutionType,
        workspace_path: str,
        workspace_name: Optional[str] = None,
        scan_id: Optional[UUID] = None,
        var_file: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        backend_config: Optional[Dict[str, Any]] = None,
        target_resources: Optional[List[str]] = None,
        auto_approve: bool = False,
        correlation_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> TerraformExecution:
        """
        Create new Terraform execution record.
        
        Args:
            project_id: Project UUID
            execution_type: Type of Terraform operation
            workspace_path: Path to Terraform workspace
            workspace_name: Terraform workspace name
            scan_id: Optional associated policy scan ID
            var_file: Path to variables file
            variables: Variable overrides
            backend_config: Backend configuration
            target_resources: List of target resource addresses
            auto_approve: Whether execution was auto-approved
            correlation_id: Correlation ID for tracing
            triggered_by: User or service that triggered execution
            
        Returns:
            Created TerraformExecution instance
        """
        execution = TerraformExecution(
            project_id=project_id,
            scan_id=scan_id,
            execution_type=execution_type,
            status=TerraformExecutionStatus.PENDING,
            workspace_path=workspace_path,
            workspace_name=workspace_name,
            var_file=var_file,
            variables=variables or {},
            backend_config=backend_config or {},
            target_resources=target_resources or [],
            auto_approve=auto_approve,
            correlation_id=correlation_id,
            triggered_by=triggered_by,
        )
        
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        
        logger.info(f"Created Terraform execution {execution.execution_id} for project {project_id}")
        return execution
    
    def get_execution(self, execution_id: UUID) -> Optional[TerraformExecution]:
        """
        Get Terraform execution by ID.
        
        Args:
            execution_id: Execution UUID
            
        Returns:
            TerraformExecution instance or None
        """
        return self.db.query(TerraformExecution).filter(
            TerraformExecution.execution_id == execution_id
        ).first()
    
    def update_execution_status(
        self,
        execution_id: UUID,
        status: TerraformExecutionStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[TerraformExecution]:
        """
        Update execution status and timing information.
        
        Args:
            execution_id: Execution UUID
            status: New status
            started_at: Execution start time
            completed_at: Execution completion time
            duration_seconds: Execution duration
            error_message: Error message if failed
            error_details: Detailed error information
            
        Returns:
            Updated TerraformExecution or None
        """
        execution = self.get_execution(execution_id)
        if not execution:
            logger.warning(f"Execution {execution_id} not found for status update")
            return None
        
        execution.status = status
        
        if started_at:
            execution.started_at = started_at
        if completed_at:
            execution.completed_at = completed_at
        if duration_seconds is not None:
            execution.duration_seconds = duration_seconds
        if error_message:
            execution.error_message = error_message
        if error_details:
            execution.error_details = error_details
        
        execution.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(execution)
        
        logger.info(f"Updated execution {execution_id} status to {status.value}")
        return execution
    
    def update_execution_results(
        self,
        execution_id: UUID,
        *,
        plan_id: Optional[str] = None,
        changes_summary: Optional[Dict[str, int]] = None,
        resources_affected: Optional[List[str]] = None,
        output_text: Optional[str] = None,
        is_valid: Optional[bool] = None,
        diagnostics: Optional[List[Dict]] = None,
        error_count: Optional[int] = None,
        warning_count: Optional[int] = None,
    ) -> Optional[TerraformExecution]:
        """
        Update execution results (plan, apply, validate).
        
        Args:
            execution_id: Execution UUID
            plan_id: Unique plan identifier
            changes_summary: Summary of changes (add, change, delete)
            resources_affected: List of affected resource addresses
            output_text: Full Terraform output
            is_valid: Validation result (for validate operations)
            diagnostics: Validation diagnostics
            error_count: Number of validation errors
            warning_count: Number of validation warnings
            
        Returns:
            Updated TerraformExecution or None
        """
        execution = self.get_execution(execution_id)
        if not execution:
            logger.warning(f"Execution {execution_id} not found for results update")
            return None
        
        if plan_id:
            execution.plan_id = plan_id
        if changes_summary:
            execution.changes_summary = changes_summary
        if resources_affected is not None:
            execution.resources_affected = resources_affected
        if output_text:
            execution.output_text = output_text
        if is_valid is not None:
            execution.is_valid = is_valid
        if diagnostics is not None:
            execution.diagnostics = diagnostics
        if error_count is not None:
            execution.error_count = error_count
        if warning_count is not None:
            execution.warning_count = warning_count
        
        execution.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(execution)
        
        logger.info(f"Updated execution {execution_id} results")
        return execution
    
    def list_executions_by_project(
        self,
        project_id: UUID,
        *,
        execution_type: Optional[TerraformExecutionType] = None,
        status: Optional[TerraformExecutionStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TerraformExecution]:
        """
        List Terraform executions for a project.
        
        Args:
            project_id: Project UUID
            execution_type: Optional filter by execution type
            status: Optional filter by status
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of TerraformExecution instances
        """
        query = self.db.query(TerraformExecution).filter(
            TerraformExecution.project_id == project_id
        )
        
        if execution_type:
            query = query.filter(TerraformExecution.execution_type == execution_type)
        if status:
            query = query.filter(TerraformExecution.status == status)
        
        query = query.order_by(desc(TerraformExecution.created_at))
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def list_executions_by_scan(
        self,
        scan_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TerraformExecution]:
        """
        List Terraform executions associated with a policy scan.
        
        Args:
            scan_id: Policy scan UUID
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of TerraformExecution instances
        """
        query = self.db.query(TerraformExecution).filter(
            TerraformExecution.scan_id == scan_id
        ).order_by(desc(TerraformExecution.created_at)).limit(limit).offset(offset)
        
        return query.all()
    
    def get_executions_by_correlation_id(
        self,
        correlation_id: str
    ) -> List[TerraformExecution]:
        """
        Get all executions with the same correlation ID.
        
        Args:
            correlation_id: Correlation ID
            
        Returns:
            List of TerraformExecution instances
        """
        return self.db.query(TerraformExecution).filter(
            TerraformExecution.correlation_id == correlation_id
        ).order_by(TerraformExecution.created_at).all()
    
    # ============================================================================
    # Terraform Resource CRUD Operations
    # ============================================================================
    
    def create_resource(
        self,
        *,
        execution_id: UUID,
        resource_address: str,
        resource_type: str,
        resource_name: str,
        module_path: Optional[str] = None,
        action: Optional[str] = None,
        change_details: Optional[Dict[str, Any]] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        resource_metadata: Optional[Dict[str, Any]] = None,
    ) -> TerraformResource:
        """
        Create Terraform resource record.
        
        Args:
            execution_id: Associated execution UUID
            resource_address: Full Terraform resource address
            resource_type: Resource type (e.g., aws_instance)
            resource_name: Resource name
            module_path: Module path if in module
            action: Resource action (create, update, delete, etc.)
            change_details: Detailed change information
            previous_state: State before change
            new_state: State after change
            provider: Provider name
            resource_metadata: Additional metadata
            
        Returns:
            Created TerraformResource instance
        """
        resource = TerraformResource(
            execution_id=execution_id,
            resource_address=resource_address,
            resource_type=resource_type,
            resource_name=resource_name,
            module_path=module_path,
            action=action,
            change_details=change_details or {},
            previous_state=previous_state,
            new_state=new_state,
            provider=provider,
            resource_metadata=resource_metadata or {},
        )
        
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        
        logger.debug(f"Created Terraform resource {resource.resource_id} for execution {execution_id}")
        return resource
    
    def bulk_create_resources(
        self,
        execution_id: UUID,
        resources: List[Dict[str, Any]]
    ) -> List[TerraformResource]:
        """
        Bulk create Terraform resources for an execution.
        
        Args:
            execution_id: Associated execution UUID
            resources: List of resource dictionaries
            
        Returns:
            List of created TerraformResource instances
        """
        resource_objs = []
        
        for res_data in resources:
            resource = TerraformResource(
                execution_id=execution_id,
                resource_address=res_data.get("resource_address"),
                resource_type=res_data.get("resource_type"),
                resource_name=res_data.get("resource_name"),
                module_path=res_data.get("module_path"),
                action=res_data.get("action"),
                change_details=res_data.get("change_details", {}),
                previous_state=res_data.get("previous_state"),
                new_state=res_data.get("new_state"),
                provider=res_data.get("provider"),
                resource_metadata=res_data.get("resource_metadata", {}),
            )
            resource_objs.append(resource)
        
        self.db.bulk_save_objects(resource_objs, return_defaults=True)
        self.db.commit()
        
        logger.info(f"Bulk created {len(resource_objs)} Terraform resources for execution {execution_id}")
        return resource_objs
    
    def get_resources_by_execution(
        self,
        execution_id: UUID
    ) -> List[TerraformResource]:
        """
        Get all resources for a Terraform execution.
        
        Args:
            execution_id: Execution UUID
            
        Returns:
            List of TerraformResource instances
        """
        return self.db.query(TerraformResource).filter(
            TerraformResource.execution_id == execution_id
        ).order_by(TerraformResource.created_at).all()
    
    def get_resources_by_type(
        self,
        execution_id: UUID,
        resource_type: str
    ) -> List[TerraformResource]:
        """
        Get resources of a specific type for an execution.
        
        Args:
            execution_id: Execution UUID
            resource_type: Resource type filter
            
        Returns:
            List of TerraformResource instances
        """
        return self.db.query(TerraformResource).filter(
            and_(
                TerraformResource.execution_id == execution_id,
                TerraformResource.resource_type == resource_type
            )
        ).all()
    
    # ============================================================================
    # Analytics and Reporting
    # ============================================================================
    
    def get_execution_statistics(
        self,
        project_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get execution statistics for a project.
        
        Args:
            project_id: Project UUID
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with statistics (total, by type, by status, success rate)
        """
        query = self.db.query(TerraformExecution).filter(
            TerraformExecution.project_id == project_id
        )
        
        if start_date:
            query = query.filter(TerraformExecution.created_at >= start_date)
        if end_date:
            query = query.filter(TerraformExecution.created_at <= end_date)
        
        executions = query.all()
        
        total = len(executions)
        by_type = {}
        by_status = {}
        
        for exec in executions:
            # Count by type
            type_key = exec.execution_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            
            # Count by status
            status_key = exec.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1
        
        completed = by_status.get(TerraformExecutionStatus.COMPLETED.value, 0)
        success_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "total_executions": total,
            "by_type": by_type,
            "by_status": by_status,
            "success_rate": round(success_rate, 2),
        }
