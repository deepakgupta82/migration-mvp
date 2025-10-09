"""
Create cloud_orchestration database if it doesn't exist.

This script connects to PostgreSQL and creates the database for cloud-orchestration-service.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Connection parameters (same as project-service)
POSTGRES_USER = "projectuser"
POSTGRES_PASSWORD = "projectpass"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
DATABASE_NAME = "cloud_orchestration"


def create_database_if_not_exists():
    """Create cloud_orchestration database if it doesn't exist."""
    
    # Connect to default postgres database
    conn = psycopg2.connect(
        dbname="postgres",
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cursor = conn.cursor()
    
    # Check if database exists
    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DATABASE_NAME,)
    )
    exists = cursor.fetchone()
    
    if not exists:
        print(f"Creating database '{DATABASE_NAME}'...")
        cursor.execute(f'CREATE DATABASE {DATABASE_NAME}')
        print(f"✅ Database '{DATABASE_NAME}' created successfully")
    else:
        print(f"✅ Database '{DATABASE_NAME}' already exists")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    try:
        create_database_if_not_exists()
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        raise
