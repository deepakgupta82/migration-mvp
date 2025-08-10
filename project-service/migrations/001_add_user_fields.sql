-- Migration 001: Add new fields to users table (NON-BREAKING)
-- This migration adds new optional fields to support enhanced user management
-- All existing functionality remains unchanged

BEGIN;

-- Add new fields to users table (all nullable for backward compatibility)
DO $$
BEGIN
    -- Add username field (nullable, unique)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'username'
    ) THEN
        ALTER TABLE users ADD COLUMN username VARCHAR(100) UNIQUE;
        RAISE NOTICE 'Added username column to users table';
    END IF;

    -- Add first_name field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'first_name'
    ) THEN
        ALTER TABLE users ADD COLUMN first_name VARCHAR(100);
        RAISE NOTICE 'Added first_name column to users table';
    END IF;

    -- Add last_name field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'last_name'
    ) THEN
        ALTER TABLE users ADD COLUMN last_name VARCHAR(100);
        RAISE NOTICE 'Added last_name column to users table';
    END IF;

    -- Add last_login field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'last_login'
    ) THEN
        ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
        RAISE NOTICE 'Added last_login column to users table';
    END IF;

    -- Add failed_login_attempts field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'failed_login_attempts'
    ) THEN
        ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;
        RAISE NOTICE 'Added failed_login_attempts column to users table';
    END IF;

    -- Add account_locked_until field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'account_locked_until'
    ) THEN
        ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP;
        RAISE NOTICE 'Added account_locked_until column to users table';
    END IF;

    -- Add password_changed_at field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'password_changed_at'
    ) THEN
        ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        RAISE NOTICE 'Added password_changed_at column to users table';
    END IF;

    -- Add must_change_password field
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'must_change_password'
    ) THEN
        ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added must_change_password column to users table';
    END IF;

END $$;

-- Generate usernames for existing users (from email prefix)
UPDATE users 
SET username = split_part(email, '@', 1) 
WHERE username IS NULL;

-- Handle duplicate usernames by appending numbers
DO $$
DECLARE
    user_record RECORD;
    new_username VARCHAR(100);
    counter INTEGER;
BEGIN
    FOR user_record IN 
        SELECT id, email, username 
        FROM users 
        WHERE username IN (
            SELECT username 
            FROM users 
            WHERE username IS NOT NULL 
            GROUP BY username 
            HAVING COUNT(*) > 1
        )
        ORDER BY created_at
    LOOP
        counter := 1;
        new_username := user_record.username;
        
        WHILE EXISTS (SELECT 1 FROM users WHERE username = new_username AND id != user_record.id) LOOP
            new_username := user_record.username || counter::text;
            counter := counter + 1;
        END LOOP;
        
        UPDATE users SET username = new_username WHERE id = user_record.id;
        RAISE NOTICE 'Updated username for user % to %', user_record.email, new_username;
    END LOOP;
END $$;

-- Set password_changed_at for existing users
UPDATE users 
SET password_changed_at = created_at 
WHERE password_changed_at IS NULL;

COMMIT;

-- Verify the migration
SELECT 
    'users' as table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
    AND column_name IN ('username', 'first_name', 'last_name', 'last_login', 'failed_login_attempts', 'account_locked_until', 'password_changed_at', 'must_change_password')
ORDER BY column_name;

-- Migration completed successfully
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 001 completed successfully - Added enhanced user fields';
END $$;
