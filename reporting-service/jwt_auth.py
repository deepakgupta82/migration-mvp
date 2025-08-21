#!/usr/bin/env python3
"""
JWT Authentication for Reporting Service
Handles JWT-based service-to-service communication
"""

import os
import sys
import requests
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
        project_service_path = os.path.join(os.path.dirname(__file__), '../project-service')
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

class ReportingJWTAuth:
    """JWT Authentication for Reporting Service"""
    
    def __init__(self):
        self.service_name = "reporting-service"
        self.service_role = ServiceRole.REPORTING_SERVICE if JWT_AVAILABLE else None
        self._service_token = None
        self._token_expires_at = None
        self._legacy_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        self._jwt_init_attempted = False

        # Don't generate initial service token during startup to prevent hanging
        # Will be generated lazily when first needed
        logger.info("Reporting JWT auth initialized in lazy mode")
    
    def _refresh_service_token(self):
        """Refresh the service JWT token"""
        if not JWT_AVAILABLE:
            logger.info("JWT not available, using legacy token")
            return
        
        try:
            self._service_token = jwt_service.create_service_token(
                service_name=self.service_name,
                service_role=self.service_role,
                permissions=[
                    "read:projects", "read:documents", "write:reports", "read:templates"
                ]
            )
            
            # Set expiration time (23 hours to refresh before expiry)
            self._token_expires_at = datetime.utcnow() + timedelta(hours=23)
            logger.info("Reporting service JWT token refreshed successfully")
            
        except Exception as e:
            logger.error(f"Failed to refresh JWT token: {e}")
            self._service_token = None
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls"""
        
        # Check if JWT token needs refresh
        if (JWT_AVAILABLE and 
            (not self._service_token or 
             not self._token_expires_at or 
             datetime.utcnow() >= self._token_expires_at)):
            self._refresh_service_token()
        
        # Use JWT token if available, otherwise fall back to legacy
        if JWT_AVAILABLE and self._service_token:
            return {"Authorization": f"Bearer {self._service_token}"}
        else:
            return {"Authorization": f"Bearer {self._legacy_token}"}
    
    async def call_project_service(self, endpoint: str, method: str = "GET", 
                                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make authenticated API call to project service"""
        
        base_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        url = f"{base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call to project service failed: {e}")
            raise
    
    async def call_backend_service(self, endpoint: str, method: str = "GET", 
                                 data: Optional[Dict] = None) -> Dict:
        """Make authenticated API call to backend service"""
        
        base_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:8000")
        url = f"{base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API call to backend service failed: {e}")
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

# Global reporting authentication instance
reporting_auth = ReportingJWTAuth()

# Convenience functions for backward compatibility
def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers (backward compatible)"""
    return reporting_auth.get_auth_headers()

async def call_project_service(endpoint: str, method: str = "GET", 
                             data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
    """Call project service with authentication (backward compatible)"""
    return await reporting_auth.call_project_service(endpoint, method, data, params)

async def call_backend_service(endpoint: str, method: str = "GET", 
                             data: Optional[Dict] = None) -> Dict:
    """Call backend service with authentication (backward compatible)"""
    return await reporting_auth.call_backend_service(endpoint, method, data)

def verify_token(token: str) -> Optional[Dict]:
    """Verify incoming token (backward compatible)"""
    return reporting_auth.verify_incoming_token(token)
