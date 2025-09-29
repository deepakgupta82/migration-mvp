# Project Service Documentation

## Service Overview

The Project Service is a specialized microservice for managing migration assessment projects in the Migration Platform. It handles all project-related operations including CRUD operations, user associations, LLM configurations, document templates, and project-specific settings.

**Port:** 8002
**Technology:** FastAPI (Python)
**Database:** PostgreSQL
**Role:** Project management and configuration

## Functionality

The Project Service provides comprehensive project management capabilities:

- **Project CRUD Operations:** Create, read, update, delete migration projects
- **User Management:** User registration, authentication, and project role assignments
- **LLM Configuration Management:** Project-specific and global LLM configurations
- **Template Management:** Global and project-specific document templates
- **File Management:** Project file tracking and metadata management
- **Statistics & Analytics:** Project statistics and usage tracking
- **Role-based Access Control:** Platform admin and project user permissions
- **Content Aggregation:** Efficient project content overview and statistics

## APIs/Endpoints

### Authentication
- `POST /token` - User login and JWT token generation
- `POST /users/register` - User registration
- `GET /users/me` - Get current user information
- `GET /users` - List all users (admin only)
- `GET /users/enhanced` - Enhanced user listing with pagination

### Project Management
- `POST /projects` - Create new project
- `GET /projects` - List accessible projects
- `GET /projects/{project_id}` - Get project details
- `PUT /projects/{project_id}` - Update project
- `DELETE /projects/{project_id}` - Delete project
- `GET /projects/stats` - Dashboard project statistics
- `GET /projects/{project_id}/stats` - Individual project statistics

### Project Files
- `POST /projects/{project_id}/files` - Add file record to project
- `GET /api/projects/{project_id}/files` - Get project files
- `GET /projects/{project_id}/files/count` - Get file count
- `PUT /projects/{project_id}/files/{file_id}` - Update file record
- `DELETE /projects/{project_id}/files/{file_id}` - Delete file record

### LLM Configuration
- `GET /llm-configurations` - List LLM configurations
- `POST /llm-configurations` - Create LLM configuration
- `GET /llm-configurations/{config_id}` - Get specific configuration
- `PUT /llm-configurations/{config_id}` - Update configuration
- `DELETE /llm-configurations/{config_id}` - Delete configuration
- `GET /models/{provider}` - Get cached models for provider
- `POST /models/{provider}/cache` - Cache models for provider

### Project LLM Configuration
- `GET /projects/{project_id}/llm-config` - Get project default LLM config
- `GET /projects/{project_id}/llm-process-configs` - Get process-specific LLM configs
- `POST /projects/{project_id}/llm-process-configs` - Update process LLM configs
- `POST /projects/{project_id}/process-llm-config/{process_key}/test` - Test LLM config

### Templates
- `GET /templates/global` - List global document templates
- `POST /templates/global` - Create global template
- `DELETE /templates/global/{template_id}` - Delete global template
- `GET /projects/{project_id}/deliverables` - List project deliverables
- `POST /projects/{project_id}/deliverables` - Create project deliverable
- `PUT /projects/{project_id}/deliverables/{template_id}` - Update deliverable
- `DELETE /projects/{project_id}/deliverables/{template_id}` - Delete deliverable

### Template Usage Tracking
- `POST /template-usage` - Track template usage
- `GET /projects/{project_id}/template-usage` - Get project template usage
- `GET /template-usage/global` - Get global template usage (admin)

### Generation Requests
- `GET /projects/{project_id}/generation-requests` - Get generation requests
- `POST /projects/{project_id}/generation-requests` - Create generation request
- `PUT /projects/{project_id}/generation-requests/{request_id}` - Update generation request

### Project Content
- `GET /projects/{project_id}/content-aggregation` - Get content aggregation
- `GET /templates/all/{project_id}` - Get all available templates

### Platform Settings
- `GET /settings` - List platform settings
- `POST /settings` - Create platform setting
- `PUT /settings/{setting_key}` - Update platform setting
- `DELETE /settings/{setting_key}` - Delete platform setting

### Project Roles
- `POST /projects/{project_id}/users/{user_id}/assign-role` - Assign project role
- `GET /projects/{project_id}/users` - List project users with roles
- `DELETE /projects/{project_id}/users/{user_id}` - Remove user from project

### Health & Monitoring
- `GET /livez` - Liveness probe
- `GET /healthz` - Readiness probe
- `GET /health` - Health check
- `GET /db/status` - Database status
- `GET /db/version` - Database version

## Data Models/Schemas

### User Models
```python
class UserCreate(BaseModel):
    email: str
    password: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

class EnhancedUserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
```

### Project Models
```python
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    rfp_summary: Optional[str] = None
    timeline_notes: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client_name: str
    client_contact: Optional[str] = None
    status: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    users: List[UserResponse] = []
```

### LLM Configuration Models
```python
class LLMConfigurationCreate(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None

class LLMConfigurationResponse(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None
```

### Template Models
```python
class DeliverableTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: str
    category: Optional[str] = "migration"
    output_format: Optional[str] = "pdf"
    template_content: Optional[str] = ""

class DeliverableTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    prompt: str
    project_id: Optional[str] = None
    template_type: str
    category: Optional[str] = None
    output_format: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
```

## Key Components

### Database Layer
- **SQLAlchemy Models**: ProjectModel, UserModel, ProjectFileModel, LLMConfigurationModel, etc.
- **Database Connection**: PostgreSQL with connection pooling and health checks
- **Migration Support**: Automatic schema updates and backward compatibility

### Repository Pattern
- **Project Repository**: Project CRUD operations and statistics
- **User Repository**: User management and authentication
- **LLM Config Repository**: LLM configuration management
- **Template Repository**: Document template operations
- **Template Usage Repository**: Usage tracking and analytics

### Authentication & Authorization
- **JWT Authentication**: Token-based auth with configurable expiration
- **Password Hashing**: Secure password storage using bcrypt
- **Role-based Access**: Platform admin vs project user permissions
- **Project-specific Roles**: Enhanced role assignments per project

### Caching System
- **In-memory Cache**: TTLCache for projects, stats, and templates
- **Cache Invalidation**: Automatic cache clearing on data changes
- **Thread-safe Operations**: Lock-protected cache access

### Middleware
- **Correlation ID**: Request tracing across service calls
- **Database Error Handling**: Graceful degradation on DB issues
- **Trailing Slash Redirect**: Canonical URL enforcement
- **CORS**: Configurable cross-origin resource sharing

## Data Flow

### Project Creation
1. **Validation**: Input validation and UUID format checking
2. **Database Transaction**: Create project with user association
3. **Cache Invalidation**: Clear relevant caches
4. **Event Publishing**: Notify other services of project creation

### LLM Configuration Resolution
1. **Project Lookup**: Retrieve project-specific LLM settings
2. **Configuration Fetch**: Get stored API keys and parameters
3. **Fallback Logic**: Use project defaults or global fallbacks
4. **Response Formatting**: Return normalized configuration object

### Template Usage Tracking
1. **Usage Recording**: Log template usage with metadata
2. **Statistics Aggregation**: Calculate usage patterns and metrics
3. **Analytics Generation**: Provide insights on template effectiveness

### User Authentication
1. **Credential Validation**: Verify email/password combination
2. **Token Generation**: Create JWT with user claims and expiration
3. **Role Assignment**: Determine permissions based on user role
4. **Session Management**: Handle token refresh and invalidation

## Complete Working Details

### Startup Process
1. **Database Initialization**: Create tables and run migrations
2. **Schema Updates**: Add additive columns for backward compatibility
3. **Model Seeding**: Populate default LLM models for providers
4. **Cache Setup**: Initialize in-memory caches with appropriate TTL
5. **Health Checks**: Verify database connectivity and dependencies

### Configuration Management
- **Environment Variables**: Database URLs, JWT secrets, service ports
- **Local Config File**: `config.local.json` for development overrides
- **Dynamic Loading**: Runtime configuration reloading without restart

### Security Features
- **Input Sanitization**: SQL injection prevention and XSS protection
- **UUID Validation**: Strict UUID format enforcement for IDs
- **Password Security**: Strong hashing with salt and pepper
- **API Key Management**: Secure storage of LLM API keys

### Performance Optimizations
- **Database Indexing**: Optimized queries with proper indexing
- **Connection Pooling**: Efficient database connection reuse
- **Query Optimization**: Efficient aggregation queries for statistics
- **Caching Strategy**: Multi-level caching for frequently accessed data

### Monitoring & Observability
- **Health Endpoints**: Liveness, readiness, and detailed status checks
- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Metrics Collection**: Usage statistics and performance monitoring
- **Error Tracking**: Comprehensive error handling and reporting

### Integration Points
- **Backend Gateway**: Primary API gateway for client requests
- **Document Service**: File upload and processing coordination
- **LLM Service**: Model validation and provider management
- **AI Agent Service**: Crew workflow triggering on project completion
- **Storage Service**: File metadata and storage coordination

The Project Service serves as the central data management layer, maintaining project state, user associations, and configuration while providing efficient access patterns for the entire platform.