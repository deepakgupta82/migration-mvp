"""Adapter layer for external integrations (MCP tools, policy engines)."""

from app.adapters.terraform_mcp_adapter import TerraformMCPAdapter

__all__ = ["TerraformMCPAdapter"]
