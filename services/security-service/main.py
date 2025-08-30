"""
Multi-Tenant Security & RBAC Service

This service provides:
1. Multi-tenant authentication and authorization
2. Role-based access control (RBAC)
3. Security policy management
4. Audit logging and compliance
5. JWT token management and validation
"""

import asyncio
import json
import logging
import os
import uuid
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure uvicorn loggers use same handlers/formatters
_root_logger = logging.getLogger()
for _lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uvl = logging.getLogger(_lname)
    _uvl.setLevel(logging.INFO)
    for _h in list(_uvl.handlers):
        _uvl.removeHandler(_h)
    for _h in _root_logger.handlers:
        _uvl.addHandler(_h)
    _uvl.propagate = False

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    PROJECT_MANAGER = "project_manager"
    MIGRATION_SPECIALIST = "migration_specialist"
    ANALYST = "analyst"
    VIEWER = "viewer"

class Permission(str, Enum):
    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    
    # User management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # Analytics and reports
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_CREATE = "analytics:create"
    
    # Security management
    SECURITY_MANAGE = "security:manage"
    AUDIT_READ = "audit:read"
    
    # Agent orchestration
    AGENT_MANAGE = "agent:manage"
    AGENT_READ = "agent:read"

@dataclass
class TenantInfo:
    """Tenant information"""
    tenant_id: str
    name: str
    domain: str
    subscription_plan: str
    max_users: int
    max_projects: int
    features_enabled: List[str]
    created_at: datetime
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

@dataclass
class UserInfo:
    """User information"""
    user_id: str
    tenant_id: str
    username: str
    email: str
    full_name: str
    role: UserRole
    permissions: Set[Permission]
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['permissions'] = list(self.permissions)
        if self.last_login:
            data['last_login'] = self.last_login.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data

@dataclass
class AuditLog:
    """Audit log entry"""
    log_id: str
    tenant_id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    ip_address: str
    user_agent: str
    timestamp: datetime
    success: bool
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class SecurityPolicy:
    """Security policy configuration"""
    policy_id: str
    tenant_id: str
    name: str
    description: str
    rules: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

class SecurityManager:
    """Manages multi-tenant security and RBAC"""
    
    def __init__(self):
        self.tenants: Dict[str, TenantInfo] = {}
        self.users: Dict[str, UserInfo] = {}  # user_id -> UserInfo
        self.user_credentials: Dict[str, str] = {}  # username -> hashed_password
        self.audit_logs: List[AuditLog] = []
        self.security_policies: Dict[str, SecurityPolicy] = {}  # policy_id -> SecurityPolicy
        self.active_sessions: Dict[str, Dict[str, Any]] = {}  # token -> session_info
        
        # JWT configuration
        self.jwt_secret = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
        self.jwt_algorithm = "HS256"
        self.token_expiry_hours = 24
        
        # Initialize role permissions mapping
        self._init_role_permissions()
        
        # Service URLs
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        
        logger.info("Security Manager initialized")
    
    def _init_role_permissions(self):
        """Initialize role-based permissions mapping"""
        self.role_permissions = {
            UserRole.SUPER_ADMIN: {
                Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
                Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE, Permission.USER_DELETE,
                Permission.ANALYTICS_READ, Permission.ANALYTICS_CREATE,
                Permission.SECURITY_MANAGE, Permission.AUDIT_READ,
                Permission.AGENT_MANAGE, Permission.AGENT_READ
            },
            UserRole.TENANT_ADMIN: {
                Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
                Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE,
                Permission.ANALYTICS_READ, Permission.ANALYTICS_CREATE,
                Permission.AUDIT_READ, Permission.AGENT_MANAGE, Permission.AGENT_READ
            },
            UserRole.PROJECT_MANAGER: {
                Permission.PROJECT_CREATE, Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
                Permission.USER_READ, Permission.ANALYTICS_READ, Permission.ANALYTICS_CREATE,
                Permission.AGENT_READ
            },
            UserRole.MIGRATION_SPECIALIST: {
                Permission.PROJECT_READ, Permission.PROJECT_UPDATE,
                Permission.ANALYTICS_READ, Permission.AGENT_READ
            },
            UserRole.ANALYST: {
                Permission.PROJECT_READ, Permission.ANALYTICS_READ, Permission.ANALYTICS_CREATE
            },
            UserRole.VIEWER: {
                Permission.PROJECT_READ, Permission.ANALYTICS_READ
            }
        }
    
    async def create_tenant(self, name: str, domain: str, subscription_plan: str = "standard") -> str:
        """Create a new tenant"""
        tenant_id = str(uuid.uuid4())
        
        max_users = {"basic": 10, "standard": 50, "premium": 200, "enterprise": 1000}.get(subscription_plan, 50)
        max_projects = {"basic": 5, "standard": 25, "premium": 100, "enterprise": 500}.get(subscription_plan, 25)
        
        features = {
            "basic": ["basic_migration", "basic_analytics"],
            "standard": ["basic_migration", "basic_analytics", "cloud_tools", "document_processing"],
            "premium": ["basic_migration", "advanced_analytics", "cloud_tools", "document_processing", "agent_orchestration"],
            "enterprise": ["basic_migration", "advanced_analytics", "cloud_tools", "document_processing", "agent_orchestration", "security_rbac", "audit_logging"]
        }.get(subscription_plan, ["basic_migration", "basic_analytics"])
        
        tenant = TenantInfo(
            tenant_id=tenant_id,
            name=name,
            domain=domain,
            subscription_plan=subscription_plan,
            max_users=max_users,
            max_projects=max_projects,
            features_enabled=features,
            created_at=datetime.now()
        )
        
        self.tenants[tenant_id] = tenant
        
        # Create default admin user for the tenant
        await self.create_user(
            tenant_id=tenant_id,
            username=f"admin@{domain}",
            email=f"admin@{domain}",
            full_name="Tenant Administrator",
            password="admin123",  # Should be changed on first login
            role=UserRole.TENANT_ADMIN
        )
        
        logger.info(f"Created tenant {name} with ID {tenant_id}")
        return tenant_id
    
    async def create_user(self, tenant_id: str, username: str, email: str, full_name: str, 
                         password: str, role: UserRole) -> str:
        """Create a new user"""
        if tenant_id not in self.tenants:
            raise ValueError("Tenant not found")
        
        # Check if username already exists
        if username in self.user_credentials:
            raise ValueError("Username already exists")
        
        user_id = str(uuid.uuid4())
        
        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Get permissions for role
        permissions = self.role_permissions.get(role, set())
        
        user = UserInfo(
            user_id=user_id,
            tenant_id=tenant_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            permissions=permissions,
            is_active=True,
            created_at=datetime.now()
        )
        
        self.users[user_id] = user
        self.user_credentials[username] = password_hash
        
        logger.info(f"Created user {username} with role {role} for tenant {tenant_id}")
        return user_id
    
    async def authenticate_user(self, username: str, password: str, ip_address: str, user_agent: str) -> Optional[str]:
        """Authenticate user and return JWT token"""
        try:
            # Verify credentials
            if username not in self.user_credentials:
                await self._log_audit("authentication", "user", username, 
                                    {"reason": "user_not_found"}, ip_address, user_agent, False)
                return None
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if self.user_credentials[username] != password_hash:
                await self._log_audit("authentication", "user", username,
                                    {"reason": "invalid_password"}, ip_address, user_agent, False)
                return None
            
            # Find user
            user = None
            for u in self.users.values():
                if u.username == username:
                    user = u
                    break
            
            if not user or not user.is_active:
                await self._log_audit("authentication", "user", username,
                                    {"reason": "user_inactive"}, ip_address, user_agent, False)
                return None
            
            # Check tenant status
            tenant = self.tenants.get(user.tenant_id)
            if not tenant or not tenant.is_active:
                await self._log_audit("authentication", "user", username,
                                    {"reason": "tenant_inactive"}, ip_address, user_agent, False)
                return None
            
            # Generate JWT token
            payload = {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "username": user.username,
                "role": user.role,
                "permissions": list(user.permissions),
                "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Store session
            self.active_sessions[token] = {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "created_at": datetime.now(),
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            
            # Update last login
            user.last_login = datetime.now()
            
            await self._log_audit("authentication", "user", user.user_id,
                                {"username": username}, ip_address, user_agent, True)
            
            logger.info(f"User {username} authenticated successfully")
            return token
            
        except Exception as e:
            logger.error(f"Authentication error for {username}: {e}")
            await self._log_audit("authentication", "user", username,
                                {"error": str(e)}, ip_address, user_agent, False)
            return None
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token and return user info"""
        try:
            if token not in self.active_sessions:
                return None
            
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if user still exists and is active
            user = self.users.get(payload["user_id"])
            if not user or not user.is_active:
                # Remove invalid session
                if token in self.active_sessions:
                    del self.active_sessions[token]
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            # Remove expired session
            if token in self.active_sessions:
                del self.active_sessions[token]
            return None
        except jwt.InvalidTokenError:
            return None
    
    async def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has specific permission"""
        user = self.users.get(user_id)
        if not user or not user.is_active:
            return False
        
        return permission in user.permissions
    
    async def logout_user(self, token: str, ip_address: str, user_agent: str):
        """Logout user and invalidate token"""
        if token in self.active_sessions:
            session = self.active_sessions[token]
            user_id = session["user_id"]
            
            del self.active_sessions[token]
            
            await self._log_audit("logout", "user", user_id,
                                {"token_invalidated": True}, ip_address, user_agent, True)
            
            logger.info(f"User {user_id} logged out")
    
    async def _log_audit(self, action: str, resource_type: str, resource_id: str,
                        details: Dict[str, Any], ip_address: str, user_agent: str, success: bool):
        """Log audit entry"""
        log_entry = AuditLog(
            log_id=str(uuid.uuid4()),
            tenant_id=details.get("tenant_id", "unknown"),
            user_id=details.get("user_id", resource_id),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.now(),
            success=success
        )
        
        self.audit_logs.append(log_entry)
        
        # Keep only last 10000 logs to prevent memory issues
        if len(self.audit_logs) > 10000:
            self.audit_logs = self.audit_logs[-5000:]
    
    def get_tenant_info(self, tenant_id: str) -> Optional[TenantInfo]:
        """Get tenant information"""
        return self.tenants.get(tenant_id)
    
    def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        """Get user information"""
        return self.users.get(user_id)
    
    def get_tenant_users(self, tenant_id: str) -> List[UserInfo]:
        """Get all users for a tenant"""
        return [user for user in self.users.values() if user.tenant_id == tenant_id]
    
    def get_audit_logs(self, tenant_id: str, limit: int = 100) -> List[AuditLog]:
        """Get audit logs for a tenant"""
        tenant_logs = [log for log in self.audit_logs if log.tenant_id == tenant_id]
        return sorted(tenant_logs, key=lambda x: x.timestamp, reverse=True)[:limit]

# Global security manager
security_manager = SecurityManager()
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """Get current authenticated user"""
    user_info = await security_manager.validate_token(credentials.credentials)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_info

def require_permission(permission: Permission):
    """Decorator to require specific permission"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get user from dependency injection
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            has_permission = await security_manager.check_permission(current_user["user_id"], permission)
            if not has_permission:
                raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Multi-Tenant Security & RBAC Service started successfully")
    
    # Create default tenant for demo
    await security_manager.create_tenant(
        name="Nagarro Demo",
        domain="nagarro.com",
        subscription_plan="enterprise"
    )
    
    yield
    
    # Shutdown
    logger.info("Multi-Tenant Security & RBAC Service shut down successfully")

# FastAPI app
app = FastAPI(
    title="Multi-Tenant Security & RBAC Service",
    description="Enterprise security and access control for Nagarro Ascent Platform",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    role: UserRole

class CreateTenantRequest(BaseModel):
    name: str
    domain: str
    subscription_plan: str = "standard"

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "3.0.0"
    service: str = "security-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/auth/login")
async def login(request: LoginRequest, req: Request):
    """User login"""
    ip_address = req.client.host
    user_agent = req.headers.get("user-agent", "unknown")
    
    token = await security_manager.authenticate_user(
        request.username, request.password, ip_address, user_agent
    )
    
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/logout")
async def logout(req: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """User logout"""
    token = req.headers.get("authorization", "").replace("Bearer ", "")
    ip_address = req.client.host
    user_agent = req.headers.get("user-agent", "unknown")
    
    await security_manager.logout_user(token, ip_address, user_agent)
    return {"message": "Logged out successfully"}

@app.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    user_info = security_manager.get_user_info(current_user["user_id"])
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"user": user_info.to_dict()}

@app.post("/tenants")
async def create_tenant(request: CreateTenantRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create new tenant (super admin only)"""
    if current_user["role"] != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super admin access required")
    
    tenant_id = await security_manager.create_tenant(
        request.name, request.domain, request.subscription_plan
    )
    
    return {"tenant_id": tenant_id, "message": "Tenant created successfully"}

@app.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get tenant information"""
    # Users can only access their own tenant unless they're super admin
    if current_user["role"] != UserRole.SUPER_ADMIN and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tenant = security_manager.get_tenant_info(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {"tenant": tenant.to_dict()}

@app.post("/tenants/{tenant_id}/users")
async def create_user(tenant_id: str, request: CreateUserRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create new user in tenant"""
    # Check permissions
    if not await security_manager.check_permission(current_user["user_id"], Permission.USER_CREATE):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Users can only create users in their own tenant unless they're super admin
    if current_user["role"] != UserRole.SUPER_ADMIN and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        user_id = await security_manager.create_user(
            tenant_id, request.username, request.email, 
            request.full_name, request.password, request.role
        )
        return {"user_id": user_id, "message": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tenants/{tenant_id}/users")
async def get_tenant_users(tenant_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all users in tenant"""
    # Check permissions
    if not await security_manager.check_permission(current_user["user_id"], Permission.USER_READ):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Users can only access their own tenant unless they're super admin
    if current_user["role"] != UserRole.SUPER_ADMIN and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    users = security_manager.get_tenant_users(tenant_id)
    return {
        "tenant_id": tenant_id,
        "users": [user.to_dict() for user in users],
        "total_users": len(users)
    }

@app.get("/tenants/{tenant_id}/audit-logs")
async def get_audit_logs(tenant_id: str, limit: int = 100, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get audit logs for tenant"""
    # Check permissions
    if not await security_manager.check_permission(current_user["user_id"], Permission.AUDIT_READ):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Users can only access their own tenant unless they're super admin
    if current_user["role"] != UserRole.SUPER_ADMIN and current_user["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    logs = security_manager.get_audit_logs(tenant_id, limit)
    return {
        "tenant_id": tenant_id,
        "logs": [log.to_dict() for log in logs],
        "total_logs": len(logs)
    }

@app.get("/permissions/check/{permission}")
async def check_user_permission(permission: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Check if current user has specific permission"""
    try:
        perm = Permission(permission)
        has_permission = await security_manager.check_permission(current_user["user_id"], perm)
        return {
            "user_id": current_user["user_id"],
            "permission": permission,
            "has_permission": has_permission
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8015,
        reload=True,
        log_level="info"
    )