"""
Shared MCP (Model Context Protocol) Library.

This package provides common models and clients for MCP integration across services.
The ai-agent-service acts as the MCP control plane, managing all MCP server connections,
tool discovery, and execution. Other services use this library to consume MCP tools via HTTP.

Usage:
    # Import models
    from common.mcp.models import (
        MCPServerConfig,
        UnifiedToolSchema,
        ExecuteToolRequest,
        ExecuteToolResponse,
        Provider,
        Transport
    )
    
    # Import client
    from common.mcp.client import MCPClient, execute_mcp_tool
    
    # Execute a tool
    client = MCPClient(base_url="http://localhost:8008")
    result = await client.execute_tool(
        server_id="aws-mgn-mcp",
        tool="list_migration_jobs",
        args={"status": "RUNNING"}
    )
"""

# Re-export models
from .models import (
    # Type literals
    Provider,
    Transport,
    
    # Secret and connection models
    SecretRef,
    STDIOConnection,
    WSConnection,
    SSEConnection,
    ConnectionConfig,
    
    # Auth models
    AWSAuth,
    AzureAuth,
    GCPAuth,
    AuthConfig,
    
    # MCP server and tool models
    MCPServerConfig,
    UnifiedToolSchema,
    MCPServerWithTools,
    
    # Execution models
    ExecuteToolRequest,
    ExecuteToolResponse,
)

# Re-export client
from .client import (
    MCPClient,
    MCPClientError,
    execute_mcp_tool,
)

__all__ = [
    # Type literals
    "Provider",
    "Transport",
    
    # Secret and connection models
    "SecretRef",
    "STDIOConnection",
    "WSConnection",
    "SSEConnection",
    "ConnectionConfig",
    
    # Auth models
    "AWSAuth",
    "AzureAuth",
    "GCPAuth",
    "AuthConfig",
    
    # MCP server and tool models
    "MCPServerConfig",
    "UnifiedToolSchema",
    "MCPServerWithTools",
    
    # Execution models
    "ExecuteToolRequest",
    "ExecuteToolResponse",
    
    # Client
    "MCPClient",
    "MCPClientError",
    "execute_mcp_tool",
]
