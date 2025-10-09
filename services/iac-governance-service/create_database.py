"""
Create the IAC Governance database.
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Connection parameters
host = "localhost"
port = 5432
user = "projectuser"
password = "projectpass"
dbname_to_create = "iac_governance"

try:
    # Connect to the default 'postgres' database
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    cursor = conn.cursor()
    
    # Check if database already exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname_to_create,))
    exists = cursor.fetchone()
    
    if exists:
        print(f"✅ Database '{dbname_to_create}' already exists")
    else:
        # Create the database
        cursor.execute(f"CREATE DATABASE {dbname_to_create} OWNER {user}")
        print(f"✅ Database '{dbname_to_create}' created successfully")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
