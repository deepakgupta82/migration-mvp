#!/usr/bin/env python3
"""
Manual Database Migration Script for Analysis Tables

This script creates the analysis tables directly using SQLAlchemy,
bypassing Alembic migration setup. It creates the following tables:
- analysis_versions
- analysis_batches
- analysis_results

Usage:
    python scripts/create_analysis_tables.py

Requirements:
- PostgreSQL database running on localhost:5432
- Database 'projectdb' with user 'projectuser' and password 'projectpass'
- Python dependencies: sqlalchemy, psycopg2-binary
"""

import sys
import os
from pathlib import Path
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import analysis models
try:
    from backend.app.models.analysis_models import Base, AnalysisVersion, AnalysisBatch, AnalysisResult
    print("✓ Successfully imported analysis models from backend")
except ImportError as e:
    print(f"✗ Failed to import backend models: {e}")
    try:
        from services.analytics_service.app.models.analysis_models import Base, AnalysisVersion, AnalysisBatch, AnalysisResult
        print("✓ Successfully imported analysis models from analytics service")
    except ImportError as e:
        print(f"✗ Failed to import analytics service models: {e}")
        sys.exit(1)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'projectdb',
    'username': 'projectuser',
    'password': 'projectpass'
}

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def create_database_url():
    """Create database URL from configuration."""
    return f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

def test_database_connection(engine):
    """Test database connection."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✓ Database connection successful")
        return True
    except SQLAlchemyError as e:
        print(f"✗ Database connection failed: {e}")
        return False

def check_existing_tables(engine):
    """Check if analysis tables already exist."""
    tables_to_check = ['analysis_versions', 'analysis_batches', 'analysis_results']
    existing_tables = []

    try:
        with engine.connect() as connection:
            for table in tables_to_check:
                result = connection.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
                ), {'table_name': table})
                exists = result.fetchone()[0]
                if exists:
                    existing_tables.append(table)
                    print(f"⚠ Table '{table}' already exists")
                else:
                    print(f"✓ Table '{table}' does not exist")
    except SQLAlchemyError as e:
        print(f"✗ Error checking existing tables: {e}")
        return []

    return existing_tables

def create_tables(engine):
    """Create analysis tables using SQLAlchemy metadata."""
    try:
        print("\n📋 Creating analysis tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ All analysis tables created successfully")
        return True
    except SQLAlchemyError as e:
        print(f"✗ Error creating tables: {e}")
        return False

def verify_table_creation(engine):
    """Verify that tables were created successfully."""
    tables_to_verify = ['analysis_versions', 'analysis_batches', 'analysis_results']
    created_tables = []

    try:
        with engine.connect() as connection:
            for table in tables_to_verify:
                result = connection.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)"
                ), {'table_name': table})
                exists = result.fetchone()[0]
                if exists:
                    created_tables.append(table)
                    print(f"✓ Verified table '{table}' exists")
                else:
                    print(f"✗ Table '{table}' was not created")
    except SQLAlchemyError as e:
        print(f"✗ Error verifying table creation: {e}")
        return []

    return created_tables

def main():
    """Main execution function."""
    logger = setup_logging()
    logger.info("Starting manual database migration for analysis tables")

    # Create database URL
    database_url = create_database_url()
    print(f"🔗 Database URL: {database_url.replace(DB_CONFIG['password'], '***')}")

    # Create engine
    try:
        engine = create_engine(database_url, echo=False)
        print("✓ Database engine created")
    except Exception as e:
        print(f"✗ Failed to create database engine: {e}")
        sys.exit(1)

    # Test connection
    if not test_database_connection(engine):
        sys.exit(1)

    # Check existing tables
    existing_tables = check_existing_tables(engine)
    if existing_tables:
        response = input(f"\n⚠ {len(existing_tables)} table(s) already exist. Continue anyway? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Migration cancelled by user")
            sys.exit(0)

    # Create tables
    if create_tables(engine):
        # Verify creation
        created_tables = verify_table_creation(engine)
        if len(created_tables) == 3:
            print("\n🎉 Migration completed successfully!")
            print(f"Created tables: {', '.join(created_tables)}")
            logger.info("Manual database migration completed successfully")
        else:
            print(f"\n⚠ Migration partially completed. Created {len(created_tables)}/3 tables")
            sys.exit(1)
    else:
        print("\n❌ Migration failed")
        sys.exit(1)

if __name__ == "__main__":
    main()