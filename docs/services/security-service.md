# Security Service

## Service Overview

The Security Service is a comprehensive multi-tenant security and role-based access control (RBAC) service that operates on port 8015. It provides enterprise-grade authentication, authorization, audit logging, and security policy management for the Nagarro Ascent platform.

### Key Features

- **Multi-tenant Authentication**: Tenant-isolated user management
- **Role-Based Access Control**: Granular permission system
- **JWT Token Management**: Secure token generation and validation
- **Audit Logging**: Comprehensive security event logging
- **Security Policies**: Configurable security rules and policies
- **Session Management**: Secure session handling and cleanup
- **User Lifecycle Management**: Complete user account management

## Functionality

### Core Capabilities

1. **Authentication & Authorization**
   - User authentication with multiple factors
   - JWT token generation and validation
   - Session management and cleanup
   - Password security and hashing

2. **Multi-tenant User Management**
   - Tenant isolation and management
   - User creation, update, and deactivation
   - Role assignment and permission management
   - User profile and preference management

3. **Role-Based Access Control**
   - Hierarchical role system (Super Admin, Tenant Admin, etc.)
   - Granular permission definitions
   - Permission inheritance and overrides
   - Dynamic permission checking

4. **Audit & Compliance**
   - Comprehensive audit logging
   - Security event tracking
   - Compliance reporting
   - Access pattern analysis

### Dependencies

- **PostgreSQL**: User and audit data storage
- **Redis**: Token caching and session management
- **WebSocket Service**: Real-time security notifications

## APIs/Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/me` - Get current user info
- `POST /auth/refresh` - Refresh JWT token

### User Management
- `POST /tenants` - Create tenant (super admin only)
- `GET /tenants/{tenant_id}` - Get tenant details
- `POST /tenants/{tenant_id}/users` - Create user
- `GET /tenants/{tenant_id}/users` - List tenant users

### Permission Management
- `GET /permissions/check/{permission}` - Check user permission
- `POST /roles/{role}/permissions` - Update role permissions
- `GET /roles/{role}/permissions` - Get role permissions

### Audit & Security
- `GET /tenants/{tenant_id}/audit-logs` - Get audit logs
- `POST /security/policies` - Create security policy
- `GET /security/policies` - List security policies

## Data Models

### User Structure
```json
{
  "user_id": "user_123",
  "tenant_id": "tenant_456",
  "username": "john.doe@company.com",
  "email": "john.doe@company.com",
  "full_name": "John Doe",
  "role": "project_manager",
  "permissions": [
    "project:read",
    "project:update",
    "analytics:read"
  ],
  "is_active": true,
  "last_login": "2024-01-01T09:00:00.000000",
  "created_at": "2023-12-01T00:00:00.000000"
}
```

### Tenant Structure
```json
{
  "tenant_id": "tenant_456",
  "name": "Acme Corporation",
  "domain": "acme.com",
  "subscription_plan": "premium",
  "max_users": 200,
  "max_projects": 100,
  "features_enabled": [
    "basic_migration",
    "advanced_analytics",
    "cloud_tools",
    "agent_orchestration"
  ],
  "is_active": true,
  "created_at": "2023-12-01T00:00:00.000000"
}
```

### Audit Log Structure
```json
{
  "log_id": "audit_789",
  "tenant_id": "tenant_456",
  "user_id": "user_123",
  "action": "login",
  "resource_type": "user",
  "resource_id": "user_123",
  "details": {
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "success": true
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "timestamp": "2024-01-01T09:00:00.000000",
  "success": true
}
```

## Key Components

### SecurityManager (`main.py`)

**Core security orchestration engine**

- **Responsibilities**:
  - User authentication and authorization
  - Token management and validation
  - Audit logging and compliance
  - Security policy enforcement

### JWT Management

**Token generation and validation**

- **Responsibilities**:
  - Secure token creation with expiration
  - Token validation and refresh
  - Session tracking and cleanup
  - Token revocation handling

## Data Flow

### Authentication Flow

1. **Login Request**: User credentials submitted
2. **Credential Validation**: Username/password verified
3. **User Lookup**: User details and permissions retrieved
4. **Token Generation**: JWT token created with user claims
5. **Session Creation**: Session tracked for monitoring
6. **Audit Logging**: Authentication event logged
7. **Response**: Token returned to client

### Authorization Flow

1. **Request Reception**: API request with JWT token
2. **Token Validation**: Token authenticity and expiration checked
3. **Permission Check**: User permissions verified for operation
4. **Policy Evaluation**: Security policies applied
5. **Access Decision**: Allow/deny decision made
6. **Audit Logging**: Access attempt logged
7. **Response**: Request processed or denied

## Complete Working Details

### Configuration

**Environment Variables**:
- `JWT_SECRET`: JWT signing secret key
- `JWT_EXPIRY_HOURS`: Token expiration time
- `PASSWORD_MIN_LENGTH`: Minimum password length
- `SESSION_TIMEOUT_MINUTES`: Session timeout duration

### User Roles and Permissions

**Role Hierarchy**:
- **Super Admin**: Full system access
- **Tenant Admin**: Tenant management and user administration
- **Project Manager**: Project management and team oversight
- **Migration Specialist**: Migration operations and tools
- **Analyst**: Data analysis and reporting
- **Viewer**: Read-only access

### Performance Characteristics

- **Authentication Speed**: Sub-second login processing
- **Token Validation**: Fast JWT verification
- **Permission Checks**: Efficient permission caching
- **Concurrent Users**: High concurrency support

### Error Handling

- **Authentication Failures**: Secure error messages without information leakage
- **Token Expiration**: Graceful token refresh process
- **Permission Denied**: Clear access control messages
- **Session Issues**: Automatic cleanup and recovery

### Monitoring and Observability

- **Authentication Metrics**: Login success/failure rates
- **Security Events**: Real-time security monitoring
- **Audit Analytics**: Access pattern analysis
- **Compliance Reporting**: Security compliance metrics

### Security Considerations

- **Password Security**: Strong hashing and salting
- **Token Security**: Secure JWT implementation
- **Session Security**: Secure session management
- **Audit Security**: Tamper-proof audit logging

### Scaling Considerations

- **Database Scaling**: User data partitioning
- **Token Distribution**: Stateless token validation
- **Audit Scaling**: Audit log partitioning and archiving
- **Load Balancing**: Session affinity for consistency