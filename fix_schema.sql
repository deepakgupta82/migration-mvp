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

-- 2. Fix template_usage foreign key constraint (main issue causing deletion errors)
DO $$
BEGIN
    -- Drop existing constraint if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'template_usage_project_id_fkey'
    ) THEN
        ALTER TABLE template_usage DROP CONSTRAINT template_usage_project_id_fkey;
        RAISE NOTICE 'Dropped existing template_usage foreign key constraint';
    END IF;
    
    -- Add new constraint with CASCADE DELETE
    ALTER TABLE template_usage 
    ADD CONSTRAINT template_usage_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Added template_usage foreign key constraint with CASCADE DELETE';
END $$;

-- 3. Fix project_files foreign key constraint
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'project_files_project_id_fkey'
    ) THEN
        ALTER TABLE project_files DROP CONSTRAINT project_files_project_id_fkey;
        RAISE NOTICE 'Dropped existing project_files foreign key constraint';
    END IF;
    
    ALTER TABLE project_files 
    ADD CONSTRAINT project_files_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Added project_files foreign key constraint with CASCADE DELETE';
END $$;

-- 4. Fix project_user_association foreign key constraint (if exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'project_user_association_project_id_fkey'
    ) THEN
        ALTER TABLE project_user_association DROP CONSTRAINT project_user_association_project_id_fkey;
        RAISE NOTICE 'Dropped existing project_user_association foreign key constraint';
    END IF;
    
    ALTER TABLE project_user_association 
    ADD CONSTRAINT project_user_association_project_id_fkey 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    
    RAISE NOTICE 'Added project_user_association foreign key constraint with CASCADE DELETE';
END $$;

-- 5. Verification queries
SELECT 'Schema verification completed' as status;

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
        'template_usage'
    )
ORDER BY tc.table_name;
