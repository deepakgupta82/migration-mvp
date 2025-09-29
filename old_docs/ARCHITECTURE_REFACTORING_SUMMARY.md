## Architecture Refactoring Summary

This document captures the current refactored state and recent incremental enhancements bridging ingestion, fusion canonicalization, retrieval, and ranking.

### Core Pillars
1. Governed ingestion & proposals (proposal → validate → commit)
2. Entity & relationship fusion with provenance deepening
3. Multi-kind embeddings (raw_chunks, entity_cards, triple_cards)
4. Hybrid RAG synthesis (RRF) + graph-aware ranking augmentation
5. Observability foundations (centrality, metrics endpoints, caching)

### Service Responsibilities
- document-service: Extraction, enrichment, fusion orchestration (full + incremental)
- vector-service: Unified Weaviate collection, per-kind logical views, entity resolution clustering, metrics
- graph-service: Canonical graph persistence, exploration, centrality analytics, caching layer
- llm-service: Governed model access, RAG synthesis with pluggable ranking strategies

### Data Lineage & Provenance
Canonical entities/relationships embed:
```
properties.source_entity_ids
properties.cluster_ids
properties.provenance (truncated list)
relationship.properties.source_relationship_ids
```
Enables traceability from canonical nodes back to proposal & raw entity cards.

### Recent Enhancements
- Fusion governance (proposal vs direct commit modes)
- Canonical triple card generation for hybrid retrieval (kind=triple_cards)
- Pagination totals & provenance deepening (cluster_ids, source_entity_ids)
- Centrality metrics endpoint (degree + normalized_total_degree)
- Caching layer for canonical exploration with invalidation on fusion persistence
- Centrality-augmented RAG ranking (`ranking_strategy=centrality_augmented`)
- Incremental fusion endpoint: `POST /fusion/projects/{project_id}/run-incremental`
- Vector metrics endpoint: `GET /projects/{project_id}/metrics` (counts per kind + total)

### Key Endpoints Snapshot
```
document-service:
	POST /fusion/projects/{project_id}/run
	POST /fusion/projects/{project_id}/run-incremental

graph-service:
	GET /api/graphs/projects/{project_id}/canonical/entities
	GET /api/graphs/projects/{project_id}/canonical/relationships
	GET /api/graphs/projects/{project_id}/canonical/centrality

vector-service:
	POST /projects/{project_id}/entity-resolution/cluster
	GET  /projects/{project_id}/metrics

llm-service:
	POST /rag/synthesize  (ranking_strategy=rrf|centrality_augmented)
```

### Caching Strategy
In-memory TTL for canonical entity & relationship list queries keyed by (project_id, filters). Automatic invalidation triggered after fusion persistence events ensures freshness while reducing graph load for repeated pagination.

### Ranking Augmentation Flow
1. Perform per-kind hybrid search (raw_chunks, entity_cards, triple_cards)
2. Fuse with RRF (rrf_score)
3. If centrality_augmented: fetch centrality once, map canonical IDs, compute `aug_score = rrf_score * (1 + weight * normalized_total_degree)`
4. Sort by aug_score (fallback to rrf_score on error)

### Incremental Fusion Overview
Filter clusters via cluster_ids and/or entity_ids → recompute only matching subset → rebuild canonical entities & relationships → provenance enrichment → persistence & vector upsert. Reduces recompute cost when small subsets change.

### Metrics & Observability (Current)
- Vector counts per kind (raw_chunks/entity_cards/triple_cards)
- Centrality degree metrics per canonical node
- Fusion stats (dedupe ratio, unmatched clusters, dropped relationships)

### Proposal Validation Enhancements (New)
Validation pipeline upgraded to produce richer governance metrics and aggregated insights:

Per-proposal metrics now include:
```
entity_count
relationship_count
duplicate_entity_names
duplicate_entity_ratio
empty_name_entities
avg_entity_name_length
p95_entity_name_length
unknown_entity_types / unknown_entity_type_list
unknown_relationship_types / unknown_relationship_type_list
entity_type_counts
relationship_type_counts
relationships_missing_endpoints
generated_at
```
Ordering fix: unknown type counts are computed BEFORE auto-registration for accuracy, then new types are appended to the Type Registry (version bumped).

Evidence Block: Each validation attaches a `validation_summary` evidence item with counts of newly added types.

Aggregation Endpoint:
`GET /projects/{project_id}/proposals/validation-summary` summarizes numeric metrics across proposals (optionally filtered by status, e.g. `validated`) computing sums or average for ratio fields. Enables dashboard readiness without client-side fan-out.

Storage Behavior:
- Postgres (PVC_STORE=postgres): metrics persisted via repository `update_proposal_validation` method.
- Redis fallback: metrics & evidence embedded in proposal JSON.

These metrics unlock downstream quality gating (e.g., thresholding duplicate ratios) and feed future evaluation dashboards planned in Phase 4.

See `NEXT_PHASE_ROADMAP.md` for Phase 4+ initiatives (evaluation harness, extended observability, personalization, advanced graph analytics).

Prepared: 2025-09-25
