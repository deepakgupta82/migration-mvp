# Dockerfile for AWS Pricing MCP Server
# Based on: https://github.com/awslabs/mcp/tree/main/src/aws-pricing-mcp-server

FROM python:3.10-slim

# Install uv package manager
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Install the AWS Pricing MCP server using uvx
RUN uv tool install awslabs.aws-pricing-mcp-server

# Expose default MCP port (not strictly needed for stdio, but useful for debugging)
EXPOSE 9051

# Set default environment variables (can be overridden in docker-compose)
ENV FASTMCP_LOG_LEVEL=ERROR
ENV AWS_REGION=us-east-1

# Run the MCP server via uvx
CMD ["uvx", "awslabs.aws-pricing-mcp-server@latest"]
