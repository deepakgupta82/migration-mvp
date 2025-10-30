"""Remediation repository for managing remediation actions."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import RemediationAction, RemediationStatus, PolicyViolation


class RemediationRepository:
    """Repository for managing remediation actions in the database."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the remediation repository.
        
        Args:
            db: SQLAlchemy async database session
        """
        self.db = db

    async def create_action(
        self,
        violation_id: UUID,
        action_type: str,
        action_name: str,
        remediation_method: str,
        action_description: Optional[str] = None,
        remediation_code: Optional[str] = None,
        remediation_params: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False,
        triggered_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
        action_metadata: Optional[Dict[str, Any]] = None,
    ) -> RemediationAction:
        """
        Create a new remediation action.
        
        Args:
            violation_id: ID of the violation to remediate
            action_type: Type of action (auto_fix, manual_fix, suppress, ignore)
            action_name: Name of the action
            remediation_method: Method to apply remediation
            action_description: Description of the action
            remediation_code: Code/script to apply fix
            remediation_params: Parameters for remediation
            requires_approval: Whether action requires approval
            triggered_by: User or service that triggered action
            correlation_id: Correlation ID for tracing
            action_metadata: Additional metadata
            
        Returns:
            Created RemediationAction instance
        """
        action = RemediationAction(
            violation_id=violation_id,
            action_type=action_type,
            action_name=action_name,
            action_description=action_description,
            remediation_method=remediation_method,
            remediation_code=remediation_code,
            remediation_params=remediation_params or {},
            status=RemediationStatus.PENDING,
            requires_approval=requires_approval,
            triggered_by=triggered_by,
            correlation_id=correlation_id,
            action_metadata=action_metadata or {},
        )
        
        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def get_action(self, action_id: UUID) -> Optional[RemediationAction]:
        """
        Get a remediation action by ID.
        
        Args:
            action_id: UUID of the action
            
        Returns:
            RemediationAction instance or None
        """
        result = await self.db.execute(
            select(RemediationAction).where(RemediationAction.action_id == action_id)
        )
        return result.scalar_one_or_none()

    async def get_actions_by_violation(
        self,
        violation_id: UUID,
        status: Optional[RemediationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RemediationAction]:
        """
        Get remediation actions for a violation.
        
        Args:
            violation_id: ID of the violation
            status: Optional status filter
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RemediationAction instances
        """
        query = select(RemediationAction).where(
            RemediationAction.violation_id == violation_id
        )
        
        if status:
            query = query.where(RemediationAction.status == status)
        
        query = query.order_by(RemediationAction.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_actions_by_correlation(
        self,
        correlation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RemediationAction]:
        """
        Get remediation actions by correlation ID.
        
        Args:
            correlation_id: Correlation ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RemediationAction instances
        """
        query = select(RemediationAction).where(
            RemediationAction.correlation_id == correlation_id
        )
        
        query = query.order_by(RemediationAction.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_actions(
        self,
        status: Optional[RemediationStatus] = None,
        action_type: Optional[str] = None,
        requires_approval: Optional[bool] = None,
        is_successful: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RemediationAction]:
        """
        List remediation actions with optional filters.
        
        Args:
            status: Filter by status
            action_type: Filter by action type
            requires_approval: Filter by approval requirement
            is_successful: Filter by success status
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RemediationAction instances
        """
        query = select(RemediationAction)
        
        conditions = []
        if status:
            conditions.append(RemediationAction.status == status)
        if action_type:
            conditions.append(RemediationAction.action_type == action_type)
        if requires_approval is not None:
            conditions.append(RemediationAction.requires_approval == requires_approval)
        if is_successful is not None:
            conditions.append(RemediationAction.is_successful == is_successful)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(RemediationAction.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        action_id: UUID,
        status: RemediationStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[int] = None,
    ) -> Optional[RemediationAction]:
        """
        Update the status of a remediation action.
        
        Args:
            action_id: ID of the action
            status: New status
            started_at: Execution start time
            completed_at: Execution completion time
            duration_seconds: Execution duration
            
        Returns:
            Updated RemediationAction instance or None
        """
        action = await self.get_action(action_id)
        if not action:
            return None
        
        action.status = status
        if started_at:
            action.started_at = started_at
        if completed_at:
            action.completed_at = completed_at
        if duration_seconds is not None:
            action.duration_seconds = duration_seconds
        
        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def update_results(
        self,
        action_id: UUID,
        is_successful: bool,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[RemediationAction]:
        """
        Update the results of a remediation action.
        
        Args:
            action_id: ID of the action
            is_successful: Whether the action was successful
            result: Execution result data
            error_message: Error message if failed
            
        Returns:
            Updated RemediationAction instance or None
        """
        action = await self.get_action(action_id)
        if not action:
            return None
        
        action.is_successful = is_successful
        action.result = result
        action.error_message = error_message
        
        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def approve_action(
        self,
        action_id: UUID,
        approved_by: str,
        approval_notes: Optional[str] = None,
    ) -> Optional[RemediationAction]:
        """
        Approve a remediation action.
        
        Args:
            action_id: ID of the action
            approved_by: User who approved
            approval_notes: Optional approval notes
            
        Returns:
            Updated RemediationAction instance or None
        """
        action = await self.get_action(action_id)
        if not action:
            return None
        
        action.approved_by = approved_by
        action.approved_at = datetime.utcnow()
        action.approval_notes = approval_notes
        
        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def count_actions(
        self,
        status: Optional[RemediationStatus] = None,
        action_type: Optional[str] = None,
        requires_approval: Optional[bool] = None,
        is_successful: Optional[bool] = None,
    ) -> int:
        """
        Count remediation actions with optional filters.
        
        Args:
            status: Filter by status
            action_type: Filter by action type
            requires_approval: Filter by approval requirement
            is_successful: Filter by success status
            
        Returns:
            Count of matching actions
        """
        query = select(func.count()).select_from(RemediationAction)
        
        conditions = []
        if status:
            conditions.append(RemediationAction.status == status)
        if action_type:
            conditions.append(RemediationAction.action_type == action_type)
        if requires_approval is not None:
            conditions.append(RemediationAction.requires_approval == requires_approval)
        if is_successful is not None:
            conditions.append(RemediationAction.is_successful == is_successful)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_pending_approvals(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RemediationAction]:
        """
        Get remediation actions pending approval.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RemediationAction instances
        """
        query = select(RemediationAction).where(
            and_(
                RemediationAction.requires_approval == True,
                RemediationAction.approved_at.is_(None),
                RemediationAction.status == RemediationStatus.PENDING,
            )
        )
        
        query = query.order_by(RemediationAction.created_at.asc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get remediation action statistics.
        
        Returns:
            Dictionary with statistics
        """
        total = await self.count_actions()
        pending = await self.count_actions(status=RemediationStatus.PENDING)
        in_progress = await self.count_actions(status=RemediationStatus.IN_PROGRESS)
        completed = await self.count_actions(status=RemediationStatus.COMPLETED)
        failed = await self.count_actions(status=RemediationStatus.FAILED)
        
        # Success rate
        query = select(func.count()).select_from(RemediationAction).where(
            and_(
                RemediationAction.status == RemediationStatus.COMPLETED,
                RemediationAction.is_successful == True,
            )
        )
        result = await self.db.execute(query)
        successful = result.scalar_one()
        
        success_rate = (successful / completed * 100) if completed > 0 else 0.0
        
        # Pending approvals
        pending_approvals = await self.count_actions(
            requires_approval=True,
            status=RemediationStatus.PENDING,
        )
        
        return {
            "total_actions": total,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "successful": successful,
            "success_rate": round(success_rate, 2),
            "pending_approvals": pending_approvals,
        }
