"""
Scan Executor Service

Orchestrates IAC policy scans: Terraform plan → OPA evaluation → violation tracking.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services import OPAClient, OPAException
from app.adapters import TerraformMCPAdapter
from app.repository import ScanRepository, PolicyRepository
from app.models import ScanStatus, PolicySeverity

logger = logging.getLogger("scan-executor")


class ScanExecutionError(Exception):
    """Exception raised for scan execution errors."""
    pass


class ScanExecutor:
    """Orchestrates IAC policy scan execution."""
    
    def __init__(
        self,
        db: Session,
        opa_client: Optional[OPAClient] = None,
        terraform_adapter: Optional[TerraformMCPAdapter] = None
    ):
        """
        Initialize scan executor.
        
        Args:
            db: Database session
            opa_client: Optional OPA client instance
            terraform_adapter: Optional Terraform adapter instance
        """
        self.db = db
        self.scan_repo = ScanRepository(db)
        self.policy_repo = PolicyRepository(db)
        self.opa_client = opa_client or OPAClient()
        self.terraform_adapter = terraform_adapter or TerraformMCPAdapter()
    
    async def execute_scan(
        self,
        scan_id: UUID,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute complete IAC policy scan.
        
        Workflow:
        1. Get scan configuration
        2. Run Terraform plan
        3. Upload policies to OPA
        4. Evaluate plan against policies
        5. Parse violations
        6. Update scan results
        
        Args:
            scan_id: Scan UUID
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Scan execution results
            
        Raises:
            ScanExecutionError: If scan execution fails
        """
        logger.info(f"Starting scan execution {scan_id} (correlation={correlation_id})")
        
        # Get scan details
        scan = self.scan_repo.get_scan(scan_id)
        if not scan:
            raise ScanExecutionError(f"Scan {scan_id} not found")
        
        start_time = datetime.utcnow()
        
        try:
            # Update scan status to running
            self.scan_repo.update_scan_status(
                scan_id,
                ScanStatus.RUNNING,
                started_at=start_time
            )
            
            # Step 1: Run Terraform plan
            logger.info(f"Step 1: Running Terraform plan for scan {scan_id}")
            plan_result = await self._run_terraform_plan(scan, correlation_id)
            
            # Step 2: Get active policies
            logger.info(f"Step 2: Getting active policies for scan {scan_id}")
            policies = self._get_active_policies(scan)
            
            if not policies:
                logger.warning(f"No active policies found for scan {scan_id}")
                # Mark scan as completed with no violations
                self.scan_repo.update_scan_status(
                    scan_id,
                    ScanStatus.COMPLETED,
                    completed_at=datetime.utcnow(),
                    duration_seconds=int((datetime.utcnow() - start_time).total_seconds())
                )
                return {
                    "scan_id": str(scan_id),
                    "status": "completed",
                    "violations": [],
                    "message": "No active policies to evaluate"
                }
            
            # Step 3: Upload policies to OPA
            logger.info(f"Step 3: Uploading {len(policies)} policies to OPA")
            await self._upload_policies_to_opa(policies, correlation_id)
            
            # Step 4: Evaluate plan against policies
            logger.info(f"Step 4: Evaluating Terraform plan against policies")
            violations = await self._evaluate_policies(
                scan,
                plan_result,
                policies,
                correlation_id
            )
            
            # Step 5: Store violations
            logger.info(f"Step 5: Storing {len(violations)} violations")
            if violations:
                self.scan_repo.bulk_create_violations(scan_id, violations)
            
            # Step 6: Update scan results
            logger.info(f"Step 6: Updating scan results")
            violation_counts = self._count_violations_by_severity(violations)
            
            self.scan_repo.update_scan_results(
                scan_id,
                total_resources=len(plan_result.get("resource_changes", [])),
                passed_checks=len(plan_result.get("resource_changes", [])) - len(violations),
                failed_checks=len(violations),
                violations_critical=violation_counts["CRITICAL"],
                violations_high=violation_counts["HIGH"],
                violations_medium=violation_counts["MEDIUM"],
                violations_low=violation_counts["LOW"],
                violations_info=violation_counts["INFO"],
            )
            
            # Mark scan as completed
            end_time = datetime.utcnow()
            self.scan_repo.update_scan_status(
                scan_id,
                ScanStatus.COMPLETED,
                completed_at=end_time,
                duration_seconds=int((end_time - start_time).total_seconds())
            )
            
            logger.info(f"Scan {scan_id} completed successfully with {len(violations)} violations")
            
            return {
                "scan_id": str(scan_id),
                "status": "completed",
                "total_resources": len(plan_result.get("resource_changes", [])),
                "violations_count": len(violations),
                "violations_by_severity": violation_counts,
                "duration_seconds": int((end_time - start_time).total_seconds())
            }
            
        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {str(e)}", exc_info=True)
            
            # Mark scan as failed
            self.scan_repo.update_scan_status(
                scan_id,
                ScanStatus.FAILED,
                completed_at=datetime.utcnow(),
                duration_seconds=int((datetime.utcnow() - start_time).total_seconds()),
                error_message=str(e),
                error_details={"exception": type(e).__name__}
            )
            
            raise ScanExecutionError(f"Scan execution failed: {str(e)}") from e
    
    async def _run_terraform_plan(
        self,
        scan: Any,
        correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Run Terraform plan for the scan.
        
        Args:
            scan: PolicyScan instance
            correlation_id: Correlation ID
            
        Returns:
            Terraform plan result
        """
        try:
            # Get scan configuration
            scan_config = scan.scan_config or {}
            
            # Run Terraform plan
            plan_result = await self.terraform_adapter.plan(
                workspace_path=scan.source_location,
                workspace_name=scan_config.get("workspace_name"),
                var_file=scan_config.get("var_file"),
                variables=scan_config.get("variables", {}),
                correlation_id=correlation_id
            )
            
            return plan_result
            
        except Exception as e:
            logger.error(f"Terraform plan failed: {str(e)}")
            raise ScanExecutionError(f"Terraform plan failed: {str(e)}") from e
    
    def _get_active_policies(self, scan: Any) -> List[Any]:
        """
        Get active policies for the scan.
        
        Args:
            scan: PolicyScan instance
            
        Returns:
            List of active PolicyTemplate instances
        """
        scan_config = scan.scan_config or {}
        
        # Get policies for framework and cloud provider
        policies = self.policy_repo.get_active_policies_for_scan(
            framework=scan.iac_framework,
            cloud_provider=scan_config.get("cloud_provider", "aws"),
            categories=scan_config.get("policy_categories")
        )
        
        return policies
    
    async def _upload_policies_to_opa(
        self,
        policies: List[Any],
        correlation_id: Optional[str]
    ) -> None:
        """
        Upload policies to OPA.
        
        Args:
            policies: List of PolicyTemplate instances
            correlation_id: Correlation ID
        """
        for policy in policies:
            try:
                # Generate policy name from template
                policy_name = f"policy_{policy.template_id}".replace("-", "_")
                
                # Upload policy code to OPA
                await self.opa_client.upload_policy(
                    policy_name=policy_name,
                    policy_code=policy.policy_code,
                    correlation_id=correlation_id
                )
                
                logger.debug(f"Uploaded policy {policy.template_name} to OPA")
                
            except OPAException as e:
                logger.error(f"Failed to upload policy {policy.template_name}: {str(e)}")
                # Continue with other policies
    
    async def _evaluate_policies(
        self,
        scan: Any,
        plan_result: Dict[str, Any],
        policies: List[Any],
        correlation_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate Terraform plan against policies.
        
        Args:
            scan: PolicyScan instance
            plan_result: Terraform plan result
            policies: List of PolicyTemplate instances
            correlation_id: Correlation ID
            
        Returns:
            List of violation dictionaries
        """
        all_violations = []
        
        # Prepare input data for OPA
        resource_changes = plan_result.get("resource_changes", [])
        
        for policy in policies:
            try:
                # Generate policy path
                policy_name = f"policy_{policy.template_id}".replace("-", "_")
                policy_path = f"{policy_name}/deny"
                
                # Evaluate each resource change against the policy
                for resource in resource_changes:
                    input_data = {
                        "resource": resource,
                        "plan": plan_result,
                        "scan_config": scan.scan_config or {}
                    }
                    
                    try:
                        # Evaluate policy
                        result = await self.opa_client.evaluate_policy(
                            policy_path=policy_path,
                            input_data=input_data,
                            correlation_id=correlation_id
                        )
                        
                        # Parse violations from result
                        resource_context = {
                            "type": resource.get("type"),
                            "name": resource.get("name"),
                            "address": resource.get("address")
                        }
                        
                        violations = self.opa_client.parse_violations(
                            result,
                            resource_context
                        )
                        
                        # Add policy template ID to each violation
                        for viol in violations:
                            viol["template_id"] = policy.template_id
                            viol["scan_id"] = scan.scan_id
                            
                            # Ensure severity is enum
                            if isinstance(viol.get("severity"), str):
                                try:
                                    viol["severity"] = PolicySeverity[viol["severity"]]
                                except KeyError:
                                    viol["severity"] = policy.severity
                            else:
                                viol["severity"] = policy.severity
                        
                        all_violations.extend(violations)
                        
                    except OPAException as e:
                        logger.warning(f"Policy evaluation failed for {policy.template_name}: {str(e)}")
                        # Continue with other resources
                
            except Exception as e:
                logger.error(f"Error evaluating policy {policy.template_name}: {str(e)}")
                # Continue with other policies
        
        return all_violations
    
    def _count_violations_by_severity(
        self,
        violations: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Count violations by severity.
        
        Args:
            violations: List of violation dictionaries
            
        Returns:
            Dictionary with counts by severity
        """
        counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        
        for viol in violations:
            severity = viol.get("severity")
            if isinstance(severity, PolicySeverity):
                counts[severity.value] += 1
            elif isinstance(severity, str):
                counts[severity.upper()] = counts.get(severity.upper(), 0) + 1
        
        return counts
