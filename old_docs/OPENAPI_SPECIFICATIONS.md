# OpenAPI Specifications

This document contains OpenAPI 3.0 specifications for all Migration Platform services.

## Table of Contents

- [Document Service](#document-service)
- [Analytics Service](#analytics-service)
- [LLM Service](#llm-service)
- [Project Service](#project-service)
- [Backend Gateway](#backend-gateway)

---

## Document Service

**Base URL:** `http://localhost:8003`
**OpenAPI Version:** 3.0.3

### Health Endpoints

#### GET /livez
Liveness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "document-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0"
}
```

#### GET /healthz
Readiness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "document-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0",
  "dependencies": {
    "minio": "healthy",
    "postgresql": "healthy"
  }
}
```

#### GET /health
Health check endpoint (backward compatibility).

**Response (200):** Same as `/healthz`

### Document Processing Endpoints

#### POST /{project_id}/upload
Upload documents to the service.

**Parameters:**
- `project_id` (path): Project identifier
- `files` (form): List of files to upload

**Request Body:**
```
Content-Type: multipart/form-data
files: [file1.pdf, file2.docx, ...]
```

**Response (200):**
```json
{
  "project_id": "uuid",
  "uploaded_files": [
    {
      "filename": "document.pdf",
      "size": 1024000,
      "uploaded_at": "2025-09-03T12:19:02.953Z"
    }
  ],
  "total_uploaded": 1,
  "message": "Successfully uploaded 1 files",
  "analysis_triggered": true
}
```

#### POST /{project_id}/process-all
Process all uploaded documents for a project.

**Parameters:**
- `project_id` (path): Project identifier

**Request Body:**
```json
{
  "file_names": ["document1.pdf", "document2.docx"],
  "reprocess": false
}
```

**Response (200):**
```json
{
  "project_id": "uuid",
  "job_id": "uuid",
  "status": "started",
  "files_to_process": ["document1.pdf"],
  "message": "Processing started",
  "started_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /{project_id}/status/{job_id}
Get processing status for a job.

**Parameters:**
- `project_id` (path): Project identifier
- `job_id` (path): Job identifier

**Response (200):**
```json
{
  "project_id": "uuid",
  "job_id": "uuid",
  "status": "completed",
  "total_files": 5,
  "processed_files": 5,
  "failed_files": 0,
  "files_status": [
    {
      "filename": "document.pdf",
      "status": "completed",
      "conversion_strategy": "markitdown",
      "timestamp": "2025-09-03T12:19:02.953Z"
    }
  ],
  "started_at": "2025-09-03T12:19:02.953Z",
  "completed_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /{project_id}/files
List uploaded files for a project.

**Parameters:**
- `project_id` (path): Project identifier

**Response (200):**
```json
{
  "files": [
    {
      "filename": "document.pdf",
      "size": 1024000,
      "uploaded_at": "2025-09-03T12:19:02.953Z",
      "processed": true
    }
  ],
  "total": 1
}
```

### Analysis Endpoints

#### POST /{project_id}/analysis
Create a new analysis result.

**Parameters:**
- `project_id` (path): Project identifier

**Request Body:**
```json
{
  "analysis_type": "content_analysis",
  "filename": "document.pdf",
  "content": "Analysis content...",
  "metadata": {
    "confidence": 0.95,
    "processing_time": 2.5
  }
}
```

**Response (201):**
```json
{
  "analysis_id": "uuid",
  "project_id": "uuid",
  "analysis_type": "content_analysis",
  "filename": "document.pdf",
  "created_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /{project_id}/analysis/{analysis_id}
Get a specific analysis result.

**Parameters:**
- `project_id` (path): Project identifier
- `analysis_id` (path): Analysis identifier

**Response (200):**
```json
{
  "analysis_id": "uuid",
  "project_id": "uuid",
  "filename": "document.pdf",
  "analysis_type": "content_analysis",
  "content": "Analysis content...",
  "metadata": {
    "confidence": 0.95,
    "processing_time": 2.5
  },
  "created_at": "2025-09-03T12:19:02.953Z",
  "updated_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /{project_id}/analysis
List analysis results for a project.

**Parameters:**
- `project_id` (path): Project identifier
- `analysis_type` (query): Filter by analysis type
- `filename` (query): Filter by filename
- `limit` (query): Maximum results (default: 50)
- `offset` (query): Pagination offset (default: 0)

**Response (200):**
```json
{
  "results": [
    {
      "analysis_id": "uuid",
      "filename": "document.pdf",
      "analysis_type": "content_analysis",
      "created_at": "2025-09-03T12:19:02.953Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

## Analytics Service

**Base URL:** `http://localhost:8014`
**OpenAPI Version:** 3.0.3

### Health Endpoints

#### GET /livez
Liveness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "analytics-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "3.0.0"
}
```

#### GET /healthz
Readiness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "analytics-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "3.0.0",
  "dependencies": {
    "postgresql": "healthy",
    "redis": "healthy"
  }
}
```

#### GET /health
Health check endpoint (backward compatibility).

**Response (200):** Same as `/healthz`

### Analytics Endpoints

#### POST /analytics/migration-complexity
Generate migration complexity analysis.

**Parameters:**
- `project_id` (query): Project identifier

**Request Body:**
```json
{
  "project_id": "uuid"
}
```

**Response (200):**
```json
{
  "report": {
    "report_id": "uuid",
    "title": "Migration Complexity Analysis - Project uuid",
    "report_type": "migration_complexity",
    "project_id": "uuid",
    "generated_at": "2025-09-03T12:19:02.953Z",
    "summary": "Overall migration complexity score: 65.2/100",
    "recommendations": [
      "Implement phased migration approach",
      "Conduct comprehensive risk assessment"
    ],
    "metrics": {
      "overall_complexity": 65.2,
      "infrastructure_complexity": 70.5,
      "dependency_complexity": 60.1,
      "data_complexity": 65.8
    },
    "charts_data": {
      "complexity_breakdown": {
        "labels": ["Infrastructure", "Dependencies", "Data"],
        "values": [70.5, 60.1, 65.8]
      }
    }
  }
}
```

#### POST /analytics/cost-optimization
Generate cost optimization analysis.

**Parameters:**
- `project_id` (query): Project identifier (optional)

**Request Body:**
```json
{
  "project_id": "uuid"
}
```

**Response (200):**
```json
{
  "report": {
    "report_id": "uuid",
    "title": "Cost Optimization Analysis",
    "report_type": "cost_optimization",
    "project_id": "uuid",
    "generated_at": "2025-09-03T12:19:02.953Z",
    "summary": "Potential monthly savings: $2500.00 (25.0% optimization)",
    "recommendations": [
      "Implement automated resource scheduling",
      "Review and optimize storage tiers"
    ],
    "metrics": {
      "current_monthly_cost": 10000.0,
      "potential_savings": 2500.0,
      "waste_percentage": 25.0,
      "efficiency_score": 75.0
    },
    "charts_data": {
      "cost_breakdown": {
        "labels": ["Compute", "Storage", "Network", "Database"],
        "values": [4500.0, 2500.0, 1500.0, 1500.0]
      }
    }
  }
}
```

#### GET /analytics/system-health
Get comprehensive system health analysis.

**Response (200):**
```json
{
  "report": {
    "report_id": "uuid",
    "title": "System Health Analysis",
    "report_type": "system_health",
    "generated_at": "2025-09-03T12:19:02.953Z",
    "summary": "Overall system health: 85.0% with 2 active alerts",
    "recommendations": [
      "Monitor CPU usage trends",
      "Review memory utilization"
    ],
    "metrics": {
      "overall_health_score": 85.0,
      "cpu_health_score": 80.0,
      "memory_health_score": 90.0,
      "active_alerts_count": 2,
      "system_uptime_days": 30
    },
    "alerts": [
      {
        "alert_id": "uuid",
        "title": "High CPU usage detected",
        "severity": "medium",
        "created_at": "2025-09-03T12:19:02.953Z"
      }
    ]
  }
}
```

### Metrics Endpoints

#### POST /metrics
Add real-time metric data.

**Request Body:**
```json
{
  "metric_name": "system_cpu_usage",
  "value": 75.5,
  "metadata": {
    "source": "monitoring_agent",
    "server": "web-01"
  }
}
```

**Response (200):**
```json
{
  "message": "Metric data added successfully"
}
```

#### GET /metrics/real-time
Get real-time metrics data.

**Parameters:**
- `metric_names` (query): Comma-separated list of metric names
- `limit` (query): Maximum data points per metric (default: 100)

**Response (200):**
```json
{
  "metrics": {
    "system_cpu_usage": [
      {
        "timestamp": "2025-09-03T12:19:02.953Z",
        "value": 75.5,
        "metadata": {
          "source": "monitoring_agent"
        }
      }
    ]
  }
}
```

#### GET /alerts
Get alerts with optional filtering.

**Parameters:**
- `severity` (query): Filter by severity (low, medium, high, critical)
- `project_id` (query): Filter by project ID

**Response (200):**
```json
{
  "alerts": [
    {
      "alert_id": "uuid",
      "title": "High CPU usage detected",
      "description": "CPU usage exceeded 80% for 5 minutes",
      "severity": "medium",
      "category": "performance",
      "created_at": "2025-09-03T12:19:02.953Z",
      "project_id": null,
      "is_resolved": false
    }
  ],
  "total_count": 1
}
```

---

## LLM Service

**Base URL:** `http://localhost:8007`
**OpenAPI Version:** 3.0.3

### Health Endpoints

#### GET /livez
Liveness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "llm-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0"
}
```

#### GET /healthz
Readiness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "llm-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0",
  "dependencies": {
    "postgresql": "healthy",
    "redis": "healthy"
  }
}
```

#### GET /health
Clean health check endpoint.

**Response (200):**
```json
{
  "service": "llm-service",
  "status": "healthy",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0",
  "langchain_available": true,
  "supported_providers": ["openai", "anthropic", "gemini", "ollama"],
  "process_types": ["entity_extraction", "crew_assessment", "rag_synthesis"],
  "cache_status": {
    "configurations_cached": 5,
    "cache_hit_rate": 0.85
  },
  "dependencies": {
    "postgresql": "healthy",
    "redis": "healthy"
  }
}
```

### Core LLM Endpoints

#### POST /api/llm/process
Process LLM request for specific process type.

**Request Body:**
```json
{
  "process_type": "entity_extraction",
  "prompt": "Extract entities from this text...",
  "project_id": "uuid",
  "allow_global": true
}
```

**Response (200):**
```json
{
  "process_type": "entity_extraction",
  "response": "Extracted entities: [Person: John Doe, Organization: Acme Corp]",
  "success": true
}
```

#### GET /api/llm/providers
List available LLM providers.

**Response (200):**
```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "supported_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
      "status": "available"
    },
    {
      "name": "anthropic",
      "display_name": "Anthropic",
      "supported_models": ["claude-3-5-sonnet", "claude-3-opus"],
      "status": "available"
    }
  ]
}
```

#### GET /api/llm/providers/status
Get status and configuration info for all providers.

**Response (200):**
```json
{
  "provider_status": {
    "openai": {
      "status": "configured",
      "models_available": 3,
      "last_tested": "2025-09-03T12:19:02.953Z"
    },
    "anthropic": {
      "status": "configured",
      "models_available": 2,
      "last_tested": "2025-09-03T12:19:02.953Z"
    }
  }
}
```

#### POST /api/llm/cluster
Perform LLM-assisted semantic clustering.

**Request Body:**
```json
{
  "project_id": "uuid",
  "items": [
    {
      "id": "item1",
      "text": "Machine learning algorithms for data processing",
      "metadata": {
        "type": "technical"
      }
    },
    {
      "id": "item2",
      "text": "Neural network architectures and applications",
      "metadata": {
        "type": "technical"
      }
    }
  ],
  "max_clusters": 5,
  "hint": "technical documentation"
}
```

**Response (200):**
```json
{
  "clusters": [
    {
      "id": "cluster_1",
      "label": "Machine Learning Fundamentals",
      "items": ["item1", "item2"],
      "size": 2,
      "confidence": 0.85
    }
  ],
  "success": true
}
```

### Configuration Management

#### GET /api/llm/configurations
Get LLM configurations.

**Response (200):**
```json
[
  {
    "id": "config_1",
    "name": "OpenAI GPT-4",
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": "0.1",
    "max_tokens": "2000",
    "description": "Primary OpenAI configuration",
    "created_at": "2025-09-03T12:19:02.953Z",
    "updated_at": "2025-09-03T12:19:02.953Z"
  }
]
```

#### POST /api/llm/configurations
Create a new LLM configuration.

**Request Body:**
```json
{
  "name": "Anthropic Claude",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "api_key": "sk-ant-api03-...",
  "temperature": "0.1",
  "max_tokens": "20000",
  "description": "Anthropic Claude configuration"
}
```

**Response (201):**
```json
{
  "id": "config_2",
  "name": "Anthropic Claude",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "temperature": "0.1",
  "max_tokens": "20000",
  "description": "Anthropic Claude configuration",
  "created_at": "2025-09-03T12:19:02.953Z",
  "updated_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /api/llm/models/{provider}
List available models for a provider.

**Parameters:**
- `provider` (path): Provider name (openai, anthropic, gemini, ollama)

**Response (200):**
```json
{
  "provider": "openai",
  "models": [
    {
      "id": "gpt-4o",
      "name": "GPT-4o",
      "description": "OpenAI GPT-4o - Most capable model"
    },
    {
      "id": "gpt-4o-mini",
      "name": "GPT-4o Mini",
      "description": "OpenAI GPT-4o Mini - Fast and efficient"
    }
  ],
  "cached": true
}
```

#### POST /api/llm/test-llm-config
Test LLM configuration by making a real API call.

**Request Body:**
```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "temperature": 0.1,
  "max_tokens": 100,
  "query": "TEST REQUEST: Please respond with 'TEST SUCCESSFUL'"
}
```

**Response (200):**
```json
{
  "status": "success",
  "provider": "openai",
  "model": "gpt-4o",
  "query": "TEST REQUEST: Please respond with 'TEST SUCCESSFUL'",
  "response": "TEST SUCCESSFUL - LLM is working correctly",
  "timestamp": "2025-09-03T12:19:02.953Z"
}
```

---

## Project Service

**Base URL:** `http://localhost:8002`
**OpenAPI Version:** 3.0.3

### Health Endpoints

#### GET /livez
Liveness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "project-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0"
}
```

#### GET /healthz
Readiness probe endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "project-service",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0",
  "dependencies": {
    "postgresql": "healthy"
  }
}
```

#### GET /health
Health check endpoint (backward compatibility).

**Response (200):** Same as `/healthz`

### Authentication

#### POST /token
Authenticate user and return JWT token.

**Request Body:**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### POST /users/register
Register a new user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "user",
  "is_active": true,
  "created_at": "2025-09-03T12:19:02.953Z"
}
```

### Project Management

#### POST /projects
Create a new project.

**Request Body:**
```json
{
  "name": "Migration Assessment Project",
  "description": "Cloud migration assessment for client",
  "client_name": "Acme Corporation",
  "client_contact": "john.doe@acme.com",
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "llm_api_key_id": "config_1",
  "llm_temperature": "0.1",
  "llm_max_tokens": "2000"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "name": "Migration Assessment Project",
  "description": "Cloud migration assessment for client",
  "client_name": "Acme Corporation",
  "status": "initiated",
  "created_at": "2025-09-03T12:19:02.953Z",
  "updated_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /projects
List projects accessible to the current user.

**Response (200):**
```json
[
  {
    "id": "uuid",
    "name": "Migration Assessment Project",
    "description": "Cloud migration assessment for client",
    "client_name": "Acme Corporation",
    "status": "running",
    "created_at": "2025-09-03T12:19:02.953Z",
    "updated_at": "2025-09-03T12:19:02.953Z"
  }
]
```

#### GET /projects/{project_id}
Get a specific project by ID.

**Parameters:**
- `project_id` (path): Project UUID

**Response (200):**
```json
{
  "id": "uuid",
  "name": "Migration Assessment Project",
  "description": "Cloud migration assessment for client",
  "client_name": "Acme Corporation",
  "status": "running",
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "created_at": "2025-09-03T12:19:02.953Z",
  "updated_at": "2025-09-03T12:19:02.953Z"
}
```

#### PUT /projects/{project_id}
Update a project.

**Parameters:**
- `project_id` (path): Project UUID

**Request Body:**
```json
{
  "name": "Updated Project Name",
  "status": "completed",
  "description": "Updated description"
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "name": "Updated Project Name",
  "description": "Updated description",
  "status": "completed",
  "updated_at": "2025-09-03T12:19:02.953Z"
}
```

### Project Files

#### POST /projects/{project_id}/files
Add a file record to a project.

**Parameters:**
- `project_id` (path): Project UUID

**Request Body:**
```json
{
  "filename": "document.pdf",
  "file_type": "application/pdf",
  "file_size": 1024000
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "filename": "document.pdf",
  "file_type": "application/pdf",
  "file_size": 1024000,
  "project_id": "uuid",
  "created_at": "2025-09-03T12:19:02.953Z"
}
```

#### GET /api/projects/{project_id}/files
Get all files for a project.

**Parameters:**
- `project_id` (path): Project UUID

**Response (200):**
```json
[
  {
    "id": "uuid",
    "filename": "document.pdf",
    "file_type": "application/pdf",
    "file_size": 1024000,
    "created_at": "2025-09-03T12:19:02.953Z"
  }
]
```

### LLM Configuration Management

#### GET /llm-configurations
List all LLM configurations.

**Response (200):**
```json
[
  {
    "id": "config_1",
    "name": "OpenAI GPT-4",
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": "0.1",
    "max_tokens": "2000",
    "description": "Primary OpenAI configuration",
    "created_at": "2025-09-03T12:19:02.953Z"
  }
]
```

#### POST /llm-configurations
Create a new LLM configuration.

**Request Body:**
```json
{
  "name": "OpenAI GPT-4 Turbo",
  "provider": "openai",
  "model": "gpt-4-turbo",
  "api_key": "sk-...",
  "temperature": "0.1",
  "max_tokens": "2000",
  "description": "OpenAI GPT-4 Turbo configuration"
}
```

**Response (201):**
```json
{
  "id": "config_2",
  "name": "OpenAI GPT-4 Turbo",
  "provider": "openai",
  "model": "gpt-4-turbo",
  "temperature": "0.1",
  "max_tokens": "2000",
  "description": "OpenAI GPT-4 Turbo configuration",
  "created_at": "2025-09-03T12:19:02.953Z"
}
```

### Template Management

#### GET /templates/global
Get all global document templates.

**Response (200):**
```json
[
  {
    "id": "template_1",
    "name": "Migration Assessment Report",
    "description": "Standard migration assessment report template",
    "template_type": "global",
    "category": "migration",
    "output_format": "pdf",
    "created_at": "2025-09-03T12:19:02.953Z"
  }
]
```

#### POST /templates/global
Create a new global template.

**Request Body:**
```json
{
  "name": "Security Assessment Report",
  "description": "Template for security assessment reports",
  "prompt": "Generate a comprehensive security assessment report...",
  "category": "security",
  "output_format": "pdf",
  "template_content": "# Security Assessment Report\n\n## Executive Summary\n..."
}
```

**Response (201):**
```json
{
  "id": "template_2",
  "name": "Security Assessment Report",
  "description": "Template for security assessment reports",
  "template_type": "global",
  "category": "security",
  "output_format": "pdf",
  "created_at": "2025-09-03T12:19:02.953Z"
}
```

---

## Backend Gateway

**Base URL:** `http://localhost:8000`
**OpenAPI Version:** 3.0.3

### Health Endpoints

#### GET /health
Comprehensive platform health check.

**Response (200):**
```json
{
  "status": "healthy",
  "services": {
    "backend": "connected",
    "project-service": "connected",
    "document-service": "connected",
    "llm-service": "connected",
    "analytics-service": "connected",
    "postgresql": "connected",
    "redis": "connected"
  },
  "details": {
    "backend": {"status": "up", "timestamp": "2025-09-03T12:19:02.953Z"},
    "project-service": {"status": "up", "timestamp": "2025-09-03T12:19:02.953Z"}
  },
  "timestamp": "2025-09-03T12:19:02.953Z"
}
```

#### GET /health/llm-configurations
LLM configuration health check.

**Response (200):**
```json
{
  "status": "healthy",
  "count": 3,
  "configured_count": 3,
  "timestamp": "2025-09-03T12:19:02.953Z"
}
```

### Gateway Proxy Endpoints

#### POST /api/projects/{project_id}/upload
Proxy to Document Service upload endpoint.

**Parameters:**
- `project_id` (path): Project UUID

**Request Body:** Multipart form data with files

**Response (200):**
```json
{
  "project_id": "uuid",
  "uploaded_files": [
    {
      "filename": "document.pdf",
      "size": 1024000,
      "uploaded_at": "2025-09-03T12:19:02.953Z"
    }
  ],
  "total_uploaded": 1,
  "message": "Successfully uploaded 1 files"
}
```

#### GET /api/projects/{project_id}/uploaded-files
Proxy to Document Service file listing.

**Parameters:**
- `project_id` (path): Project UUID

**Response (200):**
```json
{
  "files": [
    {
      "filename": "document.pdf",
      "size": 1024000,
      "uploaded_at": "2025-09-03T12:19:02.953Z",
      "processed": true
    }
  ],
  "total": 1
}
```

#### POST /api/projects/{project_id}/process-all
Proxy to Document Service processing.

**Parameters:**
- `project_id` (path): Project UUID

**Request Body:**
```json
{
  "file_names": ["document1.pdf"],
  "reprocess": false
}
```

**Response (200):**
```json
{
  "project_id": "uuid",
  "job_id": "uuid",
  "status": "started",
  "files_to_process": ["document1.pdf"],
  "message": "Processing started"
}
```

#### GET /api/llm/providers
Proxy to LLM Service providers endpoint.

**Response (200):**
```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "supported_models": ["gpt-4o", "gpt-4o-mini"],
      "status": "available"
    }
  ]
}
```

---

## Common Response Schemas

### Error Response
```json
{
  "detail": "Error message description",
  "error_type": "database_timeout",
  "timestamp": "2025-09-03T12:19:02.953Z",
  "correlation_id": "uuid"
}
```

### Pagination Response
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "limit": 50,
  "has_more": true
}
```

### Validation Error Response
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Authentication

All protected endpoints require Bearer token authentication:

```
Authorization: Bearer <jwt_token>
```

### Getting a Token

1. **Register/Login** via `/token` endpoint
2. **Use token** in `Authorization` header for subsequent requests
3. **Token expiration**: 30 minutes (configurable)

### Token Refresh

Tokens expire after 30 minutes. Obtain a new token by calling `/token` again with valid credentials.

---

## Rate Limiting

- **Global limit**: 1000 requests per minute per IP
- **Authenticated users**: 5000 requests per minute per user
- **Admin users**: 10000 requests per minute per user

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1638360000
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Validation Error |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

*Last updated: 2025-09-03*
*OpenAPI Version: 3.0.3*