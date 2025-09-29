# Prompt Management (Phase 1)

This document describes the JSON-based prompt registry, backend admin API, and service loaders introduced to centralize and safely edit LLM prompts across services.

## Scope

Phase 1 covers these services:
- ai-agent-service
- document-service
- graph-service
- llm-service

Prompts are stored per service under:

- `services/<service-name>/prompts/*.json`

Examples:
- `services/ai-agent-service/prompts/document_generation.json`
- `services/document-service/prompts/enrich_facts_entities.json`
- `services/document-service/prompts/keywords_summary.json`
- `services/graph-service/prompts/{entity_extraction.json|fact_extraction.json}`
- `services/llm-service/prompts/{rag_synthesis.json|content_summarization.json|table_extraction.json|diagram_understanding.json}`

## JSON Schema

Each prompt JSON follows this shape:

```
{
  "id": "document_generation",
  "service": "ai-agent-service",
  "purpose": "what this prompt is for",
  "description": "short explanatory text",
  "variables": ["project_id", "template_guidance", "context_snippets"],
  "version": 1,
  "text": "... prompt template text ...",
  "updated_by": "optional user",
  "updated_at": "ISO timestamp",
  "metadata": {"optional": "fields"}
}
```

Notes:
- `text` may include simple placeholders like `{{project_id}}`. Variables listed in `variables` are substituted by callers. Avoid complex logic in templates.

## Backend Admin API

Base: `http://<backend>/api/prompts`

- `GET /services` → list services that have a `prompts/` folder
- `GET /{service}` → list prompts for the service
- `GET /{service}/{id}` → get one prompt
- `POST /validate` → validate a prompt document (does not save)
- `PUT /{service}/{id}` → save/update a prompt; performs atomic write and git auto-commit (best-effort)
- `POST /{service}/reload` → ask the target service to reload its in-memory prompt cache

Auth: uses the same model as other backend routes. For local dev, the `SERVICE_AUTH_TOKEN` bearer token works.

## Service Loaders and Reload Endpoint

Each service has a minimal prompt loader with an in-memory cache and a reload endpoint:

- Loader module: `app/core/prompt_loader.py`
- Reload route: `POST /admin/prompts/reload`

Services implementing reload:
- ai-agent-service
- document-service
- graph-service
- llm-service

## Current Integrations (Phase 1)

- document-service:
  - `keywords_summary.json` used for LLM-assisted keywords + summary in `app/core/enrichment.py`
  - `entity_extraction_full.json` used in PVC pipeline
  - `enrich_facts_entities.json` available for enrichment flows
- graph-service:
  - `fact_extraction.json` and `entity_extraction.json` used by `app/core/graph_processor.py` with table-aware logic
- llm-service:
  - `rag_synthesis.json` for RAG synthesis
  - `content_summarization.json` for card summarization
  - `table_extraction.json` for multimodal table understanding
  - `diagram_understanding.json` for multimodal diagram understanding

All integrations keep resilient inline fallbacks to preserve behavior if templates are missing.

## Frontend: Editing Prompts

Open: Settings → “LLM Prompts” (dedicated page in left nav)

- Lists services that contain prompts
- Shows service-wise prompt table with purpose and description
- Edit opens a modal editor with variables and prompt text
- Validate before save
- Save writes JSON atomically and triggers a best-effort `git add/commit`
- Reload prompts immediately via backend to update service caches

## Variable Substitution

- Templates declare `variables` (e.g., `question`, `context_block`, `focus_type`).
- Callers provide a mapping for these; unknown variables are ignored; missing ones should be handled by the caller.
- Prefer explicit blocks like `{{context_block}}` to keep templates readable.

## Operational Notes

- Saving performs atomic write + best-effort git commit. If git is unavailable, file save still succeeds.
- After saving, the UI calls `POST /api/prompts/{service}/reload` to refresh in-memory caches.

## Future Work

- Expand prompt coverage across more endpoints and services.
- Add richer validation and linting for templates.
- Optional: externalize structured JSON mode schemas in the llm-service enrich endpoint.
