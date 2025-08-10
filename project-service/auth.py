"""
Authentication utilities for the project service.
Handles JWT token creation, password hashing, and user authentication.
"""

from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db, UserModel, ProjectUserRoleModel, project_user_association
import os
from enum import Enum
from jwt_service import jwt_service, TokenType, ServiceRole
from typing import Optional, Dict, Any

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, email: str, password: str) -> Union[UserModel, bool]:
    """Authenticate a user by email and password."""
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserModel:
    """Get the current user from JWT token with backward compatibility."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Handle both "Bearer token" and "token" formats
    token_value = token.replace("Bearer ", "") if token.startswith("Bearer ") else token

    # Try JWT token first (NEW)
    try:
        payload = jwt_service.verify_token(token_value)
        return await _handle_jwt_payload(payload, db)
    except ValueError:
        # JWT verification failed, try legacy authentication
        pass

    # Fallback to legacy service token (BACKWARD COMPATIBILITY)
    service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
    if token_value == service_token:
        return await _get_or_create_service_user(db)

    # Fallback to legacy JWT (BACKWARD COMPATIBILITY)
    try:
        payload = jwt.decode(token_value, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

        user = db.query(UserModel).filter(UserModel.email == email).first()
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

async def _handle_jwt_payload(payload: Dict[str, Any], db: Session) -> UserModel:
    """Handle JWT payload and return user"""
    token_type = payload.get("token_type")

    if token_type == TokenType.SERVICE_ACCESS:
        # Service-to-service authentication
        return await _get_or_create_service_user(db)

    elif token_type in [TokenType.USER_ACCESS, TokenType.OAUTH_ACCESS]:
        # User authentication (local or OAuth)
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

        # Try to find user by ID first, then by email
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user and email:
            user = db.query(UserModel).filter(UserModel.email == email).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    else:
        raise HTTPException(status_code=401, detail="Invalid token type")

async def _get_or_create_service_user(db: Session) -> UserModel:
    """Get or create service user for service-to-service communication"""
    service_user = db.query(UserModel).filter(UserModel.email == "service@backend.local").first()
    if not service_user:
        import uuid
        from datetime import datetime
        service_user = UserModel(
            id=str(uuid.uuid4()),
            email="service@backend.local",
            hashed_password="service_user_no_password",
            role="platform_admin",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(service_user)
        db.commit()
        db.refresh(service_user)
    return service_user

async def get_current_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """Get the current user and verify they are a platform admin."""
    if current_user.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# NEW enhanced authentication functions (ADDITIVE)
class UserRole(str, Enum):
    """Enhanced user roles for the platform"""
    PLATFORM_ADMIN = "platform_admin"
    PROJECT_ADMIN = "project_admin"
    PROJECT_USER = "project_user"
    USER = "user"  # Keep for backward compatibility

async def get_current_user_with_project_access(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserModel:
    """Check if user has access to project (backward compatible)"""
    from uuid import UUID

    # Platform admins always have access (EXISTING BEHAVIOR)
    if current_user.role == "platform_admin":
        return current_user

    try:
        project_uuid = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")

    # Check old association table first (BACKWARD COMPATIBILITY)
    old_association = db.execute(
        project_user_association.select().where(
            project_user_association.c.user_id == current_user.id,
            project_user_association.c.project_id == project_uuid
        )
    ).first()

    if old_association:
        return current_user

    # Check new role table
    role_assignment = db.query(ProjectUserRoleModel).filter(
        ProjectUserRoleModel.user_id == current_user.id,
        ProjectUserRoleModel.project_id == project_uuid
    ).first()

    if role_assignment:
        return current_user

    raise HTTPException(status_code=403, detail="Access denied to this project")

def get_user_project_role(user_id: str, project_id: str, db: Session) -> str:
    """Get user's role for a specific project"""
    from uuid import UUID

    try:
        user_uuid = UUID(user_id)
        project_uuid = UUID(project_id)
    except ValueError:
        return "none"

    # Check user's platform role first
    user = db.query(UserModel).filter(UserModel.id == user_uuid).first()
    if not user:
        return "none"

    if user.role == "platform_admin":
        return "project_admin"

    # Check project-specific role
    role_assignment = db.query(ProjectUserRoleModel).filter(
        ProjectUserRoleModel.user_id == user_uuid,
        ProjectUserRoleModel.project_id == project_uuid
    ).first()

    if role_assignment:
        return role_assignment.role

    # Check old association table for backward compatibility
    old_association = db.execute(
        project_user_association.select().where(
            project_user_association.c.user_id == user_uuid,
            project_user_association.c.project_id == project_uuid
        )
    ).first()

    if old_association:
        return "project_user"  # Default role for old associations

    return "none"

def create_first_admin(db: Session, email: str, password: str) -> UserModel:
    """Create the first admin user if no users exist."""
    # Check if any users exist
    existing_user = db.query(UserModel).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users already exist. Cannot create first admin."
        )

    # Create the first admin
    hashed_password = get_password_hash(password)
    admin_user = UserModel(
        email=email,
        hashed_password=hashed_password,
        role="platform_admin"
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user
