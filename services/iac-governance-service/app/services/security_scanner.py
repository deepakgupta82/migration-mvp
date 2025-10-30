"""Security scanning service for infrastructure-as-code."""

import logging
import json
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path
from uuid import UUID

from app.models.database import PolicySeverity

logger = logging.getLogger(__name__)


class SecurityScanError(Exception):
    """Exception raised when security scanning fails."""
    pass


class SecurityScanner:
    """
    Service for security scanning of infrastructure-as-code using Checkov.
    
    Provides comprehensive security, compliance, and best practice scanning
    for Terraform, CloudFormation, and other IaC frameworks.
    """

    def __init__(self):
        """Initialize the security scanner."""
        self.checkov_path = "checkov"  # Assumes checkov is in PATH
        self.tfsec_path = "tfsec"  # Optional: tfsec for Terraform-specific scans

    async def scan_terraform_directory(
        self,
        terraform_dir: Path,
        framework: str = "terraform",
        check_ids: Optional[List[str]] = None,
        skip_checks: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan Terraform directory for security issues using Checkov.
        
        Args:
            terraform_dir: Directory containing Terraform configuration
            framework: IAC framework (terraform, cloudformation, etc.)
            check_ids: Optional list of specific check IDs to run
            skip_checks: Optional list of check IDs to skip
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Security scan result dictionary
            
        Raises:
            SecurityScanError: If security scan fails
        """
        logger.info(f"Starting security scan for directory: {terraform_dir}")
        
        try:
            # Build checkov command
            cmd = [
                self.checkov_path,
                "--framework", framework,
                "--directory", str(terraform_dir),
                "--output", "json",
                "--quiet",  # Suppress progress output
            ]
            
            # Add check filters if specified
            if check_ids:
                cmd.extend(["--check", ",".join(check_ids)])
            
            if skip_checks:
                cmd.extend(["--skip-check", ",".join(skip_checks)])
            
            # Execute checkov
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            
            # Checkov returns non-zero exit code when it finds issues
            # This is expected, so we don't fail on non-zero exit
            
            # Parse JSON output
            try:
                scan_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                # If stdout is not JSON, try stderr
                if result.stderr:
                    logger.error(f"Checkov error output: {result.stderr}")
                    raise SecurityScanError(f"Checkov scan failed: {result.stderr}")
                raise SecurityScanError("Failed to parse Checkov output")
            
            # Process results
            processed_results = self._process_checkov_results(scan_data)
            
            # Add metadata
            processed_results["correlation_id"] = correlation_id
            processed_results["framework"] = framework
            processed_results["scan_directory"] = str(terraform_dir)
            
            logger.info(
                f"Security scan complete: {processed_results['summary']['total_checks']} checks, "
                f"{processed_results['summary']['passed_checks']} passed, "
                f"{processed_results['summary']['failed_checks']} failed"
            )
            
            return processed_results
            
        except subprocess.TimeoutExpired:
            logger.error("Security scan timed out")
            raise SecurityScanError("Security scan timed out after 10 minutes")
        except Exception as e:
            logger.error(f"Security scan error: {str(e)}")
            raise SecurityScanError(f"Security scan failed: {str(e)}")

    async def scan_terraform_plan(
        self,
        plan_file: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan Terraform plan file for security issues.
        
        Args:
            plan_file: Path to Terraform plan JSON file
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Security scan result dictionary
        """
        logger.info(f"Starting security scan for plan file: {plan_file}")
        
        try:
            # Build checkov command for plan file
            cmd = [
                self.checkov_path,
                "--framework", "terraform_plan",
                "--file", str(plan_file),
                "--output", "json",
                "--quiet",
            ]
            
            # Execute checkov
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            # Parse JSON output
            try:
                scan_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                if result.stderr:
                    logger.error(f"Checkov error output: {result.stderr}")
                    raise SecurityScanError(f"Plan scan failed: {result.stderr}")
                raise SecurityScanError("Failed to parse Checkov output")
            
            # Process results
            processed_results = self._process_checkov_results(scan_data)
            processed_results["correlation_id"] = correlation_id
            processed_results["framework"] = "terraform_plan"
            processed_results["plan_file"] = str(plan_file)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Plan security scan error: {str(e)}")
            raise SecurityScanError(f"Plan security scan failed: {str(e)}")

    async def scan_with_tfsec(
        self,
        terraform_dir: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan Terraform directory using tfsec (Terraform-specific scanner).
        
        Args:
            terraform_dir: Directory containing Terraform configuration
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            tfsec scan result dictionary
        """
        logger.info(f"Starting tfsec scan for directory: {terraform_dir}")
        
        try:
            # Build tfsec command
            cmd = [
                self.tfsec_path,
                str(terraform_dir),
                "--format", "json",
                "--no-color",
            ]
            
            # Execute tfsec
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            # Parse JSON output
            try:
                scan_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                if result.stderr:
                    logger.error(f"tfsec error output: {result.stderr}")
                    raise SecurityScanError(f"tfsec scan failed: {result.stderr}")
                raise SecurityScanError("Failed to parse tfsec output")
            
            # Process tfsec results
            processed_results = self._process_tfsec_results(scan_data)
            processed_results["correlation_id"] = correlation_id
            processed_results["scanner"] = "tfsec"
            processed_results["scan_directory"] = str(terraform_dir)
            
            return processed_results
            
        except FileNotFoundError:
            logger.warning("tfsec not found, skipping tfsec scan")
            raise SecurityScanError("tfsec CLI not found in PATH")
        except Exception as e:
            logger.error(f"tfsec scan error: {str(e)}")
            raise SecurityScanError(f"tfsec scan failed: {str(e)}")

    def _process_checkov_results(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Checkov scan results into standardized format."""
        results = scan_data.get("results", {})
        
        # Extract check results
        passed_checks = results.get("passed_checks", [])
        failed_checks = results.get("failed_checks", [])
        skipped_checks = results.get("skipped_checks", [])
        
        # Count by severity
        severity_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        
        # Process failed checks
        violations = []
        for check in failed_checks:
            severity = self._map_checkov_severity(check.get("check_class", ""))
            severity_counts[severity] += 1
            
            violations.append({
                "check_id": check.get("check_id"),
                "check_name": check.get("check_name"),
                "severity": severity,
                "resource": check.get("resource"),
                "file_path": check.get("file_path"),
                "file_line_range": check.get("file_line_range", []),
                "description": check.get("description", ""),
                "guideline": check.get("guideline", ""),
                "fixed_definition": check.get("fixed_definition"),
            })
        
        return {
            "status": "completed",
            "summary": {
                "total_checks": len(passed_checks) + len(failed_checks),
                "passed_checks": len(passed_checks),
                "failed_checks": len(failed_checks),
                "skipped_checks": len(skipped_checks),
                "severity_counts": severity_counts,
            },
            "violations": violations,
            "passed_checks": [
                {
                    "check_id": c.get("check_id"),
                    "check_name": c.get("check_name"),
                    "resource": c.get("resource"),
                }
                for c in passed_checks
            ],
        }

    def _process_tfsec_results(self, scan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process tfsec scan results into standardized format."""
        results = scan_data.get("results", [])
        
        # Count by severity
        severity_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }
        
        # Process findings
        violations = []
        for finding in results:
            severity = finding.get("severity", "MEDIUM").upper()
            if severity not in severity_counts:
                severity = "MEDIUM"
            
            severity_counts[severity] += 1
            
            violations.append({
                "check_id": finding.get("rule_id"),
                "check_name": finding.get("rule_description"),
                "severity": severity,
                "resource": finding.get("resource"),
                "file_path": finding.get("location", {}).get("filename"),
                "file_line_range": [
                    finding.get("location", {}).get("start_line"),
                    finding.get("location", {}).get("end_line"),
                ],
                "description": finding.get("description", ""),
                "links": finding.get("links", []),
            })
        
        return {
            "status": "completed",
            "summary": {
                "total_findings": len(results),
                "severity_counts": severity_counts,
            },
            "violations": violations,
        }

    def _map_checkov_severity(self, check_class: str) -> str:
        """Map Checkov check class to severity level."""
        # Checkov doesn't have built-in severity, so we map based on check class
        check_class_lower = check_class.lower()
        
        if any(x in check_class_lower for x in ["critical", "encryption", "public"]):
            return "CRITICAL"
        elif any(x in check_class_lower for x in ["high", "iam", "security"]):
            return "HIGH"
        elif any(x in check_class_lower for x in ["medium", "logging", "monitoring"]):
            return "MEDIUM"
        elif any(x in check_class_lower for x in ["low", "tagging", "naming"]):
            return "LOW"
        else:
            return "INFO"

    async def combined_scan(
        self,
        terraform_dir: Path,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run both Checkov and tfsec scans and combine results.
        
        Args:
            terraform_dir: Directory containing Terraform configuration
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Combined scan results
        """
        logger.info(f"Running combined security scan for: {terraform_dir}")
        
        results = {
            "correlation_id": correlation_id,
            "scan_directory": str(terraform_dir),
            "scanners_used": [],
        }
        
        # Run Checkov scan
        try:
            checkov_results = await self.scan_terraform_directory(
                terraform_dir=terraform_dir,
                correlation_id=correlation_id,
            )
            results["checkov"] = checkov_results
            results["scanners_used"].append("checkov")
        except SecurityScanError as e:
            logger.warning(f"Checkov scan failed: {str(e)}")
            results["checkov"] = {"status": "failed", "error": str(e)}
        
        # Run tfsec scan
        try:
            tfsec_results = await self.scan_with_tfsec(
                terraform_dir=terraform_dir,
                correlation_id=correlation_id,
            )
            results["tfsec"] = tfsec_results
            results["scanners_used"].append("tfsec")
        except SecurityScanError as e:
            logger.warning(f"tfsec scan failed: {str(e)}")
            results["tfsec"] = {"status": "failed", "error": str(e)}
        
        # Combine statistics
        results["combined_summary"] = self._combine_scan_summaries(results)
        
        return results

    def _combine_scan_summaries(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine summaries from multiple scanners."""
        combined = {
            "total_violations": 0,
            "severity_counts": {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "INFO": 0,
            },
            "scanners_successful": len(results.get("scanners_used", [])),
        }
        
        # Combine Checkov results
        if "checkov" in results and results["checkov"].get("status") == "completed":
            checkov_summary = results["checkov"]["summary"]
            combined["total_violations"] += checkov_summary["failed_checks"]
            for severity, count in checkov_summary["severity_counts"].items():
                combined["severity_counts"][severity] += count
        
        # Combine tfsec results
        if "tfsec" in results and results["tfsec"].get("status") == "completed":
            tfsec_summary = results["tfsec"]["summary"]
            combined["total_violations"] += tfsec_summary["total_findings"]
            for severity, count in tfsec_summary["severity_counts"].items():
                combined["severity_counts"][severity] += count
        
        return combined
