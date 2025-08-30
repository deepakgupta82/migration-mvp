import sys
sys.path.append('.')
from database import get_db_with_retry, check_database_health
try:
    db = get_db_with_retry()
    health = check_database_health()
    print('Database connection successful!')
    print(f'Status: {health.get("status")}')
    print(f'Version: {health.get("version")}')
    db.close()
except Exception as e:
    print(f'Database connection failed: {e}')
