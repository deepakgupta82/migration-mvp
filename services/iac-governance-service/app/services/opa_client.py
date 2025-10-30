"""
OPA Policy Engine Client

HTTP client for Open Policy Agent REST API.
Handles policy evaluation, data upload, and query execution.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import httpx
from httpx import AsyncClient, Response

logger = logging.getLogger("opa-client")


class OPAException(Exception):
    """Exception raised for OPA-related errors."""
    pass


class OPAClient:
    """Client for Open Policy Agent REST API."""
    
    def __init__(self, opa_url: str = "http://localhost:8181"):
        """
        Initialize OPA client.
        
        Args:
            opa_url: Base URL for OPA server (default: http://localhost:8181)
        """
        self.opa_url = opa_url.rstrip('/')
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        
        logger.info(f"OPA client initialized with URL: {self.opa_url}")
    
    async def health_check(self) -> bool:
        """
        Check OPA server health.
        
        Returns:
            True if OPA is healthy, False otherwise
        """
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.opa_url}/health")
                
                if response.status_code == 200:
                    logger.info("OPA health check passed")
                    return True
                else:
                    logger.warning(f"OPA health check failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"OPA health check error: {str(e)}")
            return False
    
    async def upload_policy(
        self,
        policy_name: str,
        policy_code: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Upload a policy to OPA.
        
        Args:
            policy_name: Name/ID of the policy (e.g., "terraform_aws_security")
            policy_code: Rego policy code
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            True if successful
            
        Raises:
            OPAException: If upload fails
        """
        url = f"{self.opa_url}/v1/policies/{policy_name}"
        
        headers = {
            "Content-Type": "text/plain",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    url,
                    content=policy_code,
                    headers=headers
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully uploaded policy '{policy_name}'")
                    return True
                else:
                    error_msg = f"Failed to upload policy '{policy_name}': {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error uploading policy '{policy_name}': {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    async def delete_policy(
        self,
        policy_name: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Delete a policy from OPA.
        
        Args:
            policy_name: Name/ID of the policy to delete
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            True if successful
            
        Raises:
            OPAException: If deletion fails
        """
        url = f"{self.opa_url}/v1/policies/{policy_name}"
        
        headers = {}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=headers)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully deleted policy '{policy_name}'")
                    return True
                else:
                    error_msg = f"Failed to delete policy '{policy_name}': {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error deleting policy '{policy_name}': {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    async def upload_data(
        self,
        data_path: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Upload data to OPA.
        
        Args:
            data_path: Path in OPA data document (e.g., "terraform/resources")
            data: Data to upload
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            True if successful
            
        Raises:
            OPAException: If upload fails
        """
        url = f"{self.opa_url}/v1/data/{data_path}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    url,
                    json=data,
                    headers=headers
                )
                
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully uploaded data to '{data_path}'")
                    return True
                else:
                    error_msg = f"Failed to upload data to '{data_path}': {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error uploading data to '{data_path}': {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    async def evaluate_policy(
        self,
        policy_path: str,
        input_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a policy with input data.
        
        Args:
            policy_path: Path to policy decision (e.g., "terraform/aws/security/deny")
            input_data: Input data for policy evaluation
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Policy evaluation result
            
        Raises:
            OPAException: If evaluation fails
        """
        url = f"{self.opa_url}/v1/data/{policy_path}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        payload = {"input": input_data}
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully evaluated policy '{policy_path}'")
                    return result
                else:
                    error_msg = f"Failed to evaluate policy '{policy_path}': {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error evaluating policy '{policy_path}': {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    async def query(
        self,
        query_string: str,
        input_data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an ad-hoc Rego query.
        
        Args:
            query_string: Rego query string
            input_data: Optional input data for query
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Query result
            
        Raises:
            OPAException: If query fails
        """
        url = f"{self.opa_url}/v1/query"
        
        headers = {
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        payload = {"query": query_string}
        if input_data:
            payload["input"] = input_data
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully executed query")
                    return result
                else:
                    error_msg = f"Failed to execute query: {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error executing query: {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    async def batch_evaluate(
        self,
        policy_path: str,
        inputs: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch evaluate multiple inputs against a policy.
        
        Args:
            policy_path: Path to policy decision
            inputs: List of input data dictionaries
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            List of evaluation results
            
        Raises:
            OPAException: If batch evaluation fails
        """
        results = []
        
        for idx, input_data in enumerate(inputs):
            try:
                result = await self.evaluate_policy(
                    policy_path,
                    input_data,
                    correlation_id
                )
                results.append(result)
                
            except OPAException as e:
                logger.warning(f"Batch evaluation failed for input {idx}: {str(e)}")
                results.append({
                    "error": str(e),
                    "input_index": idx
                })
        
        return results
    
    async def get_policies(self) -> List[str]:
        """
        Get list of all policies in OPA.
        
        Returns:
            List of policy names
            
        Raises:
            OPAException: If retrieval fails
        """
        url = f"{self.opa_url}/v1/policies"
        
        try:
            async with AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    result = response.json()
                    policies = [p["id"] for p in result.get("result", [])]
                    logger.info(f"Retrieved {len(policies)} policies from OPA")
                    return policies
                else:
                    error_msg = f"Failed to get policies: {response.status_code}"
                    logger.error(f"{error_msg} - {response.text}")
                    raise OPAException(error_msg)
                    
        except httpx.HTTPError as e:
            error_msg = f"HTTP error getting policies: {str(e)}"
            logger.error(error_msg)
            raise OPAException(error_msg) from e
    
    def parse_violations(
        self,
        evaluation_result: Dict[str, Any],
        resource_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Parse OPA evaluation result to extract violations.
        
        Args:
            evaluation_result: Result from evaluate_policy()
            resource_context: Optional context about the resource being evaluated
            
        Returns:
            List of violations with details
        """
        violations = []
        
        # OPA typically returns results in format: {"result": [...]}
        result = evaluation_result.get("result", {})
        
        # Handle different OPA response formats
        if isinstance(result, list):
            # List of violations
            for item in result:
                violation = self._format_violation(item, resource_context)
                violations.append(violation)
                
        elif isinstance(result, dict):
            # Single violation or structured result
            if "deny" in result or "violations" in result:
                deny_items = result.get("deny", result.get("violations", []))
                
                if isinstance(deny_items, list):
                    for item in deny_items:
                        violation = self._format_violation(item, resource_context)
                        violations.append(violation)
                elif deny_items:
                    # Single denial
                    violation = self._format_violation(deny_items, resource_context)
                    violations.append(violation)
        
        logger.info(f"Parsed {len(violations)} violations from OPA result")
        return violations
    
    def _format_violation(
        self,
        violation_data: Any,
        resource_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a single violation into standardized structure.
        
        Args:
            violation_data: Raw violation data from OPA
            resource_context: Optional resource context
            
        Returns:
            Formatted violation dictionary
        """
        if isinstance(violation_data, str):
            # Simple string violation
            return {
                "violation_message": violation_data,
                "severity": "MEDIUM",
                "resource_type": resource_context.get("type") if resource_context else "unknown",
                "resource_name": resource_context.get("name") if resource_context else "unknown",
                "violation_details": {}
            }
        
        elif isinstance(violation_data, dict):
            # Structured violation
            return {
                "violation_message": violation_data.get("msg", violation_data.get("message", "Policy violation")),
                "severity": violation_data.get("severity", "MEDIUM").upper(),
                "violation_rule": violation_data.get("rule", violation_data.get("policy", "unknown")),
                "resource_type": violation_data.get("resource_type", 
                                                     resource_context.get("type") if resource_context else "unknown"),
                "resource_name": violation_data.get("resource_name",
                                                     resource_context.get("name") if resource_context else "unknown"),
                "resource_identifier": violation_data.get("resource_id", ""),
                "file_path": violation_data.get("file_path"),
                "line_number": violation_data.get("line_number"),
                "recommended_fix": violation_data.get("fix", violation_data.get("recommendation")),
                "violation_details": {
                    k: v for k, v in violation_data.items()
                    if k not in ["msg", "message", "severity", "rule", "policy"]
                }
            }
        
        else:
            # Unknown format
            return {
                "violation_message": str(violation_data),
                "severity": "MEDIUM",
                "resource_type": "unknown",
                "resource_name": "unknown",
                "violation_details": {"raw": violation_data}
            }
