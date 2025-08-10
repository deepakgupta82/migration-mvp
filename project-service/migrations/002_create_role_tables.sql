-- Migration 002: Create project role tables (NON-BREAKING)
-- This migration creates new tables for enhanced role management
-- Existing project_user_association table is preserved for backward compatibility

BEGIN;

-- Create project_user_roles table for enhanced role management
CREATE TABLE IF NOT EXISTS project_user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'project_user',
    assigned_by UUID REFERENCES users(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, project_id)
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_project_user_roles_user_id ON project_user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_project_user_roles_project_id ON project_user_roles(project_id);
CREATE INDEX IF NOT EXISTS idx_project_user_roles_role ON project_user_roles(role);

-- Create user_sessions table for session management
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for session management
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active);

-- Create audit_logs table for security auditing
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for audit logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- Create oauth_providers table for future OAuth integration
CREATE TABLE IF NOT EXISTS oauth_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    client_secret TEXT NOT NULL, -- Will be encrypted
    discovery_url VARCHAR(500),
    authorization_url VARCHAR(500),
    token_url VARCHAR(500),
    userinfo_url VARCHAR(500),
    scopes TEXT DEFAULT 'openid email profile',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create oauth_user_mappings table for OAuth user mapping
CREATE TABLE IF NOT EXISTS oauth_user_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES oauth_providers(id) ON DELETE CASCADE,
    external_user_id VARCHAR(255) NOT NULL,
    external_email VARCHAR(255),
    external_username VARCHAR(255),
    external_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_id, external_user_id)
);

-- Create indexes for OAuth mappings
CREATE INDEX IF NOT EXISTS idx_oauth_mappings_user_id ON oauth_user_mappings(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_mappings_provider ON oauth_user_mappings(provider_id);
CREATE INDEX IF NOT EXISTS idx_oauth_mappings_external ON oauth_user_mappings(external_user_id);

-- Create password_history table for password policy enforcement
CREATE TABLE IF NOT EXISTS password_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for password history
CREATE INDEX IF NOT EXISTS idx_password_history_user_id ON password_history(user_id);
CREATE INDEX IF NOT EXISTS idx_password_history_created_at ON password_history(created_at);

COMMIT;

-- Verify the migration
SELECT 
    table_name,
    'created' as status
FROM information_schema.tables 
WHERE table_name IN (
    'project_user_roles', 
    'user_sessions', 
    'audit_logs', 
    'oauth_providers', 
    'oauth_user_mappings',
    'password_history'
)
ORDER BY table_name;

-- Show table counts
SELECT 
    'project_user_roles' as table_name, 
    COUNT(*) as row_count 
FROM project_user_roles
UNION ALL
SELECT 
    'user_sessions' as table_name, 
    COUNT(*) as row_count 
FROM user_sessions
UNION ALL
SELECT 
    'audit_logs' as table_name, 
    COUNT(*) as row_count 
FROM audit_logs
UNION ALL
SELECT 
    'oauth_providers' as table_name, 
    COUNT(*) as row_count 
FROM oauth_providers
UNION ALL
SELECT 
    'oauth_user_mappings' as table_name, 
    COUNT(*) as row_count 
FROM oauth_user_mappings
UNION ALL
SELECT 
    'password_history' as table_name, 
    COUNT(*) as row_count 
FROM password_history;

-- Migration completed successfully
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 002 completed successfully - Created enhanced role and security tables';
END $$;
