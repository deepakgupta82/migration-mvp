#!/usr/bin/env python3
"""
Simple migration runner for user management enhancements
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def run_migration():
    """Run the essential migration steps"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("🔄 Starting user management migration...")
        
        # Step 1: Add new fields to users table
        print("📝 Adding new fields to users table...")
        
        # Check and add username field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'username'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(100) UNIQUE")
            print("  ✅ Added username field")
        else:
            print("  ⏭️  Username field already exists")
        
        # Check and add first_name field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'first_name'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN first_name VARCHAR(100)")
            print("  ✅ Added first_name field")
        else:
            print("  ⏭️  First_name field already exists")
        
        # Check and add last_name field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'last_name'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN last_name VARCHAR(100)")
            print("  ✅ Added last_name field")
        else:
            print("  ⏭️  Last_name field already exists")
        
        # Check and add last_login field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'last_login'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
            print("  ✅ Added last_login field")
        else:
            print("  ⏭️  Last_login field already exists")
        
        # Check and add failed_login_attempts field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'failed_login_attempts'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
            print("  ✅ Added failed_login_attempts field")
        else:
            print("  ⏭️  Failed_login_attempts field already exists")
        
        # Check and add account_locked_until field
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'account_locked_until'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN account_locked_until TIMESTAMP")
            print("  ✅ Added account_locked_until field")
        else:
            print("  ⏭️  Account_locked_until field already exists")
        
        # Step 2: Generate usernames for existing users
        print("👤 Generating usernames for existing users...")
        cursor.execute("UPDATE users SET username = split_part(email, '@', 1) WHERE username IS NULL")
        
        # Step 3: Create project_user_roles table
        print("🏗️  Creating project_user_roles table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_user_roles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL DEFAULT 'project_user',
                assigned_by UUID REFERENCES users(id),
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, project_id)
            )
        """)
        print("  ✅ Created project_user_roles table")
        
        # Step 4: Migrate existing associations
        print("🔄 Migrating existing project associations...")
        cursor.execute("""
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
                SELECT 1 FROM project_user_roles pur 
                WHERE pur.user_id = pua.user_id 
                AND pur.project_id = pua.project_id
            )
        """)
        
        # Step 5: Verify migration
        print("📊 Verifying migration...")
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM project_user_association")
        old_associations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM project_user_roles")
        new_roles = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('username', 'first_name', 'last_name', 'last_login', 'failed_login_attempts', 'account_locked_until')
        """)
        new_fields = [row[0] for row in cursor.fetchall()]
        
        print(f"📈 Migration Results:")
        print(f"  - Users: {user_count}")
        print(f"  - Old associations: {old_associations}")
        print(f"  - New role assignments: {new_roles}")
        print(f"  - New user fields: {len(new_fields)}/6")
        print(f"  - Fields added: {', '.join(new_fields)}")
        
        cursor.close()
        conn.close()
        
        print("🎉 Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    run_migration()
