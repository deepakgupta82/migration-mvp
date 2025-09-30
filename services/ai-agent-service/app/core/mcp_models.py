"""
Pydantic models and types for MCP Server Registry and Unified Tool metadata.

This module defines a minimal, forward-compatible schema to store and validate
MCP server configurations for AWS, Azure, GCP, and custom providers. Secrets are
represented as opaque references (secretRef) and must not be stored in clear text.
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
