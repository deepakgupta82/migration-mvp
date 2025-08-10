-- Migration 003: Migrate existing data to new structure (NON-BREAKING)
-- This migration populates the new project_user_roles table with existing associations
-- The old project_user_association table is preserved for backward compatibility

BEGIN;

-- Migrate existing project-user associations to the new role-based system
INSERT INTO project_user_roles (user_id, project_id, role, assigned_at)
SELECT 
    pua.user_id,
    pua.project_id,
    CASE 
        WHEN u.role = 'platform_admin' THEN 'project_admin'
        ELSE 'project_user'
    END as role,
    COALESCE(p.created_at, CURRENT_TIMESTAMP) as assigned_at
FROM project_user_association pua
JOIN users u ON pua.user_id = u.id
JOIN projects p ON pua.project_id = p.id
WHERE NOT EXISTS (
    -- Only insert if not already exists (idempotent migration)
    SELECT 1 FROM project_user_roles pur 
    WHERE pur.user_id = pua.user_id 
    AND pur.project_id = pua.project_id
);

-- Create initial password history entries for existing users
INSERT INTO password_history (user_id, password_hash, created_at)
SELECT 
    id as user_id,
    hashed_password,
    COALESCE(password_changed_at, created_at, CURRENT_TIMESTAMP) as created_at
FROM users
WHERE NOT EXISTS (
    -- Only insert if not already exists (idempotent migration)
    SELECT 1 FROM password_history ph 
    WHERE ph.user_id = users.id
);

-- Update statistics for verification
DO $$
DECLARE
    old_associations_count INTEGER;
    new_roles_count INTEGER;
    users_count INTEGER;
    password_history_count INTEGER;
BEGIN
    -- Count existing associations
    SELECT COUNT(*) INTO old_associations_count FROM project_user_association;
    SELECT COUNT(*) INTO new_roles_count FROM project_user_roles;
    SELECT COUNT(*) INTO users_count FROM users;
    SELECT COUNT(*) INTO password_history_count FROM password_history;
    
    RAISE NOTICE 'Migration Statistics:';
    RAISE NOTICE '  - Old project associations: %', old_associations_count;
    RAISE NOTICE '  - New project roles: %', new_roles_count;
    RAISE NOTICE '  - Total users: %', users_count;
    RAISE NOTICE '  - Password history entries: %', password_history_count;
    
    -- Verify data integrity
    IF new_roles_count < old_associations_count THEN
        RAISE WARNING 'New roles count (%) is less than old associations count (%). Please investigate.', new_roles_count, old_associations_count;
    END IF;
    
    IF password_history_count < users_count THEN
        RAISE WARNING 'Password history count (%) is less than users count (%). Please investigate.', password_history_count, users_count;
    END IF;
END $$;

-- Create a view for backward compatibility that combines old and new role systems
CREATE OR REPLACE VIEW user_project_access AS
SELECT DISTINCT
    u.id as user_id,
    u.email,
    u.username,
    u.role as platform_role,
    p.id as project_id,
    p.name as project_name,
    COALESCE(pur.role, 'project_user') as project_role,
    COALESCE(pur.assigned_at, p.created_at) as access_granted_at,
    'enhanced' as access_source
FROM users u
JOIN project_user_roles pur ON u.id = pur.user_id
JOIN projects p ON pur.project_id = p.id
WHERE u.is_active = true

UNION

SELECT DISTINCT
    u.id as user_id,
    u.email,
    u.username,
    u.role as platform_role,
    p.id as project_id,
    p.name as project_name,
    CASE 
        WHEN u.role = 'platform_admin' THEN 'project_admin'
        ELSE 'project_user'
    END as project_role,
    p.created_at as access_granted_at,
    'legacy' as access_source
FROM users u
JOIN project_user_association pua ON u.id = pua.user_id
JOIN projects p ON pua.project_id = p.id
WHERE u.is_active = true
AND NOT EXISTS (
    -- Only include legacy associations that don't have enhanced roles
    SELECT 1 FROM project_user_roles pur 
    WHERE pur.user_id = u.id 
    AND pur.project_id = p.id
);

-- Create initial audit log entry for the migration
INSERT INTO audit_logs (
    user_id,
    action,
    resource_type,
    resource_id,
    details,
    created_at
)
SELECT 
    (SELECT id FROM users WHERE role = 'platform_admin' LIMIT 1),
    'SYSTEM_MIGRATION',
    'user_management',
    'migration_003',
    jsonb_build_object(
        'migration', 'migrate_existing_data',
        'old_associations_migrated', (SELECT COUNT(*) FROM project_user_association),
        'new_roles_created', (SELECT COUNT(*) FROM project_user_roles),
        'users_processed', (SELECT COUNT(*) FROM users)
    ),
    CURRENT_TIMESTAMP;

COMMIT;

-- Final verification queries
SELECT 
    'Data Migration Verification' as check_type,
    'project_user_association' as table_name,
    COUNT(*) as record_count
FROM project_user_association
UNION ALL
SELECT 
    'Data Migration Verification' as check_type,
    'project_user_roles' as table_name,
    COUNT(*) as record_count
FROM project_user_roles
UNION ALL
SELECT 
    'Data Migration Verification' as check_type,
    'users' as table_name,
    COUNT(*) as record_count
FROM users
UNION ALL
SELECT 
    'Data Migration Verification' as check_type,
    'password_history' as table_name,
    COUNT(*) as record_count
FROM password_history;

-- Show sample of migrated data
SELECT 
    u.email,
    u.username,
    u.role as platform_role,
    p.name as project_name,
    pur.role as project_role,
    pur.assigned_at
FROM users u
JOIN project_user_roles pur ON u.id = pur.user_id
JOIN projects p ON pur.project_id = p.id
ORDER BY u.email, p.name
LIMIT 10;

-- Migration completed successfully
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 003 completed successfully - Migrated existing data to enhanced structure';
END $$;
