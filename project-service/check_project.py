import sys
sys.path.append('.')
from database import get_db_with_retry
try:
    db = get_db_with_retry()
    from sqlalchemy import text
    result = db.execute(text('SELECT id, name, status FROM projects WHERE id = :project_id'), {'project_id': '0aadf04b-7c9f-468a-9fda-6471c8dd5276'})
    project = result.fetchone()
    if project:
        print(f'Project found: ID={project.id}, Name={project.name}, Status={project.status}')
    else:
        print('Project not found in database')

    # Also check total number of projects
    count_result = db.execute(text('SELECT COUNT(*) as count FROM projects'))
    count = count_result.fetchone()
    print(f'Total projects in database: {count.count}')

    db.close()
except Exception as e:
    print(f'Error: {e}')
