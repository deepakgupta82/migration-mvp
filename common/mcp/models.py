"""
Shared MCP (Model Context Protocol) models and types.

This module defines common Pydantic models for MCP server configurations,
authentication, tool metadata, and execution contracts. These models are used
across multiple services for MCP integration.

Originally from: services/ai-agent-service/app/core/mcp_models.py
Promoted to shared library for cross-service reuse in Phase 1.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Literal, Any
import uuid


Provider = Literal["aws", "azure", "gcp", "custom"]
Transport = Literal["stdio", "ws", "sse"]


class SecretRef(BaseModel):
    """Reference to a secret in an external vault or environment.

    For MVP we only store a logical name; actual retrieval is handled by a
    secrets provider (future). For development, this may map to an env var.
    """

    ref: str = Field(..., description="Reference key or path to the secret")
    provider: Optional[str] = Field(
        None, description="Secret store provider (e.g., keyvault|aws-sm|gcp-sm|env)"
    )


class STDIOConnection(BaseModel):
    command: str = Field(..., description="Executable to launch the MCP server")
    args: List[str] = Field(default_factory=list)
    cwd: Optional[str] = None


class WSConnection(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None  # Use SecretRef in future


class SSEConnection(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None


class ConnectionConfig(BaseModel):
    transport: Transport
    stdio: Optional[STDIOConnection] = None
    ws: Optional[WSConnection] = None
    sse: Optional[SSEConnection] = None

    @validator("stdio", always=True)
    def _validate_transport(cls, v, values):
        t = values.get("transport")
        if t == "stdio" and not v:
            raise ValueError("stdio connection required for transport=stdio")
        return v


class AWSAuth(BaseModel):
    credentials: Optional[SecretRef] = None  # e.g., env or vault reference
    access_key_id: Optional[str] = Field(None, description="AWS Access Key ID (stored as SecretRef in production)")
    secret_access_key: Optional[str] = Field(None, description="AWS Secret Access Key (stored as SecretRef in production)")
    session_token: Optional[str] = Field(None, description="AWS Session Token for temporary credentials")
    region: Optional[str] = None
    roleArn: Optional[str] = None
    externalId: Optional[str] = None


class AzureAuth(BaseModel):
    tenantId: Optional[str] = None
    clientId: Optional[str] = None
    secret: Optional[SecretRef] = None
    useManagedIdentity: Optional[bool] = False
    subscriptionIds: Optional[List[str]] = None


class GCPAuth(BaseModel):
    serviceAccountKey: Optional[SecretRef] = None
    projectIds: Optional[List[str]] = None
    useADC: Optional[bool] = False


class AuthConfig(BaseModel):
    aws: Optional[AWSAuth] = None
    azure: Optional[AzureAuth] = None
    gcp: Optional[GCPAuth] = None
    # Custom providers can add extra fields via this bag
    extra: Optional[Dict[str, Any]] = None


class MCPServerConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    provider: Provider = "custom"
    connection: ConnectionConfig
    auth: Optional[AuthConfig] = None
    env: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Environment vars (use SecretRef in future)"
    )
    tool_allowlist: Optional[List[str]] = None
    tool_denylist: Optional[List[str]] = None
    is_enabled: bool = True
    health_status: Optional[Literal["unknown", "healthy", "unhealthy"]] = "unknown"
    description: Optional[str] = None
    # Operational policies
    rate_limit_rpm: Optional[int] = Field(
        default=60, description="Max allowed MCP requests per minute for this server"
    )
    max_concurrency: Optional[int] = Field(
        default=4, description="Max concurrent MCP calls for this server"
    )
    circuit_breaker_threshold: Optional[int] = Field(
        default=5, description="Consecutive failures before opening circuit"
    )
    circuit_breaker_cooldown_sec: Optional[int] = Field(
        default=60, description="Cooldown seconds before half-open retry"
    )
    discovery_cache_ttl_sec: Optional[int] = Field(
        default=900, description="TTL for discovered tools cache in seconds"
    )
    # Telemetry timestamps (ISO8601)
    last_discovered_at: Optional[str] = None
    last_health_check_at: Optional[str] = None


class UnifiedToolSchema(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None  # JSON Schema
    server_id: str
    provider: Provider


class MCPServerWithTools(BaseModel):
    server: MCPServerConfig
    tools: List[UnifiedToolSchema] = Field(default_factory=list)


class ExecuteToolRequest(BaseModel):
    server_id: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)


class ExecuteToolResponse(BaseModel):
    success: bool
    output: Any = None
    error: Optional[str] = None
