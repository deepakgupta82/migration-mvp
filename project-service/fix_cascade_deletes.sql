-- SQL script to fix foreign key constraint violations by adding CASCADE DELETE
-- This resolves the error when deleting projects with associated data

-- Fix project_user_association table
ALTER TABLE project_user_association 
DROP CONSTRAINT IF EXISTS project_user_association_project_id_fkey;

ALTER TABLE project_user_association 
ADD CONSTRAINT project_user_association_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Fix project_files table
ALTER TABLE project_files 
DROP CONSTRAINT IF EXISTS project_files_project_id_fkey;

ALTER TABLE project_files 
ADD CONSTRAINT project_files_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Fix project_templates table (if exists)
ALTER TABLE project_templates 
DROP CONSTRAINT IF EXISTS project_templates_project_id_fkey;

ALTER TABLE project_templates 
ADD CONSTRAINT project_templates_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Fix template_usage table
ALTER TABLE template_usage 
DROP CONSTRAINT IF EXISTS template_usage_project_id_fkey;

ALTER TABLE template_usage 
ADD CONSTRAINT template_usage_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Fix generation_requests table (if exists)
ALTER TABLE generation_requests 
DROP CONSTRAINT IF EXISTS generation_requests_project_id_fkey;

ALTER TABLE generation_requests 
ADD CONSTRAINT generation_requests_project_id_fkey 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Verify the constraints were applied
SELECT 
    tc.table_name,
    tc.constraint_name,
    rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND rc.delete_rule = 'CASCADE'
    AND tc.table_name IN (
        'project_user_association', 
        'project_files', 
        'project_templates', 
        'template_usage', 
        'generation_requests'
    )
ORDER BY tc.table_name;
