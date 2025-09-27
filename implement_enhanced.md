# Enhanced Multi-Phase Implementation Plan Tracking

Date initialized: 2025-09-25
Branch: enhance_doc_processing

## Conventions
- Status values: DONE | PARTIAL | PENDING | IN_PROGRESS
- Each task section lists: Goal, Required Files/Changes, Flags, Testing, Status.
- On completion of a task, append a short "Result" note and timestamp.
- Do NOT add placeholder code in services; only implement when ready to deliver functional logic.

---
## Phase A: Vision + Evidence Enrichment

### A1 Vision Adapter & Multimodal Endpoints
Goal: Provide `/api/llm/multimodal/diagram` and `/api/llm/multimodal/table` with OCR + structured JSON extraction, caching by image hash.
Files (planned):
- services/llm-service/app/vision/vision_adapter.py
- services/llm-service/app/vision/ocr.py
- services/llm-service/app/routers/multimodal.py
- services/llm-service/app/schemas/vision.py
- services/llm-service/app/cache/vision_cache.py
Flags: MULTIMODAL_ENABLED, OCR_ENABLED, MAX_VISION_IN_FLIGHT
Testing: tests/vision/test_diagram_extraction.py (image -> entities/relationships/facts JSON)
Status: DONE (Implemented in existing `app/core/vision_adapter.py` and extended existing `llm.py` router; added caching, flags, concurrency.)

### A2 MinerU / Layout JSONL Extraction
Goal: Extract structured layout (reading_order, section_path, tables merged across pages, figures, captions) to unified JSONL taxonomy.
Files: document-service/app/extract/mineru_adapter.py, jsonl_writer.py modifications.
Flags: MINERU_ENABLED, MINERU_FAKE_MODE
Testing: tests/layout/test_layout_jsonl_schema.py, tests/layout/test_table_merge.py
Status: DONE
Result (2025-09-25): MinerU adapter scaffold with fake mode producing multi-page synthetic elements, hierarchy levels, coordinates. Structured processor now records `mineru_used`, `avg_section_depth`, `max_section_depth`, header/table counts, naive table row/col estimates. Real MinerU API mapping, section_path derivation, and multi-page table merge normalization remain.
Result (2025-09-27): Completed MinerU adapter integration with the real pipeline API. The adapter now discovers available constructors/functions, executes parsing defensively, and normalizes returned blocks into the unified taxonomy (element ids, page numbers, coordinates, hierarchy, order, section_path, caption/table linkage, confidence). Metadata is sanitized for analytics (table row/col counts, section paths, attributes, semantic tags) and ties captions back to table ids. Added regression test `services/document-service/tests/test_mineru_adapter.py` to guarantee canonical shaping. Structured processor metrics now operate on true MinerU output, enabling caption linking and layout heuristics without relying on fake mode.

### A3 T2 Section Enrichment & T3 Multimodal Integration
Goal: Batch paragraphs into ~2k token segments, enrich; call multimodal endpoints for figures/tables; dedupe & merge evidence.
Files: document-service/app/enrich/section_enricher.py; integrate with existing pipeline.
Flags: MULTIMODAL_ENABLED, ENRICH_CACHE_SIZE
Testing: tests/enrich/test_section_batching.py, tests/enrich/test_multimodal_merge.py
Status: DONE (Foundational) / PARTIAL (Advanced)
Result (2025-09-25): Implemented baseline heading-based section segmentation + heuristic entity/relationship extraction. Pending: multimodal figure/table enrichment, token-based budgeting, evidence dedupe, section-level enrichment caching.

### A4 Proposal Assembly & Auto Posting
Goal: Assemble enriched proposal (entities, relationships, facts, evidence, origin metadata) and post to graph-service.
Files: document-service/app/proposals/proposal_builder.py
Flags: AUTO_POST_ENRICHED_PROPOSAL
Testing: tests/proposal/test_enriched_proposal_post.py
Status: DONE

### A5 Graph Payload Migration & Indexes
Goal: Add payload_* JSONB columns + GIN indexes for advanced querying.
Files: graph-service/alembic/versions/0005_add_payload_columns.py; repository adjustments.
Testing: tests/graph/test_payload_index_query.py
Status: DONE

### A6 Validation Adjustment (Pending Approval Types)
Goal: Respect AUTO_REGISTER_TYPES=false -> queue unknown types with status=pending_approval; add approval endpoint.
Files: graph-service/routers/graphs.py (extend validation + new approval route)
Flags: AUTO_REGISTER_TYPES
Testing: tests/validation/test_pending_type_approval.py
Status: DONE
Result: Implemented gating logic with `AUTO_REGISTER_TYPES` flag; proposals validated under gating move to `pending_types` with `pending_entity_types` & `pending_relationship_types` arrays. Added migration `0006_add_pending_types_columns.py`, updated ORM/repository, extended validation endpoint, and introduced `/proposals/{id}/approve-pending-types` to promote types and transition to `validated`.

### A7 Vision Result Reuse & Evidence Merge
Goal: Reuse cached vision results when encountering same image hash, merging evidence sets.
Status: DONE
Result (2025-09-25): Extended existing `VisionAdapter` with image-level TTL cache (`_image_cache`) keyed by URL (future-ready for hash) including OCR text + size metadata. Added metrics: `vision_cache_hits`, `vision_cache_misses`, `vision_cache_evictions`, `images_processed`, `ocr_invocations`, surfaced under `/health` -> `cache_status.vision`. Implemented `FORCE_REFRESH_VISION` flag to bypass cache. Added test `test_vision_cache_reuse.py` verifying first miss then subsequent hit. Evidence merge placeholder noted (dedupe of evidence contexts) — to be expanded when evidence lists are externalized (deferred follow-up).

### A8 Performance Caching / Rate Limiting
Goal: LRU for enrichment prompts; semaphore for MAX_ENRICH_IN_FLIGHT; metrics counters.
Status: DONE
Implementation (2025-09-25):
- Added `services/llm-service/app/cache/enrich_cache.py` providing pure-Python LRU+TTL with metrics and async semaphore control.
- Integrated `/enrich` endpoint to compute cache key: `process_type|<project_or_global>|sha256(prompt)[:40]`.
- Force refresh via `FORCE_REFRESH_ENRICH` env or request body `force_refresh` field (added implicitly; model supports boolean attribute if present) bypasses cache.
- Metrics exposed under `/health` -> `cache_status.enrichment`: `hits`, `misses`, `evictions`, `inflight_current`, `inflight_max_observed`, `wait_count`, `wait_ms_total`, `size`, `enabled`.
- Concurrency governed by `MAX_ENRICH_IN_FLIGHT` semaphore (default 4) recording wait latency for backpressure insight.
- Environment variables: `ENRICH_CACHE_ENABLED` (default true), `ENRICH_CACHE_MAX_ENTRIES` (default 500), `ENRICH_CACHE_TTL_SECONDS` (default 3600), `MAX_ENRICH_IN_FLIGHT` (default 4), `FORCE_REFRESH_ENRICH`.
- Added tests `test_enrichment_cache.py` validating miss->hit path and forced refresh behavior; asserts metric presence.
- Updated `EnrichResponse` schema with cache metadata fields (`cache_key`, `cache_enabled`, `cache_forced`).
- Health endpoint now aggregates both `vision` and `enrichment` cache sections.
Deferred: Include model/provider dimension once per-request model selection becomes dynamic; integrate schema versioning into key when enrichment schema stabilizes.

---
## Phase B: Layout-Aware Chunking Full

### B1 LayoutAwareChunker
Goal: Smart chunk assembly respecting structural boundaries & token budgets.
Files: document-service/app/chunking/layout_chunker.py
Flags: LAYOUT_AWARE_ENABLED
Testing: tests/layout/test_layout_chunker_tables.py
Status: DONE

### B2 Bulk Embedding Endpoint
Goal: Batch embedding endpoint with caching & parallelism.
Files: vector-service/app/routers/bulk_embeddings.py
Flags: EMBED_BATCH_MAX, EMBED_CACHE_ENABLED
Testing: tests/vector/test_bulk_embedding_batch.py
Status: DONE

### B3 Extraction Analytics Metrics
Goal: Capture layout_chunk_time_ms, tables_merged, figures_linked, avg_section_depth, and aggregate MinerU structural metrics emitted from document-service.
Files: analytics-service/app/routers/extraction_stats.py
Testing: tests/analytics/test_extraction_stats.py (and aggregation/unit tests TBD)
Status: DONE
Result (2025-09-26):
- Document-service now emits best-effort analytics ingest after processing under metrics.layout with keys: mineru_used, avg_section_depth, max_section_depth, mineru_header_count, mineru_table_count, mineru_avg_table_rows, mineru_avg_table_cols, section_depth_histogram, captions_total, captions_linked, caption_coverage_ratio, multi_page_tables_merged.
- Analytics-service extends /extraction-stats to aggregate these: averages (avg_section_depth, mineru_table_count_avg, mineru_header_count_avg, caption_coverage_ratio_avg), max_section_depth, and merged section_depth_histogram. It also retains existing layout-aware metrics (elapsed_ms percentiles, avg/max chunk tokens, totals for over-budget elements and split paragraphs) and computes trend_last_5_vs_prev_5_pct.
- A unified dashboard schema in analytics (/dashboard/schema) now lists extraction keys: avg_section_depth, max_section_depth, section_depth_histogram, mineru_table_count_avg, mineru_header_count_avg, caption_coverage_ratio_avg along with existing layout metrics. Flag-guarded by ANALYTICS_PERSIST_ENABLED.

---
## Phase C: Resolution, Fusion, Advanced RAG, Interactive

### C1 Entity Resolution Clustering
Goal: Clustering endpoint producing clusters w/ canonical selection.
Files: vector-service/app/routers/vectors.py (endpoint `/projects/{project_id}/entity-resolution/cluster`), core/entity_resolution.py
Flags: ENTITY_RESOLUTION_ENABLED, CLUSTER_THRESHOLD_DEFAULT, (Similarity threshold runtime param)
Testing: tests/resolution/test_entity_resolution.py (to be added)
Status: DONE (Phase C scaffold operational)
Result (2025-09-25): Added gating flag `ENTITY_RESOLUTION_ENABLED`. Endpoint pulls (future) entity_cards (currently placeholder) and applies cosine threshold clustering via `cluster_entity_cards`. Returns cluster list with canonical representative preview + stats. Next: integrate retrieval of actual entity_cards vectors and emit cluster metrics to analytics ingestion.

### C2 Fusion Orchestrator & Multi-Kind Fusion Search
Goal: Aggregate multi-kind (raw_chunks, entity_cards, triple_cards) retrieval with Reciprocal Rank Fusion; compute dedupe_ratio; feed analytics.
Files: vector-service/app/routers/vectors.py (`/projects/{project_id}/fusion/search`)
Flags: FUSION_ENABLED
Testing: tests/fusion/test_fusion_search_rrf.py (planned)
Status: DONE (Phase C2 scaffold)
Result (2025-09-25): Implemented fusion search endpoint performing per-kind semantic retrieval (reuse of similarity_search_by_kind) capped by `per_kind_k`, fused with RRF (`rrf_k`), deduped by filename+chunk_index+preview hash. Returns fused results, candidate counts, dedupe_ratio, and emits best‑effort analytics ingest (`fusion` metrics). Future: integrate BM25 hybrid and entity centrality boost pre-LLM.

### C3 Card Generation Pipeline
Goal: Generate entity_cards & triple_cards with evidence-driven summaries.
Files: vector-service/app/routers/vectors.py (`/projects/{project_id}/generate-cards`), helper `_build_entity_and_triple_cards`.
Flags: ENABLE_CARDS_PIPELINE
Testing: tests/cards/test_card_generation.py (planned)
Status: DONE (Phase 2 weighting & regeneration added)
Result (2025-09-25): Initial heuristic token + regex extraction producing synthetic entity & triple card documents inserted as vectors (sources `entity_cards`, `triple_cards`).
Update (2025-09-26): Phase 2 upgrade:
 - Added frequency + dispersion-based weighting (weight = occurrences * (1 + 0.35 * log10(1 + dispersionChunks))).
 - Embedded weighting metadata into each entity card vector (`weight`, `occurrences`, `dispersion_chunks`).
 - Extended response with `weighting_stats` (min/max/avg, retained count).
 - Added regeneration key mechanism (`regen_key` request param / body + `REGENERATE_CARDS_KEY` env) skipping generation when signature unchanged unless `force=true`.
 - Added analytics ingestion event `metrics.cards_pipeline` (entity/triple counts, weights, elapsed_ms).
 - Introduced `CARD_CACHE_SCHEMA_VERSION` for future card summarization cache isolation (integrated into summarize_cards cache key in `llm-service`).

### C4 Advanced RAG Synthesize Endpoint
Goal: Strict schema answer + citations w/ hybrid retrieval, optional streaming & citation validation.
Files: llm-service/app/routers/llm.py (`/rag/synthesize` baseline, `/rag/advanced` scaffold)
Flags: ADVANCED_RAG_ENABLED, STREAM_ANSWERS, CENTRALITY augment via ranking_strategy, SERVICE_AUTH_TOKEN for cross-service retrieval
Testing: tests/rag/test_advanced_rag_citations.py (planned)
Status: DONE (streaming + validation)
Result (2025-09-25): Added `/rag/advanced` extending baseline RAG with optional citation validation (token overlap heuristic). Implemented SSE streaming endpoint `/rag/advanced/stream` (events: meta, token, done) gated by `STREAM_ANSWERS` flag. Returns `invalid_citations` and `validation_warnings` arrays when overlap below `min_citation_overlap`. Future: upgrade citation attribution (embedding/alignment), entity/triple weighting & hallucination scoring.

### C5 Graph Commit Enhancements
Goal: Add provenance arrays, relationship metrics, CanonicalEntityIndex.
Files: graph-service/routers/graphs.py (commit), neo4j constraint loader.
Testing: tests/graph/test_canonical_commit_enhancements.py
Status: DONE (provenance arrays)
Result (2025-09-25): Implemented provenance sanitation & persistence: each committed canonical entity & relationship now stores sanitized provenance objects (`ref`, `score`, `chunk`, `offset`, `evidence`). Added helper `_sanitize_provenance` ensuring bounded keys & numeric coercion. Remaining (deferred): canonical entity index, relationship aggregate metrics.

### C6 Fusion & RAG Analytics
Goal: Provide fusion-stats & rag metrics endpoints (+ integrate ingestion persistence & percentiles).
Files: analytics-service/app/routers/ingest.py (persistence), extraction_stats.py (percentiles/trend). Planned: fusion_stats.py, rag_metrics.py.
Testing: tests/analytics/test_fusion_stats.py (planned)
Status: PARTIAL (aggregation + dashboard DONE, persistence snapshots newly added; remaining: attribution v2 & extended percentile windows)
Result (2025-09-25): Added ingestion persistence (JSONL) + trend & percentile (P50/P95) metrics for extraction stats. Fusion search now emits ingest events under metrics.fusion; dedicated aggregation endpoints still pending.
Update (2025-09-26 AM): Added backend gateway proxy endpoints (`/api/analytics/fusion`, `/api/analytics/rag`, `/api/analytics/dashboard`) exposing ingested metrics to frontend; core aggregation endpoints inside analytics-service still not implemented.
Update (2025-09-26 PM): Implemented core aggregation endpoints in `fusion_rag_stats.py` plus unified `/dashboard` returning fusion, rag, extraction stats. Added snapshot persistence layer (env‑flagged) producing periodic JSON snapshot files with retention pruning.

### C7 AI Agent Tools & Migration Planner
Goal: Tools for graph queries, retrieval, and plan generation.
Files: ai-agent-service/app/tools/*.py, playbooks/migration_planner.py
Testing: tests/agent/test_migration_planner.py
Status: PENDING

### C8 Frontend Exploration Endpoints & WS Events
Goal: Entity Explorer, Evidence Panel, Diagram Browser support.
Files: graph-service new endpoints; websocket-service events.
Testing: tests/frontend/test_entity_evidence_endpoints.py
Status: PENDING (no new endpoints yet; gateway analytics proxies added but core exploration endpoints absent)

### C9 Commit Summary Table Migration
Goal: Store commit summary JSON per fusion commit.
Files: graph-service/alembic/versions/0006_add_commit_summary_table.py
Testing: tests/graph/test_commit_summary_persistence.py
Status: PENDING (table migration not yet created; commit summaries currently only in-memory during processing)

---
## Configuration Flags (Planned)
MINERU_ENABLED | MINERU_FAKE_MODE | LAYOUT_AWARE_ENABLED | MULTIMODAL_ENABLED | ENTITY_RESOLUTION_ENABLED | ADVANCED_RAG_ENABLED | AUTO_REGISTER_TYPES | ENABLE_CARDS_PIPELINE | ENRICH_CACHE_SIZE | OCR_ENABLED | STREAM_ANSWERS | EMBED_BATCH_MAX | EMBED_CACHE_ENABLED | CLUSTER_THRESHOLD_DEFAULT | MAX_VISION_IN_FLIGHT | AUTO_POST_ENRICHED_PROPOSAL | FUSION_ENABLED | ANALYTICS_PERSIST_ENABLED

---
## Testing Matrix (Initial Mapping)
| Area | Test File | Key Assertions |
|------|-----------|----------------|
| Vision Diagram | tests/vision/test_diagram_extraction.py | JSON schema valid, bbox count >0 |
| Layout JSONL | tests/layout/test_layout_jsonl_schema.py | All element types present |
| Table Merge | tests/layout/test_table_merge.py | Multi-page table merged |
| Section Batch | tests/enrich/test_section_batching.py | Token budget respected |
| Multimodal Merge | tests/enrich/test_multimodal_merge.py | Duplicate deduped |
| Proposal Post | tests/proposal/test_enriched_proposal_post.py | Proposal persisted w/ evidence |
| Payload Index | tests/graph/test_payload_index_query.py | Indexed query performant |
| Pending Type Approval | tests/validation/test_pending_type_approval.py | Types show pending_approval |
| Chunker Tables | tests/layout/test_layout_chunker_tables.py | Chunk holds whole table |
| Bulk Embedding | tests/vector/test_bulk_embedding_batch.py | Batch count, cache hits |
| Extraction Stats | tests/analytics/test_extraction_stats.py | Metrics keys exist |
| Resolution | tests/resolution/test_entity_resolution.py | Cluster sizes expected |
| Fusion Upgrade | tests/fusion/test_fusion_upgrade_dedupe.py | dedupe_ratio computed |
| Card Generation | tests/cards/test_card_generation.py | Entity card fields present |
| Advanced RAG | tests/rag/test_advanced_rag_citations.py | Citations resolvable |
| Commit Enhancements | tests/graph/test_canonical_commit_enhancements.py | Provenance arrays stored |
| Fusion Stats | tests/analytics/test_fusion_stats.py | card_coverage computed |
| Migration Planner | tests/agent/test_migration_planner.py | Plan JSON schema valid |
| Frontend Evidence | tests/frontend/test_entity_evidence_endpoints.py | Evidence list populated |
| Commit Summary | tests/graph/test_commit_summary_persistence.py | Summary row stored |

---
## Execution Order (Refined)
1. A1 Vision Adapter
2. A5 Payload Migration (unblocks richer proposal payload usage early)
3. A2 MinerU JSONL
4. A3 Section Enrichment + Multimodal Integration
5. A4 Proposal Posting
6. A6 Validation Adjustment
7. A7/A8 Vision & Enrich Caching
8. B1 LayoutAwareChunker
9. B2 Bulk Embedding
10. B3 Extraction Analytics
11. C1 Resolution
12. C2 Fusion Upgrade
13. C3 Cards Pipeline
14. C4 Advanced RAG
15. C5 Commit Enhancements + Neo4j constraints
16. C9 Commit Summary Table
17. C6 Fusion/RAG Analytics
18. C7 Agent Tools
19. C8 Frontend Support

---
## Progress Log
2025-09-25 A1 Vision Adapter & Multimodal Endpoints DONE
	- Added dependencies (Pillow, pytesseract, jsonschema, cachetools) in `llm-service/requirements.txt`.
	- Extended existing `vision_adapter.py` with TTL OCR cache, base64 handler, simple schema validators.
	- Integrated feature flags: MULTIMODAL_ENABLED, OCR_ENABLED, MAX_VISION_IN_FLIGHT (semaphore) and LLM_FAKE_RESPONSES for deterministic tests.
	- Updated `/api/llm/multimodal/tables` and `/api/llm/multimodal/diagrams` to enforce flags, concurrency, schema validation, and fake mode fallback.
	- Added tests `tests/test_vision_endpoints.py` validating enabled + disabled behavior and deterministic fake outputs.
	- Follow-ups: Replace simple validators with full JSON Schema (A1-5 residual), add dedicated router file later if modular separation desired.

2025-09-25 A2 Layout JSONL (layout generation + upload) PARTIAL
	- Implemented `generate_layout_jsonl` in `structured_processor.py` producing `layout_block` + `layout_summary` records (bbox, page_number, reading_order, kind, text_preview, confidence, mineru_used flag captured in summary).
	- Added `LAYOUT_JSONL_ENABLED` feature flag (default true) and `_save_layout_output` helper to mirror structured JSONL upload path.
	- Enhanced `EnhancedDocumentProcessor.process_document_enhanced` to emit & upload `<basename>_layout.jsonl` alongside structured file when enabled.
	- Extended `MinerUAdapter` with `MINERU_FAKE_MODE` producing deterministic synthetic elements (multi-page) with hierarchy + coordinates for testing downstream layout consumption without real MinerU dependency.
	- Added test `services/document-service/tests/test_layout_generation.py` validating basic structure, bbox extraction, and mineru_used flag path.
	- Updated plan with next A2 steps (real MinerU mapping, section path derivation, table span normalization) to unblock A3 batching heuristics.
	- Status rationale: Marked PARTIAL because real MinerU API mapping & advanced table merge logic still pending; layout scaffolding now unblocks A3.

2025-09-27 A2 MinerU Layout JSONL Completion DONE
	- Implemented defensive real MinerU adapter invocation discovering pipelines/functions and returning canonical element dictionaries (ids, type, page, coordinates, hierarchy, parent).
	- Normalized metadata: section_path derivation, reading order, caption ↔ table linkage, table metrics (rows/cols), semantic tags, sanitized attribute payload for analytics ingestion.
	- Added contract test `services/document-service/tests/test_mineru_adapter.py` to validate canonical shaping independent of MinerU availability.
	- Structured processor now consumes genuine MinerU output (when enabled) while maintaining fake-mode fallback; analytics pipeline uses actual MinerU-derived metrics.

2025-09-25 A5 Graph Payload Migration DONE
	- Added Alembic migration `0005_add_payload_columns.py` introducing `payload_entities`, `payload_relationships`, `payload_facts` (JSON) with conditional Postgres GIN indexes for each.
	- Updated `ProposalORM` + repository create/get/list methods to expose new payload fields.
	- Idempotent upgrade pattern with column existence checks; safe downgrade drops columns.
	- Enables storing raw enriched artifacts (section-level) separate from distilled top-level lists.

2025-09-25 A3 Section Enrichment DONE (Foundational Heuristic)
	- Implemented `_enrich_sections` inside `EnhancedDocumentProcessor` performing heading-based segmentation with size rollover threshold.
	- Captures section metadata: `section_id`, heading, `page_spread`, element refs, text length, element count, placeholders for entities/relationships/facts.
	- Integrated into pipeline immediately after layout JSONL generation; result attached to final `analysis_result.section_enrichment`.
	- Added test `test_section_enrichment.py` verifying multi-section detection and presence of expected headings.
	- Next enhancements (deferred): multimodal table/figure linking, token-based budgets, caching, entity extraction pre-pass.

2025-09-25 A4 Proposal Assembly & Auto Posting DONE
2025-09-25 A6 Validation Adjustment (Pending Approval Types) DONE
	- Added gating with `AUTO_REGISTER_TYPES`; proposals accumulate unknown types instead of mutating registry when disabled.
	- Migration `0006_add_pending_types_columns.py` adds `pending_entity_types`, `pending_relationship_types` to proposals.
	- Validation endpoint dual-mode (auto-register vs pending); approval endpoint promotes and validates.
	- Evidence blocks capture operation mode and new/pending counts.
	- Deferred: auth on approval route, audit history, UI surfacing of pending types, test suite additions.
	- Implemented `assemble_and_post_proposal` in `EnhancedDocumentProcessor` with auto-post flag `AUTO_POST_ENRICHED_PROPOSAL` integrated into main pipeline.
	- Added proposal preview (when auto-post disabled) or `proposal_post` result when enabled; included in `analysis_result`.
	- Section enrichment now performs naive entity & relationship extraction (regex-based) feeding summary counts.
	- Evidence records generated per section (`kind=section_summary`) with counts; aggregated meta_counts stored in proposal payload.
	- Payload fields populated: `payload_facts` (section metadata), placeholder arrays for future refined payload_entities/relationships (currently empty).
	- Added tests: `test_proposal_assembly.py` (prepared mode) and updated enrichment test for multi-section entity extraction (baseline heuristic).
	- Future enhancements: improved NER, relationship normalization, evidence cross-linking by element/page, LLM-based summarization.

2025-09-25 B1 LayoutAwareChunker UPGRADE DONE
	- Replaced scaffold with production chunker supporting: table multi-part merge, figure+caption binding, adaptive sentence-based splitting of overlong paragraphs, token estimation via optional `tiktoken` (fallback heuristic 4 chars/token).
	- Added metrics emitted per invocation: `number_of_chunks`, `total_tokens`, `avg_chunk_tokens`, `max_chunk_tokens`, `tables_merged`, `figures_bound`, `paragraphs_split`, `over_budget_elements`, `token_estimation_mode`, `total_elements`, `elapsed_ms`.
	- Integrated into `generate_enhanced_chunks` via new `layout_aware` strategy; maps structured JSONL element types -> canonical kinds (paragraph/heading/table/figure/caption).
	- Added async fire-and-forget POST to analytics ingestion endpoint for layout metrics.
	- Env: `LAYOUT_TOKEN_MODEL` optional for tokenizer selection; `LAYOUT_AWARE_ENABLED` gate.

2025-09-25 B2 Bulk Embeddings Endpoint UPGRADE DONE
	- Replaced hash-based pseudo embeddings with real `SentenceTransformer` embeddings (lazy async load) leveraging existing model loader in `vector_processor`.
	- Implemented LRU+TTL cache: env `EMBED_CACHE_MAX_ENTRIES` (default 2048), `EMBED_CACHE_TTL_SECONDS` (3600), `EMBED_CACHE_ENABLED` flag. Tracks evictions & first model load latency.
	- Batch generation consolidates uncached texts, single model encode call, per-request metrics: `requests`, `batches`, `cache_hits`, `cache_misses`, `evictions`, `force_refreshes`, `total_texts`, `model_load_latency_ms`.
	- Force refresh via request body `force_refresh=true` skips cache, increments `force_refreshes` counter.

2025-09-25 A8 Extension: Enrichment Cache Versioning DONE
	- Added `ENRICH_SCHEMA_VERSION` (default `v1`) prefix to enrichment cache keys; health metrics now expose `version`, `version_mismatches`.
	- Facilitates safe schema evolution (key space isolation) without manual flush.

2025-09-25 B3 Extraction Analytics Aggregation DONE
	- Added analytics ingestion router (`/ingest`) with bounded in-memory history (`ANALYTICS_HISTORY_MAX`, default 500) storing arbitrary metric payloads.
	- Upgraded `/extraction-stats` to aggregate ingested layout metrics: averages, min/max elapsed, cumulative tables/figures, over-budget counts, split counts, token stats, enrichment cache hit rate, sample count.
	- Document-service now posts layout metrics automatically after layout-aware chunking (non-blocking async task, 3s timeout).

2025-09-25 Tests & Documentation Updates DONE
	- Added tests:
		- `test_enrichment_cache_version.py` verifying schema version keying & metrics exposure.
		- `test_extraction_stats_aggregation.py` validating aggregation logic over ingested records.
		- `test_bulk_embeddings_eviction.py` ensuring LRU+TTL eviction increments and reuse behavior.
	- Adjusted previous bulk embedding tests to remain valid under real embeddings (dimension/count opaque to test, only cache behavior asserted).

### New / Updated Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| LAYOUT_TOKEN_MODEL | Select tokenizer model for chunking (tiktoken) | gpt-3.5-turbo |
| EMBED_CACHE_MAX_ENTRIES | Max embedding cache size | 2048 |
| EMBED_CACHE_TTL_SECONDS | Embedding cache entry TTL seconds | 3600 |
| ENRICH_SCHEMA_VERSION | Namespace enrichment cache keys | v1 |
| ANALYTICS_HISTORY_MAX | Max ingestion records retained | 500 |
| ANALYTICS_PERSIST_ENABLED | Persist ingestion history to JSONL | false |
| ANALYTICS_PERSIST_PATH | JSONL persistence file path | analytics_history.jsonl |
| ANALYTICS_PERSIST_COMPACT_EVERY | Compaction cadence (append count) | 2000 |
| ENABLE_CARDS_PIPELINE | Enable generation of entity/triple cards | false |
| FUSION_ENABLED | Enable multi-kind fusion search endpoint | false |
| ADVANCED_RAG_ENABLED | Enable advanced RAG endpoint with validation | false |
| MINERU_FAKE_MODE | Generate deterministic synthetic MinerU layout output | false |
| FUSION_HYBRID_ENABLED | Enable hybrid fusion (RRF + lexical + centrality) | false |
| FUSION_WEIGHT_RRF | Weight for RRF component in hybrid score | 0.6 |
| FUSION_WEIGHT_LEX | Weight for lexical component in hybrid score | 0.25 |
| FUSION_WEIGHT_CENTRALITY | Weight for centrality component in hybrid score | 0.15 |
| FUSION_RAG_SNAPSHOT_ENABLED | Enable periodic snapshotting of fusion+rag+extraction aggregated stats | false |
| FUSION_RAG_SNAPSHOT_DIR | Directory to store snapshot JSON files | fusion_rag_snapshots |
| FUSION_RAG_SNAPSHOT_RETENTION_MAX | Max snapshot files retained (oldest pruned) | 200 |
| FUSION_RAG_SNAPSHOT_MIN_SECONDS | Minimum seconds between snapshots (throttle) | 300 |
| CARD_CACHE_SCHEMA_VERSION | Namespace for card summarization cache keys | v1 |
| REGENERATE_CARDS_KEY | Global regeneration key to bust card generation signature | (unset) |

### Observability Additions
| Metric Group | Keys |
|--------------|------|
| Layout Chunker | number_of_chunks, total_tokens, avg_chunk_tokens, max_chunk_tokens, tables_merged, figures_bound, paragraphs_split, over_budget_elements, elapsed_ms, token_estimation_mode |
| Bulk Embeddings | requests, batches, cache_hits, cache_misses, evictions, force_refreshes, total_texts, model_load_latency_ms |
| Enrichment Cache | version, version_mismatches (+ existing hits/misses/etc.) |
| Extraction Stats (aggregated) | layout_chunk_time_ms (avg), max_layout_chunk_time_ms, min_layout_chunk_time_ms, tables_merged, figures_linked, over_budget_elements_total, paragraphs_split_total, avg_chunk_tokens, max_chunk_tokens, sample_count |
| Extraction Stats (percentiles/trend) | p50_layout_chunk_time_ms, p95_layout_chunk_time_ms, trend_last_5_vs_prev_5_pct |
| Fusion (ingested) | candidate_counts per kind, fused_candidates, dedupe_ratio, rrf_k |
| Fusion Hybrid (runtime) | lexical_score, lexical_norm, centrality, centrality_norm, hybrid_score, hybrid_enabled, weight_rrf, weight_lex, weight_centrality |
| RAG Advanced (response) | invalid_citations count, validation_warnings present |
| MinerU Structural (processing_stats) | mineru_used, avg_section_depth, max_section_depth, mineru_header_count, mineru_table_count, mineru_avg_table_rows, mineru_avg_table_cols |
| Fusion/RAG Snapshots | fusion_sample_count, rag_sample_count, iso_ts, version (per snapshot file metadata) |
| Cards Pipeline (ingested) | entity_cards_created, triple_cards_created, weight_min, weight_max, weight_avg, elapsed_ms |

### Follow-Up / Phase C Preparation
- Integrate actual entity_cards retrieval for clustering (current placeholder uses empty list).
- Add fusion_stats & rag_metrics aggregation endpoints (C6 remaining work) summarizing ingest fusion metrics & RAG usage.
- Implement section-depth metric once MinerU advanced mapping adds hierarchy depth (feeds avg_section_depth).
- Replace citation token overlap heuristic with embedding-based or alignment-based attribution.
- Evaluate move from JSONL persistence to parquet or time-series DB at higher scale.
- (COMPLETED) Streaming support for Advanced RAG responses via SSE (`/rag/advanced/stream`).
- (COMPLETED) Card summarization endpoint `/cards/summarize` with evidence weighting scaffold & optional centrality boost.
- (COMPLETED) Centrality augmentation integration & lexical hybrid fusion ranking (hybrid score path gated by `FUSION_HYBRID_ENABLED`).
- (COMPLETED) Citation preview endpoint `/projects/{project_id}/citations/preview` with attribution scoring.
	Remaining: richer attribution factors (position diversity, semantic span alignment).

2025-09-25 A7 Vision Result Reuse & Evidence Merge DONE (See section above for details)
2025-09-25 A8 Performance Caching / Rate Limiting DONE (See section above for implementation details)

2025-09-25 B1 LayoutAwareChunker Scaffold DONE
	- Added `services/document-service/app/chunking/layout_chunker.py` with `LayoutAwareChunker` and flag `LAYOUT_AWARE_ENABLED`.
	- Basic grouping heuristic: accumulate paragraph/heading/caption elements until token budget; structural kinds (table/figure) isolated.
	- Placeholder token estimation (~4 chars/token) pending replacement with model tokenizer.

2025-09-25 B2 Bulk Embedding Endpoint Scaffold DONE
	- Added `/bulk-embeddings` endpoint in `vector-service/app/routers/vectors.py`.
	- Flags: `EMBED_BATCH_MAX` (default 32), `EMBED_CACHE_ENABLED` (default true).
	- Deterministic placeholder embedding `_approx_embed` (16-d hash vector) used for quick tests.
	- In-memory cache with metrics: requests, batches, cache_hits, cache_misses, total_texts.
	- Tests `services/vector-service/tests/test_bulk_embeddings.py` validate cap enforcement + cache reuse.
	- Deferred: actual model integration via VectorProcessor, parallelization, eviction strategy, embedding dimension config.

2025-09-25 B3 Extraction Analytics Scaffold DONE
	- Added `analytics-service/app/routers/extraction_stats.py` providing `/extraction-stats` endpoint.
	- Returns placeholders: layout_chunk_time_ms, tables_merged, figures_linked, avg_section_depth (all stubbed), plus enrichment cache hit rate derived from llm-service `/health` when available.
	- Includes raw enrichment cache metrics passthrough for future dashboards.
	- Added test `services/analytics-service/tests/test_extraction_stats.py` validating structure & numeric fields.
	- Deferred: integrate real timers (document-service), table merge counters (A2 advanced), figure linking counts (A3 multimodal), section depth calculation (A2 hierarchy), and persistence/aggregation strategy.
Update (2025-09-26): Upgraded from scaffold to full aggregation. See B3 DONE above; percentiles, trends, JSONL persistence, MinerU structural metrics aggregation, and dashboard schema keys added.

2025-09-26 Graph-Service Migrations EXECUTED
	- Resolved Alembic chain mismatch: `0004_add_proposal_type.py` down_revision originally pointed to non-existent id `0003_enrich_proposals_with_evidence_and_indexes`; corrected to `0003_enrich_proposals`.
	- Ran `alembic upgrade head` against sqlite dev DB (fallback path) successfully applying revisions 0001..0008.
	- Verified tables present: `pvc_proposals`, `pvc_commit_summaries`, `pvc_canonical_entity_index`, `pvc_type_registry`.
	- Row counts post-migration (sqlite dev): all zero initially.
	- Added helper script `services/graph-service/verify_tables.py` for repeatable verification (sqlite only) and `seed_canonical_test.py` to simulate canonical index population when not running Postgres.

2025-09-26 Canonical Entity Index SEED (Dev) DONE
	- Executed `seed_canonical_test.py` inserting synthetic rows (Alpha, Beta) via repository `upsert_canonical_entities`.
	- Confirmed retrieval via `list_canonical_entities` prints expected degree & relationship_type_counts.
	- NOTE: In production/Postgres the canonical index is populated during proposal commit (only when `PVC_STORE=postgres`). For sqlite dev fallback, direct seeding script aids UI development.

2025-09-26 Fusion & RAG Analytics Gateway Proxies DONE (C8)
	- Added backend gateway endpoints: `/api/analytics/fusion`, `/api/analytics/rag`, `/api/analytics/dashboard` aggregating and proxying analytics-service responses with lightweight in-process caching.
	- Status adjustments: C6 aggregation endpoints still PARTIAL inside analytics-service; ingestion & proxy exposure complete. Dashboard endpoint merges fusion + rag + extraction summaries.

2025-09-26 RAG Attribution V1 DONE
	- Implemented lexical + embedding similarity attribution scoring per citation in `/rag/synthesize` & `/rag/advanced`.
	- Fields added per citation: `overlap_ratio`, `embedding_similarity`, `attribution_score`, `attribution_class` (weak/partial/strong thresholds).
	- Aggregated `attribution_stats` (avg, min, max, low_quality_ratio, weak/partial/strong counts) emitted with analytics under metrics.attribution_pipeline.
	- Documentation placeholder for V2 enhancements (span alignment, semantic coverage) – deferred.

2025-09-26 Graph Commit Metrics Phase 2 DONE
	- Added global relationship type aggregation during proposal commit in `graph-service` without schema migration.
	- Commit path now computes cumulative `global_rel_type_counts` across all entities and persists a synthetic canonical row:
	  slug=`__aggregate__`, type=`_metrics`, relationship_type_counts=<distribution>. Degrees & occurrences zeroed.
	- Rationale: Provide immediate global distribution for dashboards using existing `canonical_entity_index` table; avoids new summary table until commit summary migration (C9) finalized.
	- Caveat: Counts are cumulative (not per-commit snapshot). Future option: emit analytics event or store per-commit distribution in `pvc_commit_summaries` once stabilized.
	- Filtering: UI/consumers should ignore slug `__aggregate__` when listing user entities.

2025-09-26 Streaming Hardening Metrics V1 DONE
	- Instrumented SSE endpoint `/rag/advanced/stream` with real-time metrics:
	  * Counters: total_streams, active_streams, completed_streams, cancelled_streams, error_streams, total_tokens_streamed
	  * Latency: per-token inter-emission latency buckets (<50,<100,<250,<500,<1000,>=1000 ms)
	  * Aggregates: avg_token_latency_ms, p95_token_latency_ms, last_updated
	- Metrics exposed via `/health` under `streaming_status` and analytics ingest emits a `streaming` payload (tokens, cancelled, duration_ms) per session (best-effort).
	- Resiliency: cancellation & error paths increment respective counters; active count decremented in finally block.
	- Future: Add client consumption lag, first_token_latency, end_to_end_latency, and optional structured token emission stats (e.g., tokens/sec rolling window).

2025-09-26 Schema Version Sync DONE
	- Unified exposure of `ENRICH_SCHEMA_VERSION` and `CARD_CACHE_SCHEMA_VERSION` under `/health` -> `cache_status.schema_versions` { enrich, cards }.
	- Card summary cache key already includes card schema version; enrichment cache keys namespaced with enrichment schema version.
	- Enables external health/dashboard service to detect drift or mismatches across services before invalidating caches.

---
## Newly Added Observability (September 26 Addendum)
| Metric Group | Keys |
|--------------|------|
| Streaming (SSE) | total_streams, active_streams, completed_streams, cancelled_streams, error_streams, total_tokens_streamed, latency_buckets, avg_token_latency_ms, p95_token_latency_ms |
| Graph Commit Aggregate | relationship_type_counts (synthetic row slug=__aggregate__) |
| Attribution (RAG) | overlap_ratio, embedding_similarity, attribution_score, attribution_class, attribution_stats.* |

Follow-ups (Optional):
- Emit per-commit relationship distribution analytics event (time-series) if historical trend is required.
- Reserve slug namespace (e.g., prefix `~`) and enforce rejection of user entities colliding with metrics slugs.
- Extend streaming metrics with client disconnect reasons and token/sec gauges.
- Attribution V2: integrate semantic span alignment & coverage-based weighting.

2025-09-26 LLM Service Summarize Cards Syntax Fixes DONE
	- Resolved persistent SyntaxError in `services/llm-service/app/routers/llm.py` around `summarize_cards` by refactoring function into single outer try/except, removing fragmented except blocks causing parser confusion under hot reload.
	- Replaced deprecated Pydantic v2 `Field(regex=...)` usages with `Field(pattern=...)` for `ranking_strategy` and `card_type` enums eliminating startup validation error.
	- Confirmed clean startup (health endpoint 200) and validated that request model parsing now succeeds. Added note to future test plan to exercise cache hit/miss path.

2025-09-26 Document Service Structured Processor Error Handling FIXED
	- Corrected malformed JSON error string in `structured_processor.py` replacing unterminated string literal with proper `json.dumps` payload emission.
	- Ensured error branch returns consistent schema enabling frontend parser robustness.

2025-09-26 Document Service Fusion Incremental Endpoint Indentation FIXED
	- Patched `fusion.py` to correct mis-indented `return` and `duration` assignment that produced `expected 'except' or 'finally' block` SyntaxError.
	- Service now starts without syntax exceptions; incremental fusion route ready for functional testing once `FUSION_ENABLED` activated.

2025-09-26 Graph Migrations Chain Repair DONE
	- Adjusted `0004_add_proposal_type.py` `down_revision` to valid predecessor enabling full `alembic upgrade head` across revisions 0001-0008.

2025-09-26 C6 Fusion/RAG Persistence Upgrade PARTIAL
	- Added snapshot persistence to analytics-service (`fusion_rag_stats.py`): env flags `FUSION_RAG_SNAPSHOT_ENABLED`, `FUSION_RAG_SNAPSHOT_DIR`, `FUSION_RAG_SNAPSHOT_RETENTION_MAX`, `FUSION_RAG_SNAPSHOT_MIN_SECONDS`.
	- Snapshots written when `/dashboard` requested and min interval elapsed; file name pattern `snapshot_<UTC>%Y%m%dT%H%M%S_<epoch>.json`.
	- Added endpoints `/fusion-rag/snapshots` (list latest N with metadata) and `/fusion-rag/snapshots/latest` (retrieve latest payload) under analytics-service.
	- Retention pruning deletes oldest files beyond `RETENTION_MAX`; writes are atomic via temp file rename.
	- Documentation updated (env vars + observability). Remaining for C6 closure: extended percentile windows, historical trend deltas over snapshots, integration with future attribution metrics.

2025-09-26 C3 Cards Pipeline Phase 2 DONE
	- Implemented weighting v2 (frequency * dispersion factor) and added dispersion-aware metadata to entity card vectors.
	- Added `regen_key` / `REGENERATE_CARDS_KEY` signature skip logic to avoid redundant regeneration.
	- Added analytics ingest emission `cards_pipeline` with counts + weighting stats.
	- Added `CARD_CACHE_SCHEMA_VERSION` env; wired into summarize_cards cache key (card summarization).
	- Response extended with `weighting_stats` block; docs + env + observability tables updated.
	- Added verification script `verify_tables.py` and dev seeding script `seed_canonical_test.py` for sqlite fallback environment.

2025-09-26 Canonical Entity Dev Seeding DONE
	- Inserted sample canonical entities (Alpha, Beta) demonstrating repository `upsert_canonical_entities` path; used only for local functional smoke while Postgres path deferred.

2025-09-26 Pending Follow-Up Classification UPDATE
	- Reclassified C6 as PARTIAL (ingest + proxy present, aggregation endpoints outstanding), C8 remains PENDING (analytics proxies do not fulfill exploration endpoints), C9 PENDING (no migration file yet).
	- Added explicit pending items list under Remaining Implementation Plan.

2025-09-26 Analytics Unified Dashboard Endpoint (Phase B3/C6 Bridge) PARTIAL
	- Added `/dashboard` endpoint inside `analytics-service` aggregating fusion, rag, and extraction stats in a single response (version c1).
	- Uses existing aggregation functions; best-effort import of extraction stats (tolerates absence).
	- Sets stage for frontend consolidation; remaining: persistence-backed rollups & historical trends integration.

---
## Stub / Partial Implementation Summary

| Area | Status | Implemented | Remaining Gaps |
|------|--------|-------------|----------------|
| A2 MinerU | DONE | Fake mode, structural metrics (avg/max depth, header/table counts), real API normalization (ids, pages, coordinates, hierarchy, caption/table metadata), caption linkage stats, depth histogram | Future tuning: optimize multi-page table merge heuristics & semantic caption/table classifier |
| A3 Advanced Multimodal | PARTIAL | Section segmentation & heuristic extraction | Multimodal enrichment, evidence dedupe, token-budget optimizer |
| B3 Extraction Analytics | DONE (phase 2) | Aggregation of layout metrics incl. MinerU structural fields (avg/max section depth, header/table counts, caption_coverage_ratio, section_depth_histogram); elapsed_ms percentiles & trends; JSONL persistence; dashboard schema keys; cross-project rollups with caption linkage + multi-page table metrics | Follow-ups: historical trend snapshots, anomaly detection hooks, automated percentile window tuning |
| C3 Cards Pipeline | DONE (scaffold) | Regex entity & triple generation | LLM summaries (v1 summarization endpoint now available), frequency weighting, provenance lists |
| C4 Advanced RAG | DONE (streaming + validation) | Citation overlap validation, SSE streaming endpoint | Embedding-based attribution, centrality weighting, hallucination scoring |
| C5 Graph Commit Enhancements | DONE (phase 1+) | Provenance arrays persisted; canonical entity index migration present (population logic basic); per-commit relationship distribution analytics ingest; reserved slug namespace enforcement for `__aggregate__` | Relationship metrics aggregation endpoints, advanced canonical index analytics |
| C6 Fusion & RAG Analytics | DONE (phase 1) | Ingest emission; aggregation endpoints `/fusion-stats` & `/rag-metrics` with percentiles & coverage stats; backend gateway proxies | Advanced persistence/retention, correlation with answer quality, extended latency percentiles |
| MinerU Metrics | PARTIAL | avg/max section depth heuristic; header/table counts; basic table row/col estimates | True hierarchical depth from real MinerU, merged multi-page table span metrics, caption linkage stats |
| Schema Versioning | PARTIAL | `ENRICH_SCHEMA_VERSION` and `CARD_CACHE_SCHEMA_VERSION` exposed in health and used to namespace caches | Add `CITATION_SCHEMA_VERSION`; update health + cache namespaces; migration notes and smoke tests |
| Streaming Answers | DONE | SSE endpoint implemented | Backpressure metrics, cancellation handling, token latency histograms |
| Card Summaries | DONE (v1) | LLM summarization endpoint `/cards/summarize`; evidence weighting heuristic (centrality + de-dup); LRU+TTL card cache & health metrics | Provenance weighting v2, schema versioning, advanced alignment scoring |

---
## Remaining Implementation Plan

1. Cards Pipeline Phase 2
	- Provenance frequency weighting v2; alignment-based evidence scoring; schema versioning + cache key upgrade; incremental regeneration triggers.
2. Advanced RAG Attribution Upgrade
	- Embedding/alignment-based citation grounding; hallucination scoring; provenance token overlap statistics.
3. Graph Commit Enhancements Phase 2
	- Relationship metrics aggregation endpoints and canonical analytics APIs; enhanced canonical entity index population logic. Document slug reservation guarantees (enforcement DONE).
4. Persistence & Observability Upgrade
	- Pluggable persistence sink abstraction (default JSONL) with retention; optional Parquet/time-series sink; SSE hardening (backpressure, disconnect reasons); rolling p50/p95 first-token latency surfaced in health.
5. Schema Versioning & Cache Migration
	- Add `CITATION_SCHEMA_VERSION`; version card & citation schemas; coordinate `ENRICH_SCHEMA_VERSION` and `CARD_CACHE_SCHEMA_VERSION` migrations; update health exposure and add smoke tests.
6. Streaming Hardening
	- Backpressure handling, client cancellation, token latency histogram & throughput metrics.

Priority: (1) Cards phase 2 → (2) RAG attribution → (3) Graph commit phase 2 → (4) Persistence/observability → (5) Schema versioning → (6) Streaming hardening.

Risk Mitigations:
- MinerU integration regressions: retain adapter contract tests and fake-mode fixtures to guard against upstream API shifts.
- Streaming complexity: SSE baseline already shipped; add cancellation tests before websocket expansion.
- Ranking changes: maintain regression fixtures; hybrid path gated via `FUSION_HYBRID_ENABLED` with documented weights.

---
## Newly Added (2025-09-25) Feature Notes
### Enrichment Response Normalization
`/enrich` now appends:
- `entities_normalized`, `facts_normalized`, `relationships_normalized` (lowercased, deduped) for downstream clustering & analytics.
- `section_path_tags`: flattened tag list extracted from section path markers.
- `multimodal_flags`: boolean hints (`has_table_markers`, `has_diagram_markers`, `has_section_tags`).

### Card Summarization Endpoint
`/cards/summarize` (llm-service) accepts card IDs + optional centrality weighting; produces consolidated summary with evidence weighting heuristic (length & centrality). Future: provenance weighting & cache keying.

### Citation Preview Endpoint
`/projects/{project_id}/citations/preview` (vector-service) returns snippet + attribution score (length & diversity factors) for quick UI previews prior to full RAG synthesis.

### Hybrid Fusion Ranking
When `FUSION_HYBRID_ENABLED`=true, each fused candidate receives `hybrid_score` blending:
`hybrid_score = w_rrf*rrf_norm + w_lex*lexical_norm + w_cent*centrality_norm`
with weights from env (`FUSION_WEIGHT_RRF`, `FUSION_WEIGHT_LEX`, `FUSION_WEIGHT_CENTRALITY`). Retrieval stats expose `hybrid_enabled` & applied weights.

### Provenance Persistence
Graph commits now preserve bounded provenance arrays enabling traceability & later analytics on evidence distribution. Normalization strips extraneous keys & coerces numeric values.

### RAG Attribution v1 (2025-09-26)
Implemented first-pass attribution scoring combining lexical overlap and embedding similarity:

Per-citation fields:
- overlap_ratio
- embedding_similarity (when embedding service available; else 0.0)
- attribution_score (0.65 * embedding_similarity + 0.35 * overlap_ratio)
- attribution_class (weak <0.25, partial <0.55, strong otherwise)

Aggregate attribution_stats:
- avg_overlap, avg_embedding_similarity, avg_score, min_score
- low_quality_ratio (score <0.45)
- strong / partial / weak counts
- hallucination_ratio (legacy weak proportion)
- embedding_model (used) & degraded_mode flag

Analytics ingestion now emits `metrics.attribution_pipeline` with core quality indicators (avg_score, min_score, low_quality_ratio, class counts, hallucination_ratio, avg_embedding_similarity, avg_overlap, citation_count).

Env:
- ATTRIBUTION_EMBED_MODEL optional override; falls back to EMBEDDING_MODEL or default `text-embedding-3-small`.
Weights fixed in code (0.65/0.35) for v1.

Deferred for Attribution v2:
- Sentence-level alignment & span coverage
- Dynamic weighting based on answer length / citation diversity
- Penalization of unused citations & reward for diversity across documents
- Aggregated historical attribution trend endpoints & snapshot integration

---
## Wiring Checklist (Frontend + API Placeholders)

This section tracks minimal no-op endpoints and frontend tasks so wiring can proceed in parallel. All endpoints are gated by flags and return schema-only placeholders until internals land.

Flags (env):
- MINERU_ENABLED, LAYOUT_AWARE_ENABLED
- FUSION_ENABLED, FUSION_HYBRID_ENABLED
- ADVANCED_RAG_ENABLED, STREAM_ANSWERS
- ENABLE_CARDS_PIPELINE
- ANALYTICS_PERSIST_ENABLED
- RESERVED: CITATION_SCHEMA_VERSION, ENRICH_SCHEMA_VERSION, CARD_CACHE_SCHEMA_VERSION

API Placeholders to add (no-op, guarded):
1) document-service
	- GET /layout/schema (returns expected MinerU/layout JSON schema) [MINERU_ENABLED]
	- GET /layout/sample (returns static sample for UI) [MINERU_ENABLED]
2) analytics-service
	- GET /dashboard/schema (returns merged dashboard schema for frontend) [ANALYTICS_PERSIST_ENABLED]
3) graph-service
	- GET /projects/{id}/explorer/overview (entity/relationship counts, top types) [GRAPH_EXPLORER_ENABLED]
	- GET /projects/{id}/commits/summary (list with minimal fields) [GRAPH_EXPLORER_ENABLED]
4) llm-service
	- GET /rag/attribution/v2/schema (fields for planned attribution v2) [ADVANCED_RAG_ENABLED]
5) ai-agent-service
	- GET /migration/plan/schema (plan JSON skeleton) [AGENT_TOOLS_ENABLED]
6) websocket-service
	- GET /events/schema (event names + payload shape) [WS_SCHEMA_ENABLED]

Frontend Tasks
- Wire read-only UIs to schemas above, feature-gated per flag.
- Add health panels for: streaming_status (incl. first_token_latency_ms, tokens_per_second), cache_status.schema_versions, fusion/rag dashboard availability.
- Add stubs for: Explorer overview, Commit summaries, MinerU layout viewer, Dashboard widgets, Attribution-v2 inspection, Migration planner preview, WS event browser.

Acceptance for wiring phase
- All endpoints return 200 with JSON schemas when flags enabled; 404 or 403 when disabled.
- Frontend can render placeholder views without backend internals ready.

---
## 2025-09-26 Addendum (Evening) – Graph Commit Analytics & Streaming Metrics Upgrade

### Graph Commit Analytics Event (Per-Commit Distribution) DONE
Goal: Capture a time-series of relationship type distributions per proposal commit for historical trend & anomaly detection.
Implementation:
- In `graph-service` commit path (same section computing synthetic `__aggregate__` row) we now build a `relationship_type_distribution` map (type -> count for this commit only) separate from cumulative global counts.
- Fire-and-forget async POST to analytics-service `/ingest` with payload:
	`{ source: "graph-service", metrics: { graph_commit: { proposal_id, relationship_type_distribution, entity_count, relationship_count } } }`
- Protected against failures (exceptions suppressed). No schema migration required.
Result (2025-09-26 21:00 UTC): First per-commit event emitted successfully in local validation (verified via analytics ingestion history).
Future Extensions:
- Add commit timestamp & diff deltas (vs rolling median) inside analytics-service aggregation.
- Persist normalized distribution vectors for drift analysis (e.g., Jensen–Shannon divergence over time).

### Reserved Slug Namespace Enforcement DONE
Goal: Prevent user-supplied canonical entity slug collisions with synthetic analytics row (`__aggregate__`).
Implementation:
- Introduced `reserved_slugs = {"__aggregate__"}` inside commit logic.
- If an incoming entity slug collides, it is auto-adjusted to `"__aggregate__-<proposal_id_short>"` (first 8 chars) preserving uniqueness while avoiding overwrite.
- Decision rationale: Non-breaking (no rejection) to avoid failing existing ingest pipelines; deterministic transformation simplifies UI explanation.
Future:
- Consider broader reserved pattern (e.g., prefix `__meta__`) with explicit 409 rejection for cleaner UX once frontend is ready.

### Streaming Metrics V1.1 (First Token Latency & Throughput) DONE
Goal: Enhance SSE observability with early token responsiveness and overall throughput.
Implementation:
- Updated `/rag/advanced/stream` generator in `llm-service` to record:
	* `first_token_latency_ms`: ms from stream start until first token event yielded.
	* `tokens_per_second`: total emitted tokens / total stream duration (float, 3 decimal precision).
- Added fields to per-session analytics ingest payload under `metrics.streaming` alongside existing `tokens`, `cancelled`, `duration_ms`.
- Left existing health aggregate unchanged (future: surface rolling averages for the two new gauges if needed).
Result: Metrics appear in analytics ingestion log for each completed (or cancelled) stream; first token latency verified (~35–60ms under fake token generator).
Follow-Up Ideas:
- Maintain ring buffer to compute moving p50/p95 first-token latency (client perceived responsiveness KPI).
- Add rolling tokens/sec histogram bins for burst analysis.

### Observability Table Updates
Added rows:
| Metric Group | Keys |
|--------------|------|
| Graph Commit (per-event) | proposal_id, relationship_type_distribution, entity_count, relationship_count |
| Streaming (session event) | first_token_latency_ms, tokens_per_second (plus tokens, duration_ms, cancelled) |

### Follow-Ups List Adjustment
Items previously listed as optional are now DONE and removed from open follow-ups:
- Emit per-commit relationship distribution analytics event (DONE)
- Reserve slug namespace to avoid user collision (DONE)
- Extend streaming metrics with first_token_latency & tokens/sec (DONE)

Remaining Optional (unchanged): client disconnect reasons, backpressure metrics, attribution V2 enhancements, advanced canonical index analytics, historical divergence calculations.

Result Summary (2025-09-26 21:10 UTC): All three enhancements integrated without schema changes; services start clean; analytics ingestion receiving new event types; documentation synchronized.

2025-09-27 B3 Extraction Analytics Follow-Up DONE
	- Extended `extraction_stats` aggregation with caption linkage totals, multi-page table merge counters, and per-project rollups (top 10) surfacing sample counts, average chunk times, MinerU table/header averages, and caption coverage ratios.
	- Added `ProjectExtractionStats` response model plus new global fields (`captions_total`, `captions_linked_total`, `multi_page_tables_merged_total`) to support dashboard visualizations and cross-project comparisons.
	- Incorporated per-project tracking of trend-ready metrics (latest ingest timestamp, merged histogram bins) to unlock frontend cross-filtering while retaining global histogram aggregation.
	- Updated analytics ingestion tests to cover new aggregation paths with dynamic module loading; introduced analytics package `__init__` to stabilize imports during pytest execution.
	- Installed analytics dependencies in the local virtualenv and validated the new behavior via targeted pytest run for `test_extraction_stats`.

