-- SQL script to fix database schema issues
-- This adds missing columns and fixes foreign key constraints

-- 1. Add file_size column to project_files table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'project_files' AND column_name = 'file_size'
    ) THEN
        ALTER TABLE project_files ADD COLUMN file_size INTEGER;
        RAISE NOTICE 'Added file_size column to project_files table';
    ELSE
        RAISE NOTICE 'file_size column already exists in project_files table';
    END IF;
END $$;

-- 2. Fix foreign key constraints with CASCADE DELETE
-- Fix project_user_association table
DO $$
BEGIN
    -- Drop existing constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'project_user_association_project_id_fkey'
    ) THEN
        ALTER TABLE project_user_association DROP CONSTRAINT project_user_association_project_id_fkey;
    END IF;
    
    -- Add new constraint with CASCADE DELETE
    ALTER TABLE project_user_association 
    ADD CONSTRAINT project_user_association_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Fixed project_user_association foreign key constraint';
END $$;

-- Fix project_files table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'project_files_project_id_fkey'
    ) THEN
        ALTER TABLE project_files DROP CONSTRAINT project_files_project_id_fkey;
    END IF;
    
    ALTER TABLE project_files 
    ADD CONSTRAINT project_files_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Fixed project_files foreign key constraint';
END $$;

-- Fix template_usage table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'template_usage_project_id_fkey'
    ) THEN
        ALTER TABLE template_usage DROP CONSTRAINT template_usage_project_id_fkey;
    END IF;
    
    ALTER TABLE template_usage 
    ADD CONSTRAINT template_usage_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Fixed template_usage foreign key constraint';
END $$;

-- Fix project_templates table (if it exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'project_templates'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = 'project_templates_project_id_fkey'
        ) THEN
            ALTER TABLE project_templates DROP CONSTRAINT project_templates_project_id_fkey;
        END IF;
        
        ALTER TABLE project_templates 
        ADD CONSTRAINT project_templates_project_id_fkey 
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
        
        RAISE NOTICE 'Fixed project_templates foreign key constraint';
    END IF;
END $$;

-- Fix generation_requests table (if it exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'generation_requests'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = 'generation_requests_project_id_fkey'
        ) THEN
            ALTER TABLE generation_requests DROP CONSTRAINT generation_requests_project_id_fkey;
        END IF;
        
        ALTER TABLE generation_requests 
        ADD CONSTRAINT generation_requests_project_id_fkey 
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
        
        RAISE NOTICE 'Fixed generation_requests foreign key constraint';
    END IF;
END $$;

-- 3. Verify the changes
SELECT 'Schema verification:' as status;

-- Check if file_size column exists
SELECT 
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'project_files' AND column_name = 'file_size'
        ) 
        THEN '✅ file_size column exists in project_files'
        ELSE '❌ file_size column missing in project_files'
    END as file_size_status;

-- Check CASCADE DELETE constraints
SELECT 
    tc.table_name,
    tc.constraint_name,
    rc.delete_rule,
    '✅ CASCADE DELETE configured' as status
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
