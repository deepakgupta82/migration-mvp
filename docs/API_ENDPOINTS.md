# API Endpoints Reference

This document provides a comprehensive reference of all API endpoints across the Migration Platform services, including canonical paths, health endpoints, and standardization information.

## Table of Contents

- [Health Endpoints](#health-endpoints)
- [Service Registry](#service-registry)
- [Document Service](#document-service)
- [Analytics Service](#analytics-service)
- [LLM Service](#llm-service)
- [Project Service](#project-service)
- [Backend Gateway](#backend-gateway)
- [Frontend Mapping](#frontend-mapping)
- [Canonical Path Conventions](#canonical-path-conventions)
- [Migration Information](#migration-information)

## Health Endpoints

All services implement standardized health check endpoints with consistent response formats:

### Standard Health Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/livez` | GET | Liveness probe - service is running | ✅ Implemented |
| `/healthz` | GET | Readiness probe - service ready to accept traffic | ✅ Implemented |
| `/health` | GET | Health check endpoint (backward compatibility) | ✅ Implemented |

### Health Response Format

```json
{
  "status": "healthy|unhealthy|degraded",
  "service": "service-name",
  "uptime": 1234,
  "timestamp": "2025-09-03T12:19:02.953Z",
  "version": "1.0.0",
  "dependencies": {
    "postgresql": "healthy",
    "redis": "healthy"
  }
}
```

## Service Registry

**Port:** 8011
**Base URL:** `http://localhost:8011`

### Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/services` | GET | List all registered services | ✅ Active |
| `/services/{service_name}` | GET | Get service details | ✅ Active |
| `/health` | GET | Service registry health | ✅ Active |

## Document Service

**Port:** 8003
**Base URL:** `http://localhost:8003`
**Canonical Prefix:** `/api/documents/`

### Core Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/{project_id}/upload` | POST | Upload documents | ✅ Active |
| `/{project_id}/process-all` | POST | Process all uploaded documents | ✅ Active |
| `/{project_id}/process-selected` | POST | Process selected documents | ✅ Active |
| `/{project_id}/status/{job_id}` | GET | Get processing status | ✅ Active |
| `/{project_id}/files` | GET | List uploaded files | ✅ Active |

### Legacy Compatibility

| Legacy Endpoint | Canonical Equivalent | Status |
|----------------|--------------------|--------|
| `/{project_id}/upload` | `/api/documents/{project_id}/upload` | ✅ Active |
| `/{project_id}/process-all` | `/api/documents/{project_id}/process-all` | ✅ Active |

### Analysis Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/{project_id}/analysis` | POST | Create analysis result | ✅ Active |
| `/{project_id}/analysis/{analysis_id}` | GET | Get analysis result | ✅ Active |
| `/{project_id}/analysis` | GET | List project analysis results | ✅ Active |
| `/{project_id}/analysis/batch` | POST | Create analysis batch | ✅ Active |
| `/{project_id}/analysis/batch/{batch_id}` | GET | Get analysis batch | ✅ Active |
| `/{project_id}/analysis/batches` | GET | List project analysis batches | ✅ Active |

### LLM Analysis Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/llm-analysis-health` | GET | Get LLM analysis health | ✅ Active |
| `/llm-analysis-cache/clear` | POST | Clear LLM analysis cache | ✅ Active |

## Analytics Service

**Port:** 8014
**Base URL:** `http://localhost:8014`
**Canonical Prefix:** `/analytics/`

### Core Analytics Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/analytics/migration-complexity` | POST | Generate migration complexity analysis | ✅ Active |
| `/analytics/cost-optimization` | POST | Generate cost optimization analysis | ✅ Active |
| `/analytics/agent-efficiency` | POST | Generate AI agent efficiency analysis | ✅ Active |
| `/analytics/predictive` | POST | Generate predictive analysis | ✅ Active |
| `/analytics/system-health` | GET | Get comprehensive system health analysis | ✅ Active |

### Metrics and Monitoring

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/metrics` | POST | Add real-time metric data | ✅ Active |
| `/metrics/real-time` | GET | Get real-time metrics data | ✅ Active |
| `/trends/analyze` | POST | Perform trend analysis | ✅ Active |
| `/alerts` | GET | Get alerts with filtering | ✅ Active |
| `/alerts/{alert_id}` | PUT | Update alert status | ✅ Active |

### Dashboard Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/dashboards` | POST | Create custom analytics dashboard | ✅ Active |
| `/dashboards/{dashboard_id}` | GET | Get dashboard configuration | ✅ Active |

### Summary Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/summary` | GET | Get comprehensive analytics summary | ✅ Active |
| `/reports` | GET | Get all generated reports | ✅ Active |
| `/reports/{report_id}` | GET | Get specific report | ✅ Active |

## LLM Service

**Port:** 8007
**Base URL:** `http://localhost:8007`
**Canonical Prefix:** `/api/llm/`

### Core LLM Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/llm/process` | POST | Process LLM request | ✅ Active |
| `/api/llm/providers` | GET | List available LLM providers | ✅ Active |
| `/api/llm/providers/status` | GET | Get provider status and configuration | ✅ Active |
| `/api/llm/process-types` | GET | List supported LLM process types | ✅ Active |
| `/api/llm/recommendations/{process_type}` | GET | Get model recommendations | ✅ Active |
| `/api/llm/resolve` | GET | Resolve provider/model configuration | ✅ Active |

### Clustering Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/llm/cluster` | POST | Perform LLM-assisted semantic clustering | ✅ Active |

### Configuration Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/llm/configurations` | GET | Get LLM configurations | ✅ Active |
| `/api/llm/configurations` | POST | Create LLM configuration | ✅ Active |
| `/api/llm/configurations/{config_id}` | GET | Get specific configuration | ✅ Active |
| `/api/llm/configurations/{config_id}` | PUT | Update configuration | ✅ Active |
| `/api/llm/configurations/{config_id}` | DELETE | Delete configuration | ✅ Active |

### Model Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/llm/models/{provider}` | GET | List available models for provider | ✅ Active |
| `/api/llm/test-llm-config` | POST | Test LLM configuration | ✅ Active |

### Legacy Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/llm/entity-extraction/{project_id}` | GET | Legacy entity extraction endpoint | ✅ Active |
| `/api/llm/crew-assessment/{project_id}` | GET | Legacy crew assessment endpoint | ✅ Active |
| `/api/llm/crew-documentation/{project_id}` | GET | Legacy crew documentation endpoint | ✅ Active |

## Project Service

**Port:** 8002
**Base URL:** `http://localhost:8002`
**Canonical Prefix:** `/` (root-level API)

### Authentication Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/token` | POST | Authenticate and get JWT token | ✅ Active |
| `/users/register` | POST | Register new user | ✅ Active |
| `/users/me` | GET | Get current user information | ✅ Active |
| `/users` | GET | List all users (admin only) | ✅ Active |
| `/users/enhanced` | GET | List users with enhanced information | ✅ Active |

### Project Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects` | POST | Create new project | ✅ Active |
| `/projects` | GET | List projects | ✅ Active |
| `/projects/stats` | GET | Get project statistics | ✅ Active |
| `/projects/{project_id}` | GET | Get specific project | ✅ Active |
| `/projects/{project_id}` | PUT | Update project | ✅ Active |
| `/projects/{project_id}` | DELETE | Delete project | ✅ Active |

### Project Files

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects/{project_id}/files` | POST | Add file record to project | ✅ Active |
| `/api/projects/{project_id}/files` | GET | Get project files | ✅ Active |
| `/projects/{project_id}/files/count` | GET | Get file count | ✅ Active |
| `/projects/{project_id}/files/{file_id}` | PUT | Update project file | ✅ Active |
| `/projects/{project_id}/files/{file_id}` | DELETE | Delete project file | ✅ Active |

### Project Content

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects/{project_id}/content-aggregation` | GET | Get aggregated content overview | ✅ Active |

### LLM Configuration (Project Service)

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/llm-configurations` | GET | List LLM configurations | ✅ Active |
| `/api/llm-configurations` | GET | List LLM configurations (API prefix) | ✅ Active |
| `/llm-configurations` | POST | Create LLM configuration | ✅ Active |
| `/api/llm-configurations` | POST | Create LLM configuration (API prefix) | ✅ Active |
| `/llm-configurations/{config_id}` | GET | Get specific configuration | ✅ Active |
| `/llm-configurations/{config_id}` | PUT | Update configuration | ✅ Active |
| `/api/llm-configurations/{config_id}` | PUT | Update configuration (API prefix) | ✅ Active |
| `/llm-configurations/{config_id}` | DELETE | Delete configuration | ✅ Active |
| `/api/llm-configurations/{config_id}` | DELETE | Delete configuration (API prefix) | ✅ Active |

### Template Management

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects/{project_id}/deliverables` | GET | List deliverable templates | ✅ Active |
| `/projects/{project_id}/deliverables` | POST | Create deliverable template | ✅ Active |
| `/projects/{project_id}/deliverables/{template_id}` | PUT | Update deliverable template | ✅ Active |
| `/projects/{project_id}/deliverables/{template_id}` | DELETE | Delete deliverable template | ✅ Active |
| `/templates/global` | GET | List global templates | ✅ Active |
| `/templates/global` | POST | Create global template | ✅ Active |
| `/templates/global/{template_id}` | DELETE | Delete global template | ✅ Active |
| `/templates/all/{project_id}` | GET | Get all available templates | ✅ Active |

### Platform Settings

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/settings` | GET | List platform settings | ✅ Active |
| `/platform-settings` | GET | List platform settings (alias) | ✅ Active |
| `/settings` | POST | Create platform setting | ✅ Active |
| `/settings/{setting_key}` | PUT | Update platform setting | ✅ Active |
| `/settings/{setting_key}` | DELETE | Delete platform setting | ✅ Active |

### Project Roles

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects/{project_id}/users/{user_id}/assign-role` | POST | Assign role to user | ✅ Active |
| `/projects/{project_id}/users` | GET | List project users with roles | ✅ Active |
| `/projects/{project_id}/users/{user_id}` | DELETE | Remove user from project | ✅ Active |

### Generation History

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/projects/{project_id}/generation-history` | GET | Get document generation history | ✅ Active |
| `/projects/{project_id}/generation-requests` | GET | Get generation requests | ✅ Active |
| `/projects/{project_id}/generation-requests` | POST | Create generation request | ✅ Active |
| `/projects/{project_id}/generation-requests/{request_id}` | PUT | Update generation request | ✅ Active |

### Template Usage

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/template-usage` | POST | Track template usage | ✅ Active |
| `/projects/{project_id}/template-usage` | GET | Get project template usage | ✅ Active |
| `/template-usage/global` | GET | Get global template usage | ✅ Active |

### Model Cache

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/models/{provider}` | GET | Get cached models for provider | ✅ Active |
| `/models/{provider}/cache` | POST | Cache models for provider | ✅ Active |

### Database Status

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/db/status` | GET | Get detailed database status | ✅ Active |
| `/db/version` | GET | Get database version | ✅ Active |

## Backend Gateway

**Port:** 8000
**Base URL:** `http://localhost:8000`

### Gateway Endpoints

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/projects/*` | ALL | Project service proxy | ✅ Active |
| `/api/projects/{project_id}/upload` | POST | Document upload proxy | ✅ Active |
| `/api/projects/{project_id}/uploaded-files` | GET | Document listing proxy | ✅ Active |
| `/api/projects/{project_id}/process-all` | POST | Document processing proxy | ✅ Active |
| `/api/projects/{project_id}/process-selected` | POST | Selective processing proxy | ✅ Active |
| `/api/llm/*` | ALL | LLM service proxy | ✅ Active |
| `/health` | GET | Platform health check | ✅ Active |
| `/health/llm-configurations` | GET | LLM configuration health | ✅ Active |
| `/health/containers` | GET | Container stats | ✅ Active |

## Frontend Mapping

This section maps key UI surfaces to canonical backend endpoints, including new flag-guarded, no-op endpoints that enable the frontend to scaffold features in parallel.

Feature flags can be toggled via environment variables. When flags are disabled, the endpoints return 404 so the UI should handle feature discovery gracefully.

### Feature Flags

- `MINERU_ENABLED` → Layout schema/sample (Document Service)
- `ANALYTICS_PERSIST_ENABLED` → Dashboard schema (Analytics Service)
- `GRAPH_EXPLORER_ENABLED` → Explorer overview and commits summary (Graph Service)
- `ADVANCED_RAG_ENABLED` → Attribution v2 schema (LLM Service)
- `AGENT_TOOLS_ENABLED` → Migration plan schema (AI Agent Service)
- `WS_SCHEMA_ENABLED` → WebSocket events schema (WebSocket Service)

### UI → API Mapping

1) Documents → Layout Preview and Schema (MinerU/Structured)
- Service: Document Service (8003)
- Endpoints:
  - GET `/api/documents/layout/schema` (flag: MINERU_ENABLED)
  - GET `/api/documents/layout/sample` (flag: MINERU_ENABLED)
- Purpose: Allows UI to render example layout blocks and expected schema while backend extraction evolves.

2) Analytics → Unified Dashboard Schema
- Service: Analytics Service (8014)
- Endpoint:
  - GET `/analytics/dashboard/schema` (flag: ANALYTICS_PERSIST_ENABLED)
- Purpose: Frontend can bootstrap dashboard cards/sections (fusion, rag, extraction) based on declared keys.

3) Graph → Explorer Overview & Commit Summaries
- Service: Graph Service (8006)
- Endpoints:
  - GET `/api/graphs/projects/{project_id}/explorer/overview` (flag: GRAPH_EXPLORER_ENABLED)
  - GET `/api/graphs/projects/{project_id}/commits/summary` (flag: GRAPH_EXPLORER_ENABLED)
- Purpose: Populate entity/relationship overviews and commit activity tables.

4) Chat/RAG → Attribution V2 Schema
- Service: LLM Service (8007)
- Endpoint:
  - GET `/api/llm/rag/attribution/v2/schema` (flag: ADVANCED_RAG_ENABLED)
- Purpose: Define shape of future citation objects (alignment/coverage/hallucination fields) for UI adapters.

5) Migration Planner → Plan Schema
- Service: AI Agent Service (8008)
- Endpoint:
  - GET `/migration/plan/schema` (flag: AGENT_TOOLS_ENABLED)
- Purpose: Allows the planner UI to render anticipated sections/steps before the full backend is wired.

6) Real-time → WebSocket Event Schema
- Service: WebSocket Service (8009)
- Endpoint:
  - GET `/events/schema` (flag: WS_SCHEMA_ENABLED)
- Purpose: UI can subscribe to known channels and anticipate payload shapes for notifications/streaming.

### Example Consumption Patterns

- Feature discovery:
  - The UI attempts a GET to the schema endpoint; on 404 it hides the feature toggle.
- Local development base URLs:
  - Document: `http://localhost:8003`
  - Analytics: `http://localhost:8014`
  - Graph: `http://localhost:8006`
  - LLM: `http://localhost:8007`
  - AI Agent: `http://localhost:8008`
  - WebSocket: `http://localhost:8009`

Notes:
- All schema endpoints are read-only and safe to call frequently.
- When features go live, these schemas remain backward compatible; new fields are additive.

## Canonical Path Conventions

### Trailing Slash Normalization

All services implement 308 Permanent Redirect from trailing slash variants to canonical non-slash forms:

- **Implementation**: `GET /api/projects/` → `GET /api/projects` (308 redirect)
- **Exclusions**: Health endpoints (`/livez`, `/healthz`, `/health`) are exempt
- **Method Support**: Only GET requests are redirected; other HTTP methods are processed normally
- **Query Parameters**: Preserved during redirects

### Service-Specific Prefixes

| Service | Canonical Prefix | Legacy Support |
|---------|------------------|---------------|
| Document Service | `/api/documents/` | Both prefixed and non-prefixed |
| Analytics Service | `/analytics/` | Standard prefix only |
| LLM Service | `/api/llm/` | Standard prefix only |
| Project Service | `/` | Root-level API |

### Benefits

- **SEO Optimization**: Prevents duplicate content issues
- **Caching Efficiency**: Ensures consistent cache keys
- **API Consistency**: Standardized URL format across all endpoints

## Migration Information

### Backward Compatibility

- **Legacy Endpoints**: All existing endpoints continue to work
- **Graceful Degradation**: Services handle both old and new URL formats
- **Deprecation Timeline**: Legacy endpoints will be supported for 2 release cycles

### Client Migration Guide

1. **Update Base URLs**: Use canonical service URLs with proper prefixes
2. **Remove Trailing Slashes**: Update client code to use canonical non-slash URLs
3. **Use Prefixed Endpoints**: Prefer prefixed endpoints where available
4. **Test Health Endpoints**: Verify health checks work with new format

### Breaking Changes

- **None**: All changes are backward compatible
- **New Features**: Enhanced health endpoints and standardized paths
- **Performance**: Improved caching and SEO optimization

## Implementation Status

### Phase 1: Core Standardization ✅ COMPLETED

- ✅ Trailing slash normalization implemented across all services
- ✅ Standardized health endpoints (`/livez`, `/healthz`, `/health`)
- ✅ Service-specific canonical prefixes established
- ✅ Backward compatibility maintained
- ✅ Documentation updated

### Phase 2: Enhanced Features (Planned)

- 🔄 OpenAPI specification generation
- 🔄 API versioning strategy
- 🔄 Enhanced security guidelines
- 🔄 Service registry integration improvements

## Testing

### Validation Checklist

- [x] All trailing slash variants redirect with 308 status
- [x] Query parameters preserved in redirects
- [x] Health endpoints exempt from redirects
- [x] Non-GET methods not affected
- [x] Backward compatibility maintained
- [x] No compilation errors in any service

### Example Test Cases

```bash
# Should redirect with 308
curl -I "http://localhost:8003/api/documents/test-project/upload/"

# Should work normally
curl -I "http://localhost:8003/api/documents/test-project/upload"

# Should not redirect (health endpoint)
curl -I "http://localhost:8003/health"
```

## Support

For questions about API endpoints or migration:

- **Documentation**: See [API_ENDPOINT_AUDIT_REPORT.md](API_Endpoint_Audit_Report.md)
- **Migration Guide**: See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Governance**: See [API_GOVERNANCE.md](API_GOVERNANCE.md)

---

*Last updated: 2025-09-03*
*Document Version: 1.0.0*