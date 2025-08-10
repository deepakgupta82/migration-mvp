#!/usr/bin/env python3
"""
JWT Service for Platform Authentication
Handles both user-based and service-to-service JWT authentication
"""

import os
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Union
from enum import Enum
from dataclasses import dataclass
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

class TokenType(str, Enum):
    """JWT Token Types"""
    USER_ACCESS = "user_access"
    USER_REFRESH = "user_refresh"
    SERVICE_ACCESS = "service_access"
    OAUTH_ACCESS = "oauth_access"

class ServiceRole(str, Enum):
    """Service Roles for Service-to-Service Communication"""
    BACKEND_SERVICE = "backend_service"
    PROJECT_SERVICE = "project_service"
    REPORTING_SERVICE = "reporting_service"
    FRONTEND_SERVICE = "frontend_service"

@dataclass
class JWTConfig:
    """JWT Configuration"""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    service_token_expire_hours: int = 24
    issuer: str = "nagarro-ascent-platform"
    audience: str = "ascent-services"

class JWTService:
    """Centralized JWT Service for all authentication needs"""
    
    def __init__(self, config: JWTConfig):
        self.config = config
        self._private_key = None
        self._public_key = None
        self._generate_keys()
    
    def _generate_keys(self):
        """Generate RSA key pair for JWT signing (for production)"""
        # For development, use HMAC with secret key
        # For production, use RSA keys
        if self.config.algorithm.startswith('RS'):
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            self._private_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            self._public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
    
    def create_user_access_token(self, user_id: str, email: str, role: str, 
                                permissions: List[str] = None) -> str:
        """Create JWT access token for user authentication"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "permissions": permissions or [],
            "token_type": TokenType.USER_ACCESS,
            "iat": now,
            "exp": now + timedelta(minutes=self.config.access_token_expire_minutes),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "jti": str(uuid.uuid4())
        }
        
        return jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
    
    def create_user_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token for user authentication"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "token_type": TokenType.USER_REFRESH,
            "iat": now,
            "exp": now + timedelta(days=self.config.refresh_token_expire_days),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "jti": str(uuid.uuid4())
        }
        
        return jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
    
    def create_service_token(self, service_name: str, service_role: ServiceRole,
                           permissions: List[str] = None) -> str:
        """Create JWT token for service-to-service communication"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": f"service:{service_name}",
            "service_name": service_name,
            "service_role": service_role,
            "permissions": permissions or self._get_default_service_permissions(service_role),
            "token_type": TokenType.SERVICE_ACCESS,
            "iat": now,
            "exp": now + timedelta(hours=self.config.service_token_expire_hours),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "jti": str(uuid.uuid4())
        }
        
        return jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
    
    def create_oauth_token(self, user_id: str, email: str, provider: str,
                          external_id: str, permissions: List[str] = None) -> str:
        """Create JWT token for OAuth authenticated users"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "email": email,
            "oauth_provider": provider,
            "external_id": external_id,
            "permissions": permissions or [],
            "token_type": TokenType.OAUTH_ACCESS,
            "iat": now,
            "exp": now + timedelta(minutes=self.config.access_token_expire_minutes),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "jti": str(uuid.uuid4())
        }
        
        return jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)
    
    def verify_token(self, token: str) -> Dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token, 
                self.config.secret_key, 
                algorithms=[self.config.algorithm],
                issuer=self.config.issuer,
                audience=self.config.audience
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
    
    def refresh_user_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh user access token using refresh token"""
        try:
            payload = self.verify_token(refresh_token)
            
            if payload.get("token_type") != TokenType.USER_REFRESH:
                raise ValueError("Invalid refresh token type")
            
            user_id = payload.get("sub")
            # Get user details from database to create new access token
            # This would typically involve a database lookup
            
            new_access_token = self.create_user_access_token(
                user_id=user_id,
                email=payload.get("email", ""),
                role=payload.get("role", "user")
            )
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer"
            }
            
        except Exception as e:
            raise ValueError(f"Token refresh failed: {str(e)}")
    
    def _get_default_service_permissions(self, service_role: ServiceRole) -> List[str]:
        """Get default permissions for service roles"""
        permissions_map = {
            ServiceRole.BACKEND_SERVICE: [
                "read:projects", "write:projects", "read:users", "write:documents",
                "read:embeddings", "write:embeddings", "read:graph", "write:graph"
            ],
            ServiceRole.PROJECT_SERVICE: [
                "read:projects", "write:projects", "read:users", "write:users",
                "read:settings", "write:settings"
            ],
            ServiceRole.REPORTING_SERVICE: [
                "read:projects", "read:documents", "write:reports", "read:templates"
            ],
            ServiceRole.FRONTEND_SERVICE: [
                "read:projects", "read:users", "read:settings"
            ]
        }
        return permissions_map.get(service_role, [])

# Global JWT service instance
jwt_config = JWTConfig(
    secret_key=os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production"),
    algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
    refresh_token_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    service_token_expire_hours=int(os.getenv("JWT_SERVICE_TOKEN_EXPIRE_HOURS", "24"))
)

jwt_service = JWTService(jwt_config)
