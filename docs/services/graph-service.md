# Graph Service

## Service Overview

The Graph Service is a knowledge graph management service that operates on port 8006. It provides Neo4j-based graph database operations, entity extraction, relationship mapping, and graph visualization capabilities. The service handles knowledge graph construction, querying, and maintenance for the platform.

## Prompt Templates (New)

Phase 1 externalized templates are stored under `services/graph-service/prompts/` and loaded at runtime via `app/core/prompt_loader.py`.

- `entity_extraction.json` — entity extraction from plain text or table-aware content
- `fact_extraction.json` — relationship/fact extraction with table awareness

Notes:
- `app/core/graph_processor.py` composes prompts with spreadsheet/table-specific context when inputs originate from spreadsheets or TABLE blocks.
- If a template is missing, the processor falls back to inline guidance to preserve behavior.
- Edit templates from the UI: Settings → LLM Prompts → select `graph-service`.

### Loader and Reload

- Loader: `app/core/prompt_loader.py` in-memory cache.
- Reload endpoint: `POST /admin/prompts/reload` to hot-reload.
- Central backend supports `POST /api/prompts/graph-service/reload` which forwards to this service.

## APIs/Endpoints

Graph operations unchanged. Prompt-driven flows are used during entity and relationship extraction in graph construction and updates.

## File Structure

- Templates: `services/graph-service/prompts/*.json`
- Loader: `services/graph-service/app/core/prompt_loader.py`
- Processor: `services/graph-service/app/core/graph_processor.py`

## Table-aware LLM Extraction

When processing spreadsheet or table-like content (e.g., .xlsx, .xls, .csv or structured elements summarized as `TABLE:`), the graph-service augments the LLM prompt with explicit row-aware guidance and requires strict JSON output of the form `{ "entities": [], "relationships": [] }`.