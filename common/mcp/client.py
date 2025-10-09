"""
HTTP-based MCP Tool Execution Client.

This client allows services to invoke MCP tools via the ai-agent-service REST API
without managing MCP connections directly. The ai-agent-service acts as the MCP
control plane, managing all MCP server connections, tool discovery, and execution.

Usage:
    from common.mcp.client import MCPClient
    
    client = MCPClient(base_url="http://localhost:8008")
    
    # List available tools
    tools = await client.list_tools(provider="aws")
    
    # Execute a tool
    result = await client.execute_tool(
        server_id="aws-pricing-mcp",
        tool="get_pricing",
        args={"service": "ec2", "region": "us-east-1"}
    )
"""

import httpx
from typing import Dict, List, Optional, Any
from .models import (
    MCPServerConfig,
    UnifiedToolSchema,
    ExecuteToolRequest,
    ExecuteToolResponse,
    Provider
)


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPClient:
    """HTTP client for executing MCP tools via ai-agent-service."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8008",
        timeout: float = 300.0,
        service_token: Optional[str] = None
    ):
        """
        Initialize MCP HTTP client.
        
        Args:
            base_url: Base URL of ai-agent-service (MCP control plane)
            timeout: Request timeout in seconds (default 300s for long-running tools)
            service_token: Optional service-to-service authentication token
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        
        if service_token:
            self.headers["Authorization"] = f"Bearer {service_token}"
    
    async def list_servers(self, provider: Optional[Provider] = None) -> List[MCPServerConfig]:
        """
        List all registered MCP servers.
        
        Args:
            provider: Optional filter by provider (aws, azure, gcp, custom)
            
        Returns:
            List of MCP server configurations
        """
        url = f"{self.base_url}/api/mcp/servers"
        params = {"provider": provider} if provider else {}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return [MCPServerConfig(**server) for server in data]
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to list MCP servers: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise MCPClientError(f"Failed to list MCP servers: {str(e)}")
    
    async def get_server(self, server_id: str) -> MCPServerConfig:
        """
        Get specific MCP server configuration.
        
        Args:
            server_id: MCP server ID
            
        Returns:
            MCP server configuration
        """
        url = f"{self.base_url}/api/mcp/servers/{server_id}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return MCPServerConfig(**response.json())
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to get MCP server: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise MCPClientError(f"Failed to get MCP server: {str(e)}")
    
    async def list_tools(
        self,
        server_id: Optional[str] = None,
        provider: Optional[Provider] = None
    ) -> List[UnifiedToolSchema]:
        """
        List available MCP tools across all servers or filtered by server/provider.
        
        Args:
            server_id: Optional filter by specific MCP server
            provider: Optional filter by provider (aws, azure, gcp, custom)
            
        Returns:
            List of available tool schemas
        """
        url = f"{self.base_url}/api/mcp/tools"
        params = {}
        if server_id:
            params["server_id"] = server_id
        if provider:
            params["provider"] = provider
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return [UnifiedToolSchema(**tool) for tool in data]
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to list MCP tools: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise MCPClientError(f"Failed to list MCP tools: {str(e)}")
    
    async def execute_tool(
        self,
        server_id: str,
        tool: str,
        args: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> ExecuteToolResponse:
        """
        Execute an MCP tool on a specific server.
        
        Args:
            server_id: MCP server ID
            tool: Tool name to execute
            args: Tool input arguments
            correlation_id: Optional correlation ID for distributed tracing
            
        Returns:
            Tool execution result
        """
        url = f"{self.base_url}/api/mcp/execute"
        
        headers = self.headers.copy()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        request = ExecuteToolRequest(
            server_id=server_id,
            tool=tool,
            args=args
        )
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=request.dict()
                )
                response.raise_for_status()
                return ExecuteToolResponse(**response.json())
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to execute MCP tool: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise MCPClientError(f"Failed to execute MCP tool: {str(e)}")
    
    async def health_check(self, server_id: str) -> Dict[str, Any]:
        """
        Check health status of an MCP server.
        
        Args:
            server_id: MCP server ID
            
        Returns:
            Health status information
        """
        url = f"{self.base_url}/api/mcp/servers/{server_id}/health"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise MCPClientError(f"Failed to check MCP server health: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise MCPClientError(f"Failed to check MCP server health: {str(e)}")


# Convenience function for quick one-off tool executions
async def execute_mcp_tool(
    server_id: str,
    tool: str,
    args: Dict[str, Any],
    base_url: str = "http://localhost:8008",
    correlation_id: Optional[str] = None
) -> ExecuteToolResponse:
    """
    Execute an MCP tool without creating a persistent client.
    
    Args:
        server_id: MCP server ID
        tool: Tool name to execute
        args: Tool input arguments
        base_url: Base URL of ai-agent-service
        correlation_id: Optional correlation ID
        
    Returns:
        Tool execution result
    """
    client = MCPClient(base_url=base_url)
    return await client.execute_tool(server_id, tool, args, correlation_id)
