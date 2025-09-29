# API Migration Guide

This guide provides comprehensive instructions for migrating client applications to use the standardized Migration Platform APIs. All changes maintain backward compatibility, so existing applications will continue to work.

## Table of Contents

- [Overview](#overview)
- [Migration Timeline](#migration-timeline)
- [Backward Compatibility](#backward-compatibility)
- [Migration Strategies](#migration-strategies)
- [Service-Specific Migrations](#service-specific-migrations)
- [Testing Your Migration](#testing-your-migration)
- [Troubleshooting](#troubleshooting)
- [Support](#support)

---

## Overview

### What Changed

The Migration Platform APIs have been standardized with the following improvements:

1. **Health Endpoints**: Standardized `/livez`, `/healthz`, `/health` endpoints across all services
2. **Trailing Slash Normalization**: Automatic 308 redirects for consistent URL formats
3. **Service Prefixes**: Canonical prefixes for better API organization
4. **Enhanced Documentation**: Complete OpenAPI specifications and governance policies

### Key Benefits

- **Improved Reliability**: Standardized health checks for better monitoring
- **Better SEO**: Consistent URL formats for API documentation
- **Enhanced Developer Experience**: Comprehensive OpenAPI specifications
- **Future-Ready**: Governance policies for long-term API evolution

### Migration Impact

- **Zero Breaking Changes**: All existing endpoints continue to work
- **Automatic Redirects**: Trailing slash variants redirect to canonical forms
- **Enhanced Monitoring**: New health endpoints for better observability
- **Future Compatibility**: Clear migration path for upcoming changes

---

## Migration Timeline

### Phase 1: Current (Completed ✅)

**Status**: ✅ **ACTIVE**
**Timeline**: September 2025 - Ongoing

**Changes**:
- Health endpoints added to all services
- Trailing slash redirects implemented
- Service prefixes standardized
- Full backward compatibility maintained

**Action Required**: None - All changes are backward compatible

### Phase 2: Deprecation Warnings (Planned)

**Status**: 📋 **PLANNED**
**Timeline**: Q1 2026

**Changes**:
- Deprecation warnings logged for legacy endpoints
- Email notifications sent to registered users
- Client SDK updates with canonical endpoints

**Action Required**: Monitor logs for deprecation warnings

### Phase 3: Legacy Removal (Future)

**Status**: 🔮 **FUTURE**
**Timeline**: Q3 2026+

**Changes**:
- Legacy endpoints return 410 Gone
- Strict canonical path enforcement
- Breaking changes for non-compliant clients

**Action Required**: Migrate to canonical endpoints before Phase 3

---

## Backward Compatibility

### Guaranteed Compatibility

All existing client applications will continue to work without modification:

#### ✅ Fully Supported
- All existing endpoint URLs
- Current authentication methods
- Existing request/response formats
- Current error handling patterns

#### ✅ Enhanced Features
- New health endpoints available
- Automatic redirects for trailing slashes
- Improved error messages
- Better logging and monitoring

#### ✅ Future Migration Path
- Clear deprecation warnings (Phase 2)
- Migration guides and tooling
- Extended support periods
- Professional services assistance

### Compatibility Matrix

| Feature | Current Status | Phase 2 | Phase 3 |
|---------|----------------|---------|---------|
| Legacy endpoints | ✅ Working | ⚠️ Warnings | ❌ Removed |
| New health endpoints | ✅ Available | ✅ Available | ✅ Available |
| Trailing slash redirects | ✅ Active | ✅ Active | ✅ Active |
| Service prefixes | ✅ Supported | ✅ Supported | ✅ Required |

---

## Migration Strategies

### Strategy 1: Gradual Migration (Recommended)

**Best For**: Large applications, production systems

1. **Assessment Phase**
   ```bash
   # Check current endpoint usage
   grep -r "api.migration-platform.com" /path/to/your/code
   ```

2. **Health Check Integration**
   ```javascript
   // Add health checks to your monitoring
   const healthCheck = async (service) => {
     try {
       const response = await fetch(`${service}/healthz`);
       return response.ok;
     } catch (error) {
       console.warn(`${service} health check failed:`, error);
       return false;
     }
   };
   ```

3. **Incremental Updates**
   ```javascript
   // Before: Legacy endpoint
   const projects = await api.get('/api/projects/');

   // After: Canonical endpoint (automatic redirect)
   const projects = await api.get('/api/projects');

   // Best: Explicit canonical usage
   const projects = await api.get('/api/projects');
   ```

4. **Testing and Validation**
   ```bash
   # Test all endpoints
   npm run test:api
   # Check for deprecation warnings
   grep "deprecated" logs/application.log
   ```

### Strategy 2: Big Bang Migration

**Best For**: Small applications, greenfield projects

1. **Complete Code Update**
   ```javascript
   // Update all API calls at once
   const API_ENDPOINTS = {
     // Old endpoints
     // projects: '/api/projects/',
     // documents: '/upload/{project_id}',

     // New canonical endpoints
     projects: '/api/projects',
     documents: '/api/documents/{project_id}/upload',
     analytics: '/analytics/migration-complexity',
     llm: '/api/llm/process'
   };
   ```

2. **Configuration Update**
   ```javascript
   // Update base URLs and endpoints
   const config = {
     baseURL: 'https://api.migration-platform.com',
     endpoints: API_ENDPOINTS,
     timeout: 30000
   };
   ```

3. **Full Test Suite Execution**
   ```bash
   # Run complete test suite
   npm run test
   # Integration tests
   npm run test:integration
   # End-to-end tests
   npm run test:e2e
   ```

### Strategy 3: Hybrid Approach

**Best For**: Mixed environments, phased rollouts

1. **Feature Flags**
   ```javascript
   const USE_CANONICAL_ENDPOINTS = process.env.NODE_ENV === 'production';

   const getProjects = async () => {
     const endpoint = USE_CANONICAL_ENDPOINTS
       ? '/api/projects'
       : '/api/projects/';

     return await api.get(endpoint);
   };
   ```

2. **Service-by-Service Migration**
   ```javascript
   // Migrate one service at a time
   const services = {
     projects: { migrated: true, endpoint: '/api/projects' },
     documents: { migrated: false, endpoint: '/upload/{project_id}' },
     analytics: { migrated: true, endpoint: '/analytics/migration-complexity' }
   };
   ```

---

## Service-Specific Migrations

### Document Service Migration

#### Current Endpoints
```javascript
// Legacy (still works)
POST /upload/{project_id}
GET /files/{project_id}
POST /process-all/{project_id}

// Canonical (recommended)
POST /api/documents/{project_id}/upload
GET /api/documents/{project_id}/files
POST /api/documents/{project_id}/process-all
```

#### Migration Steps
```javascript
// 1. Update imports
import { DocumentService } from '@migration-platform/api-client';

// 2. Update service initialization
const documentService = new DocumentService({
  baseURL: 'https://api.migration-platform.com',
  useCanonicalEndpoints: true  // New option
});

// 3. Update method calls
// Before
await documentService.upload(projectId, file);

// After (automatic canonical usage)
await documentService.upload(projectId, file);
```

#### Health Check Integration
```javascript
// Add to your health monitoring
const documentHealth = await fetch('http://localhost:8003/healthz');
if (documentHealth.ok) {
  const status = await documentHealth.json();
  console.log('Document service:', status.status);
}
```

### Analytics Service Migration

#### Current Endpoints
```javascript
// Legacy (still works)
POST /analytics/migration-complexity
POST /analytics/cost-optimization

// Enhanced (new features)
GET /analytics/system-health
POST /metrics
GET /alerts
```

#### Migration Steps
```javascript
// 1. Update analytics client
const analyticsClient = new AnalyticsClient({
  baseURL: 'https://api.migration-platform.com',
  version: 'v1'  // Explicit version
});

// 2. Add new monitoring features
// System health monitoring
const systemHealth = await analyticsClient.getSystemHealth();

// Real-time metrics
await analyticsClient.addMetric('custom_metric', 42.0, {
  source: 'client_app',
  version: '1.2.3'
});

// Alert monitoring
const alerts = await analyticsClient.getAlerts({
  severity: 'high',
  project_id: projectId
});
```

### LLM Service Migration

#### Current Endpoints
```javascript
// Legacy (still works)
POST /api/llm/process

// Enhanced (new features)
GET /api/llm/providers
POST /api/llm/cluster
GET /api/llm/models/{provider}
POST /api/llm/test-llm-config
```

#### Migration Steps
```javascript
// 1. Update LLM client
const llmClient = new LLMClient({
  baseURL: 'https://api.migration-platform.com'
});

// 2. Add provider discovery
const providers = await llmClient.listProviders();
const models = await llmClient.listModels('openai');

// 3. Enhanced error handling
try {
  const result = await llmClient.process({
    process_type: 'entity_extraction',
    prompt: 'Extract entities from this text...',
    project_id: projectId
  });
} catch (error) {
  if (error.response?.status === 429) {
    // Handle rate limiting
    await delay(error.response.headers['retry-after']);
    return retryRequest();
  }
  throw error;
}
```

### Project Service Migration

#### Current Endpoints
```javascript
// Legacy (still works)
GET /projects/
POST /projects/

// Enhanced (new features)
GET /projects/stats
GET /projects/{id}/content-aggregation
POST /projects/{id}/llm-process-configs
```

#### Migration Steps
```javascript
// 1. Update project client
const projectClient = new ProjectClient({
  baseURL: 'https://api.migration-platform.com'
});

// 2. Add dashboard features
const stats = await projectClient.getStats();
const content = await projectClient.getContentAggregation(projectId);

// 3. Enhanced project management
await projectClient.updateLLMConfig(projectId, {
  entity_extraction: {
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.1
  }
});
```

---

## Testing Your Migration

### Automated Testing

#### Unit Tests
```javascript
describe('API Migration Tests', () => {
  test('canonical endpoints work', async () => {
    const response = await api.get('/api/projects');
    expect(response.status).toBe(200);
  });

  test('legacy endpoints redirect', async () => {
    const response = await api.get('/api/projects/');
    expect(response.status).toBe(308);
    expect(response.headers.location).toBe('/api/projects');
  });

  test('health endpoints work', async () => {
    const services = ['document-service', 'analytics-service', 'llm-service'];
    for (const service of services) {
      const response = await fetch(`${service}/healthz`);
      expect(response.ok).toBe(true);
    }
  });
});
```

#### Integration Tests
```javascript
describe('End-to-End Migration Tests', () => {
  test('complete workflow with canonical endpoints', async () => {
    // 1. Create project
    const project = await api.post('/api/projects', {
      name: 'Migration Test Project',
      description: 'Testing API migration'
    });

    // 2. Upload document
    const uploadResponse = await api.post(
      `/api/documents/${project.id}/upload`,
      formData
    );

    // 3. Process document
    const processResponse = await api.post(
      `/api/documents/${project.id}/process-all`
    );

    // 4. Check analytics
    const analysis = await api.post('/analytics/migration-complexity', {
      project_id: project.id
    });

    expect(project.id).toBeDefined();
    expect(uploadResponse.success).toBe(true);
    expect(processResponse.status).toBe('started');
    expect(analysis.report).toBeDefined();
  });
});
```

### Manual Testing Checklist

#### Pre-Migration Testing
- [ ] All existing API calls work
- [ ] Authentication still functions
- [ ] Error handling works as expected
- [ ] Performance is acceptable

#### Migration Testing
- [ ] Canonical endpoints work
- [ ] Legacy endpoints redirect properly
- [ ] Health endpoints return correct status
- [ ] New features work as documented

#### Post-Migration Testing
- [ ] No deprecation warnings in logs
- [ ] All functionality works with canonical endpoints
- [ ] Performance improved or maintained
- [ ] Monitoring and alerting work correctly

### Load Testing

#### Performance Validation
```bash
# Test endpoint performance
ab -n 1000 -c 10 https://api.migration-platform.com/api/projects

# Test health endpoints
ab -n 10000 -c 50 https://api.migration-platform.com/health

# Test redirects
ab -n 1000 -c 10 https://api.migration-platform.com/api/projects/
```

#### Monitoring Setup
```javascript
// Add performance monitoring
const responseTime = async (endpoint) => {
  const start = Date.now();
  const response = await fetch(endpoint);
  const duration = Date.now() - start;

  // Log slow responses
  if (duration > 1000) {
    console.warn(`Slow response: ${endpoint} took ${duration}ms`);
  }

  return response;
};
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Redirect Loops
```javascript
// Problem: Client not handling 308 redirects
const response = await fetch('/api/projects/', {
  redirect: 'manual'  // Don't follow redirects automatically
});

if (response.status === 308) {
  const canonicalUrl = response.headers.get('location');
  return fetch(canonicalUrl);  // Manual redirect handling
}
```

#### Issue 2: Health Check Failures
```javascript
// Problem: Health checks failing
const checkHealth = async (service) => {
  try {
    const response = await fetch(`${service}/healthz`, {
      timeout: 5000  // Increase timeout
    });
    return response.ok;
  } catch (error) {
    console.error(`Health check failed for ${service}:`, error);
    return false;
  }
};
```

#### Issue 3: Authentication Issues
```javascript
// Problem: Token expiration during migration
class APIClient {
  constructor() {
    this.token = null;
    this.tokenExpiry = null;
  }

  async getToken() {
    if (!this.token || Date.now() > this.tokenExpiry) {
      const response = await fetch('/token', {
        method: 'POST',
        body: new URLSearchParams({
          username: this.username,
          password: this.password
        })
      });
      const data = await response.json();
      this.token = data.access_token;
      this.tokenExpiry = Date.now() + (30 * 60 * 1000); // 30 minutes
    }
    return this.token;
  }

  async request(endpoint, options = {}) {
    const token = await this.getToken();
    return fetch(endpoint, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`
      }
    });
  }
}
```

### Debug Mode

#### Enable Debug Logging
```javascript
// Enable detailed API logging
const DEBUG_API = process.env.NODE_ENV === 'development';

const apiClient = {
  async request(endpoint, options = {}) {
    if (DEBUG_API) {
      console.log('API Request:', {
        endpoint,
        method: options.method || 'GET',
        headers: options.headers,
        timestamp: new Date().toISOString()
      });
    }

    const response = await fetch(endpoint, options);

    if (DEBUG_API) {
      console.log('API Response:', {
        endpoint,
        status: response.status,
        headers: Object.fromEntries(response.headers),
        timestamp: new Date().toISOString()
      });
    }

    return response;
  }
};
```

#### Network Inspection
```bash
# Monitor API calls
curl -v https://api.migration-platform.com/api/projects

# Check redirects
curl -I https://api.migration-platform.com/api/projects/

# Test health endpoints
curl -s https://api.migration-platform.com/health | jq .
```

### Rollback Procedures

#### Emergency Rollback
```javascript
// Feature flag for rollback
const USE_LEGACY_ENDPOINTS = process.env.ROLLBACK_API === 'true';

const endpoints = USE_LEGACY_ENDPOINTS ? {
  projects: '/api/projects/',
  documents: '/upload/{project_id}',
  analytics: '/analytics'
} : {
  projects: '/api/projects',
  documents: '/api/documents/{project_id}/upload',
  analytics: '/analytics/migration-complexity'
};
```

#### Gradual Rollback
```javascript
// Rollback one service at a time
const rollbackConfig = {
  'document-service': false,
  'analytics-service': false,
  'llm-service': false
};

const getEndpoint = (service, endpoint) => {
  if (rollbackConfig[service]) {
    return legacyEndpoints[service][endpoint];
  }
  return canonicalEndpoints[service][endpoint];
};
```

---

## Support

### Getting Help

#### Documentation Resources

- **API Endpoints Reference**: [API_ENDPOINTS.md](API_ENDPOINTS.md)
- **OpenAPI Specifications**: [OPENAPI_SPECIFICATIONS.md](OPENAPI_SPECIFICATIONS.md)
- **Governance Policies**: [API_GOVERNANCE.md](API_GOVERNANCE.md)
- **Architecture Overview**: [ARCHITECTURE.md](../ARCHITECTURE.md)

#### Support Channels

- **Email**: support@migration-platform.com
- **Slack**: #api-migration-support
- **GitHub Issues**: github.com/migration-platform/api-migration
- **Status Page**: status.migration-platform.com

#### Professional Services

For enterprise customers, we offer:

- **Migration Assessment**: Code review and migration planning
- **Implementation Support**: Hands-on migration assistance
- **Training**: API best practices and governance training
- **Custom Tooling**: Automated migration tools

### Escalation Process

#### Level 1: Self-Service
- Check documentation
- Review troubleshooting guide
- Test with provided examples

#### Level 2: Community Support
- Post in Slack channels
- Check GitHub issues
- Review existing solutions

#### Level 3: Technical Support
- Email support@migration-platform.com
- Response within 4 hours
- Direct engineer assistance

#### Level 4: Executive Escalation
- Business-critical issues
- Response within 1 hour
- Executive-level involvement

### Service Level Agreements

#### Migration Support SLA

| Issue Severity | Response Time | Resolution Time |
|----------------|---------------|-----------------|
| Critical | 1 hour | 4 hours |
| High | 4 hours | 24 hours |
| Medium | 24 hours | 72 hours |
| Low | 72 hours | 1 week |

#### Success Criteria

Your migration is successful when:

- [ ] All API calls use canonical endpoints
- [ ] No deprecation warnings in application logs
- [ ] Health checks are integrated into monitoring
- [ ] Test suite passes with 100% success rate
- [ ] Performance meets or exceeds baseline metrics
- [ ] Documentation is updated for new endpoints

---

## Quick Reference

### Most Common Changes

```javascript
// 1. Remove trailing slashes
// Before: /api/projects/
// After:  /api/projects

// 2. Use canonical prefixes
// Before: /upload/{project_id}
// After:  /api/documents/{project_id}/upload

// 3. Add health checks
// New: GET /healthz for all services

// 4. Enhanced error handling
// New: Check for 308 redirects
```

### Migration Checklist

- [ ] Review current API usage
- [ ] Update base URLs and endpoints
- [ ] Add health check monitoring
- [ ] Update error handling for redirects
- [ ] Test all functionality
- [ ] Monitor for deprecation warnings
- [ ] Update documentation
- [ ] Train development team

### Key Benefits After Migration

- **Improved Performance**: Optimized URL routing
- **Better Monitoring**: Standardized health endpoints
- **Enhanced Reliability**: Consistent error handling
- **Future-Proof**: Ready for API evolution
- **Developer Experience**: Comprehensive documentation

---

*Last updated: September 2025*
*Version: 1.0.0*
*Contact: Platform Architecture Team*