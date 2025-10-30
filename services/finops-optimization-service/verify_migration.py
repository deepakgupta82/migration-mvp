"""Verify migration success"""
import psycopg2

conn = psycopg2.connect('postgresql://projectuser:projectpass@localhost/finops_optimization')
cur = conn.cursor()

print("=== Database Migration Verification ===\n")

# Check tables
print("Tables created:")
cur.execute("""
    SELECT tablename FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY tablename
""")
tables = [row[0] for row in cur.fetchall()]
for table in tables:
    print(f"  ✓ {table}")

# Check enums
print("\nEnum types created:")
cur.execute("""
    SELECT typname FROM pg_type 
    WHERE typcategory = 'E' 
    AND typname NOT LIKE 'pg_%' AND typname NOT LIKE '_%'
    ORDER BY typname
""")
enums = [row[0] for row in cur.fetchall()]
for enum in enums:
    print(f"  ✓ {enum}")

# Check indexes
print("\nIndexes created:")
cur.execute("""
    SELECT indexname FROM pg_indexes 
    WHERE schemaname = 'public' 
    AND indexname NOT LIKE 'pg_%'
    ORDER BY indexname
""")
indexes = [row[0] for row in cur.fetchall()]
for idx in indexes:
    print(f"  ✓ {idx}")

# Verify cost_metadata column
print("\nVerifying cost_metadata column in cost_data:")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'cost_data' AND column_name = 'cost_metadata'
""")
result = cur.fetchone()
if result:
    print(f"  ✓ Column exists: {result[0]} ({result[1]})")
else:
    print("  ✗ Column NOT found!")

conn.close()
print("\n✅ Migration verification complete!")
