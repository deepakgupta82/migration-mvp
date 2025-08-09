-- Migration script to add global template support
-- Run this against the project-service PostgreSQL database

-- Add new columns to deliverable_templates table
ALTER TABLE deliverable_templates 
ADD COLUMN IF NOT EXISTS template_type VARCHAR(20) DEFAULT 'project',
ADD COLUMN IF NOT EXISTS category VARCHAR(50),
ADD COLUMN IF NOT EXISTS output_format VARCHAR(20) DEFAULT 'pdf',
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS created_by UUID,
ADD COLUMN IF NOT EXISTS template_content TEXT,
ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_used TIMESTAMP;

-- Make project_id nullable for global templates
ALTER TABLE deliverable_templates 
ALTER COLUMN project_id DROP NOT NULL;

-- Add foreign key constraint for created_by (if users table exists)
-- ALTER TABLE deliverable_templates 
-- ADD CONSTRAINT fk_deliverable_templates_created_by 
-- FOREIGN KEY (created_by) REFERENCES users(id);

-- Insert sample global templates
INSERT INTO deliverable_templates (
    id, name, description, prompt, project_id, template_type, category, 
    output_format, is_active, created_by, template_content, usage_count, 
    created_at, updated_at
) VALUES 
(
    gen_random_uuid(),
    'Standard Migration Playbook',
    'Comprehensive enterprise migration playbook with best practices, methodologies, and step-by-step guidance',
    'Generate a comprehensive migration playbook that includes: 1) Executive Summary, 2) Migration Strategy and Approach, 3) Detailed Migration Phases with tasks and deliverables, 4) Risk Assessment and Mitigation Strategies, 5) Timeline and Resource Planning, 6) Success Criteria and KPIs, 7) Communication Plan, 8) Rollback Procedures. Include specific technical details based on the analyzed infrastructure and business requirements.',
    NULL,
    'global',
    'migration',
    'pdf',
    true,
    '00000000-0000-0000-0000-000000000001',
    'Detailed playbook with migration phases, tasks, deliverables, success criteria, risk mitigation strategies, and timeline templates',
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'Infrastructure Assessment Report',
    'Comprehensive technical assessment of current infrastructure state',
    'Create a detailed infrastructure assessment report including: 1) Current State Analysis, 2) Infrastructure Inventory and Dependencies, 3) Performance and Capacity Analysis, 4) Security and Compliance Review, 5) Technology Stack Evaluation, 6) Gap Analysis, 7) Recommendations for Improvement, 8) Migration Readiness Assessment. Base the analysis on the uploaded documents and discovered infrastructure components.',
    NULL,
    'global',
    'assessment',
    'pdf',
    true,
    '00000000-0000-0000-0000-000000000001',
    'Technical assessment with current state analysis, infrastructure inventory, performance metrics, and migration readiness evaluation',
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'Risk Assessment Matrix',
    'Comprehensive risk analysis and mitigation strategies',
    'Generate a detailed risk assessment matrix that covers: 1) Technical Risks (compatibility, performance, security), 2) Business Risks (downtime, data loss, user impact), 3) Operational Risks (resource availability, timeline constraints), 4) Financial Risks (budget overruns, ROI impact), 5) Compliance and Regulatory Risks. For each risk, provide: probability assessment, impact analysis, mitigation strategies, contingency plans, and responsible parties.',
    NULL,
    'global',
    'risk',
    'xlsx',
    true,
    '00000000-0000-0000-0000-000000000001',
    'Risk matrix with probability/impact analysis, mitigation strategies, and contingency planning',
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'Technical Architecture Blueprint',
    'Standard technical architecture documentation template',
    'Create a comprehensive technical architecture blueprint including: 1) Current State Architecture Diagram, 2) Target State Architecture Design, 3) Migration Path and Transition States, 4) Technology Stack Specifications, 5) Integration Points and Data Flow, 6) Security Architecture, 7) Performance and Scalability Considerations, 8) Deployment and Infrastructure Requirements. Include detailed technical specifications and architectural decisions.',
    NULL,
    'global',
    'architecture',
    'pdf',
    true,
    '00000000-0000-0000-0000-000000000001',
    'Architecture blueprint with current state, target state, migration paths, and technical specifications',
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'Executive Summary Dashboard',
    'High-level executive summary for stakeholders',
    'Generate an executive summary dashboard that provides: 1) Project Overview and Objectives, 2) Key Findings and Insights, 3) Migration Strategy Summary, 4) Timeline and Milestones, 5) Resource Requirements and Budget Impact, 6) Risk Summary and Mitigation Approach, 7) Expected Benefits and ROI, 8) Next Steps and Recommendations. Present information in a clear, executive-friendly format with visual elements and key metrics.',
    NULL,
    'global',
    'executive',
    'pptx',
    true,
    '00000000-0000-0000-0000-000000000001',
    'Executive dashboard with project overview, key findings, strategy summary, and ROI analysis',
    0,
    NOW(),
    NOW()
);

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_deliverable_templates_type ON deliverable_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_deliverable_templates_category ON deliverable_templates(category);
CREATE INDEX IF NOT EXISTS idx_deliverable_templates_active ON deliverable_templates(is_active);

-- Update existing templates to be project-specific
UPDATE deliverable_templates 
SET template_type = 'project' 
WHERE template_type IS NULL AND project_id IS NOT NULL;

COMMIT;
