# Canonical Path Conventions

This document outlines the canonical path conventions established across all services in the Migration Platform.

## Overview

All services now implement:
1. **Trailing slash normalization** with 308 Permanent Redirects
2. **Standardized API prefixes** for backward compatibility
3. **Consistent path structure** across services

## Trailing Slash Normalization

### Implementation
- All services implement 308 Permanent Redirect from trailing slash variants to canonical non-slash forms
- Example: `/api/projects/` → `/api/projects`
- Health check endpoints (`/livez`, `/healthz`, `/health`) are exempt from redirects
- Only GET requests are redirected; other HTTP methods are processed normally

### Benefits
- **SEO Optimization**: Prevents duplicate content issues
- **Caching Efficiency**: Ensures consistent cache keys
- **API Consistency**: Standardized URL format across all endpoints

## Service-Specific Conventions

### Document Service (Port 8003)
**Canonical Prefix**: `/api/documents/`

**Backward Compatibility**:
- All endpoints available with and without `/api/documents/` prefix
- Example: Both `/api/documents/{project_id}/upload` and `/{project_id}/upload` work

**Key Endpoints**:
- `POST /{project_id}/upload` - Upload documents
- `POST /{project_id}/process-all` - Process all documents
- `GET /{project_id}/status/{job_id}` - Get processing status
- `POST /{project_id}/structured-process/{filename}` - Structured processing

### Analytics Service (Port 8014)
**Canonical Prefix**: `/analytics/`

**Key Endpoints**:
- `POST /analytics/migration-complexity` - Migration complexity analysis
- `POST /analytics/cost-optimization` - Cost optimization analysis
- `GET /analytics/system-health` - System health analysis
- `POST /metrics` - Add metrics data

### LLM Service (Port 8007)
**Canonical Prefix**: `/api/llm/`

**Key Endpoints**:
- `POST /api/llm/process` - Process LLM requests
- `GET /api/llm/providers` - List providers
- `POST /api/llm/cluster` - Semantic clustering
- `GET /api/llm/configurations` - LLM configurations

### Project Service (Port 8002)
**Canonical Prefix**: `/` (root-level API)

**Key Endpoints**:
- `GET /projects` - List projects
- `POST /projects` - Create project
- `GET /projects/{project_id}` - Get project details
- `PUT /projects/{project_id}` - Update project
- `GET /users/me` - Current user info

## Implementation Details

### Middleware Configuration
Each service includes a trailing slash redirect middleware that:
1. Checks if the request path ends with `/`
2. Excludes health check endpoints
3. Only processes GET requests
4. Preserves query parameters in redirects
5. Returns 308 Permanent Redirect status

### Router Configuration
- Document Service: Router included twice (with and without prefix)
- Other services: Standard router inclusion with appropriate prefixes

## Migration Guide

### For Existing Clients
- No breaking changes - all existing endpoints continue to work
- Trailing slash variants will redirect to canonical forms
- Both prefixed and non-prefixed Document Service endpoints work

### For New Development
- Use canonical non-slash URLs
- Prefer prefixed endpoints where available
- Document Service: Use `/api/documents/` prefix for new integrations

## Testing

### Validation Checklist
- [ ] All trailing slash variants redirect with 308 status
- [ ] Query parameters preserved in redirects
- [ ] Health endpoints exempt from redirects
- [ ] Non-GET methods not affected
- [ ] Backward compatibility maintained
- [ ] No compilation errors in any service

### Example Test Cases
```bash
# Should redirect with 308
curl -I "http://localhost:8003/api/documents/test-project/upload/"

# Should work normally
curl -I "http://localhost:8003/api/documents/test-project/upload"

# Should not redirect (health endpoint)
curl -I "http://localhost:8003/health"
```

## Future Considerations

- Consider implementing HSTS headers for additional security
- Monitor redirect patterns for optimization opportunities
- Evaluate client-side URL normalization for improved UX