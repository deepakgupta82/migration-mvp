## 2025-08-10---
2025-08-12 18:25:47 IST
Committed chroma_db length.bin changes to allow branch switch:
[ToMarkItDown 8c323888] chore: commit chroma_db length.bin changes to allow branch switch
 8 files changed, 0 insertions(+), 0 deletions(-)
---
## 2025-08-12 MegaParse /v1/file Troubleshooting

- Ran curl POST to /v1/file with test_upload.txt, received HTTP 403 Forbidden.
- /healthz endpoint returns HTTP 200 OK, confirming service is up.
- Request format matches API docs; issue likely authentication or server config on /v1/file.

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
