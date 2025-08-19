"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
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

# NEW enhanced user response schema (ADDITIVE)
class EnhancedUserResponse(BaseModel):
    id: UUID
    email: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# NEW project role schemas (ADDITIVE)
class ProjectRoleInfo(BaseModel):
    project_id: UUID
    project_name: str
    role: str
    assigned_at: datetime
    assigned_by: Optional[UUID] = None

class ProjectRoleAssignment(BaseModel):
    role: str  # 'project_admin' or 'project_user'

class ProjectUserRoleResponse(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID
    role: str
    assigned_by: Optional[UUID] = None
    assigned_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Project schemas (updated to include users and LLM configuration)
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    project_overview: Optional[str] = None
    project_intent: Optional[str] = None
    # Extended project context fields (all optional)
    client_summary: Optional[str] = None
    rfp_summary: Optional[str] = None
    rfp_responses: Optional[str] = None
    expectations: Optional[str] = None
    deliverables_summary: Optional[str] = None
    timeline_notes: Optional[str] = None

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
    project_overview: Optional[str] = None
    project_intent: Optional[str] = None
    client_summary: Optional[str] = None
    rfp_summary: Optional[str] = None
    rfp_responses: Optional[str] = None
    expectations: Optional[str] = None
    deliverables_summary: Optional[str] = None
    timeline_notes: Optional[str] = None
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
    category: Optional[str] = "migration"
    output_format: Optional[str] = "pdf"
    template_content: Optional[str] = None

class DeliverableTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None

class DeliverableTemplateResponse(DeliverableTemplateBase):
    id: UUID
    project_id: Optional[UUID] = None  # Nullable for global templates
    template_type: Optional[str] = "project"
    category: Optional[str] = "migration"
    output_format: Optional[str] = "pdf"
    is_active: Optional[bool] = True
    created_by: Optional[UUID] = None
    template_content: Optional[str] = None
    usage_count: Optional[int] = 0
    last_used: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# LLM Configuration schemas
class LLMConfigurationBase(BaseModel):
    name: str
    provider: str  # openai, gemini, anthropic, etc.
    model: str     # gpt-4o, gemini-1.5-pro, etc.
    api_key: str
    temperature: str = "0.1"
    max_tokens: str = "4000"
    description: Optional[str] = None

class LLMConfigurationCreate(LLMConfigurationBase):
    pass

class LLMConfigurationUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None
    description: Optional[str] = None

class LLMConfigurationResponse(LLMConfigurationBase):
    id: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Project File schemas
class ProjectFileCreate(BaseModel):
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None  # File size in bytes
    project_id: UUID

class ProjectFileResponse(BaseModel):
    id: UUID
    filename: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None  # File size in bytes
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

# ---------------- LLM Process Config Schemas (for per-process configs) ----------------

class LLMConfigRequest(BaseModel):
    provider: str
    model: str
    api_key_id: Optional[str] = None
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 4000

class ProcessLLMConfigRequest(BaseModel):
    entity_extraction: Optional[LLMConfigRequest] = None
    crew_assessment: Optional[LLMConfigRequest] = None
    crew_documentation: Optional[LLMConfigRequest] = None
    rag_synthesis: Optional[LLMConfigRequest] = None
    hybrid_search: Optional[LLMConfigRequest] = None

class ProcessLLMConfigResponse(BaseModel):
    project_id: str
    entity_extraction: Optional[Dict[str, Any]] = None
    crew_assessment: Optional[Dict[str, Any]] = None
    crew_documentation: Optional[Dict[str, Any]] = None
    rag_synthesis: Optional[Dict[str, Any]] = None
    hybrid_search: Optional[Dict[str, Any]] = None

class ProcessLLMTestRequest(BaseModel):
    use_project_default: Optional[bool] = False
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.1
    api_key: Optional[str] = None
    api_key_id: Optional[str] = None
    query: Optional[str] = "Hello, please respond with 'OK' to confirm you're working."
