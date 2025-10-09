"""Configuration management for IAC governance service."""

import os
from typing import Optional


class Config:
    """Service configuration from environment variables."""
    
    # Service identity
    SERVICE_NAME: str = "iac-governance-service"
    SERVICE_PORT: int = int(os.getenv("IAC_GOVERNANCE_PORT", "8021"))
    SERVICE_VERSION: str = "1.0.0"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "IAC_GOVERNANCE_DB_URL",
        os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/iac_governance")
    )
    
    # MCP Integration (ai-agent-service as control plane)
    MCP_CONTROL_PLANE_URL: str = os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8008")
    MCP_SERVICE_TOKEN: Optional[str] = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
    
    # Service Registry
    SERVICE_REGISTRY_URL: str = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
    REGISTER_WITH_REGISTRY: bool = os.getenv("REGISTER_WITH_REGISTRY", "true").lower() == "true"
    
    # CORS
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3001"
    ).split(",")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_JSON_LOGS: bool = os.getenv("ENABLE_JSON_LOGS", "false").lower() == "true"
    
    # Telemetry
    ENABLE_CORRELATION_ID: bool = True
    ENABLE_REQUEST_LOGGING: bool = True
    
    # OPA (Open Policy Agent) Configuration
    OPA_URL: str = os.getenv("OPA_URL", "http://localhost:8181")
    OPA_TIMEOUT_SECONDS: int = int(os.getenv("OPA_TIMEOUT_SECONDS", "30"))
    
    # Scan Configuration
    MAX_CONCURRENT_SCANS: int = int(os.getenv("MAX_CONCURRENT_SCANS", "5"))
    SCAN_TIMEOUT_SECONDS: int = int(os.getenv("SCAN_TIMEOUT_SECONDS", "300"))


config = Config()
