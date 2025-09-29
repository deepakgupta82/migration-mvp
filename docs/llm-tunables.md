# LLM/Input-size Tunables and Defaults

This document summarizes the primary tunables across services, right-sized defaults by document type, and an experiment plan to validate improvements.

## Tunables by Service

- Document-service
  - USE_ENHANCED_WORKFLOW, LAYOUT_JSONL_ENABLED
  - ENABLE_LLM_ANALYSIS, ENABLE_VECTOR_INTEGRATION, ENABLE_GRAPH_INTEGRATION
  - ENABLE_PARALLEL_PROCESSING, MAX_CONCURRENT_INTEGRATIONS
  - Chunking: SEMANTIC_MAX_CHUNK, SEMANTIC_OVERLAP
  - Section enrichment: SECTION_ENRICHMENT_ENABLED, SECTION_TOKEN_BUDGET
  - Websocket: WEBSOCKET_DEDUP_WINDOW_SECONDS
  - Graph shaping hints: document_type, GRAPH_TABLE_CONTENT_MAX_CHARS
- Graph-service
  - GRAPH_BASE_TIMEOUT_SECONDS, GRAPH_MAX_TIMEOUT_SECONDS, GRAPH_MAX_RETRIES
  - LLM extraction cap ≈ 50k chars (service-side), request strict_json
  - GRAPH_MAX_ELEMENTS (cap)
- LLM-service
  - ENFORCE_PROJECT_LLM (true)
  - temperature, max_tokens (defaults ~0.1 and 8000)

## Quick Defaults

Added to `.env`:

- Narrative PDFs
  - SEMANTIC_MAX_CHUNK=4000, SEMANTIC_OVERLAP=350
  - SECTION_ENRICHMENT_ENABLED=true, SECTION_TOKEN_BUDGET=1000
  - GRAPH_BASE_TIMEOUT_SECONDS=120, GRAPH_MAX_TIMEOUT_SECONDS=240, GRAPH_MAX_RETRIES=2
  - GRAPH_NARRATIVE_CAP_CHARS=28000
- Spreadsheets
  - GRAPH_SPREADSHEET_CAP_CHARS=20000
  - TABLE_GRAPH_BATCH_CHARS=12000, TABLE_GRAPH_MAX_ELEMENTS=450
  - GRAPH_TABLE_CONTENT_MAX_CHARS=20000

## Routing Profiles (implemented)

- Automatic doc-type detection: `excel_table` | `narrative` | `ocr_scanned` | `mixed`
- Propagated `doc_type` to vector and graph integrations
- Spreadsheet mode enables batched graph extraction (char and element caps)

## Provider-aware input budgeting

- Effective input caps computed per doc type using env fallbacks:
  - narrative: `GRAPH_NARRATIVE_CAP_CHARS` (default 28k)
  - spreadsheets: `GRAPH_SPREADSHEET_CAP_CHARS` (default 20k)
- Recommendation: fetch model context window and max_tokens from project LLM config to adjust caps dynamically.

## Strong JSON mode

- Graph requests include `strict_json=true` hint. Services should prefer structured JSON outputs; the LLM-service already includes JSON repair fallbacks when needed.

## Agent-ready output metadata

- Vector payload enriched with metadata: project_id, document_id, page_number, element_id, element_type, doc_type.
- Graph payloads carry document_id and document_type hints; post-step facts extraction is triggered best-effort per batch.

## Experiment Plan

- Datasets: narrative PDFs (5–10), spreadsheets (3–5). Include `D4_Asset_list_systems_Unix_v22.xlsx`.
- Sweeps
  - Narrative: SEMANTIC_MAX_CHUNK ∈ {2000, 3500, 4500, 6000}; Graph cap ∈ {20k, 24k, 32k}
  - Spreadsheet: TABLE_GRAPH_BATCH_CHARS ∈ {8k, 12k, 20k}; TABLE_GRAPH_MAX_ELEMENTS ∈ {300, 450, 600}
  - Timeouts: (120/240) vs (150/300)
- Metrics: graph success rate, timeouts, p50/p95 latency, token usage, entities/relationships, cost/doc
- Acceptance: graph success ≥95%; p95 latency within target; +20% recall vs baseline on sample

## Notes

- 1 token ≈ 4 characters. Reserve 4–8k chars buffer for outputs when sizing prompts.
- Keep ENFORCE_PROJECT_LLM=true; ensure project has per-process configs for `entity_extraction` and `table_extraction`.
