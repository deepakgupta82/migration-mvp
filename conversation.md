## 2025-08-10

- Created git branch `snappy_ui` for snappy stats/list loading improvements.
- Added `cachetools` to requirements.txt.
- Implemented in-memory caching for `/projects/stats` and `/projects` endpoints in `project-service/main.py` using `TTLCache`.
- Added cache invalidation on project create, update, and delete.
- Committed changes: "feat: add in-memory caching for project stats and list endpoints with cache invalidation on project changes"
- Fixed logging KeyError for missing correlation_id by introducing SafeFormatter in logging setup. Committed as "fix: prevent logging KeyError for missing correlation_id by using SafeFormatter"

## 2025-08-11

**Issue:**  
Backend was unable to authenticate with project-service after refactor, resulting in 401 errors when loading LLM configurations.

**Root Cause:**  
backend/app/core/project_service.py did not send SERVICE_AUTH_TOKEN as Bearer token if no JWT or API key was set.

**Fix:**  
Patched _get_auth_headers in ProjectServiceClient to send SERVICE_AUTH_TOKEN as Bearer token if neither JWT nor API key is set.

**Commit:**  
fix: allow backend to authenticate with project-service using SERVICE_AUTH_TOKEN as Bearer token if no JWT or API key is set
