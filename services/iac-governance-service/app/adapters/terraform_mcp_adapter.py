"""
Terraform MCP Adapter

Integrates with Terraform MCP server via ai-agent-service's MCP infrastructure.
Provides high-level operations for Terraform IAC management.

Key Operations:
- Plan: Generate execution plan
- Apply: Apply changes to infrastructure
- Validate: Validate configuration syntax
- Destroy: Destroy managed infrastructure
- Workspace: Manage Terraform workspaces
- State: Query Terraform state

Architecture:
- Uses shared MCPClient from common/mcp/client.py
- Calls ai-agent-service (port 8008) MCP endpoints
- Returns structured responses for database persistence
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from common.mcp.client import MCPClient
from app.core.config import config

logger = logging.getLogger("terraform-mcp-adapter")


class TerraformExecutionError(Exception):
    """Raised when Terraform execution fails."""
    pass


class TerraformMCPAdapter:
    """
    Adapter for Terraform MCP server integration.
    
    Provides typed, high-level interface to Terraform operations via MCP tools.
    """
    
    def __init__(self, ai_agent_base_url: str = None):
        """
        Initialize Terraform MCP adapter.
        
        Args:
            ai_agent_base_url: Base URL for ai-agent-service (default: http://localhost:8008)
        """
        self.ai_agent_base_url = ai_agent_base_url or "http://localhost:8008"
        self.mcp_client = MCPClient(base_url=self.ai_agent_base_url)
        self.server_id = "terraform-mcp-server"  # Expected Terraform MCP server ID
        
    async def health_check(self) -> bool:
        """
        Check if Terraform MCP server is available.
        
        Returns:
            bool: True if server is healthy, False otherwise
        """
        try:
            result = await self.mcp_client.health_check(self.server_id)
            return result.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Terraform MCP health check failed: {e}")
            return False
    
    async def plan(
        self,
        *,
        workspace_path: str,
        correlation_id: Optional[str] = None,
        var_file: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        target: Optional[List[str]] = None,
        destroy: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate Terraform execution plan.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            correlation_id: Correlation ID for request tracing
            var_file: Path to variable file (.tfvars)
            variables: Dictionary of variable overrides
            target: List of resource addresses to target
            destroy: Generate destroy plan instead of apply plan
            
        Returns:
            Dict with keys:
                - plan_id: Unique plan identifier
                - changes: Summary of planned changes (add, change, delete counts)
                - resources: List of resources affected
                - output: Full plan output text
                - success: Boolean indicating success
                - error: Error message if failed
                
        Raises:
            TerraformExecutionError: If plan generation fails
        """
        logger.info(f"Generating Terraform plan for workspace: {workspace_path}")
        
        # Build MCP tool arguments
        args = {
            "workspace_path": workspace_path,
            "destroy": destroy,
        }
        
        if var_file:
            args["var_file"] = var_file
        if variables:
            args["variables"] = variables
        if target:
            args["target"] = target
        
        try:
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_plan",
                arguments=args,
                correlation_id=correlation_id or f"plan-{datetime.utcnow().timestamp()}",
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error during plan generation")
                logger.error(f"Terraform plan failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "plan_id": output.get("plan_id") or f"plan-{datetime.utcnow().timestamp()}",
                "changes": output.get("changes", {"add": 0, "change": 0, "delete": 0}),
                "resources": output.get("resources", []),
                "output": output.get("output_text", ""),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform plan execution failed: {e}")
            raise TerraformExecutionError(f"Plan execution failed: {str(e)}")
    
    async def apply(
        self,
        *,
        workspace_path: str,
        plan_file: Optional[str] = None,
        correlation_id: Optional[str] = None,
        var_file: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        target: Optional[List[str]] = None,
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply Terraform changes.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            plan_file: Path to saved plan file (if using pre-generated plan)
            correlation_id: Correlation ID for request tracing
            var_file: Path to variable file (.tfvars)
            variables: Dictionary of variable overrides
            target: List of resource addresses to target
            auto_approve: Skip interactive approval (dangerous!)
            
        Returns:
            Dict with keys:
                - apply_id: Unique apply identifier
                - changes_applied: Summary of changes (add, change, delete counts)
                - resources: List of resources affected
                - duration_seconds: Execution duration
                - output: Full apply output text
                - success: Boolean indicating success
                - error: Error message if failed
                
        Raises:
            TerraformExecutionError: If apply fails
        """
        logger.info(f"Applying Terraform changes for workspace: {workspace_path}")
        
        # Build MCP tool arguments
        args = {
            "workspace_path": workspace_path,
            "auto_approve": auto_approve,
        }
        
        if plan_file:
            args["plan_file"] = plan_file
        if var_file:
            args["var_file"] = var_file
        if variables:
            args["variables"] = variables
        if target:
            args["target"] = target
        
        try:
            start_time = datetime.utcnow()
            
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_apply",
                arguments=args,
                correlation_id=correlation_id or f"apply-{start_time.timestamp()}",
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error during apply")
                logger.error(f"Terraform apply failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "apply_id": output.get("apply_id") or f"apply-{start_time.timestamp()}",
                "changes_applied": output.get("changes", {"add": 0, "change": 0, "delete": 0}),
                "resources": output.get("resources", []),
                "duration_seconds": duration,
                "output": output.get("output_text", ""),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform apply execution failed: {e}")
            raise TerraformExecutionError(f"Apply execution failed: {str(e)}")
    
    async def validate(
        self,
        *,
        workspace_path: str,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate Terraform configuration syntax.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            correlation_id: Correlation ID for request tracing
            
        Returns:
            Dict with keys:
                - valid: Boolean indicating if configuration is valid
                - diagnostics: List of validation errors/warnings
                - error_count: Number of errors found
                - warning_count: Number of warnings found
                - success: Boolean indicating success
                - error: Error message if validation check failed
        """
        logger.info(f"Validating Terraform configuration: {workspace_path}")
        
        args = {"workspace_path": workspace_path}
        
        try:
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_validate",
                arguments=args,
                correlation_id=correlation_id or f"validate-{datetime.utcnow().timestamp()}",
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error during validation")
                logger.error(f"Terraform validate failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "valid": output.get("valid", False),
                "diagnostics": output.get("diagnostics", []),
                "error_count": output.get("error_count", 0),
                "warning_count": output.get("warning_count", 0),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform validate execution failed: {e}")
            raise TerraformExecutionError(f"Validation failed: {str(e)}")
    
    async def destroy(
        self,
        *,
        workspace_path: str,
        correlation_id: Optional[str] = None,
        var_file: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        target: Optional[List[str]] = None,
        auto_approve: bool = False,
    ) -> Dict[str, Any]:
        """
        Destroy Terraform-managed infrastructure.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            correlation_id: Correlation ID for request tracing
            var_file: Path to variable file (.tfvars)
            variables: Dictionary of variable overrides
            target: List of resource addresses to target for destruction
            auto_approve: Skip interactive approval (dangerous!)
            
        Returns:
            Dict with keys:
                - destroy_id: Unique destroy identifier
                - resources_destroyed: Count of resources destroyed
                - duration_seconds: Execution duration
                - output: Full destroy output text
                - success: Boolean indicating success
                - error: Error message if failed
        """
        logger.info(f"Destroying Terraform infrastructure for workspace: {workspace_path}")
        
        args = {
            "workspace_path": workspace_path,
            "auto_approve": auto_approve,
        }
        
        if var_file:
            args["var_file"] = var_file
        if variables:
            args["variables"] = variables
        if target:
            args["target"] = target
        
        try:
            start_time = datetime.utcnow()
            
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_destroy",
                arguments=args,
                correlation_id=correlation_id or f"destroy-{start_time.timestamp()}",
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error during destroy")
                logger.error(f"Terraform destroy failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "destroy_id": output.get("destroy_id") or f"destroy-{start_time.timestamp()}",
                "resources_destroyed": output.get("resources_destroyed", 0),
                "duration_seconds": duration,
                "output": output.get("output_text", ""),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform destroy execution failed: {e}")
            raise TerraformExecutionError(f"Destroy execution failed: {str(e)}")
    
    async def list_workspaces(
        self,
        *,
        workspace_path: str,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List Terraform workspaces.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            correlation_id: Correlation ID for request tracing
            
        Returns:
            Dict with keys:
                - workspaces: List of workspace names
                - current_workspace: Name of currently selected workspace
                - success: Boolean indicating success
                - error: Error message if failed
        """
        logger.info(f"Listing Terraform workspaces for: {workspace_path}")
        
        args = {"workspace_path": workspace_path}
        
        try:
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_workspace_list",
                arguments=args,
                correlation_id=correlation_id or f"workspace-list-{datetime.utcnow().timestamp()}",
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error listing workspaces")
                logger.error(f"Terraform workspace list failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "workspaces": output.get("workspaces", []),
                "current_workspace": output.get("current", "default"),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform workspace list failed: {e}")
            raise TerraformExecutionError(f"Workspace list failed: {str(e)}")
    
    async def show_state(
        self,
        *,
        workspace_path: str,
        address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Show Terraform state information.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            address: Optional resource address to show (e.g., aws_instance.example)
            correlation_id: Correlation ID for request tracing
            
        Returns:
            Dict with keys:
                - state: State information (JSON)
                - resources: List of resources in state
                - outputs: Terraform outputs
                - success: Boolean indicating success
                - error: Error message if failed
        """
        logger.info(f"Showing Terraform state for: {workspace_path}")
        
        args = {"workspace_path": workspace_path}
        
        if address:
            args["address"] = address
        
        try:
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_state_show",
                arguments=args,
                correlation_id=correlation_id or f"state-show-{datetime.utcnow().timestamp()}",
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error showing state")
                logger.error(f"Terraform state show failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "state": output.get("state", {}),
                "resources": output.get("resources", []),
                "outputs": output.get("outputs", {}),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform state show failed: {e}")
            raise TerraformExecutionError(f"State show failed: {str(e)}")
    
    async def init(
        self,
        *,
        workspace_path: str,
        backend_config: Optional[Dict[str, str]] = None,
        upgrade: bool = False,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize Terraform working directory.
        
        Args:
            workspace_path: Path to Terraform workspace directory
            backend_config: Backend configuration overrides
            upgrade: Upgrade modules and plugins
            correlation_id: Correlation ID for request tracing
            
        Returns:
            Dict with keys:
                - initialized: Boolean indicating success
                - modules_downloaded: Count of modules downloaded
                - providers_installed: Count of providers installed
                - output: Init output text
                - success: Boolean indicating success
                - error: Error message if failed
        """
        logger.info(f"Initializing Terraform workspace: {workspace_path}")
        
        args = {
            "workspace_path": workspace_path,
            "upgrade": upgrade,
        }
        
        if backend_config:
            args["backend_config"] = backend_config
        
        try:
            result = await self.mcp_client.execute_tool(
                server_id=self.server_id,
                tool_name="terraform_init",
                arguments=args,
                correlation_id=correlation_id or f"init-{datetime.utcnow().timestamp()}",
            )
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error during init")
                logger.error(f"Terraform init failed: {error_msg}")
                raise TerraformExecutionError(error_msg)
            
            output = result.get("output", {})
            
            return {
                "initialized": True,
                "modules_downloaded": output.get("modules_downloaded", 0),
                "providers_installed": output.get("providers_installed", 0),
                "output": output.get("output_text", ""),
                "success": True,
                "error": None,
            }
            
        except TerraformExecutionError:
            raise
        except Exception as e:
            logger.error(f"Terraform init failed: {e}")
            raise TerraformExecutionError(f"Init failed: {str(e)}")
