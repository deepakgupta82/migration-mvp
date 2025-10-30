"""Cost estimation service for infrastructure changes."""

import logging
import json
import subprocess
from typing import Dict, Any, Optional, List
from uuid import UUID
from pathlib import Path

logger = logging.getLogger(__name__)


class CostEstimationError(Exception):
    """Exception raised when cost estimation fails."""
    pass


class CostEstimator:
    """
    Service for estimating infrastructure costs using Infracost.
    
    Provides cost analysis for Terraform plans and helps teams understand
    the financial impact of infrastructure changes before deployment.
    """

    def __init__(self, infracost_api_key: Optional[str] = None):
        """
        Initialize the cost estimator.
        
        Args:
            infracost_api_key: API key for Infracost (optional, uses env var if not provided)
        """
        self.api_key = infracost_api_key
        self.infracost_path = "infracost"  # Assumes infracost is in PATH

    async def estimate_terraform_cost(
        self,
        terraform_dir: Path,
        terraform_plan_file: Optional[Path] = None,
        currency: str = "USD",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Estimate cost for Terraform plan.
        
        Args:
            terraform_dir: Directory containing Terraform configuration
            terraform_plan_file: Optional path to Terraform plan JSON file
            currency: Currency for cost estimation
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Cost estimation result dictionary
            
        Raises:
            CostEstimationError: If cost estimation fails
        """
        logger.info(f"Estimating costs for Terraform directory: {terraform_dir}")
        
        try:
            # Build infracost command
            cmd = [
                self.infracost_path,
                "breakdown",
                "--format", "json",
                "--path", str(terraform_dir),
            ]
            
            # Add plan file if provided
            if terraform_plan_file and terraform_plan_file.exists():
                cmd.extend(["--terraform-plan-flags", str(terraform_plan_file)])
            
            # Execute infracost
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Infracost execution failed: {error_msg}")
                raise CostEstimationError(f"Cost estimation failed: {error_msg}")
            
            # Parse JSON output
            cost_data = json.loads(result.stdout)
            
            # Extract key metrics
            total_monthly_cost = cost_data.get("totalMonthlyCost", "0")
            total_monthly_cost_float = float(total_monthly_cost)
            
            projects = cost_data.get("projects", [])
            
            # Calculate cost breakdown
            breakdown = {
                "total_monthly_cost": total_monthly_cost_float,
                "currency": currency,
                "projects": len(projects),
                "resources": self._count_resources(projects),
                "cost_components": self._extract_cost_components(projects),
                "resource_breakdown": self._extract_resource_breakdown(projects),
            }
            
            logger.info(
                f"Cost estimation complete: ${total_monthly_cost_float:.2f}/{currency}/month"
            )
            
            return {
                "status": "success",
                "cost_estimate": breakdown,
                "raw_data": cost_data,
                "correlation_id": correlation_id,
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Cost estimation timed out")
            raise CostEstimationError("Cost estimation timed out after 5 minutes")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Infracost output: {str(e)}")
            raise CostEstimationError(f"Invalid Infracost output: {str(e)}")
        except Exception as e:
            logger.error(f"Cost estimation error: {str(e)}")
            raise CostEstimationError(f"Cost estimation failed: {str(e)}")

    async def compare_plans(
        self,
        baseline_dir: Path,
        comparison_dir: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare costs between two Terraform configurations.
        
        Args:
            baseline_dir: Directory with baseline configuration
            comparison_dir: Directory with comparison configuration
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Cost comparison result dictionary
        """
        logger.info(f"Comparing costs: {baseline_dir} vs {comparison_dir}")
        
        try:
            # Get cost for baseline
            baseline_result = await self.estimate_terraform_cost(
                terraform_dir=baseline_dir,
                correlation_id=correlation_id,
            )
            
            # Get cost for comparison
            comparison_result = await self.estimate_terraform_cost(
                terraform_dir=comparison_dir,
                correlation_id=correlation_id,
            )
            
            # Calculate difference
            baseline_cost = baseline_result["cost_estimate"]["total_monthly_cost"]
            comparison_cost = comparison_result["cost_estimate"]["total_monthly_cost"]
            
            difference = comparison_cost - baseline_cost
            percentage_change = (
                (difference / baseline_cost * 100) if baseline_cost > 0 else 0
            )
            
            return {
                "status": "success",
                "baseline_cost": baseline_cost,
                "comparison_cost": comparison_cost,
                "difference": difference,
                "percentage_change": round(percentage_change, 2),
                "currency": "USD",
                "baseline_breakdown": baseline_result["cost_estimate"],
                "comparison_breakdown": comparison_result["cost_estimate"],
                "correlation_id": correlation_id,
            }
            
        except Exception as e:
            logger.error(f"Cost comparison error: {str(e)}")
            raise CostEstimationError(f"Cost comparison failed: {str(e)}")

    async def estimate_plan_diff(
        self,
        plan_json_file: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Estimate cost impact of a Terraform plan.
        
        Args:
            plan_json_file: Path to Terraform plan JSON file
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Cost diff result dictionary
        """
        logger.info(f"Estimating cost diff for plan: {plan_json_file}")
        
        try:
            # Build infracost diff command
            cmd = [
                self.infracost_path,
                "diff",
                "--format", "json",
                "--path", str(plan_json_file),
            ]
            
            # Execute infracost
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Infracost diff execution failed: {error_msg}")
                raise CostEstimationError(f"Cost diff failed: {error_msg}")
            
            # Parse JSON output
            diff_data = json.loads(result.stdout)
            
            # Extract diff metrics
            total_monthly_diff = diff_data.get("diffTotalMonthlyCost", "0")
            total_monthly_diff_float = float(total_monthly_diff)
            
            past_total = diff_data.get("pastTotalMonthlyCost", "0")
            past_total_float = float(past_total)
            
            return {
                "status": "success",
                "past_monthly_cost": past_total_float,
                "new_monthly_cost": past_total_float + total_monthly_diff_float,
                "monthly_diff": total_monthly_diff_float,
                "percentage_change": self._calculate_percentage_change(
                    past_total_float, total_monthly_diff_float
                ),
                "currency": "USD",
                "raw_diff_data": diff_data,
                "correlation_id": correlation_id,
            }
            
        except Exception as e:
            logger.error(f"Cost diff estimation error: {str(e)}")
            raise CostEstimationError(f"Cost diff failed: {str(e)}")

    def _count_resources(self, projects: List[Dict]) -> int:
        """Count total resources across all projects."""
        total = 0
        for project in projects:
            breakdown = project.get("breakdown", {})
            resources = breakdown.get("resources", [])
            total += len(resources)
        return total

    def _extract_cost_components(self, projects: List[Dict]) -> List[Dict[str, Any]]:
        """Extract cost components from projects."""
        components = []
        
        for project in projects:
            breakdown = project.get("breakdown", {})
            resources = breakdown.get("resources", [])
            
            for resource in resources:
                cost_components = resource.get("costComponents", [])
                for component in cost_components:
                    components.append({
                        "resource": resource.get("name"),
                        "component": component.get("name"),
                        "monthly_cost": float(component.get("monthlyCost", "0")),
                        "unit": component.get("unit"),
                    })
        
        return components

    def _extract_resource_breakdown(self, projects: List[Dict]) -> List[Dict[str, Any]]:
        """Extract per-resource cost breakdown."""
        breakdown = []
        
        for project in projects:
            project_breakdown = project.get("breakdown", {})
            resources = project_breakdown.get("resources", [])
            
            for resource in resources:
                monthly_cost = float(resource.get("monthlyCost", "0"))
                
                breakdown.append({
                    "resource_type": resource.get("resourceType"),
                    "resource_name": resource.get("name"),
                    "monthly_cost": monthly_cost,
                    "cost_components_count": len(resource.get("costComponents", [])),
                })
        
        # Sort by cost descending
        breakdown.sort(key=lambda x: x["monthly_cost"], reverse=True)
        
        return breakdown

    def _calculate_percentage_change(
        self,
        baseline: float,
        diff: float
    ) -> float:
        """Calculate percentage change."""
        if baseline == 0:
            return 100.0 if diff > 0 else 0.0
        return round((diff / baseline * 100), 2)

    async def get_cost_summary(
        self,
        terraform_dir: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get a simplified cost summary for a Terraform configuration.
        
        Args:
            terraform_dir: Directory containing Terraform configuration
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Simplified cost summary
        """
        logger.info(f"Getting cost summary for: {terraform_dir}")
        
        result = await self.estimate_terraform_cost(
            terraform_dir=terraform_dir,
            correlation_id=correlation_id,
        )
        
        cost_estimate = result["cost_estimate"]
        
        # Sort resources by cost
        resources = cost_estimate.get("resource_breakdown", [])
        top_resources = resources[:10]  # Top 10 most expensive
        
        return {
            "total_monthly_cost": cost_estimate["total_monthly_cost"],
            "currency": cost_estimate["currency"],
            "total_resources": cost_estimate["resources"],
            "top_cost_resources": top_resources,
            "cost_by_category": self._categorize_costs(resources),
        }

    def _categorize_costs(self, resources: List[Dict]) -> Dict[str, float]:
        """Categorize costs by resource type."""
        categories = {}
        
        for resource in resources:
            resource_type = resource["resource_type"]
            monthly_cost = resource["monthly_cost"]
            
            # Extract category from resource type (e.g., aws_instance -> compute)
            category = self._get_resource_category(resource_type)
            
            if category not in categories:
                categories[category] = 0.0
            
            categories[category] += monthly_cost
        
        # Sort by cost
        sorted_categories = dict(
            sorted(categories.items(), key=lambda x: x[1], reverse=True)
        )
        
        return sorted_categories

    def _get_resource_category(self, resource_type: str) -> str:
        """Determine resource category from type."""
        # Simple categorization - can be enhanced
        if any(x in resource_type.lower() for x in ["instance", "vm", "compute"]):
            return "compute"
        elif any(x in resource_type.lower() for x in ["storage", "bucket", "disk", "volume"]):
            return "storage"
        elif any(x in resource_type.lower() for x in ["database", "db", "rds", "sql"]):
            return "database"
        elif any(x in resource_type.lower() for x in ["network", "vpc", "subnet", "gateway"]):
            return "networking"
        elif any(x in resource_type.lower() for x in ["load_balancer", "lb", "alb", "elb"]):
            return "load_balancing"
        else:
            return "other"
