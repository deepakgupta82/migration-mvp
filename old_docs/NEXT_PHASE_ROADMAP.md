# Next Phase Roadmap (Phase 4+)

## Context Recap
Phase 3 delivered: governed ingestion → clustering → fusion canonicalization → hybrid RAG (RRF) → provenance deepening → centrality analytics → centrality-augmented ranking → incremental fusion → vector metrics.

The platform now supports:
- Multi-kind embeddings (raw_chunks, entity_cards, triple_cards)
- Canonical entity/relationship graph with provenance lineage
- Fusion governance (proposal vs direct) + incremental recompute
- Hybrid RAG with optional graph-centrality ranking augmentation
- Basic analytics & counts + centrality endpoint + vector metrics

## Phase 4 Objectives
1. Quality & Testing Hardening
2. Retrieval Evaluation & Continuous Scoring
3. Observability & Performance Instrumentation
4. Security & Policy Controls
5. Personalization & Contextual Ranking Extensions
6. Advanced Graph & Semantic Analytics
7. Operational Tooling & Automation

---
## 1. Quality & Testing Hardening
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| High coverage for fusion & RAG paths | Prevent regression in canonical pipeline | Unit tests (fusion mapping, incremental filters, ranking augmentation) |
| Contract tests across services | Ensure inter-service payload stability | JSON schema snapshots; backward-compat harness |
| Synthetic load tests for vector & RAG | Validate latency under scale | Locust/gatling scenario scripts |
| Error simulation tests | Validate resilience & fallbacks | Chaos-style tests (failed centrality fetch, vector timeout) |

KPIs: >85% critical path coverage; <5% regression incidents per release.

---
## 2. Retrieval Evaluation & Continuous Scoring
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| Establish golden questions set | Baseline relevance & answer quality | eval/benchmark_questions.json |
| Offline scoring harness | Track improvements & regressions | eval/run_eval.py (BLEU, ROUGE-L, semantic similarity, citation presence) |
| Automated nightly eval | Continuous feedback loop | GitHub Action / scheduler invoking harness; stores metrics (JSON + Markdown trend) |
| Drift detection (embedding vs answer quality) | Detect model/config degradation | Stats aggregator comparing week-over-week MAP / MRR |

KPIs: Answer factuality >= target threshold; citation coverage >90% for answerable queries.

---
## 3. Observability & Performance Instrumentation
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| Structured tracing / correlation | Cross-service latency attribution | Correlation ID propagation middleware additions |
| Latency histograms (ingest, fusion, search, RAG) | Identify bottlenecks | Prometheus-style endpoints or push gateway adapter |
| Cache effectiveness metrics | Validate TTL strategy | Counters: cache_hit, cache_miss, invalidations |
| Centrality augmentation timing | Monitor overhead | Timing logs around centrality fetch & merge |
| Resource usage profiling | Capacity planning | Periodic logs of memory/embedding batch durations |

KPIs: p95 RAG latency < X sec; cache hit rate >60%; centrality overhead <10% of total synthesis time.

---
## 4. Security & Policy Controls
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| AuthZ scoping of project data | Prevent cross-project leakage | Service-side project isolation checks (middleware) |
| Input sanitization for filenames / content | Defense-in-depth | Validation layer & rejection metrics |
| Token audit logging | Trace misuse | Append-only audit log channel |
| Rate limiting for expensive endpoints | Protect resources | Simple Redis token bucket for /rag/* & /fusion/* |
| Secret & config scan integration | Supply chain hygiene | CI step (gitleaks / trivy) |

KPIs: Zero critical security findings; clear auditability for sensitive ops.

---
## 5. Personalization & Contextual Ranking Extensions
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| User / role adaptive weighting | Increase relevance per persona | Extend ranking_strategy: role_weighted, history_boost |
| Session memory signals (recently cited entities) | Maintain topical focus | Short-term entity frequency boosting layer |
| Feedback loop (thumbs up/down) | Closed-loop improvement | Feedback endpoint + weight updates |
| Learning-to-Rank candidate features | Optimize ranking beyond heuristics | Feature extraction pipeline (rrf_score, centrality, recency, feedback_score) |

KPIs: Relative MAP increase >10% after personalization layer.

---
## 6. Advanced Graph & Semantic Analytics
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| Community detection (Louvain) | Higher-level domain segmentation | /canonical/communities endpoint |
| Path search (k-shortest) for reasoning traces | Transparent answer provenance | /graphs/path/explanations endpoint |
| Temporal evolution snapshots | Track knowledge drift | Snapshot store & diff endpoint |
| Influence scoring (PageRank) | Alternate centrality dimension | page_rank field integration into ranking_strategy |

KPIs: Query explainability coverage >80%; path retrieval p95 < target.

---
## 7. Operational Tooling & Automation
| Goal | Rationale | Deliverables |
|------|-----------|--------------|
| CLI orchestration (admin ops) | Simplify multi-service maintenance | cli/management.py (re-run fusion, invalidate caches) |
| Auto-scaling heuristics doc | Prepare for infra scaling | SCALING_GUIDE.md |
| Data retention & cleanup jobs | Control storage costs | Scheduled purger for stale raw_chunks |
| Migration automation harness | Safer schema evolutions | alembic preflight validation script |

KPIs: Mean admin action time reduced; successful zero-downtime migrations.

---
## Implementation Waves
Wave 1 (Foundational Hardening): Tests (critical paths), evaluation harness skeleton, metrics for cache & centrality overhead.
Wave 2 (Observability & Security): Tracing, rate limiting, audit, Prometheus integration.
Wave 3 (Retrieval Intelligence): Personalization strategies & L2R feature pipeline.
Wave 4 (Advanced Graph Analytics): Communities, PageRank, path explanations.
Wave 5 (Operational Excellence): CLI, cleanup, retention, scaling guide.

## Immediate Next Sprint Candidates
- Add pytest coverage (centrality ranking, incremental fusion, vector metrics) ✔ (planned here)
- Add eval harness stub with placeholder metrics
- Correlation ID middleware propagation across services
- Cache hit/miss counters + exposure endpoint

## KPI Tracking File Layout (Proposed)
```
/metrics
  retrieval_eval_history.json
  fusion_stats_history.json
  cache_metrics.log
/eval
  benchmark_questions.json
  run_eval.py
```

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Cross-service schema drift | Runtime 500s | Contract tests & schema version header |
| Centrality fetch latency spike | Slower RAG | Timeout + fallback already present; add metrics & circuit breaker |
| Personalization complexity creep | Delivery delays | Phase gating: start with static weights then iterate |
| Evaluation ground-truth scarcity | Unreliable scores | Bootstrap synthetic Q/A + partial manual curation |

## Exit Criteria for Phase 4
- Critical path tests & eval harness operational
- Observability (latency + cache + centrality metrics) exposed
- Security baseline (authZ checks + rate limiting) in place
- At least one personalization strategy live & measurable

---
## Appendix: Proposed Ranking Strategy Expansion
```
ranking_strategy ∈ { rrf, centrality_augmented, role_weighted, history_boost, l2r_experimental }
```
Each adds an augmentation stage with feature logging to enable later ML ranking.

---
Prepared: 2025-09-25
