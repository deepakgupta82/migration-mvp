"""
Initialize AWS Pricing MCP Server configuration.

This script registers the AWS Pricing MCP server with the AI Agent service's MCP registry.
It can be run at startup or invoked manually to configure the server.

Usage:
    python scripts/init_aws_pricing_mcp.py [--docker]

Args:
    --docker: Configure for Docker container (default: local uvx installation)
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))
# Add root directory to path to import common modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from common.mcp import (
    MCPServerConfig,
    ConnectionConfig,
    STDIOConnection,
    AuthConfig,
    AWSAuth,
    SecretRef
)
from app.repository.mcp_registry import get_registry


def create_aws_pricing_mcp_config(use_docker: bool = False) -> MCPServerConfig:
    """
    Create AWS Pricing MCP server configuration.
    
    Args:
        use_docker: If True, configure for Docker; otherwise for local uvx
        
    Returns:
        MCPServerConfig instance
    """
    
    if use_docker:
        # Docker configuration using official AWS Labs pattern
        # Uses 'docker run --rm --interactive --env-file' for stateless invocation
        # Note: We use our locally built image since AWS Labs doesn't publish to GHCR
        env_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            ".env.aws"
        )
        connection = ConnectionConfig(
            transport="stdio",
            stdio=STDIOConnection(
                command="docker",
                args=[
                    "run",
                    "--rm",
                    "--interactive",
                    "--env-file", env_file_path,
                    "migration-platform/aws-pricing-mcp:latest"
                ],
                cwd=None
            )
        )
    else:
        # Local uvx installation
        connection = ConnectionConfig(
            transport="stdio",
            stdio=STDIOConnection(
                command="uvx",
                args=["awslabs.aws-pricing-mcp-server@latest"],
                cwd=None
            )
        )
    
    # AWS authentication configuration
    # For Docker: credentials passed via --env-file, no need for explicit auth config
    # For Local: use SecretRef to read from environment
    if use_docker:
        # Docker mode: credentials in .env.aws file, passed via --env-file
        auth = None  # Not needed, handled by --env-file
    else:
        # For local, use SecretRef to read from environment
        auth = AuthConfig(
            aws=AWSAuth(
                credentials=SecretRef(
                    ref="AWS_CREDENTIALS",
                    provider="env"
                ),
                region=os.getenv("AWS_REGION", "us-east-1")
            )
        )
    
    # Environment variables for the MCP server
    # For Docker: all vars in .env.aws file
    # For Local: set in shell environment
    env = None if use_docker else {
        "FASTMCP_LOG_LEVEL": os.getenv("FASTMCP_LOG_LEVEL", "ERROR"),
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
    }
    
    # Create the configuration
    config = MCPServerConfig(
        name="AWS Pricing MCP" + (" (Docker)" if use_docker else ""),
        provider="aws",
        connection=connection,
        auth=auth,
        env=env,
        tool_allowlist=None,  # Allow all tools by default
        tool_denylist=None,
        is_enabled=True,
        description=(
            "AWS Pricing MCP Server - Provides real-time AWS pricing information, "
            "cost analysis, service catalog exploration, and pricing comparisons. "
            f"Running via {'docker run --rm --interactive' if use_docker else 'uvx'}."
        ),
        rate_limit_rpm=60,
        max_concurrency=4,
        circuit_breaker_threshold=5,
        circuit_breaker_cooldown_sec=60,
        discovery_cache_ttl_sec=900
    )
    
    return config


def main():
    """Main entry point for the initialization script."""
    parser = argparse.ArgumentParser(
        description="Initialize AWS Pricing MCP Server configuration"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Configure for Docker container (default: local uvx)"
    )
    args = parser.parse_args()
    
    # Get the MCP registry
    registry = get_registry()
    
    # Create the configuration
    config = create_aws_pricing_mcp_config(use_docker=args.docker)
    
    # Register the server
    registry.upsert(config)
    
    print(f"✅ AWS Pricing MCP Server registered successfully!")
    print(f"   - Server ID: {config.id}")
    print(f"   - Name: {config.name}")
    print(f"   - Provider: {config.provider}")
    print(f"   - Transport: {config.connection.transport}")
    print(f"   - Docker mode: {args.docker}")
    print()
    print("📝 Next steps:")
    print("   1. Ensure AWS credentials are configured:")
    if args.docker:
        print("      - Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in docker-compose.yml")
        print("      - Or mount ~/.aws directory to the container")
    else:
        print("      - Run: aws configure")
        print("      - Or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars")
    print()
    print("   2. Ensure IAM permissions include 'pricing:*'")
    print()
    print("   3. Discover available tools:")
    print(f"      POST http://localhost:8008/api/mcp/servers/{config.id}/discover")
    print()
    print("   4. Test a tool:")
    print(f"      POST http://localhost:8008/api/mcp/tools/execute")
    print(f"      Body: {{\"server_id\": \"{config.id}\", \"tool\": \"get_aws_services\", \"args\": {{}}}}")
    

if __name__ == "__main__":
    main()
