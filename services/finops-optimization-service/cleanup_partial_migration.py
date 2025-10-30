"""Cleanup partial migration artifacts"""
import psycopg2

# Connect to database
conn = psycopg2.connect('postgresql://projectuser:projectpass@localhost/finops_optimization')
conn.autocommit = True
cur = conn.cursor()

# First, check what exists
print("Checking existing types...")
cur.execute("SELECT typname FROM pg_type WHERE typcategory = 'E' AND typname LIKE '%type' OR typname LIKE '%status' OR typname LIKE '%level'")
existing = [row[0] for row in cur.fetchall()]
print(f"Found enums: {existing}")

# Drop all enums that might have been created
enums = [
    'budgettype', 'budgetstatus', 'recommendationtype', 'recommendationstatus',
    'effortlevel', 'risklevel', 'anomalyalerttype', 'severity',
    'alertstatus', 'allocationruletype'
]

print("\nDropping enum types...")
for enum in enums:
    try:
        cur.execute(f'DROP TYPE IF EXISTS {enum} CASCADE')
        print(f"  Dropped: {enum}")
    except Exception as e:
        print(f"  Error dropping {enum}: {e}")

# Check what's left
print("\nChecking remaining types...")
cur.execute("SELECT typname FROM pg_type WHERE typcategory = 'E' AND (typname LIKE '%type' OR typname LIKE '%status' OR typname LIKE '%level')")
remaining = [row[0] for row in cur.fetchall()]
if remaining:
    print(f"Warning: Some enums still exist: {remaining}")
else:
    print("All enums successfully removed")

# Drop tables if they exist
print("\nDropping any partial tables...")
tables = ['cost_allocation_rules', 'anomaly_alerts', 'optimization_recommendations', 'cost_data', 'budgets']
for table in tables:
    try:
        cur.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
        print(f"  Dropped: {table}")
    except Exception as e:
        print(f"  Error dropping {table}: {e}")

# Reset alembic version
print("\nResetting Alembic version table...")
try:
    cur.execute("DROP TABLE IF EXISTS alembic_version CASCADE")
    print("  Alembic version table dropped")
except Exception as e:
    print(f"  Error dropping alembic_version: {e}")

conn.close()
print("\nCleanup complete!")
