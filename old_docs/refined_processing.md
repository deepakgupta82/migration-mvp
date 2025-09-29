# Enhanced Document Processing Pipeline

## Overview

The enhanced document processing pipeline implements a multi-phase, multi-service architecture for comprehensive document understanding and knowledge extraction. This system transforms raw documents into structured knowledge graphs, vector embeddings, and interactive insights through coordinated processing across document, vector, graph, and LLM services.

## 1. Overall Architecture and Data Flows

### Service Architecture

The pipeline currently operates across multiple cooperating services (core + supporting):

- **Document Service**: Primary document parsing, structured & layout JSONL generation, section enrichment (foundational), proposal assembly & auto‑posting, layout‑aware chunking.
- **Vector Service**: Embedding generation (real SentenceTransformers), bulk embeddings endpoint, multi‑kind semantic retrieval, fusion orchestrator (RRF + optional hybrid scoring), entity & triple card generation (heuristic v1), citation preview.
- **Graph Service**: Proposal validation & commit with provenance persistence (phase 1), type gating / pending approval, (dev) canonical entity seeding; full commit summary table still pending.
- **LLM Service**: Vision adapter (OCR + multimodal fake/real modes) with caching, enrichment caching (LRU+TTL + concurrency control), advanced RAG (streaming + citation validation), card summarization endpoint (stabilized after syntax refactor), planned future attribution upgrades.
- **Analytics Service**: Metrics ingestion (JSONL optional persistence), aggregation (layout / extraction stats, percentiles), gateway exposure via backend proxies; fusion & RAG aggregation endpoints still under development.
- **Frontend & Gateway Layer**: Exposes consolidated analytics proxy endpoints (`/api/analytics/fusion`, `/api/analytics/rag`, `/api/analytics/dashboard`) and will later surface entity explorer & evidence panels (not yet implemented).

### Data Flow Overview

```
Raw Document → Document Service → Structured JSONL + Layout JSONL
    ↓
Vector Service → Embeddings (raw_chunks, entity_cards, triple_cards)
    ↓
Graph Service → Entities + Relationships + Discovery Facts
    ↓
LLM Service → Multimodal Enrichment + RAG Synthesis
```

### Processing Phases

The implementation follows three main phases:

- **Phase A**: Vision + Evidence Enrichment (Foundation)
- **Phase B**: Layout-Aware Chunking (Structure)
- **Phase C**: Resolution, Fusion, Advanced RAG (Integration)

## 2. End-to-End Processing Pipeline

When a document enters the enhanced processing pipeline, it undergoes a comprehensive transformation from raw content to actionable knowledge. This multi-phase process extracts and synthesizes information at multiple levels, creating interconnected representations that enable advanced retrieval, analysis, and interactive exploration.

### Document Ingestion and Initial Parsing

The journey begins when a raw document—such as a PDF, Word file, or technical specification—is ingested into the Document Service. The service employs unstructured.io as its primary parsing engine, breaking down the document into structured elements: titles, paragraphs, lists, tables, and figures. Each element is enriched with metadata including page numbers, element types, and confidence scores.

Simultaneously, if MinerU processing is enabled (currently fake mode in dev), the system produces synthetic layout elements capturing approximate reading order, hierarchy depth estimates, and element bounding boxes. Advanced features (real MinerU API mapping, multi‑page table merge normalization, caption linkage) are planned but not yet integrated. This layout layer – even in synthetic form – underpins structural chunking and future enrichment heuristics.

### Multimodal Evidence Enrichment

As the document is parsed, the system identifies visual elements that require specialized analysis. Images, diagrams, and complex tables are extracted and sent to the LLM Service's vision adapter. Using OCR technology and multimodal language models, these visual elements are transformed into structured data: entities, relationships, and factual statements.

For example, an architectural diagram might yield entities like "web server" and "database," with relationships indicating "connects_to" or "hosts." Tables containing infrastructure details are parsed into structured records with confidence scores. This multimodal evidence is cached using content-based hashing to avoid redundant processing of identical images across documents.

### Section-Level Integration and Enrichment

With textual parsing complete, the system performs foundational section-level enrichment. Document content is segmented using heading heuristics into semantically coherent sections (target ~2k token budget heuristic; precise token budgeting pending). Advanced multimodal integration (automatic figure/table association, evidence dedupe & confidence-weighted reconciliation) is scheduled but not yet enabled. Current enriched sections include placeholder entity / relationship heuristic extraction and metadata counts that feed proposal payloads.

### Knowledge Graph Construction

The enriched sections feed into proposal assembly, where the system (currently via heuristic extraction, with advanced LLM pass planned) gathers entities, relationships, and facts. Entities might include infrastructure components (servers, networks), business concepts (applications, services), and technical artifacts (APIs, databases). Relationships capture how these entities interact: "Application A depends on Database B" or "Server C hosts Service D."

Each extracted element is (phase 1) accompanied by section-level provenance metadata counts; fine‑grained evidence citations per relationship/entity are a future enhancement. Proposals are automatically posted to the Graph Service, validated (respecting pending type approval gating), and committed. Graph payload JSON columns (entities / relationships / facts placeholders) are persisted. Provenance arrays for committed entities/relationships (sanitized phase 1) are stored; canonical entity indexing and commit summary table migration remain pending.

### Layout-Aware Chunking and Vectorization

Parallel to graph construction, the document undergoes layout‑aware chunking that respects structural boundaries. Current implementation preserves table blocks and binds figures to captions; hierarchical section awareness is heuristic (refined depth metrics will arrive with full MinerU integration). Token estimation uses a model tokenizer when available (fallback heuristic) and will later incorporate dynamic budget adjustments.

These chunks, along with generated entity cards and relationship triples, are sent to the Vector Service for embedding. Using transformer-based models like Sentence Transformers, the system creates dense vector representations that capture semantic meaning. Multiple embedding collections are maintained: raw text chunks for general retrieval, entity cards for entity-centric search, and triple cards for relationship-focused queries.

### Entity Resolution and Knowledge Fusion

As multiple documents are processed, the system (when enabled) clusters similar entity cards using cosine similarity on embeddings. Canonical selection currently uses heuristic richness & frequency; deeper evidence strength metrics and graph centrality feedback are roadmap items.

The Fusion Orchestrator performs multi‑kind retrieval and Reciprocal Rank Fusion (RRF). Optional hybrid fusion (lexical + centrality weighting) is gated by configuration and presently experimental; centrality scoring integration with live graph metrics is planned. Deduplication ratio tracking is active; canonical entity index & fast global lookup table are pending.

### Evidence-Driven Card Generation

To facilitate efficient retrieval and presentation, the system generates lightweight cards for entities and relationships. Current (v1) cards are produced via heuristic extraction with basic summarization; an upgraded LLM-driven summarization pass with provenance weighting and incremental regeneration is planned.

Cards are embedded and stored in dedicated vector collections, enabling semantic search. They act as entry points for deeper exploration; future iterations will embed citation provenance and confidence distributions.

### Advanced Retrieval-Augmented Generation

The culmination of this processing enables question-answering and analysis. The current Advanced RAG system combines multi‑kind semantic retrieval and (optionally) experimental hybrid scoring. Planned enhancements include deeper graph traversal weighting and embedding-based citation attribution.

When a user asks a question like "What are the dependencies of the payment service?", the system:

1. Retrieves relevant entity cards and relationship triples using hybrid search
2. Traverses the knowledge graph to find connected entities
3. Applies centrality ranking to prioritize the most important relationships
4. Synthesizes this information into a coherent, cited answer using language models

Answers include strict schema validation and optional streaming (SSE). Present citation validation uses token overlap heuristics; roadmap: embedding/alignment-based attribution, hallucination scoring, and centrality-informed re-ranking.

### Interactive Exploration and Analytics

The processed knowledge enables interactive features through AI agents and frontend interfaces. Agents can perform complex reasoning tasks, such as migration planning or impact analysis, using tools that query the graph, retrieve evidence, and generate structured outputs.

Planned frontend components will provide entity explorers, evidence panels, and diagram browsers. Currently, only aggregated analytics proxy endpoints are exposed; dedicated exploration & evidence endpoints and websocket events remain pending.

Throughout this pipeline, caching mechanisms prevent redundant processing, parallel execution maximizes throughput, and graceful degradation ensures reliability. The result is a comprehensive knowledge system that transforms documents into interactive, queryable intelligence.

## 3. Information Extraction Levels

### Text Level
- **Raw Text**: Basic OCR and text extraction from documents
- **Structured Text**: Element-level parsing with types (title, paragraph, list, table)
- **Semantic Text**: LLM-enhanced text with confidence scores and semantic tags

### Layout Level
- **Reading Order**: Document element sequencing and hierarchy
- **Section Paths**: Hierarchical section structure with depth tracking
- **Table Merging**: Multi-page table reconstruction and normalization

### Entity Level
- **Named Entities**: People, organizations, locations, technologies
- **Infrastructure Components**: Servers, databases, networks, applications
- **Relationships**: Directed edges between entities with types and properties

### Relationship Level
- **Direct Relationships**: Explicit connections (HOSTS, CONNECTS_TO, USES)
- **Inferred Relationships**: LLM-derived connections with confidence scores
- **Evidence-Based**: Relationships supported by document citations

### Fact Level
- **Key Facts**: Declarative statements extracted from content
- **Categories**: Infrastructure, technology, business, security, performance, compliance
- **Evidence Links**: Source document and element references

### Evidence Level
- **Source Citations**: Document, page, and element identifiers
- **Confidence Scores**: Extraction quality metrics
- **Multimodal Evidence**: Image and diagram-derived information

## 4. Service Integration Points

### Document ↔ Vector Service
- **Chunking Integration**: `SemanticChunker` generates chunks for embedding
- **Multi-Kind Collections**: Separate collections for `raw_chunks`, `entity_cards`, `triple_cards`
- **Batch Processing**: Synchronous and asynchronous embedding endpoints

### Document ↔ Graph Service
- **Entity Extraction**: LLM-based extraction with parallel chunking for large documents
- **Proposal Posting**: Structured element transmission for graph construction
- **Fact Extraction**: Discovery node creation for foundational knowledge

### Document ↔ LLM Service
- **Multimodal Enrichment**: Vision analysis for tables and diagrams
- **Content Analysis**: LLM-powered document understanding and summarization
- **RAG Synthesis**: Hybrid retrieval and answer generation

### Vector ↔ Graph Service
- **Entity Resolution**: Clustering of entity card embeddings
- **Canonical Selection**: Representative entity identification
- **Centrality Augmentation**: Graph-based ranking enhancement

### Vector ↔ LLM Service
- **Hybrid Search**: Semantic + keyword search combination
- **RRF Fusion**: Multi-kind result ranking and fusion
- **Context Building**: Structured context for LLM synthesis

## 5. Key Algorithms and Technologies

### Document Processing
- **Unstructured.io**: Primary document parsing library
- **MinerU**: Advanced PDF layout analysis (optional)
- **Tesseract OCR**: Text extraction from images
- **JSONL Output**: Structured element serialization

### Vector Processing
- **Weaviate**: Vector database for embeddings
- **Sentence Transformers**: Embedding model (all-MiniLM-L6-v2 default)
- **Cosine Similarity**: Entity clustering and search
- **Reciprocal Rank Fusion**: Multi-source result ranking

### Graph Processing
- **Neo4j**: Graph database for knowledge representation
- **LLM Entity Extraction**: AI-powered entity and relationship identification
- **Parallel Chunking**: Large document processing optimization
- **Redis Caching**: Performance optimization for repeated queries

### LLM Processing
- **LangChain**: LLM orchestration framework
- **Multi-Provider Support**: OpenAI, Anthropic, Google Gemini, Ollama
- **Vision Models**: Multimodal analysis for images and diagrams
- **Process Types**: Specialized prompts for different analysis tasks

## 6. Configuration Flags and Impact

### Core Processing Flags
- `ENABLE_VECTOR_INTEGRATION`: Controls vector service integration (default: true)
- `ENABLE_GRAPH_INTEGRATION`: Controls graph service integration (default: true)
- `ENABLE_LLM_ANALYSIS`: Enables LLM-powered analysis (default: true)
- `MULTIMODAL_ENABLED`: Enables vision and OCR features (default: true)
- `LAYOUT_AWARE_ENABLED`: Enables layout-aware processing (default: false)

### Performance Flags
- `MAX_CONCURRENT_INTEGRATIONS`: Parallel service calls (default: 2)
- `ENABLE_PARALLEL_PROCESSING`: Sequential vs parallel execution (default: true)
- `MAX_VISION_IN_FLIGHT`: Concurrent vision requests (default: 4)
- `GRAPH_ADVANCED_EXTRACTION`: Enables parallel LLM chunking (default: true)

### Caching and Limits
- `VISION_CACHE_SIZE`: OCR result cache size (default: 256)
- `VISION_CACHE_TTL`: OCR cache TTL in seconds (default: 900)
- `GRAPH_MAX_FACTS`: Maximum facts per document (default: 100)
- `GRAPH_PARALLEL_WORKERS`: Concurrent LLM calls (default: 4)

### Feature Gates
- `ENTITY_RESOLUTION_ENABLED`: Enables entity clustering (default: false)
- `ENABLE_CARDS_PIPELINE`: Enables entity/triple card generation (default: true)
- `ADVANCED_RAG_ENABLED`: Enables enhanced RAG features (default: false)
- `AUTO_REGISTER_TYPES`: Graph type auto-registration (default: false)

## 7. Current Implementation Status

### Implementation Status Snapshot (2025-09-26)

Phase A (Foundation)
- A1 Vision Adapter: DONE (caching + concurrency; evidence merge dedupe future)
- A2 MinerU / Layout JSONL: PARTIAL (fake mode + structural metrics; real API & table span merge pending)
- A3 Section Enrichment (Foundational): DONE (advanced multimodal enrichment & dedupe pending)
- A4 Proposal Assembly & Auto Posting: DONE
- A5 Graph Payload Migration: DONE
- A6 Validation Adjustment (Type Gating): DONE
- A7 Vision Result Reuse: DONE
- A8 Enrichment Performance Caching: DONE

Phase B (Structure)
- B1 Layout-Aware Chunking: DONE (heuristic hierarchy depth; advanced MinerU depth pending)
- B2 Bulk Embedding Endpoint: DONE (real embeddings + cache)
- B3 Extraction Analytics: PARTIAL (aggregation + percentiles done; real table/figure linkage metrics pending)

Phase C (Integration & Advanced Retrieval)
- C1 Entity Resolution: DONE (cluster heuristic; richer evidence weighting pending)
- C2 Fusion Orchestrator: DONE (RRF; hybrid lexical/centrality experimental)
- C3 Card Generation: DONE (heuristic v1; LLM provenance upgrade pending)
- C4 Advanced RAG: DONE (streaming + overlap validation; attribution upgrade planned)
- C5 Graph Commit Enhancements: DONE (provenance phase 1; canonical index & summaries pending)
- C6 Fusion & RAG Analytics: PARTIAL (ingest + proxies; dedicated fusion_stats/rag_metrics endpoints pending)
- C7 AI Agent Tools: PENDING
- C8 Frontend Exploration Endpoints & WS Events: PENDING (analytics proxies only)
- C9 Commit Summary Table Migration: PENDING

Summary of Remaining Gaps
- MinerU real integration & advanced layout semantics
- Multimodal figure/table enrichment & evidence dedupe
- Fusion/RAG aggregation endpoints (analytics service)
- Commit summary table & canonical entity index persistence
- Card LLM summarization upgrade with provenance weighting
- Advanced RAG attribution (embedding/alignment) & hallucination scoring
- Interactive frontend entity explorer, evidence panels, websocket events

## 8. New Capabilities

### Enrichment Response Normalization
The `/enrich` endpoint now provides normalized outputs for downstream processing:
- `entities_normalized`: Lowercased, deduplicated entity lists
- `facts_normalized`: Normalized fact statements
- `relationships_normalized`: Standardized relationship formats
- `section_path_tags`: Flattened tag lists from section path markers
- `multimodal_flags`: Boolean indicators for table/diagram/section content presence

### Card Summarization Endpoint
- **Endpoint**: `/cards/summarize` (LLM Service)
- **Functionality**: Generates consolidated summaries from multiple entity/triple cards
- **Features**: Evidence weighting heuristic, optional centrality boost, caching support

### Citation Preview Endpoint
- **Endpoint**: `/projects/{project_id}/citations/preview` (Vector Service)
- **Functionality**: Provides citation snippets with attribution scoring
- **Features**: Length and diversity factors for preview quality assessment

### Hybrid Fusion Ranking
- **Configuration**: Enabled via `FUSION_HYBRID_ENABLED` flag
- **Algorithm**: Combines RRF, lexical, and centrality scores with configurable weights
- **Weights**: `FUSION_WEIGHT_RRF` (0.6), `FUSION_WEIGHT_LEX` (0.25), `FUSION_WEIGHT_CENTRALITY` (0.15)
- **Output**: `hybrid_score` for each fused candidate with component breakdowns

### Provenance Persistence
- **Implementation**: Graph commits now store sanitized provenance arrays
- **Features**: Bounded keys, numeric coercion, evidence traceability
- **Benefits**: Enables analytics on evidence distribution and source attribution

### Streaming RAG Responses
- **Endpoint**: `/rag/advanced/stream` (LLM Service)
- **Protocol**: Server-Sent Events (SSE) for real-time responses
- **Events**: `meta`, `token`, `done` with structured data
- **Gating**: Controlled by `STREAM_ANSWERS` flag

### Advanced Citation Validation
- **Features**: Token overlap heuristics, embedding-based attribution
- **Output**: `invalid_citations` count, `validation_warnings` array
- **Threshold**: Configurable `min_citation_overlap` parameter

## 9. Updated Processing Flow

The current operational pipeline reflects implemented enhancements:

1. **Document Ingestion** → Structured JSONL + Layout JSONL (MinerU fake mode)
2. **Section Enrichment** → Heading-based segmentation with heuristic extraction
3. **Proposal Assembly** → Auto-posting with payload storage and pending type handling
4. **Vision Caching** → Content-based reuse of multimodal analysis results
5. **Layout-Aware Chunking** → Structural boundary respect with token budgeting
6. **Bulk Embedding** → Cached batch processing with real SentenceTransformers
7. **Entity Resolution** → Clustering with canonical selection
8. **Fusion Search** → Multi-kind RRF with optional hybrid ranking
9. **Card Generation** → Evidence-driven summaries with LLM enhancement
10. **Advanced RAG** → Streaming responses with citation validation
11. **Graph Commits** → Provenance persistence and relationship metrics

Operational Readiness Notes (2025-09-26)
- All core services (document, vector, graph, llm) start cleanly after recent syntax and migration chain fixes.
- Summarize cards endpoint stabilized post refactor; Pydantic v2 compatibility addressed (regex→pattern).
- Fusion incremental route loads without syntax errors; functional smoke tests (fusion search, summarize cards) scheduled next.
- Analytics ingestion active; aggregation endpoints for fusion/RAG not yet surfaced (proxy endpoints provide interim visibility).
- Dev sqlite environment seeded with sample canonical entities (Alpha, Beta); production Postgres path will rely on proposal commits (canonical index phase 2 pending).

## 10. Comprehensive Metrics and Observability

### Metrics Groups

| Metric Group | Keys |
|--------------|------|
| Vision Cache | vision_cache_hits, vision_cache_misses, vision_cache_evictions, images_processed, ocr_invocations |
| Enrichment Cache | hits, misses, evictions, inflight_current, inflight_max_observed, wait_count, wait_ms_total, size, enabled, version, version_mismatches |
| Layout Chunker | number_of_chunks, total_tokens, avg_chunk_tokens, max_chunk_tokens, tables_merged, figures_bound, paragraphs_split, over_budget_elements, elapsed_ms, token_estimation_mode |
| Bulk Embeddings | requests, batches, cache_hits, cache_misses, evictions, force_refreshes, total_texts, model_load_latency_ms |
| Extraction Stats (aggregated) | layout_chunk_time_ms (avg), max_layout_chunk_time_ms, min_layout_chunk_time_ms, tables_merged, figures_linked, over_budget_elements_total, paragraphs_split_total, avg_chunk_tokens, max_chunk_tokens, sample_count |
| Extraction Stats (percentiles) | p50_layout_chunk_time_ms, p95_layout_chunk_time_ms, trend_last_5_vs_prev_5_pct |
| Fusion | candidate_counts per kind, fused_candidates, dedupe_ratio, rrf_k, hybrid_score, lexical_score, centrality |
| RAG Advanced | invalid_citations count, validation_warnings present |
| MinerU Structural | mineru_used, avg_section_depth, max_section_depth, mineru_header_count, mineru_table_count, mineru_avg_table_rows, mineru_avg_table_cols |

### Analytics Ingestion
- **Endpoint**: `/ingest` (Analytics Service)
- **Persistence**: JSONL files with compaction (`ANALYTICS_PERSIST_ENABLED`)
- **History**: Bounded in-memory retention (`ANALYTICS_HISTORY_MAX`)
- **Aggregation**: Percentiles, trends, and cumulative statistics

## 11. New Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| LAYOUT_TOKEN_MODEL | Select tokenizer model for chunking | gpt-3.5-turbo |
| EMBED_CACHE_MAX_ENTRIES | Max embedding cache size | 2048 |
| EMBED_CACHE_TTL_SECONDS | Embedding cache entry TTL | 3600 |
| ENRICH_SCHEMA_VERSION | Namespace enrichment cache keys | v1 |
| ANALYTICS_HISTORY_MAX | Max ingestion records retained | 500 |
| ANALYTICS_PERSIST_ENABLED | Persist ingestion history to JSONL | false |
| ANALYTICS_PERSIST_PATH | JSONL persistence file path | analytics_history.jsonl |
| ANALYTICS_PERSIST_COMPACT_EVERY | Compaction cadence | 2000 |
| ENABLE_CARDS_PIPELINE | Enable card generation | false |
| FUSION_ENABLED | Enable fusion search endpoint | false |
| ADVANCED_RAG_ENABLED | Enable advanced RAG features | false |
| MINERU_FAKE_MODE | Generate synthetic MinerU output | false |
| FUSION_HYBRID_ENABLED | Enable hybrid fusion ranking | false |
| FUSION_WEIGHT_RRF | RRF component weight | 0.6 |
| FUSION_WEIGHT_LEX | Lexical component weight | 0.25 |
| FUSION_WEIGHT_CENTRALITY | Centrality component weight | 0.15 |
| STREAM_ANSWERS | Enable streaming RAG responses | false |

Flag Activation Status (Dev Snapshot)
- Vision & enrichment caching enabled by default enabling performance baselines.
- Fusion, Advanced RAG, Cards pipeline, and Hybrid Fusion remain gated (disabled) until targeted smoke validation passes.
- MinerU fake mode toggled selectively for structural tests; real integration off.

This enhanced pipeline represents a comprehensive approach to document understanding, combining traditional NLP techniques with modern AI capabilities to create actionable knowledge from unstructured content.