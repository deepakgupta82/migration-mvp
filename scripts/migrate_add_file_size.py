#!/usr/bin/env python3
"""
Database migration script to add file_size column to project_files table
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/migration_platform")

def migrate_database():
    """Add file_size column to project_files table if it doesn't exist"""
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if file_size column already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'project_files' 
                AND column_name = 'file_size'
            """))
            
            if result.fetchone():
                print("✅ file_size column already exists in project_files table")
                return True
            
            # Add the file_size column
            print("📝 Adding file_size column to project_files table...")
            conn.execute(text("""
                ALTER TABLE project_files 
                ADD COLUMN file_size INTEGER
            """))
            conn.commit()
            
            print("✅ Successfully added file_size column to project_files table")
            return True
            
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting database migration...")
    success = migrate_database()
    
    if success:
        print("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migration failed!")
        sys.exit(1)
