"""
Terraform Migration Verification Script

Applies migration 002 and verifies Terraform tables were created correctly.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/iac_governance"
)

print(f"Connecting to database: {DATABASE_URL.split('@')[1]}")

# Create engine
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)


def verify_table_exists(table_name: str) -> bool:
    """Verify table exists."""
    tables = inspector.get_table_names()
    exists = table_name in tables
    status = "✅" if exists else "❌"
    print(f"{status} Table '{table_name}' {'exists' if exists else 'MISSING'}")
    return exists


def verify_table_columns(table_name: str, expected_columns: list) -> bool:
    """Verify table has expected columns."""
    if not verify_table_exists(table_name):
        return False
    
    columns = {col['name'] for col in inspector.get_columns(table_name)}
    missing = set(expected_columns) - columns
    extra = columns - set(expected_columns)
    
    if missing:
        print(f"  ❌ Missing columns: {missing}")
    if extra:
        print(f"  ⚠️  Extra columns: {extra}")
    
    if not missing:
        print(f"  ✅ All {len(expected_columns)} expected columns present")
    
    return len(missing) == 0


def verify_indexes(table_name: str, expected_indexes: list) -> bool:
    """Verify table has expected indexes."""
    indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
    missing = set(expected_indexes) - indexes
    
    if missing:
        print(f"  ❌ Missing indexes: {missing}")
    else:
        print(f"  ✅ All {len(expected_indexes)} expected indexes present")
    
    return len(missing) == 0


def verify_foreign_keys(table_name: str, expected_fks: list) -> bool:
    """Verify table has expected foreign keys."""
    fks = {fk['constrained_columns'][0]: fk['referred_table'] 
           for fk in inspector.get_foreign_keys(table_name)}
    
    for col, ref_table in expected_fks:
        if col in fks and fks[col] == ref_table:
            print(f"  ✅ Foreign key {col} → {ref_table}")
        else:
            print(f"  ❌ Missing FK: {col} → {ref_table}")
            return False
    
    return True


def verify_enum_type(enum_name: str, expected_values: list) -> bool:
    """Verify enum type exists with expected values."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT enumlabel 
            FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = :enum_name
            ORDER BY enumlabel
        """), {"enum_name": enum_name})
        
        actual_values = [row[0] for row in result]
        
        if set(actual_values) == set(expected_values):
            print(f"  ✅ Enum '{enum_name}' has correct values: {actual_values}")
            return True
        else:
            print(f"  ❌ Enum '{enum_name}' values mismatch")
            print(f"     Expected: {expected_values}")
            print(f"     Actual: {actual_values}")
            return False


def main():
    """Run verification."""
    print("\n" + "="*60)
    print("TERRAFORM MIGRATION VERIFICATION")
    print("="*60 + "\n")
    
    all_passed = True
    
    # Verify enums
    print("\n1. Verifying Enum Types:")
    print("-" * 40)
    if not verify_enum_type('terraformexecutionstatus', ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED']):
        all_passed = False
    if not verify_enum_type('terraformexecutiontype', ['INIT', 'PLAN', 'APPLY', 'DESTROY', 'VALIDATE']):
        all_passed = False
    
    # Verify terraform_executions table
    print("\n2. Verifying terraform_executions Table:")
    print("-" * 40)
    terraform_executions_columns = [
        'execution_id', 'project_id', 'scan_id', 'execution_type', 'status',
        'workspace_path', 'workspace_name', 'var_file', 'variables', 'backend_config',
        'target_resources', 'auto_approve', 'plan_id', 'changes_summary',
        'resources_affected', 'started_at', 'completed_at', 'duration_seconds',
        'output_text', 'error_message', 'error_details', 'is_valid', 'diagnostics',
        'error_count', 'warning_count', 'execution_metadata', 'correlation_id',
        'triggered_by', 'created_at', 'updated_at'
    ]
    if not verify_table_columns('terraform_executions', terraform_executions_columns):
        all_passed = False
    
    terraform_executions_indexes = [
        'ix_terraform_executions_project_id',
        'ix_terraform_executions_status',
        'ix_terraform_executions_execution_type',
        'ix_terraform_executions_project_status',
        'ix_terraform_executions_correlation_id',
        'ix_terraform_executions_created_at',
    ]
    if not verify_indexes('terraform_executions', terraform_executions_indexes):
        all_passed = False
    
    if not verify_foreign_keys('terraform_executions', [('scan_id', 'policy_scans')]):
        all_passed = False
    
    # Verify terraform_resources table
    print("\n3. Verifying terraform_resources Table:")
    print("-" * 40)
    terraform_resources_columns = [
        'resource_id', 'execution_id', 'resource_address', 'resource_type',
        'resource_name', 'module_path', 'action', 'change_details',
        'previous_state', 'new_state', 'provider', 'resource_metadata',
        'created_at', 'updated_at'
    ]
    if not verify_table_columns('terraform_resources', terraform_resources_columns):
        all_passed = False
    
    terraform_resources_indexes = [
        'ix_terraform_resources_execution_id',
        'ix_terraform_resources_resource_type',
        'ix_terraform_resources_action',
        'ix_terraform_resources_resource_address',
    ]
    if not verify_indexes('terraform_resources', terraform_resources_indexes):
        all_passed = False
    
    if not verify_foreign_keys('terraform_resources', [('execution_id', 'terraform_executions')]):
        all_passed = False
    
    # Final summary
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TERRAFORM MIGRATION CHECKS PASSED!")
    else:
        print("❌ SOME TERRAFORM MIGRATION CHECKS FAILED")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
