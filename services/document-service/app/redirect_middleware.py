"""
Migration Logging Middleware for Document Service API Standardization

This middleware logs usage of legacy API endpoints to track migration progress
while maintaining full backward compatibility.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("document-service.migration")

class DocumentServiceMigrationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log legacy endpoint usage for migration tracking.

    This maintains backward compatibility while encouraging migration to standardized endpoints.
    """

    def __init__(self, app, endpoint_map: Optional[Dict[str, str]] = None):
        super().__init__(app)
        # Default mapping from legacy to standardized endpoints for logging
        self.endpoint_map = endpoint_map or {
            # Documents endpoints
            r"^/([^/]+)/upload$": "/api/documents/documents/{project_id}/upload",
            r"^/([^/]+)/process-all$": "/api/documents/documents/{project_id}/process",
            r"^/([^/]+)/process-selected$": "/api/documents/documents/{project_id}/process-selected",
            r"^/([^/]+)/status/([^/]+)$": "/api/documents/documents/{project_id}/status/{job_id}",
            r"^/([^/]+)/structured-process/([^/]+)$": "/api/documents/documents/{project_id}/structured-process/{filename}",
            r"^/([^/]+)/structured-process-all$": "/api/documents/documents/{project_id}/structured-process",
            r"^/([^/]+)/structured-status/([^/]+)$": "/api/documents/documents/{project_id}/structured-status/{job_id}",
            r"^/([^/]+)/generate-enhanced-chunks/([^/]+)$": "/api/documents/documents/{project_id}/chunks/{filename}",
            r"^/([^/]+)/extract-content-batch$": "/api/documents/documents/{project_id}/extract-batch",

            # Analysis endpoints
            r"^/([^/]+)/content/([^/]+)$": "/api/documents/analysis/{project_id}/content/{filename}",
            r"^/([^/]+)/analyze/([^/]+)$": "/api/documents/analysis/{project_id}/analyze/{filename}",
            r"^/([^/]+)/insights$": "/api/documents/analysis/{project_id}/insights",
            r"^/([^/]+)/analyze-batch$": "/api/documents/analysis/{project_id}/analyze-batch",
            r"^/([^/]+)/content-analysis/([^/]+)$": "/api/documents/analysis/{project_id}/batch/{analysis_id}",
            r"^/([^/]+)/llm-analyze/([^/]+)$": "/api/documents/analysis/{project_id}/llm/{filename}",
            r"^/([^/]+)/llm-analyze-batch$": "/api/documents/analysis/{project_id}/llm-batch",
            r"^/([^/]+)/llm-analysis-status/([^/]+)$": "/api/documents/analysis/{project_id}/llm-status/{analysis_id}",
            r"^/([^/]+)/analysis$": "/api/documents/analysis/{project_id}/results",
            r"^/([^/]+)/analysis/batch$": "/api/documents/analysis/{project_id}/results/batch",
            r"^/([^/]+)/analysis/batch/([^/]+)$": "/api/documents/analysis/{project_id}/results/batch/{batch_id}",
            r"^/([^/]+)/analysis/batches$": "/api/documents/analysis/{project_id}/results/batches",
            r"^/([^/]+)/analysis/([^/]+)$": "/api/documents/analysis/{project_id}/results/{analysis_id}",
            r"^/([^/]+)/analysis/([^/]+)/version$": "/api/documents/analysis/{project_id}/results/{analysis_id}/version",
            r"^/([^/]+)/analysis/([^/]+)/versions$": "/api/documents/analysis/{project_id}/results/{analysis_id}/versions",
            r"^/([^/]+)/analysis/([^/]+)/version/([^/]+)$": "/api/documents/analysis/{project_id}/results/{analysis_id}/version/{version_number}",

            # Search endpoints
            r"^/([^/]+)/search$": "/api/documents/search/{project_id}/content",

            # Config endpoints
            r"^/workflow-config$": "/api/documents/config/workflow",
            r"^/llm-analysis-health$": "/api/documents/config/health",
            r"^/llm-analysis-cache/clear$": "/api/documents/config/cache/clear",
            r"^/([^/]+)/test-endpoint$": "/api/documents/config/test",
        }

        # Compile regex patterns for better performance
        self.compiled_patterns = {}
        for pattern, replacement in self.endpoint_map.items():
            self.compiled_patterns[pattern] = {
                'regex': re.compile(pattern),
                'replacement': replacement
            }

    async def dispatch(self, request: Request, call_next):
        """
        Intercept requests and log legacy endpoint usage for migration tracking.
        """
        path = request.url.path

        # Skip logging for standardized endpoints (already using new structure)
        if path.startswith("/api/documents/"):
            response = await call_next(request)
            # Add migration encouragement header for new endpoints
            response.headers["X-API-Standardized"] = "true"
            return response

        # Check if path matches any legacy pattern
        for pattern_data in self.compiled_patterns.values():
            match = pattern_data['regex'].match(path)
            if match:
                # Extract project_id from the match for logging
                project_id = match.group(1) if match.groups() else "unknown"

                # Build standardized path template
                standardized_path = pattern_data['replacement']

                # Log the legacy usage for migration tracking
                logger.info(
                    f"Legacy endpoint usage detected: '{path}' | "
                    f"Consider migrating to: '{standardized_path}' | "
                    f"Project: {project_id} | "
                    f"Method: {request.method}"
                )

                # Add migration hint header
                response = await call_next(request)
                response.headers["X-API-Migration-Hint"] = standardized_path
                response.headers["X-API-Legacy-Usage"] = "true"
                return response

        # No legacy pattern matched, proceed with normal request
        response = await call_next(request)
        return response


def create_migration_middleware(endpoint_map: Optional[Dict[str, str]] = None):
    """
    Factory function to create the migration middleware with custom mapping if needed.

    Args:
        endpoint_map: Optional custom endpoint mapping dictionary for logging

    Returns:
        DocumentServiceMigrationMiddleware instance
    """
    return DocumentServiceMigrationMiddleware(None, endpoint_map)