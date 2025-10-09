"""Verify database migration was successful."""

import psycopg2

# Database connection
DATABASE_URL = "postgresql://projectuser:projectpass@localhost:5432/cloud_orchestration"

def verify_tables():
    """Check if migration tables exist."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Check for alembic_version table
        cursor.execute("""
            SELECT version_num FROM alembic_version
        """)
        version = cursor.fetchone()
        
        if version:
            print(f"✅ Alembic version: {version[0]}")
        else:
            print("⚠️  No alembic version found")
        
        # Check for migration tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('migration_waves', 'migration_resources', 'migration_tasks')
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print(f"\n✅ Found {len(tables)} migration tables:")
        for table in tables:
            print(f"   - {table[0]}")
            
            # Get column count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = '{table[0]}'
            """)
            col_count = cursor.fetchone()[0]
            print(f"     ({col_count} columns)")
        
        cursor.close()
        conn.close()
        
        if len(tables) == 3:
            print("\n✅ Migration successful! All tables created.")
            return True
        else:
            print(f"\n❌ Migration incomplete. Expected 3 tables, found {len(tables)}")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying migration: {e}")
        return False


if __name__ == "__main__":
    verify_tables()
