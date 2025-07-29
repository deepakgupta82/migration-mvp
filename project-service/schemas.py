"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Project schemas (updated to include users and LLM configuration)
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None

class ProjectCreate(ProjectBase):
    # Optional LLM configuration during creation
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = "0.1"
    llm_max_tokens: Optional[str] = "4000"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_contact: Optional[str] = None
    status: Optional[str] = None
    # LLM configuration updates
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = None
    llm_max_tokens: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: UUID
    status: str
    report_url: Optional[str] = None
    report_content: Optional[str] = None
    report_artifact_url: Optional[str] = None
    # LLM configuration
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[str] = None
    llm_max_tokens: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    users: List[UserResponse] = []

    class Config:
        from_attributes = True

# Platform Settings schemas
class PlatformSettingBase(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class PlatformSettingCreate(PlatformSettingBase):
    pass

class PlatformSettingUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None

class PlatformSettingResponse(PlatformSettingBase):
    last_updated_by: UUID
    updated_at: datetime
    updated_by_user: UserResponse

    class Config:
        from_attributes = True

# Deliverable Template schemas
class DeliverableTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: str

class DeliverableTemplateCreate(DeliverableTemplateBase):
    pass

class DeliverableTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None

class DeliverableTemplateResponse(DeliverableTemplateBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Project File schemas
class ProjectFileCreate(BaseModel):
    filename: str
    file_type: Optional[str] = None
    project_id: UUID

class ProjectFileResponse(BaseModel):
    id: UUID
    filename: str
    file_type: Optional[str] = None
    upload_timestamp: datetime
    project_id: UUID

    class Config:
        from_attributes = True

# Dashboard Stats schema
class ProjectStats(BaseModel):
    total_projects: int
    active_projects: int
    completed_assessments: int
    average_risk_score: Optional[float] = None
