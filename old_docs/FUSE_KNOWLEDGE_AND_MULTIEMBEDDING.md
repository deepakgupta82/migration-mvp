# Fuse-Knowledge Orchestrator and Multi-Embedding Collections

This guide explains the new cross-document PVC orchestrator and how to use separate vector "kinds" for embeddings, plus exactly how to enable/disable the feature flags `PVC_ENABLED` and `VECTORS_USE_KIND`.

## What was added

- Document-service: `POST /api/documents/{project_id}/pvc/fuse-knowledge`
  - Registers entity and relationship types (status `pending_approval`) using graph-service
  - Commits proposals in batch by `proposal_ids` or by `status_filter` (default `validated`)
  - Emits a `graph_updated` event to stats-service
- Vector-service: per-kind collection endpoints (logical views) using the `source` tag
  - `POST /api/vectors/projects/{project_id}/collections/{kind}`
  - `GET /api/vectors/projects/{project_id}/collections/{kind}`
  - `POST /api/vectors/projects/{project_id}/collections/{kind}/documents/sync`
  - Allowed kinds: `raw_chunks`, `entity_cards`, `triple_cards`
- Document-service embeds can target a specific kind when `VECTORS_USE_KIND` is set. If not set, legacy endpoints are used.
  
New (search-by-kind):
- `POST /api/vectors/projects/{project_id}/collections/{kind}/search`
- `POST /api/vectors/projects/{project_id}/collections/{kind}/search/hybrid`

## Endpoints

- Fuse-Knowledge orchestrator
  - `POST /api/documents/{project_id}/pvc/fuse-knowledge`
  - Request body examples:
    - Commit all validated proposals:
      ```json
      { "status_filter": "validated" }
      ```
    - Register only types (no commit):
      ```json
      {
        "entity_types": [
          { "name": "Company", "description": "Organizations" },
          { "name": "Person", "description": "Individuals" }
        ],
        "relationship_types": [
          { "name": "EMPLOYS", "from_type": "Company", "to_type": "Person", "description": "Employment relation" }
        ],
        "register_only": true
      }
      ```

- Vector-service per-kind
  - Prepare/get per-kind collection:
    - `POST /api/vectors/projects/{project_id}/collections/{kind}`
    - `GET /api/vectors/projects/{project_id}/collections/{kind}`
  - Upsert per-kind documents (forces `source=kind`):
    - `POST /api/vectors/projects/{project_id}/collections/{kind}/documents/sync`
  
  - Search per-kind:
    - `POST /api/vectors/projects/{project_id}/collections/{kind}/search`
    - `POST /api/vectors/projects/{project_id}/collections/{kind}/search/hybrid`

## Feature flags

- `PVC_ENABLED` (document-service only)
  - Controls access to PVC endpoints like `fuse-knowledge`.
  - Code reference: `services/document-service/app/routers/documents.py` function `_pvc_enabled()` reads `PVC_ENABLED` env var or config key `document_service.pvc_enabled` (via `BACKEND_CONFIG_URL`).
  - Enable: set to `true`, `1`, `yes`, or `on`
  - Disable: set to `false`, `0`, `no`, or unset

- `VECTORS_USE_KIND` (document-service only)
  - When set, document-service will route embeddings to per-kind endpoints. Recommended value for chunk embeddings: `raw_chunks`.
  - Code reference: search for `VECTORS_USE_KIND` in `services/document-service/app/routers/documents.py` (used during PVC processing paths).
  - Allowed: `raw_chunks`, `entity_cards`, `triple_cards` (matches vector-service KIND_VALUES)

## Where to enable/disable

You have several options. The services are currently started by VS Code tasks that run Uvicorn in the respective service folders.

1) Per-session (PowerShell) — recommended for quick testing

- For document-service (port 8003), in a new PowerShell pane:
  ```powershell
  # Enable PVC and route embeddings to raw_chunks for this session only
  $env:PVC_ENABLED = "true"
  $env:VECTORS_USE_KIND = "raw_chunks"
  
  # Start only document-service (if not already running via tasks)
  cd "services\document-service"
  .\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload
  ```
- To disable later in the same session:
  ```powershell
  Remove-Item Env:PVC_ENABLED -ErrorAction Ignore
  Remove-Item Env:VECTORS_USE_KIND -ErrorAction Ignore
  ```

2) VS Code tasks.json (persistent per-run of the task)

- If you maintain custom tasks, add these env vars under the `options.env` of the `document` task.
- Example snippet conceptually:
  ```jsonc
  {
    "label": "document",
    "type": "process",
    "command": ".venv/Scripts/python.exe",
    "args": ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--reload"],
    "options": {
      "cwd": "${workspaceFolder}/services/document-service",
      "env": {
        "PVC_ENABLED": "true",
        "VECTORS_USE_KIND": "raw_chunks"
      }
    }
  }
  ```
  Note: Your tasks are already defined and running; if you want this persistent, edit your task definition (e.g., in `.vscode/tasks.json`). If that file isn’t present, you can create one, or set the variables per-session as shown above.

3) Central config (optional)

- `_pvc_enabled()` also checks a remote/local config key: `document_service.pvc_enabled` from `BACKEND_CONFIG_URL` (defaults to `http://localhost:8000/config/config.local.json`).
- You can add this flag there to make it universally true without env vars. Example `config.local.json` snippet:
  ```json
  {
    "document_service": {
      "pvc_enabled": true
    }
  }
  ```
- Vectors kind is only read from env at the moment; keep using env for that.

## How to try it

- Ensure services are running (your VS Code tasks already show document-service on 8003, vector-service on 8005, graph-service on 8006, stats on 8004).
- Enable flags for the document-service process as shown above.
- Run the smoke script:
  ```powershell
  powershell -NoProfile -File .\scripts\smoke_fuse_knowledge.ps1
  # Or to register-only
  powershell -NoProfile -File .\scripts\smoke_fuse_knowledge.ps1 -RegisterOnly
  ```

- Try vector search by kind (PowerShell):
  ```powershell
  $headers = @{ Authorization = 'Bearer service-backend-token' }
  $body = @{ query = 'your query', limit = 10, include_metadata = $true } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "http://localhost:8005/api/vectors/projects/61502d23-4928-4377-92c8-81b9c4f0fffd/collections/raw_chunks/search" -Headers $headers -ContentType 'application/json' -Body $body
  ```

- Try hybrid search by kind:
  ```powershell
  $headers = @{ Authorization = 'Bearer service-backend-token' }
  $body = @{ query = 'your query', limit = 10, semantic_weight = 0.7 } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "http://localhost:8005/api/vectors/projects/61502d23-4928-4377-92c8-81b9c4f0fffd/collections/raw_chunks/search/hybrid" -Headers $headers -ContentType 'application/json' -Body $body
  ```

## Notes and defaults

- If `PVC_ENABLED` is not enabled, PVC endpoints (including `fuse-knowledge`) return 403 with a helpful message.
- If `VECTORS_USE_KIND` is unset, embeddings go to the legacy endpoint (`/documents/sync`) and `source` remains as provided by the caller (usually `document-service`).
- Vector-service per-kind endpoints implement logical separation using `source` field. Physical Weaviate schema is unchanged (`DocumentChunk`).

## Troubleshooting

- 403 from fuse-knowledge: ensure `PVC_ENABLED` is true in the document-service environment (or set in central config via `document_service.pvc_enabled`).
- 400 invalid kind: ensure `VECTORS_USE_KIND` or kind path uses one of `raw_chunks`, `entity_cards`, `triple_cards`.
- Weaviate not ready: check `WEAVIATE_URL` and that Weaviate is running; vector-service `/health` should be healthy.
- Neo4j/Graph errors: verify graph-service connectivity and credentials.
