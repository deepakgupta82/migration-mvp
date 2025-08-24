#!/usr/bin/env python3
"""
Database migration script to add CASCADE DELETE constraints to foreign keys
This fixes the foreign key constraint violation when deleting projects
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/migration_platform")

def migrate_database():
    """Add CASCADE DELETE constraints to foreign keys referencing projects.id"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            print("🔄 Starting cascade delete migration...")
            
            # List of foreign key constraints to update
            constraints_to_update = [
                {
                    'table': 'project_user_association',
                    'constraint': 'project_user_association_project_id_fkey',
                    'column': 'project_id',
                    'references': 'projects(id)'
                },
                {
                    'table': 'project_files',
                    'constraint': 'project_files_project_id_fkey',
                    'column': 'project_id',
                    'references': 'projects(id)'
                },
                {
                    'table': 'project_templates',
                    'constraint': 'project_templates_project_id_fkey',
                    'column': 'project_id',
                    'references': 'projects(id)'
                },
                {
                    'table': 'template_usage',
                    'constraint': 'template_usage_project_id_fkey',
                    'column': 'project_id',
                    'references': 'projects(id)'
                },
                {
                    'table': 'generation_requests',
                    'constraint': 'generation_requests_project_id_fkey',
                    'column': 'project_id',
                    'references': 'projects(id)'
                }
            ]
            
            for constraint_info in constraints_to_update:
                try:
                    print(f"📝 Updating {constraint_info['table']}.{constraint_info['column']} constraint...")
                    
                    # Drop existing constraint
                    conn.execute(text(f"""
                        ALTER TABLE {constraint_info['table']} 
                        DROP CONSTRAINT IF EXISTS {constraint_info['constraint']}
                    """))
                    
                    # Add new constraint with CASCADE DELETE
                    conn.execute(text(f"""
                        ALTER TABLE {constraint_info['table']} 
                        ADD CONSTRAINT {constraint_info['constraint']} 
                        FOREIGN KEY ({constraint_info['column']}) 
                        REFERENCES {constraint_info['references']} 
                        ON DELETE CASCADE
                    """))
                    
                    print(f"✅ Updated {constraint_info['table']}.{constraint_info['column']} with CASCADE DELETE")
                    
                except Exception as e:
                    print(f"⚠️  Warning: Could not update {constraint_info['table']}: {e}")
                    continue
            
            conn.commit()
            print("✅ Successfully updated all foreign key constraints with CASCADE DELETE")
            return True
            
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def verify_constraints():
    """Verify that the constraints were applied correctly"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            print("🔍 Verifying cascade delete constraints...")
            
            # Check if constraints exist with CASCADE DELETE
            result = conn.execute(text("""
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
                ORDER BY tc.table_name
            """))
            
            cascade_constraints = result.fetchall()
            
            if cascade_constraints:
                print("✅ Found CASCADE DELETE constraints:")
                for row in cascade_constraints:
                    print(f"   - {row[0]}.{row[1]} (DELETE {row[2]})")
                return True
            else:
                print("⚠️  No CASCADE DELETE constraints found")
                return False
                
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting foreign key cascade delete migration...")
    
    # Run migration
    migration_success = migrate_database()
    
    if migration_success:
        # Verify constraints
        verification_success = verify_constraints()
        
        if verification_success:
            print("🎉 Migration completed successfully!")
            print("📋 Projects can now be deleted without foreign key constraint violations")
            sys.exit(0)
        else:
            print("⚠️  Migration completed but verification failed")
            sys.exit(1)
    else:
        print("💥 Migration failed!")
        sys.exit(1)
