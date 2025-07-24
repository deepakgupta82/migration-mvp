-- =====================================================================================
-- AgentiMigrate Platform - PostgreSQL Database Initialization
-- Complete schema setup with tables, indexes, and sample data
-- =====================================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================================================
-- CLIENTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'enterprise',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    industry VARCHAR(100),
    size_employees INTEGER,
    annual_revenue DECIMAL(15,2),
    primary_contact_name VARCHAR(200) NOT NULL,
    primary_contact_email VARCHAR(255) NOT NULL,
    primary_contact_phone VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    website VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for clients
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_type ON clients(type);
CREATE INDEX IF NOT EXISTS idx_clients_industry ON clients(industry);
CREATE INDEX IF NOT EXISTS idx_clients_created_at ON clients(created_at);
CREATE INDEX IF NOT EXISTS idx_clients_tags ON clients USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_clients_metadata ON clients USING GIN(metadata);

-- =====================================================================================
-- PROJECTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    assigned_to VARCHAR(100),
    estimated_duration_days INTEGER,
    actual_duration_days INTEGER,
    budget DECIMAL(15,2),
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for projects
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_client_id ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_assigned_to ON projects(assigned_to);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_tags ON projects USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_projects_metadata ON projects USING GIN(metadata);

-- =====================================================================================
-- ASSESSMENTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'infrastructure',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(100) NOT NULL,
    assigned_to VARCHAR(100),
    target_cloud_provider VARCHAR(50),
    source_environment VARCHAR(100),
    assessment_scope TEXT[],
    uploaded_documents TEXT[],
    processed_documents TEXT[],
    generated_artifacts TEXT[],
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,
    current_phase VARCHAR(100),
    phases_completed TEXT[],
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for assessments
CREATE INDEX IF NOT EXISTS idx_assessments_project_id ON assessments(project_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_type ON assessments(type);
CREATE INDEX IF NOT EXISTS idx_assessments_assigned_to ON assessments(assigned_to);
CREATE INDEX IF NOT EXISTS idx_assessments_created_at ON assessments(created_at);
CREATE INDEX IF NOT EXISTS idx_assessments_target_cloud ON assessments(target_cloud_provider);
CREATE INDEX IF NOT EXISTS idx_assessments_tags ON assessments USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_assessments_metadata ON assessments USING GIN(metadata);

-- =====================================================================================
-- ASSESSMENT RESULTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS assessment_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    migration_strategy TEXT,
    estimated_cost DECIMAL(15,2),
    estimated_duration_weeks INTEGER,
    risk_level VARCHAR(50) DEFAULT 'medium',
    recommendations TEXT[],
    technical_debt_score DECIMAL(5,2),
    cloud_readiness_score DECIMAL(5,2),
    complexity_score DECIMAL(5,2),
    dependencies JSONB DEFAULT '[]'::jsonb,
    architecture_patterns TEXT[],
    technology_stack TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for assessment results
CREATE INDEX IF NOT EXISTS idx_assessment_results_assessment_id ON assessment_results(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_risk_level ON assessment_results(risk_level);
CREATE INDEX IF NOT EXISTS idx_assessment_results_created_at ON assessment_results(created_at);

-- =====================================================================================
-- DOCUMENTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT,
    content_type VARCHAR(100),
    file_path VARCHAR(500),
    storage_key VARCHAR(500),
    upload_status VARCHAR(50) DEFAULT 'uploaded',
    processing_status VARCHAR(50) DEFAULT 'pending',
    extracted_text TEXT,
    extracted_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    uploaded_by VARCHAR(100) NOT NULL,
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_assessment_id ON documents(assessment_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_documents_upload_status ON documents(upload_status);
CREATE INDEX IF NOT EXISTS idx_documents_processing_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents USING GIN(tags);

-- =====================================================================================
-- REPORTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'assessment',
    format VARCHAR(20) NOT NULL DEFAULT 'pdf',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    file_path VARCHAR(500),
    storage_key VARCHAR(500),
    file_size BIGINT,
    generated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    template_used VARCHAR(100),
    generation_parameters JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for reports
CREATE INDEX IF NOT EXISTS idx_reports_assessment_id ON reports(assessment_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(type);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);

-- =====================================================================================
-- INFRASTRUCTURE COMPONENTS TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS infrastructure_components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    current_technology VARCHAR(100),
    target_technology VARCHAR(100),
    migration_complexity VARCHAR(50) DEFAULT 'medium',
    migration_priority INTEGER DEFAULT 5,
    dependencies TEXT[],
    configuration JSONB DEFAULT '{}'::jsonb,
    assessment_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    tags TEXT[],
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for infrastructure components
CREATE INDEX IF NOT EXISTS idx_infra_components_project_id ON infrastructure_components(project_id);
CREATE INDEX IF NOT EXISTS idx_infra_components_type ON infrastructure_components(type);
CREATE INDEX IF NOT EXISTS idx_infra_components_category ON infrastructure_components(category);
CREATE INDEX IF NOT EXISTS idx_infra_components_complexity ON infrastructure_components(migration_complexity);
CREATE INDEX IF NOT EXISTS idx_infra_components_priority ON infrastructure_components(migration_priority);
CREATE INDEX IF NOT EXISTS idx_infra_components_tags ON infrastructure_components USING GIN(tags);

-- =====================================================================================
-- AUDIT LOG TABLE
-- =====================================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes for audit log
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_type ON audit_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_id ON audit_log(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_by ON audit_log(changed_by);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log(changed_at);

-- =====================================================================================
-- SAMPLE DATA INSERTION
-- =====================================================================================

-- Insert sample client
INSERT INTO clients (
    id, name, type, status, industry, size_employees, annual_revenue,
    primary_contact_name, primary_contact_email, primary_contact_phone,
    address, city, state, country, postal_code, website, description,
    created_by, tags, metadata
) VALUES (
    '550e8400-e29b-41d4-a716-446655440001',
    'TechCorp Solutions',
    'enterprise',
    'active',
    'Technology',
    2500,
    150000000.00,
    'John Smith',
    'john.smith@techcorp.com',
    '+1-555-0123',
    '123 Technology Drive',
    'San Francisco',
    'California',
    'United States',
    '94105',
    'https://www.techcorp.com',
    'Leading technology company specializing in enterprise software solutions',
    'system',
    ARRAY['enterprise', 'technology', 'large-scale'],
    '{"industry_vertical": "software", "compliance_requirements": ["SOC2", "GDPR"], "preferred_cloud": "aws"}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Insert sample project
INSERT INTO projects (
    id, name, description, client_id, status, created_by, assigned_to,
    estimated_duration_days, budget, tags, metadata
) VALUES (
    '550e8400-e29b-41d4-a716-446655440002',
    'Legacy ERP Migration to Cloud',
    'Comprehensive migration of legacy ERP system to cloud-native architecture',
    '550e8400-e29b-41d4-a716-446655440001',
    'active',
    'system',
    'migration-team',
    120,
    500000.00,
    ARRAY['erp', 'cloud-migration', 'legacy-modernization'],
    '{"priority": "high", "business_impact": "critical", "migration_type": "lift-and-shift-then-optimize"}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Insert sample assessment
INSERT INTO assessments (
    id, project_id, name, type, status, description, created_by, assigned_to,
    target_cloud_provider, source_environment, assessment_scope,
    progress_percentage, current_phase, phases_completed, tags, metadata
) VALUES (
    '550e8400-e29b-41d4-a716-446655440003',
    '550e8400-e29b-41d4-a716-446655440002',
    'ERP Infrastructure Assessment',
    'infrastructure',
    'in_progress',
    'Comprehensive assessment of current ERP infrastructure for cloud migration',
    'system',
    'assessment-team',
    'aws',
    'on-premises-datacenter',
    ARRAY['servers', 'databases', 'networking', 'storage', 'applications'],
    45.0,
    'infrastructure_analysis',
    ARRAY['document_collection', 'initial_discovery'],
    ARRAY['infrastructure', 'erp', 'assessment'],
    '{"assessment_methodology": "6Rs", "tools_used": ["discovery_agent", "performance_monitoring"], "timeline_weeks": 8}'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- Insert sample infrastructure components
INSERT INTO infrastructure_components (
    id, project_id, name, type, category, description, current_technology,
    target_technology, migration_complexity, migration_priority, dependencies,
    configuration, assessment_notes, created_by, tags, metadata
) VALUES 
(
    '550e8400-e29b-41d4-a716-446655440004',
    '550e8400-e29b-41d4-a716-446655440002',
    'Primary Database Server',
    'database',
    'data_tier',
    'Main Oracle database server hosting ERP data',
    'Oracle 11g on Windows Server 2012',
    'Amazon RDS for Oracle',
    'medium',
    1,
    ARRAY['app-server-01', 'backup-storage'],
    '{"cpu_cores": 16, "memory_gb": 64, "storage_gb": 2000, "database_size_gb": 800}'::jsonb,
    'Critical component requiring careful migration planning due to data volume',
    'system',
    ARRAY['database', 'oracle', 'critical'],
    '{"migration_strategy": "replatform", "estimated_downtime_hours": 8, "data_migration_method": "dms"}'::jsonb
),
(
    '550e8400-e29b-41d4-a716-446655440005',
    '550e8400-e29b-41d4-a716-446655440002',
    'Application Server Cluster',
    'application_server',
    'application_tier',
    'Load-balanced application servers running ERP application',
    'WebLogic on Windows Server 2016',
    'Amazon ECS with Fargate',
    'high',
    2,
    ARRAY['database-server', 'load-balancer'],
    '{"server_count": 4, "cpu_cores_each": 8, "memory_gb_each": 32, "load_balancer": "F5"}'::jsonb,
    'Complex application requiring containerization and modernization',
    'system',
    ARRAY['application', 'weblogic', 'cluster'],
    '{"migration_strategy": "refactor", "containerization_required": true, "estimated_effort_weeks": 12}'::jsonb
),
(
    '550e8400-e29b-41d4-a716-446655440006',
    '550e8400-e29b-41d4-a716-446655440002',
    'File Storage System',
    'storage',
    'storage_tier',
    'Network-attached storage for documents and backups',
    'NetApp FAS8200',
    'Amazon EFS + S3',
    'low',
    4,
    ARRAY['backup-system'],
    '{"capacity_tb": 50, "performance_tier": "high", "backup_frequency": "daily"}'::jsonb,
    'Straightforward migration to cloud storage services',
    'system',
    ARRAY['storage', 'netapp', 'files'],
    '{"migration_strategy": "rehost", "data_transfer_method": "aws_datasync", "estimated_transfer_days": 3}'::jsonb
);

-- Insert sample documents
INSERT INTO documents (
    id, project_id, assessment_id, filename, original_filename, file_size,
    content_type, file_path, storage_key, upload_status, processing_status,
    uploaded_by, tags, metadata
) VALUES 
(
    '550e8400-e29b-41d4-a716-446655440007',
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440003',
    'infrastructure_inventory.pdf',
    'TechCorp_Infrastructure_Inventory_2024.pdf',
    2048576,
    'application/pdf',
    '/uploads/projects/550e8400-e29b-41d4-a716-446655440002/infrastructure_inventory.pdf',
    'projects/550e8400-e29b-41d4-a716-446655440002/documents/infrastructure_inventory.pdf',
    'uploaded',
    'processed',
    'system',
    ARRAY['infrastructure', 'inventory', 'documentation'],
    '{"document_type": "technical_specification", "page_count": 45, "extraction_confidence": 0.95}'::jsonb
),
(
    '550e8400-e29b-41d4-a716-446655440008',
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440003',
    'network_diagram.pdf',
    'Current_Network_Architecture.pdf',
    1536000,
    'application/pdf',
    '/uploads/projects/550e8400-e29b-41d4-a716-446655440002/network_diagram.pdf',
    'projects/550e8400-e29b-41d4-a716-446655440002/documents/network_diagram.pdf',
    'uploaded',
    'processed',
    'system',
    ARRAY['network', 'architecture', 'diagram'],
    '{"document_type": "architecture_diagram", "diagram_count": 8, "extraction_confidence": 0.88}'::jsonb
);

-- =====================================================================================
-- CREATE APPLICATION USER
-- =====================================================================================

-- Create application user with limited privileges
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'agentimigrate_app') THEN
        CREATE USER agentimigrate_app WITH PASSWORD 'app_secure_password_2024';
    END IF;
END
$$;

-- Grant necessary permissions to application user
GRANT CONNECT ON DATABASE projectdb TO agentimigrate_app;
GRANT USAGE ON SCHEMA public TO agentimigrate_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO agentimigrate_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agentimigrate_app;

-- Grant permissions on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agentimigrate_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO agentimigrate_app;

-- =====================================================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_assessments_updated_at BEFORE UPDATE ON assessments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_assessment_results_updated_at BEFORE UPDATE ON assessment_results FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_infrastructure_components_updated_at BEFORE UPDATE ON infrastructure_components FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================================================

-- View for project summary with client information
CREATE OR REPLACE VIEW project_summary AS
SELECT 
    p.id,
    p.name,
    p.description,
    p.status,
    p.created_at,
    p.updated_at,
    p.assigned_to,
    p.estimated_duration_days,
    p.budget,
    c.name as client_name,
    c.industry as client_industry,
    (SELECT COUNT(*) FROM assessments WHERE project_id = p.id) as assessment_count,
    (SELECT COUNT(*) FROM infrastructure_components WHERE project_id = p.id) as component_count
FROM projects p
JOIN clients c ON p.client_id = c.id;

-- View for assessment progress
CREATE OR REPLACE VIEW assessment_progress AS
SELECT 
    a.id,
    a.name,
    a.status,
    a.progress_percentage,
    a.current_phase,
    a.created_at,
    a.started_at,
    a.completed_at,
    p.name as project_name,
    c.name as client_name,
    (SELECT COUNT(*) FROM documents WHERE assessment_id = a.id) as document_count,
    (SELECT COUNT(*) FROM reports WHERE assessment_id = a.id) as report_count
FROM assessments a
JOIN projects p ON a.project_id = p.id
JOIN clients c ON p.client_id = c.id;

-- =====================================================================================
-- COMPLETION MESSAGE
-- =====================================================================================

DO $$
BEGIN
    RAISE NOTICE 'AgentiMigrate PostgreSQL database initialization completed successfully!';
    RAISE NOTICE 'Database schema created with sample data';
    RAISE NOTICE 'Application user "agentimigrate_app" created with appropriate permissions';
    RAISE NOTICE 'Sample client: TechCorp Solutions';
    RAISE NOTICE 'Sample project: Legacy ERP Migration to Cloud';
    RAISE NOTICE 'Sample assessment: ERP Infrastructure Assessment';
END
$$;
