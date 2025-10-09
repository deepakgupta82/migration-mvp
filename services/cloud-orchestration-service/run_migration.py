"""Run Alembic migration with proper environment setup."""

import os
import sys
import subprocess

# Set environment variable
os.environ["CLOUD_ORCHESTRATION_DB_URL"] = "postgresql://projectuser:projectpass@localhost:5432/cloud_orchestration"

# Run alembic upgrade
result = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

sys.exit(result.returncode)
