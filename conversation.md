## 2025-08-14---User wanted to ignore all files in data/chroma_db/ via .gitignore.
Ran `git rm -r --cached data/chroma_db/` but no files were tracked, confirmed by `git ls-files data/chroma_db/` (empty output).
No further action needed; .gitignore entry is sufficient.
Timestamp: 2025-08-14 12:22:07 Asia/Calcutta

## 2025-08-10---User requested deletion of Docker containers: markitdow_mcp_service, project_service, frontend_service, db_init_service, markitdown_api_service, markitdown_service, backend_service, reporting_service.
Response: Ran `docker rm -f` for all listed containers. All except markitdow_mcp_service were deleted; markitdow_mcp_service did not exist.
Timestamp: 2025-08-14 12:07:29 Asia/Calcutta

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
