import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
try:
    # Use the same DATABASE_URL as in database.py
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/projectdb")

    # Parse the DATABASE_URL
    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)

    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, status, created_at FROM projects WHERE id = '0aadf04b-7c9f-468a-9fda-6471c8dd5276'")
    result = cursor.fetchone()
    if result:
        print(f'Project found: ID={result[0]}, Name={result[1]}, Status={result[2]}, Created={result[3]}')
    else:
        print('Project not found in database')

    # Also check total number of projects
    cursor.execute("SELECT COUNT(*) FROM projects")
    count = cursor.fetchone()[0]
    print(f'Total projects in database: {count}')

    cursor.close()
    conn.close()
except Exception as e:
    print(f"Database error: {e}")
