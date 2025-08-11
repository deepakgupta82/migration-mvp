## 2025-08-10

- Created git branch `snappy_ui` for snappy stats/list loading improvements.
- Added `cachetools` to requirements.txt.
- Implemented in-memory caching for `/projects/stats` and `/projects` endpoints in `project-service/main.py` using `TTLCache`.
- Added cache invalidation on project create, update, and delete.
- Committed changes: "feat: add in-memory caching for project stats and list endpoints with cache invalidation on project changes"
- Fixed logging KeyError for missing correlation_id by introducing SafeFormatter in logging setup. Committed as "fix: prevent logging KeyError for missing correlation_id by using SafeFormatter"
