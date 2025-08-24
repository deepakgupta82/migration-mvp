import os, sys, json, asyncio
from datetime import datetime

# Ensure backend is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

from app.routers import logs_router

async def main():
    print('BASE_DIR:', logs_router.BASE_DIR)
    print('DEFAULT_LOG_DIR:', logs_router.DEFAULT_LOG_DIR)
    print('LOG_DIR:', logs_router.LOG_DIR)
    print('SERVICE_LOG_DIRS:')
    for d in logs_router.SERVICE_LOG_DIRS:
        print(' -', d, 'exists=' , os.path.exists(d))
    print('Discovered files via _list_all_log_files():')
    files = logs_router._list_all_log_files()
    for f in files:
        print(' *', f, 'exists=', os.path.exists(f))
    print('Listing services...')
    services = await logs_router.list_log_services()
    print(json.dumps(services, indent=2))

    print('\nSearch all logs (no filters, limit=50)...')
    res = await logs_router.search_logs(q=None, correlation_id=None, services=None, level=None, project_id=None, from_time=None, to_time=None, limit=50)
    print(json.dumps(res, indent=2))

    print('\nSearch by correlation id corr_123 ...')
    res2 = await logs_router.search_logs(q=None, correlation_id='corr_123', services=None, level=None, project_id=None, from_time=None, to_time=None, limit=50)
    print(json.dumps(res2, indent=2))

    print('\nTail backend logs...')
    res3 = await logs_router.get_logs(service='backend', tail=10)
    print(json.dumps(res3, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
