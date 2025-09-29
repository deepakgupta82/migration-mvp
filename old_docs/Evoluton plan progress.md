# Ascent Evolution Plan - Implementation Progress

## Phase 1: Supercharge the Knowledge Core

### Task 1: Upgrade Document Intake Engine
- Added `unstructured[all]>=0.14.6` to `services/document-service/requirements.txt`.
- Implemented Unstructured auto partitioner in `DocumentProcessor._perform_conversion_sync` with safe fallbacks (MarkItDown, PyMuPDF, pdfminer, pdfplumber).
- Local verification guidance added; debug outputs saved under `markitdown_debug/` when enabled.

### Task 2: Data Importer Microservice (local-only)
- Created `services/data-importer-service` with FastAPI app.
	- `GET /health`
	- `POST /importers/aws/migration-evaluator` (CSV upload) → upserts assets to `GRAPH_SERVICE_URL/graph/assets`.
- Runs locally via `uvicorn app.main:app --reload --port 8095`.
- Next: add Azure endpoint and dependency/dependency metrics posting once graph endpoints are confirmed.

Checkpoint: Phase 1 tasks 1–2 completed and runnable locally. Next, add AWS documentation MCP wrapper and a local sync script to enrich graph with pricing/specs.

### Task 3: AWS Documentation MCP wrapper and local sync (planned)
- To be added next: local-only script `scripts\\sync\\aws_data_sync.py` calling an MCP wrapper or official endpoint to pull pricing/specs and upsert into graph (`/api/graphs/projects/{project_id}/assets` with price fields).
- Not Dockerized yet; will run with a simple `python` entrypoint and .env configuration.

