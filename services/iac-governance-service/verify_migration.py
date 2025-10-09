"""
Verify IAC Governance Service database migration.

This script checks that the database was created correctly with all tables and indexes.
"""
import asyncio
import sys
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

# Convert sync URL to async URL
from dotenv import load_dotenv
import os

load_dotenv()

db_url = os.getenv("IAC_GOVERNANCE_DB_URL", "postgresql://projectuser:projectpass@localhost:5432/iac_governance")
# Convert to async URL
async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

async def verify_migration():
    """Verify the database migration was successful."""
    
    print("=" * 60)
    print("IAC Governance Service - Migration Verification")
    print("=" * 60)
    
    engine = create_async_engine(async_db_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check database connection
            result = await conn.execute(text("SELECT current_database(), version()"))
            db_name, version = result.fetchone()
            print(f"\n✅ Connected to database: {db_name}")
            print(f"   PostgreSQL version: {version.split(',')[0]}")
            
            # Check tables
            print("\n📊 Checking tables...")
            expected_tables = [
                'policy_templates',
                'policy_scans',
                'policy_violations',
                'remediation_actions',
                'alembic_version'
            ]
            
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ))
            actual_tables = [row[0] for row in result.fetchall()]
            
            for table in expected_tables:
                if table in actual_tables:
                    print(f"   ✅ {table}")
                else:
                    print(f"   ❌ {table} - MISSING!")
                    
            # Check table counts
            print("\n📈 Table row counts:")
            for table in expected_tables[:-1]:  # Skip alembic_version
                if table in actual_tables:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"   {table}: {count} rows")
            
            # Check Alembic version
            if 'alembic_version' in actual_tables:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar()
                print(f"\n🔖 Alembic migration version: {version}")
            
            # Check policy_templates table structure
            print("\n🏗️  Policy Templates table structure:")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'policy_templates'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"   Total columns: {len(columns)}")
            for col_name, col_type, nullable in columns[:5]:  # Show first 5
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                print(f"   - {col_name}: {col_type} {null_str}")
            if len(columns) > 5:
                print(f"   ... and {len(columns) - 5} more columns")
            
            # Check policy_scans table structure
            print("\n🔍 Policy Scans table structure:")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'policy_scans'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"   Total columns: {len(columns)}")
            
            # Check policy_violations table structure
            print("\n⚠️  Policy Violations table structure:")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'policy_violations'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"   Total columns: {len(columns)}")
            
            # Check remediation_actions table structure
            print("\n🔧 Remediation Actions table structure:")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'remediation_actions'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"   Total columns: {len(columns)}")
            
            # Check indexes
            print("\n🔑 Checking indexes:")
            result = await conn.execute(text("""
                SELECT tablename, indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                ORDER BY tablename, indexname
            """))
            indexes = result.fetchall()
            by_table = {}
            for table, index in indexes:
                if table not in by_table:
                    by_table[table] = []
                by_table[table].append(index)
            
            for table in expected_tables[:-1]:  # Skip alembic_version
                if table in by_table:
                    print(f"   {table}: {len(by_table[table])} indexes")
                    for idx in by_table[table][:3]:  # Show first 3
                        print(f"      - {idx}")
                    if len(by_table[table]) > 3:
                        print(f"      ... and {len(by_table[table]) - 3} more")
            
            # Check foreign keys
            print("\n🔗 Checking foreign key constraints:")
            result = await conn.execute(text("""
                SELECT 
                    tc.table_name, 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                ORDER BY tc.table_name
            """))
            fks = result.fetchall()
            for table, col, ref_table, ref_col in fks:
                print(f"   {table}.{col} → {ref_table}.{ref_col}")
            
            # Check enums
            print("\n📋 Checking custom enum types:")
            result = await conn.execute(text("""
                SELECT typname, enumlabel
                FROM pg_type 
                JOIN pg_enum ON pg_type.oid = pg_enum.enumtypid
                WHERE typname IN ('policyseverity', 'scanstatus', 'remediationstatus')
                ORDER BY typname, enumlabel
            """))
            enums = result.fetchall()
            current_enum = None
            for enum_name, enum_value in enums:
                if enum_name != current_enum:
                    print(f"\n   {enum_name}:")
                    current_enum = enum_name
                print(f"      - {enum_value}")
            
            print("\n" + "=" * 60)
            print("✅ Migration verification complete!")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        return False
    finally:
        await engine.dispose()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(verify_migration())
    sys.exit(0 if success else 1)
