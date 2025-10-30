"""
Policy Repository Layer

Database operations for policy template management.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from app.models import PolicyTemplate, PolicySeverity

logger = logging.getLogger("policy-repository")


class PolicyRepository:
    """Repository for policy template data access."""
    
    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def create_policy(
        self,
        *,
        template_name: str,
        policy_category: str,
        severity: PolicySeverity,
        engine_type: str,
        policy_code: str,
        supported_frameworks: List[str],
        cloud_providers: List[str],
        template_description: Optional[str] = None,
        is_active: bool = True,
        is_blocking: bool = False,
        auto_remediate: bool = False,
        tags: Optional[List[str]] = None,
        policy_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> PolicyTemplate:
        """
        Create new policy template.
        
        Args:
            template_name: Name of the policy template
            template_description: Description of the policy
            policy_category: Category (e.g., "security", "compliance")
            severity: Severity level
            engine_type: Policy engine type (e.g., "opa", "rego")
            policy_code: Policy code (Rego for OPA)
            supported_frameworks: List of supported IaC frameworks
            cloud_providers: List of supported cloud providers
            is_active: Whether policy is active
            is_blocking: Whether policy blocks deployments
            auto_remediate: Whether to auto-remediate violations
            tags: Optional tags for categorization
            policy_metadata: Optional metadata
            created_by: User who created the policy
            
        Returns:
            Created PolicyTemplate instance
        """
        policy = PolicyTemplate(
            template_name=template_name,
            template_description=template_description,
            policy_category=policy_category,
            severity=severity,
            engine_type=engine_type,
            policy_code=policy_code,
            supported_frameworks=supported_frameworks,
            cloud_providers=cloud_providers,
            is_active=is_active,
            is_blocking=is_blocking,
            auto_remediate=auto_remediate,
            tags=tags or [],
            policy_metadata=policy_metadata or {},
            created_by=created_by,
        )
        
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        
        logger.info(f"Created policy template {policy.template_id}: {template_name}")
        return policy
    
    def get_policy(self, template_id: UUID) -> Optional[PolicyTemplate]:
        """
        Get policy template by ID.
        
        Args:
            template_id: Policy template UUID
            
        Returns:
            PolicyTemplate instance or None
        """
        return self.db.query(PolicyTemplate).filter(
            PolicyTemplate.template_id == template_id
        ).first()
    
    def get_policy_by_name(self, template_name: str) -> Optional[PolicyTemplate]:
        """
        Get policy template by name.
        
        Args:
            template_name: Policy template name
            
        Returns:
            PolicyTemplate instance or None
        """
        return self.db.query(PolicyTemplate).filter(
            PolicyTemplate.template_name == template_name
        ).first()
    
    def list_policies(
        self,
        *,
        policy_category: Optional[str] = None,
        severity: Optional[PolicySeverity] = None,
        is_active: Optional[bool] = None,
        is_blocking: Optional[bool] = None,
        cloud_provider: Optional[str] = None,
        framework: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PolicyTemplate]:
        """
        List policy templates with optional filters.
        
        Args:
            policy_category: Filter by category
            severity: Filter by severity
            is_active: Filter by active status
            is_blocking: Filter by blocking status
            cloud_provider: Filter by cloud provider support
            framework: Filter by framework support
            tags: Filter by tags (any match)
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of PolicyTemplate instances
        """
        query = self.db.query(PolicyTemplate)
        
        if policy_category:
            query = query.filter(PolicyTemplate.policy_category == policy_category)
        if severity:
            query = query.filter(PolicyTemplate.severity == severity)
        if is_active is not None:
            query = query.filter(PolicyTemplate.is_active == is_active)
        if is_blocking is not None:
            query = query.filter(PolicyTemplate.is_blocking == is_blocking)
        if cloud_provider:
            query = query.filter(PolicyTemplate.cloud_providers.contains([cloud_provider]))
        if framework:
            query = query.filter(PolicyTemplate.supported_frameworks.contains([framework]))
        if tags:
            # Match any of the provided tags
            query = query.filter(PolicyTemplate.tags.overlap(tags))
        
        query = query.order_by(desc(PolicyTemplate.created_at))
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def update_policy(
        self,
        template_id: UUID,
        **updates
    ) -> Optional[PolicyTemplate]:
        """
        Update policy template.
        
        Args:
            template_id: Policy template UUID
            **updates: Fields to update
            
        Returns:
            Updated PolicyTemplate or None
        """
        policy = self.get_policy(template_id)
        if not policy:
            logger.warning(f"Policy {template_id} not found for update")
            return None
        
        # Update allowed fields
        allowed_fields = {
            'template_name', 'template_description', 'policy_category', 'severity',
            'policy_code', 'supported_frameworks', 'cloud_providers', 'is_active',
            'is_blocking', 'auto_remediate', 'tags', 'policy_metadata'
        }
        
        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                setattr(policy, key, value)
        
        policy.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(policy)
        
        logger.info(f"Updated policy template {template_id}")
        return policy
    
    def delete_policy(self, template_id: UUID) -> bool:
        """
        Delete policy template.
        
        Args:
            template_id: Policy template UUID
            
        Returns:
            True if deleted, False if not found
        """
        policy = self.get_policy(template_id)
        if not policy:
            logger.warning(f"Policy {template_id} not found for deletion")
            return False
        
        self.db.delete(policy)
        self.db.commit()
        
        logger.info(f"Deleted policy template {template_id}")
        return True
    
    def activate_policy(self, template_id: UUID) -> Optional[PolicyTemplate]:
        """
        Activate a policy template.
        
        Args:
            template_id: Policy template UUID
            
        Returns:
            Updated PolicyTemplate or None
        """
        return self.update_policy(template_id, is_active=True)
    
    def deactivate_policy(self, template_id: UUID) -> Optional[PolicyTemplate]:
        """
        Deactivate a policy template.
        
        Args:
            template_id: Policy template UUID
            
        Returns:
            Updated PolicyTemplate or None
        """
        return self.update_policy(template_id, is_active=False)
    
    def get_active_policies_for_scan(
        self,
        framework: str,
        cloud_provider: str,
        categories: Optional[List[str]] = None
    ) -> List[PolicyTemplate]:
        """
        Get active policies for a scan.
        
        Args:
            framework: IaC framework (e.g., "terraform")
            cloud_provider: Cloud provider (e.g., "aws", "azure")
            categories: Optional list of categories to include
            
        Returns:
            List of active PolicyTemplate instances
        """
        query = self.db.query(PolicyTemplate).filter(
            and_(
                PolicyTemplate.is_active == True,
                PolicyTemplate.supported_frameworks.contains([framework]),
                PolicyTemplate.cloud_providers.contains([cloud_provider])
            )
        )
        
        if categories:
            query = query.filter(PolicyTemplate.policy_category.in_(categories))
        
        query = query.order_by(desc(PolicyTemplate.severity))
        
        return query.all()
    
    def count_policies(
        self,
        *,
        is_active: Optional[bool] = None,
        policy_category: Optional[str] = None,
    ) -> int:
        """
        Count policies with optional filters.
        
        Args:
            is_active: Filter by active status
            policy_category: Filter by category
            
        Returns:
            Count of matching policies
        """
        query = self.db.query(PolicyTemplate)
        
        if is_active is not None:
            query = query.filter(PolicyTemplate.is_active == is_active)
        if policy_category:
            query = query.filter(PolicyTemplate.policy_category == policy_category)
        
        return query.count()
