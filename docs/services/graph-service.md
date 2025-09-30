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

### Natural Language → Cypher (New)

- POST `/projects/{project_id}/query/nl2cypher`
	- Body: `{ nl: string, limit?: number (default 50) }`
	- Returns: `{ project_id, nl, cypher, parameters }`
	- Builds a safe, read-only, project-scoped Cypher query from natural language. Does not execute the query.
	- Metrics: increments `metrics:{project_id}:nl2c:build_attempts` and on success `...:build_success` in Redis.

- POST `/projects/{project_id}/query/run`
	- Body: `{ cypher: string, limit?: number (default 100) }`
	- Returns: `{ project_id, columns, rows, stats }`
	- Sanitizes Cypher for read-only and project scoping, validates with `EXPLAIN`, then executes and returns rows/columns.
	- Metrics: increments `metrics:{project_id}:nl2c:run_attempts`, on success increments `...:run_success` and computes `...:pass_rate`.

### Project Metrics (New)

- GET `/projects/{project_id}/metrics`
	- Returns a compact health/coverage snapshot:
		- `extraction_yield` (placeholder float, from Redis `metrics:{project_id}:extraction_yield`)
		- `link_coverage` (computed via Neo4j: fraction of Entities with `REFERS_TO` to CanonicalEntity)
		- `nl2cypher_pass_rate` (run_success/run_attempts; also cached in Redis)
		- `schema_conformance` (placeholder float, from Redis `metrics:{project_id}:schema_conformance`)

### Ontology Registry (New)

- GET `http://localhost:8006/api/ontology`
	- Returns the latest ontology payload with metadata. 404 if none saved yet.
- PUT `http://localhost:8006/api/ontology`
	- Body: JSON object with at least `entities: []` and `relationships: []` arrays.
	- Persists a new version on disk and returns `{ version, created_at }`.

Storage:
- Filesystem-backed under `services/graph-service/var/ontology` by default.
- Override with `ONTOLOGY_STORAGE_DIR` env variable when running the service.

Notes:
- Minimal validation only checks presence and types of top-level `entities` and `relationships` arrays.
- Versions auto-increment patch component (0.1.0 → 0.1.1 …) unless an explicit version is provided.

## File Structure

- Templates: `services/graph-service/prompts/*.json`
- Loader: `services/graph-service/app/core/prompt_loader.py`
- Processor: `services/graph-service/app/core/graph_processor.py`

## Table-aware LLM Extraction

When processing spreadsheet or table-like content (e.g., .xlsx, .xls, .csv or structured elements summarized as `TABLE:`), the graph-service augments the LLM prompt with explicit row-aware guidance and requires strict JSON output of the form `{ "entities": [], "relationships": [] }`.

## Maintenance: Project-wide Linking (New)

Endpoint:
- POST `/projects/{project_id}/maintenance/materialize-refers-to`
	- Query params:
		- `min_score` (float, default 0.55): minimum vector similarity threshold
		- `max_candidates` (int, default 5): number of candidates to inspect per entity
		- `preferred_kind` (string, default `entity_cards`): one of `entity_cards|raw_chunks|triple_cards`
		- `use_hybrid` (bool, default true): use hybrid search when available
		- `dry_run` (bool, default false): if true, returns a plan of proposed links without writing

Behavior:
- Enumerates project Entities that don’t already point to a CanonicalEntity via `REFERS_TO`
- Queries the vector-service for candidates using the preferred kind (falls back to `raw_chunks`)
- Picks the best matching CanonicalEntity factoring score and optional type alignment
- MERGEs `(Entity)-[:REFERS_TO {score, provenance}]->(CanonicalEntity)` and ensures `(Project)-[:CONTAINS]` to both nodes
- Returns `{ project_id, created_relationships, details }`

Requirements:
- Vector-service should have cards generated (`/projects/{project_id}/generate-cards`) for best results
- Canonical entities must exist in this project (committed through fusion or other flows)

## Maintenance: Canonical Relationship Materialization (New)

Endpoint:
- POST `/projects/{project_id}/maintenance/materialize-canonical-relationships`
	- Query params:
		- `min_support` (int, default 2): minimum number of entity-level edges to promote a canonical edge
		- `max_pairs` (int, default 1000): cap on canonical pairs to process
		- `allow_types` (string, optional): comma-separated whitelist of relationship types (UPPER_SNAKE_CASE)

Behavior:
- Aggregates `(Entity)-[REL]->(Entity)` edges where both entities are linked via `REFERS_TO` to canonical entities
- MERGEs `(CanonicalEntity)-[REL]->(CanonicalEntity)` with `support` (count of underlying entity edges)
- On create: sets `created_at, project_id, support`; on match: increments `support`, sets `updated_at`

Config defaults:
- GRAPH_REL_MIN_SUPPORT (default 2)
- GRAPH_REL_MAX_PAIRS (default 1000)

Notes:
- This does not create new canonical nodes; it only promotes relationships when canonical nodes/REFERS_TO already exist
- Use `allow_types` to limit to safe curated relationship types if needed

## Maintenance: Project Summary (New)

Endpoint:
- GET `/projects/{project_id}/maintenance/summary`

Returns a compact JSON with:
- `entities_total` and `entities_unlinked` (Entities without REFERS_TO)
- `refers_to_edges` count
- `entity_edge_counts_by_type` and `canonical_edge_counts_by_type` (top 50 by count)

Use this to quickly assess whether you need to run REFERS_TO linking or canonical relationship promotion.

### Configurable defaults for linking

You can control the default behavior via env or central config client keys (graph_service.linking.*):

- GRAPH_LINK_MIN_SCORE (default 0.55)
- GRAPH_LINK_MAX_CANDIDATES (default 5)
- GRAPH_LINK_PREFERRED_KIND (default entity_cards)
- GRAPH_LINK_USE_HYBRID (default true)

These are used when the endpoint parameters are not provided.

### Smoke test helper

Run a quick smoke test without PowerShell quoting issues:

- File: `tools/smoke_materialize_refers_to.py`
- Example:
	- Set AUTH_TOKEN=service-backend-token
	- python tools/smoke_materialize_refers_to.py --project <project_id> [--dry-run 1]

To promote canonical relationships:

- File: `tools/smoke_materialize_canonical_relationships.py`
- Example:
	- Set AUTH_TOKEN=service-backend-token
	- python tools/smoke_materialize_canonical_relationships.py --project <project_id> --min-support 2 --max-pairs 1000 [--allow-types HOSTS,CONNECTS_TO] [--dry-run 1]

## Orchestrated Maintenance: Run Phases (New)

Endpoint:
- POST `/projects/{project_id}/maintenance/run-phases`
	- Query params:
		- `dry_run` (bool, default false): plan-only mode; performs no writes
		- `min_score`, `max_candidates`, `preferred_kind`, `use_hybrid`: forwarded to REFERS_TO linking
		- `min_support`, `max_pairs`, `allow_types`: forwarded to canonical relationship materialization

Behavior:
- Executes two steps sequentially with a shared correlation id (if header `X-Correlation-ID` is provided):
	1) Materialize REFERS_TO links from Entities to CanonicalEntity
	2) Promote canonical relationships by aggregating entity-level edges
- Returns a combined JSON payload with results from both steps.

Example:
- POST `http://localhost:8006/projects/{project_id}/maintenance/run-phases?dry_run=1&min_score=0.6&min_support=2`

### Maintenance History (New)

- GET `/projects/{project_id}/maintenance/history?limit=20`
	- Returns recent maintenance runs (both dry-run plans and applied runs). Backed by Redis list `graph:maint:history:{project_id}`; keeps last 200 entries.

Payload shape (example):
```
{
	"project_id": "...",
	"ts": "2025-09-30T12:34:56.789Z",
	"action": "run-phases|materialize-refers-to|materialize-canonical-relationships",
	"dry_run": true,
	"params": { /* request params */ },
	"summary": { /* step results */ }
}
```

## Explorer and Retrieval (New)

- GET `/projects/{project_id}/explorer/overview`
	- Returns entity/relationship counts and top types. Requires env `GRAPH_EXPLORER_ENABLED=1`.

- GET `/projects/{project_id}/canonical/centrality`
	- Returns simple degree centrality metrics for canonical entities. Useful for ranking/diagnostics.

- GET `/projects/{project_id}/search/fuse`
	- Parameters: `q`, `kinds=entity_cards,raw_chunks`, `k=10`, `use_hybrid=true`, `boost_centrality=false`
	- Performs RRF fusion across the requested vector kinds; optional small centrality-based boost.
	- Supports per-kind weighting via `weights=entity_cards:1.0,raw_chunks:0.8` and tuning via `centrality_scale` and `normalized_centrality`.

### UI Wiring (New)

- Project Detail → Graph → Explorer tab includes:
  - Overview metrics and a compact "Top Central Canonical Entities" widget that calls `GET /projects/{id}/canonical/centrality`.
  - Fused Search form with a toggle to enable the `boost_centrality` parameter for `GET /projects/{id}/search/fuse`.
	- Project Metrics card showing `link_coverage`, `nl2cypher_pass_rate`, and placeholders for `extraction_yield` and `schema_conformance` via `GET /projects/{id}/metrics`.
- Project Detail → Graph → Centrality tab shows a sortable table of canonical entities by degree, backed by `GET /projects/{id}/canonical/centrality`.

### UI Polish (Phase 9)

- Centrality view: client-side sorting by columns (Name, Total/Out/In Degree) and basic pagination controls.
- Explorer view: fused search results now include an expandable "Show details" section per result listing per-source rank and score; maintenance history includes simple pagination controls.

## CLI Helper (Phase 8)

- File: `tools/run_phases.py`
	- Invokes `POST /projects/{project_id}/maintenance/run-phases` with appropriate headers.
	- Options: `--dry-run` or `--apply`, score/support params, `--admin` (adds `X-User-Role: admin`), and `--corr` for `X-Correlation-ID`.
	- Environment: `AUTH_TOKEN` (default `service-backend-token`).

Examples:

```
# Windows PowerShell
$env:AUTH_TOKEN = 'service-backend-token'
python tools/run_phases.py --project <project-id> --dry-run
python tools/run_phases.py --project <project-id> --apply --min-score 0.6 --min-support 2 --admin
```

## Ranking Helpers and Tests (Phase 8)

- Helpers: `common/ranking.py`
	- `compute_rrf_fusion(per_kind_results, weights=None, rrf_k=60.0)`
	- `apply_centrality_boost(items, degree_map, scale=0.05, normalized=True)`
- Tests: `tests/test_ranking.py` validates RRF weighting effects and centrality scaling/normalization.

## Minimal RBAC Header Enforcement

To reduce cross-project mistakes in shared environments, certain maintenance endpoints enforce a project header when enabled via env:

- Set `GRAPH_ENFORCE_PROJECT_HEADER=1`
- Provide header `X-Project-Id: <project_id>` matching the URL path

Currently enforced on:
- POST `/projects/{project_id}/maintenance/materialize-refers-to`
- POST `/projects/{project_id}/maintenance/materialize-canonical-relationships`
- POST `/projects/{project_id}/maintenance/run-phases`

If the header is missing or mismatched, the service returns 403.

### Optional Admin Role & Throttling (New)

- Admin role enforcement (for non-dry runs only):
	- Set `GRAPH_ENFORCE_ADMIN_ROLE=1` to require header `X-User-Role: admin` for write operations
	- Affects: run-phases (apply), materialize-refers-to (apply), materialize-canonical-relationships (apply)
- Per-project throttle (for non-dry runs only):
	- Set `GRAPH_WRITE_THROTTLE_SECONDS=60` to prevent repeated apply runs within 60 seconds per project

## CORS Configuration (Updated)

- Defaults are read from config client key `backend.cors_origins` or fallback to `http://localhost:3000` and `http://localhost:8000`.
- You can override at runtime via environment variable:
	- `GRAPH_CORS_ORIGINS="http://localhost:3000,http://localhost:5173,http://localhost:8000"`
	- Values are comma-separated; whitespace is trimmed.