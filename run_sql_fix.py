#!/usr/bin/env python3
"""
Python script to run SQL fixes for database schema issues
"""

import os
import sys
import psycopg2
from psycopg2 import sql

# Database configuration
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def run_sql_fixes():
    """Run SQL fixes for database schema issues"""
    try:
        # Connect to database
        print("🔄 Connecting to database...")
        conn = psycopg2.connect(**DATABASE_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to database successfully")
        
        # 1. Add file_size column if it doesn't exist
        print("📝 Adding file_size column if missing...")
        cursor.execute("""
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
        """)
        print("✅ File size column check completed")
        
        # 2. Fix template_usage foreign key constraint (main issue)
        print("🔗 Fixing template_usage foreign key constraint...")
        cursor.execute("""
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
        """)
        print("✅ Template usage constraint fixed")
        
        # 3. Fix project_files foreign key constraint
        print("🔗 Fixing project_files foreign key constraint...")
        cursor.execute("""
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
        """)
        print("✅ Project files constraint fixed")
        
        # 4. Fix project_user_association foreign key constraint
        print("🔗 Fixing project_user_association foreign key constraint...")
        cursor.execute("""
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
        """)
        print("✅ Project user association constraint fixed")
        
        # 5. Verify the changes
        print("🔍 Verifying schema changes...")
        
        # Check file_size column
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'project_files' AND column_name = 'file_size'
                    ) 
                    THEN 'EXISTS'
                    ELSE 'MISSING'
                END as file_size_status;
        """)
        file_size_result = cursor.fetchone()
        if file_size_result[0] == 'EXISTS':
            print("✅ file_size column exists in project_files table")
        else:
            print("❌ file_size column missing in project_files table")
        
        # Check CASCADE DELETE constraints
        cursor.execute("""
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
                    'template_usage'
                )
            ORDER BY tc.table_name;
        """)
        
        cascade_constraints = cursor.fetchall()
        if cascade_constraints:
            print("✅ CASCADE DELETE constraints found:")
            for row in cascade_constraints:
                print(f"   - {row[0]}.{row[1]} (DELETE {row[2]})")
        else:
            print("⚠️  No CASCADE DELETE constraints found")
        
        cursor.close()
        conn.close()
        
        print("🎉 Database schema fixes completed successfully!")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting database schema fixes...")
    success = run_sql_fixes()
    
    if success:
        print("✅ All fixes applied successfully!")
        print("📋 Summary:")
        print("   • Added file_size column to project_files table")
        print("   • Fixed foreign key constraints with CASCADE DELETE")
        print("   • Projects can now be deleted without constraint violations")
        sys.exit(0)
    else:
        print("❌ Some fixes failed!")
        sys.exit(1)
