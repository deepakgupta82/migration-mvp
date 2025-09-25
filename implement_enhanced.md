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
Flags: MINERU_ENABLED
Testing: tests/layout/test_layout_jsonl_schema.py, tests/layout/test_table_merge.py
Status: PENDING

### A3 T2 Section Enrichment & T3 Multimodal Integration
Goal: Batch paragraphs into ~2k token segments, enrich; call multimodal endpoints for figures/tables; dedupe & merge evidence.
Files: document-service/app/enrich/section_enricher.py; integrate with existing pipeline.
Flags: MULTIMODAL_ENABLED, ENRICH_CACHE_SIZE
Testing: tests/enrich/test_section_batching.py, tests/enrich/test_multimodal_merge.py
Status: PENDING

### A4 Proposal Assembly & Auto Posting
Goal: Assemble enriched proposal (entities, relationships, facts, evidence, origin metadata) and post to graph-service.
Files: document-service/app/proposals/proposal_builder.py
Flags: AUTO_POST_ENRICHED_PROPOSAL
Testing: tests/proposal/test_enriched_proposal_post.py
Status: PENDING

### A5 Graph Payload Migration & Indexes
Goal: Add payload_* JSONB columns + GIN indexes for advanced querying.
Files: graph-service/alembic/versions/0005_add_payload_columns.py; repository adjustments.
Testing: tests/graph/test_payload_index_query.py
Status: PENDING

### A6 Validation Adjustment (Pending Approval Types)
Goal: Respect AUTO_REGISTER_TYPES=false -> queue unknown types with status=pending_approval; add approval endpoint.
Files: graph-service/routers/graphs.py (extend validation + new approval route)
Flags: AUTO_REGISTER_TYPES
Testing: tests/validation/test_pending_type_approval.py
Status: PENDING

### A7 Vision Result Reuse & Evidence Merge
Goal: Reuse cached vision results when encountering same image hash, merging evidence sets.
Status: PENDING

### A8 Performance Caching / Rate Limiting
Goal: LRU for enrichment prompts; semaphore for MAX_VISION_IN_FLIGHT; metrics counters.
Files: llm-service/app/cache/lru_enrich.py; instrumentation.
Status: PENDING

---
## Phase B: Layout-Aware Chunking Full

### B1 LayoutAwareChunker
Goal: Smart chunk assembly respecting structural boundaries & token budgets.
Files: document-service/app/chunking/layout_chunker.py
Flags: LAYOUT_AWARE_ENABLED
Testing: tests/layout/test_layout_chunker_tables.py
Status: PENDING

### B2 Bulk Embedding Endpoint
Goal: Batch embedding endpoint with caching & parallelism.
Files: vector-service/app/routers/bulk_embeddings.py
Flags: EMBED_BATCH_MAX, EMBED_CACHE_ENABLED
Testing: tests/vector/test_bulk_embedding_batch.py
Status: PENDING

### B3 Extraction Analytics Metrics
Goal: Capture layout_chunk_time_ms, tables_merged, figures_linked, avg_section_depth.
Files: analytics-service/app/routers/extraction_stats.py (or vector-service interim)
Testing: tests/analytics/test_extraction_stats.py
Status: PENDING

---
## Phase C: Resolution, Fusion, Advanced RAG, Interactive

### C1 Entity Resolution Clustering
Goal: Clustering endpoint producing clusters w/ canonical selection.
Files: vector-service/app/routers/entity_resolution.py
Flags: ENTITY_RESOLUTION_ENABLED, CLUSTER_THRESHOLD_DEFAULT
Testing: tests/resolution/test_entity_resolution.py
Status: PENDING

### C2 Fusion Orchestrator Upgrade
Goal: Aggregate proposals, resolve, canonicalize, commit, compute dedupe_ratio.
Files: document-service/app/core/fusion_orchestrator.py (extend), new mapping storage.
Testing: tests/fusion/test_fusion_upgrade_dedupe.py
Status: PARTIAL (existing basic fusion logic present)

### C3 Card Generation Pipeline
Goal: Generate entity_cards & triple_cards with evidence-driven summaries.
Files: document-service/app/cards/card_generator.py
Flags: ENABLE_CARDS_PIPELINE
Testing: tests/cards/test_card_generation.py
Status: PENDING

### C4 Advanced RAG Synthesize Endpoint
Goal: Strict schema answer + citations w/ hybrid retrieval and optional streaming.
Files: llm-service/app/routers/rag.py (extend), schemas updates.
Flags: ADVANCED_RAG_ENABLED, STREAM_ANSWERS
Testing: tests/rag/test_advanced_rag_citations.py
Status: PARTIAL (baseline RAG exists w/ centrality augmentation)

### C5 Graph Commit Enhancements
Goal: Add provenance arrays, relationship metrics, CanonicalEntityIndex.
Files: graph-service/routers/graphs.py (commit), neo4j constraint loader.
Testing: tests/graph/test_canonical_commit_enhancements.py
Status: PARTIAL

### C6 Fusion & RAG Analytics
Goal: Provide fusion-stats & rag metrics endpoints.
Files: analytics-service/app/routers/fusion_stats.py, rag_metrics.py
Testing: tests/analytics/test_fusion_stats.py
Status: PENDING

### C7 AI Agent Tools & Migration Planner
Goal: Tools for graph queries, retrieval, and plan generation.
Files: ai-agent-service/app/tools/*.py, playbooks/migration_planner.py
Testing: tests/agent/test_migration_planner.py
Status: PENDING

### C8 Frontend Exploration Endpoints & WS Events
Goal: Entity Explorer, Evidence Panel, Diagram Browser support.
Files: graph-service new endpoints; websocket-service events.
Testing: tests/frontend/test_entity_evidence_endpoints.py
Status: PENDING

### C9 Commit Summary Table Migration
Goal: Store commit summary JSON per fusion commit.
Files: graph-service/alembic/versions/0006_add_commit_summary_table.py
Testing: tests/graph/test_commit_summary_persistence.py
Status: PENDING

---
## Configuration Flags (Planned)
MINERU_ENABLED | LAYOUT_AWARE_ENABLED | MULTIMODAL_ENABLED | ENTITY_RESOLUTION_ENABLED | ADVANCED_RAG_ENABLED | AUTO_REGISTER_TYPES | ENABLE_CARDS_PIPELINE | ENRICH_CACHE_SIZE | OCR_ENABLED | STREAM_ANSWERS | EMBED_BATCH_MAX | EMBED_CACHE_ENABLED | CLUSTER_THRESHOLD_DEFAULT | MAX_VISION_IN_FLIGHT | AUTO_POST_ENRICHED_PROPOSAL

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

