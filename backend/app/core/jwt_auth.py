#!/usr/bin/env python3
"""
JWT Authentication for Backend Service
Handles JWT-based service-to-service communication
"""

import os
import sys
import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# Allow disabling JWT logic for debugging via environment variable
DISABLE_JWT = os.getenv("DISABLE_JWT", "0") == "1"

if DISABLE_JWT:
    JWT_AVAILABLE = False
    logger.warning("DISABLE_JWT is set. Skipping JWT service import and using legacy authentication.")
else:
    # Prefer shared common package, fallback to legacy project-service import
    try:
        from nagarro_ascent_common.auth import jwt_service, ServiceRole, TokenType
        JWT_AVAILABLE = True
        logger.info("JWT service loaded from shared common package 'nagarro_ascent_common'")
    except Exception as common_err:
        # Add project-service to path to import JWT service (legacy)
        project_service_path = os.path.join(os.path.dirname(__file__), '../../../project-service')
        project_service_path = os.path.abspath(project_service_path)
        sys.path.insert(0, project_service_path)
        try:
            from jwt_service import jwt_service, ServiceRole, TokenType
            JWT_AVAILABLE = True
            logger.info(f"JWT service loaded successfully from {project_service_path}")
        except ImportError as e:
            JWT_AVAILABLE = False
            logger.warning(f"JWT service not available from shared package ({common_err}) nor {project_service_path}: {e}")
            logger.info("Falling back to legacy authentication")

class BackendJWTAuth:
    """JWT Authentication for Backend Service"""
    
    def __init__(self):
        self.service_name = "backend-service"
        self.service_role = ServiceRole.BACKEND_SERVICE if JWT_AVAILABLE else None
        self._service_token = None
        self._token_expires_at = None
        self._legacy_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self._jwt_init_attempted = False

        # Don't generate initial service token during startup to prevent hanging
        # Will be generated lazily when first needed
        logger.info("Backend JWT auth initialized in lazy mode")
    
    def _refresh_service_token(self):
        """Refresh the service JWT token with timeout and error handling"""
        if not JWT_AVAILABLE:
            logger.info("JWT not available, using legacy token")
            return

        try:
            # Use threading timeout instead of signal (Windows compatible)
            import threading
            import time

            result = {"token": None, "error": None}

            def create_token():
                try:
                    result["token"] = jwt_service.create_service_token(
                        service_name=self.service_name,
                        service_role=self.service_role,
                        permissions=[
                            "read:projects", "write:projects", "read:users", "write:documents",
                            "read:embeddings", "write:embeddings", "read:graph", "write:graph"
                        ]
                    )
                except Exception as e:
                    result["error"] = e

            # Start token creation in a separate thread with timeout
            thread = threading.Thread(target=create_token)
            thread.daemon = True
            thread.start()
            thread.join(timeout=5)  # 5-second timeout

            if thread.is_alive():
                logger.warning("JWT token refresh timed out, falling back to legacy authentication")
                self._service_token = None
                return

            if result["error"]:
                raise result["error"]

            if result["token"]:
                self._service_token = result["token"]
                # Set expiration time (23 hours to refresh before expiry)
                self._token_expires_at = datetime.utcnow() + timedelta(hours=23)
                logger.info("Backend service JWT token refreshed successfully")
            else:
                logger.warning("JWT token creation returned None")
                self._service_token = None

        except TimeoutError:
            logger.warning("JWT token refresh timed out, falling back to legacy authentication")
            self._service_token = None
        except Exception as e:
            logger.error(f"Failed to refresh JWT token: {e}")
            logger.info("Falling back to legacy authentication")
            self._service_token = None
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls with lazy JWT initialization"""

        # Lazy JWT initialization - only attempt once
        if JWT_AVAILABLE and not self._jwt_init_attempted:
            self._jwt_init_attempted = True
            logger.info("Attempting lazy JWT initialization...")
            self._refresh_service_token()

        # Check if JWT token needs refresh (only if already initialized)
        if (JWT_AVAILABLE and self._jwt_init_attempted and
            (not self._service_token or
             not self._token_expires_at or
             datetime.utcnow() >= self._token_expires_at)):
            logger.info("JWT token expired, refreshing...")
            self._refresh_service_token()

        # Use JWT token if available, otherwise fall back to legacy
        if JWT_AVAILABLE and self._service_token:
            logger.debug("Using JWT authentication")
            return {"Authorization": f"Bearer {self._service_token}"}
        else:
            logger.debug("Using legacy authentication")
            return {"Authorization": f"Bearer {self._legacy_token}"}
    
    async def call_project_service(self, endpoint: str, method: str = "GET", 
                                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make authenticated API call to project service (async, non-blocking)"""
        base_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        url = f"{base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"API call to project service failed: {e}")
            raise
    
    async def call_reporting_service(self, endpoint: str, method: str = "GET", 
                                   data: Optional[Dict] = None) -> Dict:
        """Make authenticated API call to reporting service (async, non-blocking)"""
        base_url = os.getenv("REPORTING_SERVICE_URL", "http://localhost:8001")
        url = f"{base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            logger.error(f"API call to reporting service failed: {e}")
            raise
    
    def verify_incoming_token(self, token: str) -> Optional[Dict]:
        """Verify incoming JWT token from other services"""
        
        if not JWT_AVAILABLE:
            # Fall back to legacy token verification
            if token.replace("Bearer ", "") == self._legacy_token:
                return {"service": "legacy", "valid": True}
            return None
        
        try:
            # Remove Bearer prefix if present
            token_value = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
            
            # Verify JWT token
            payload = jwt_service.verify_token(token_value)
            
            # Check if it's a valid service token
            if payload.get("token_type") in [TokenType.SERVICE_ACCESS, TokenType.USER_ACCESS]:
                return payload
            
            return None
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None
    
    def get_service_info(self) -> Dict[str, str]:
        """Get service information for debugging"""
        return {
            "service_name": self.service_name,
            "jwt_available": JWT_AVAILABLE,
            "has_service_token": bool(self._service_token),
            "token_expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None,
            "auth_mode": "jwt" if JWT_AVAILABLE and self._service_token else "legacy"
        }

# Global backend authentication instance
backend_auth = BackendJWTAuth()

# Convenience functions for backward compatibility
def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers (backward compatible)"""
    return backend_auth.get_auth_headers()

async def call_project_service(endpoint: str, method: str = "GET", 
                             data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
    """Call project service with authentication (backward compatible)"""
    return await backend_auth.call_project_service(endpoint, method, data, params)

async def call_reporting_service(endpoint: str, method: str = "GET", 
                               data: Optional[Dict] = None) -> Dict:
    """Call reporting service with authentication (backward compatible)"""
    return await backend_auth.call_reporting_service(endpoint, method, data)

def verify_token(token: str) -> Optional[Dict]:
    """Verify incoming token (backward compatible)"""
    return backend_auth.verify_incoming_token(token)
