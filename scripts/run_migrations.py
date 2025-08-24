#!/usr/bin/env python3
"""
Database migration runner for user management enhancements
Runs migrations safely with proper error handling and rollback capability
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'user': 'projectuser',
    'password': 'projectpass'
}

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def run_migration_file(filepath, description):
    """Run a single migration file"""
    logger.info(f"🔄 Running migration: {description}")
    
    try:
        # Read migration file
        with open(filepath, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Execute migration
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Execute the migration
        cursor.execute(migration_sql)
        
        logger.info(f"✅ Migration completed successfully: {description}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {description}")
        logger.error(f"Error: {e}")
        return False

def check_migration_status():
    """Check current database schema status"""
    logger.info("🔍 Checking current database schema...")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if new user fields exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('username', 'first_name', 'last_name', 'last_login', 'failed_login_attempts')
        """)
        user_fields = [row[0] for row in cursor.fetchall()]
        
        # Check if new tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('project_user_roles', 'user_sessions', 'audit_logs', 'oauth_providers')
        """)
        new_tables = [row[0] for row in cursor.fetchall()]
        
        # Check existing data
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM project_user_association")
        old_associations = cursor.fetchone()[0]
        
        try:
            cursor.execute("SELECT COUNT(*) FROM project_user_roles")
            new_roles = cursor.fetchone()[0]
        except:
            new_roles = 0
        
        logger.info(f"📊 Current Status:")
        logger.info(f"  - Users: {user_count}")
        logger.info(f"  - Old project associations: {old_associations}")
        logger.info(f"  - New project roles: {new_roles}")
        logger.info(f"  - Enhanced user fields: {len(user_fields)}/5")
        logger.info(f"  - New tables: {len(new_tables)}/4")
        
        cursor.close()
        conn.close()
        
        return {
            'user_count': user_count,
            'old_associations': old_associations,
            'new_roles': new_roles,
            'user_fields': user_fields,
            'new_tables': new_tables
        }
        
    except Exception as e:
        logger.error(f"Failed to check migration status: {e}")
        return None

def main():
    """Main migration runner"""
    logger.info("🚀 Starting User Management Database Migrations")
    logger.info("=" * 60)
    
    # Check initial status
    initial_status = check_migration_status()
    if not initial_status:
        logger.error("❌ Failed to check initial database status")
        sys.exit(1)
    
    # Define migrations
    migrations = [
        {
            'file': 'migrations/001_add_user_fields.sql',
            'description': 'Add enhanced user fields (username, names, security fields)',
            'required_fields': ['username', 'first_name', 'last_name', 'last_login', 'failed_login_attempts']
        },
        {
            'file': 'migrations/002_create_role_tables.sql',
            'description': 'Create enhanced role and security tables',
            'required_tables': ['project_user_roles', 'user_sessions', 'audit_logs', 'oauth_providers']
        },
        {
            'file': 'migrations/003_migrate_existing_data.sql',
            'description': 'Migrate existing data to new structure',
            'data_migration': True
        }
    ]
    
    # Run migrations
    success_count = 0
    for i, migration in enumerate(migrations, 1):
        logger.info(f"\n📋 Migration {i}/{len(migrations)}: {migration['description']}")
        
        filepath = migration['file']
        if not os.path.exists(filepath):
            logger.error(f"❌ Migration file not found: {filepath}")
            continue
        
        # Check if migration is needed
        if 'required_fields' in migration:
            existing_fields = initial_status.get('user_fields', [])
            if all(field in existing_fields for field in migration['required_fields']):
                logger.info(f"⏭️  Migration already applied: {migration['description']}")
                success_count += 1
                continue
        
        if 'required_tables' in migration:
            existing_tables = initial_status.get('new_tables', [])
            if all(table in existing_tables for table in migration['required_tables']):
                logger.info(f"⏭️  Migration already applied: {migration['description']}")
                success_count += 1
                continue
        
        # Run migration
        if run_migration_file(filepath, migration['description']):
            success_count += 1
        else:
            logger.error(f"❌ Migration failed, stopping at step {i}")
            break
    
    # Final status check
    logger.info("\n" + "=" * 60)
    logger.info("📊 Final Migration Status")
    final_status = check_migration_status()
    
    if success_count == len(migrations):
        logger.info("🎉 All migrations completed successfully!")
        logger.info("✅ User management enhancement database schema is ready")
    else:
        logger.error(f"❌ {len(migrations) - success_count} migrations failed")
        logger.error("🔄 Please check errors and retry")
        sys.exit(1)

if __name__ == "__main__":
    main()
