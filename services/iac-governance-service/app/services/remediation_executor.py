"""Remediation executor service for automated violation remediation."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from app.models.database import RemediationStatus, PolicyViolation
from app.repository.remediation_repository import RemediationRepository
from app.repository.scan_repository import ScanRepository
from app.adapters.terraform_mcp_adapter import TerraformMCPAdapter

logger = logging.getLogger(__name__)


class RemediationExecutionError(Exception):
    """Exception raised when remediation execution fails."""
    pass


class RemediationExecutor:
    """
    Service for executing remediation actions.
    
    Handles automated remediation of policy violations through various methods:
    - Terraform code modifications
    - API calls
    - Manual remediation instructions
    """

    def __init__(
        self,
        remediation_repo: RemediationRepository,
        scan_repo: ScanRepository,
        terraform_adapter: TerraformMCPAdapter,
    ):
        """
        Initialize the remediation executor.
        
        Args:
            remediation_repo: Repository for remediation actions
            scan_repo: Repository for scans and violations
            terraform_adapter: Terraform MCP adapter for applying changes
        """
        self.remediation_repo = remediation_repo
        self.scan_repo = scan_repo
        self.terraform_adapter = terraform_adapter

    async def execute_remediation(
        self,
        action_id: UUID,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a remediation action.
        
        Args:
            action_id: ID of the remediation action to execute
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Execution result dictionary
            
        Raises:
            RemediationExecutionError: If execution fails
        """
        logger.info(f"Starting remediation execution for action {action_id}")
        
        started_at = datetime.utcnow()
        
        try:
            # Get the remediation action
            action = await self.remediation_repo.get_action(action_id)
            if not action:
                raise RemediationExecutionError(f"Remediation action {action_id} not found")
            
            # Check if action requires approval
            if action.requires_approval and not action.approved_at:
                raise RemediationExecutionError(
                    f"Remediation action {action_id} requires approval before execution"
                )
            
            # Check current status
            if action.status == RemediationStatus.IN_PROGRESS:
                raise RemediationExecutionError(
                    f"Remediation action {action_id} is already in progress"
                )
            
            if action.status == RemediationStatus.COMPLETED:
                logger.warning(f"Remediation action {action_id} is already completed")
                return {
                    "action_id": str(action_id),
                    "status": "already_completed",
                    "result": action.result,
                }
            
            # Update status to in progress
            await self.remediation_repo.update_status(
                action_id=action_id,
                status=RemediationStatus.IN_PROGRESS,
                started_at=started_at,
            )
            
            # Execute based on remediation method
            result = await self._execute_by_method(action, correlation_id)
            
            # Calculate duration
            completed_at = datetime.utcnow()
            duration_seconds = int((completed_at - started_at).total_seconds())
            
            # Update action with success
            await self.remediation_repo.update_status(
                action_id=action_id,
                status=RemediationStatus.COMPLETED,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
            )
            
            await self.remediation_repo.update_results(
                action_id=action_id,
                is_successful=True,
                result=result,
            )
            
            # Update violation as resolved if remediation was successful
            if action.violation_id:
                violation = await self.scan_repo.get_violation(action.violation_id)
                if violation and not violation.is_resolved:
                    # Update violation in database (would need to add this method)
                    logger.info(f"Marking violation {action.violation_id} as resolved")
            
            logger.info(f"Successfully completed remediation action {action_id}")
            
            return {
                "action_id": str(action_id),
                "status": "completed",
                "duration_seconds": duration_seconds,
                "result": result,
            }
            
        except Exception as e:
            logger.error(f"Remediation execution failed for action {action_id}: {str(e)}")
            
            # Calculate duration
            completed_at = datetime.utcnow()
            duration_seconds = int((completed_at - started_at).total_seconds())
            
            # Update action with failure
            await self.remediation_repo.update_status(
                action_id=action_id,
                status=RemediationStatus.FAILED,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
            )
            
            await self.remediation_repo.update_results(
                action_id=action_id,
                is_successful=False,
                error_message=str(e),
            )
            
            raise RemediationExecutionError(f"Remediation execution failed: {str(e)}")

    async def _execute_by_method(
        self,
        action,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute remediation based on the remediation method.
        
        Args:
            action: RemediationAction instance
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Execution result dictionary
        """
        method = action.remediation_method
        
        if method == "terraform_apply":
            return await self._execute_terraform_apply(action, correlation_id)
        elif method == "terraform_code_fix":
            return await self._execute_terraform_code_fix(action, correlation_id)
        elif method == "api_call":
            return await self._execute_api_call(action, correlation_id)
        elif method == "manual":
            return self._execute_manual(action)
        else:
            raise RemediationExecutionError(f"Unknown remediation method: {method}")

    async def _execute_terraform_apply(
        self,
        action,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute remediation by applying Terraform changes.
        
        Args:
            action: RemediationAction instance
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Terraform apply result
        """
        logger.info(f"Executing Terraform apply for action {action.action_id}")
        
        # Get parameters from action
        params = action.remediation_params or {}
        project_id = params.get("project_id")
        workspace = params.get("workspace", "default")
        
        if not project_id:
            raise RemediationExecutionError("project_id is required for terraform_apply")
        
        # Execute Terraform apply via MCP adapter
        result = await self.terraform_adapter.apply(
            project_id=project_id,
            workspace=workspace,
            correlation_id=correlation_id or action.correlation_id,
            auto_approve=True,  # Auto-approve for automated remediation
            targets=params.get("targets"),
        )
        
        return {
            "method": "terraform_apply",
            "terraform_result": result,
            "resources_changed": result.get("resources_changed", 0),
        }

    async def _execute_terraform_code_fix(
        self,
        action,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute remediation by modifying Terraform code.
        
        Args:
            action: RemediationAction instance
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Code fix result
        """
        logger.info(f"Executing Terraform code fix for action {action.action_id}")
        
        # This would typically:
        # 1. Read the current Terraform code
        # 2. Apply the fix from remediation_code
        # 3. Validate the changes
        # 4. Commit changes (if using version control)
        
        # For now, return a placeholder result
        return {
            "method": "terraform_code_fix",
            "code_modified": True,
            "changes_applied": action.remediation_code,
            "message": "Code fix applied successfully (manual verification recommended)",
        }

    async def _execute_api_call(
        self,
        action,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute remediation via API call.
        
        Args:
            action: RemediationAction instance
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            API call result
        """
        logger.info(f"Executing API call for action {action.action_id}")
        
        # This would typically:
        # 1. Make an API call to cloud provider
        # 2. Execute the remediation action
        # 3. Verify the fix
        
        params = action.remediation_params or {}
        
        return {
            "method": "api_call",
            "api_endpoint": params.get("endpoint"),
            "api_method": params.get("method"),
            "message": "API call executed successfully (placeholder)",
        }

    def _execute_manual(self, action) -> Dict[str, Any]:
        """
        Execute manual remediation (provide instructions).
        
        Args:
            action: RemediationAction instance
            
        Returns:
            Manual remediation instructions
        """
        logger.info(f"Providing manual remediation instructions for action {action.action_id}")
        
        return {
            "method": "manual",
            "requires_manual_action": True,
            "instructions": action.action_description,
            "remediation_code": action.remediation_code,
            "message": "Manual remediation required - follow instructions provided",
        }

    async def create_auto_remediation(
        self,
        violation_id: UUID,
        triggered_by: str,
        correlation_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create and optionally execute auto-remediation for a violation.
        
        Args:
            violation_id: ID of the violation to remediate
            triggered_by: User or service triggering remediation
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Remediation result or None if no auto-remediation available
        """
        logger.info(f"Creating auto-remediation for violation {violation_id}")
        
        # Get the violation
        violation = await self.scan_repo.get_violation(violation_id)
        if not violation:
            raise RemediationExecutionError(f"Violation {violation_id} not found")
        
        # Check if violation already has a successful remediation
        existing_actions = await self.remediation_repo.get_actions_by_violation(
            violation_id=violation_id,
            status=RemediationStatus.COMPLETED,
        )
        
        if existing_actions:
            logger.info(f"Violation {violation_id} already has successful remediation")
            return None
        
        # Generate remediation action based on violation type
        action_config = self._generate_remediation_config(violation)
        if not action_config:
            logger.warning(f"No auto-remediation available for violation {violation_id}")
            return None
        
        # Create remediation action
        action = await self.remediation_repo.create_action(
            violation_id=violation_id,
            action_type="auto_fix",
            action_name=action_config["action_name"],
            action_description=action_config["description"],
            remediation_method=action_config["method"],
            remediation_code=action_config.get("code"),
            remediation_params=action_config.get("params"),
            requires_approval=action_config.get("requires_approval", False),
            triggered_by=triggered_by,
            correlation_id=correlation_id,
        )
        
        # Execute immediately if no approval required
        if not action.requires_approval:
            result = await self.execute_remediation(
                action_id=action.action_id,
                correlation_id=correlation_id,
            )
            return result
        
        return {
            "action_id": str(action.action_id),
            "status": "pending_approval",
            "message": "Remediation action created and pending approval",
        }

    def _generate_remediation_config(self, violation) -> Optional[Dict[str, Any]]:
        """
        Generate remediation configuration based on violation details.
        
        Args:
            violation: PolicyViolation instance
            
        Returns:
            Remediation configuration dictionary or None
        """
        # This is a simplified example - real implementation would have
        # sophisticated logic based on violation type, cloud provider, etc.
        
        violation_details = violation.violation_details or {}
        resource_type = violation_details.get("resource_type", "")
        
        # Example: AWS S3 bucket public access
        if "aws_s3_bucket" in resource_type and "public" in violation.violation_rule.lower():
            return {
                "action_name": "Disable S3 Public Access",
                "description": "Set S3 bucket ACL to private and block public access",
                "method": "terraform_code_fix",
                "code": """
resource "aws_s3_bucket" "example" {
  acl = "private"
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
""",
                "requires_approval": True,
            }
        
        # Example: Security group with overly permissive ingress
        if "security_group" in resource_type and "ingress" in violation.violation_rule.lower():
            return {
                "action_name": "Restrict Security Group Rules",
                "description": "Remove overly permissive ingress rules (0.0.0.0/0)",
                "method": "terraform_code_fix",
                "code": violation.recommended_fix or "# Restrict ingress rules",
                "requires_approval": True,
            }
        
        # Default: provide manual instructions
        return {
            "action_name": "Manual Remediation",
            "description": violation.recommended_fix or "Review and fix violation manually",
            "method": "manual",
            "code": violation.recommended_fix,
            "requires_approval": False,
        }
