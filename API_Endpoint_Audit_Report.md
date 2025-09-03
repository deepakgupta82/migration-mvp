# API Endpoint Audit and Optimization Report

**Date:** September 3, 2025

**Auditor:** GitHub Copilot

## 1. Executive Summary

Overall, the API landscape is functional and reasonably consistent, centered on an API Gateway pattern. Key issues observed:
- Naming/productization inconsistencies, notably the Document Service exposing non-/api-prefixed routes while others use /api.
- Duplicate/canonical routes (e.g., trailing-slash variants) and overlapping domain responsibilities (Document Service “analysis” vs. Analytics Service analysis).
- Multiple “health” endpoints across services without a single normalized contract.
- Gateway-proxied endpoints duplicate direct service endpoints, which is expected but requires clear canonical usage guidance.
- A small set of endpoints appear unreferenced from the frontend and not clearly used by inter-service calls; these are candidates for deprecation after verification.

Benefits of addressing these:
- Reduced ambiguity and support load, faster onboarding.
- Clearer service boundaries, better maintainability.
- Safer refactoring using aliasing/redirects to avoid breaking changes.
- Easier observability and governance (consistent health schemas, versioning).

## 2. Methodology

- Reviewed API_ENDPOINTS.md and API_ENDPOINTS_DOCUMENTATION.md end-to-end.
- Simulated codebase scan:
  - Gateway and each microservice route definitions (FastAPI style).
  - Frontend calls (central ApiService and component usages listed in the docs).
  - Inter-service HTTP calls and common client patterns.
- Checks performed: conflicts, duplicates, naming inconsistencies, service-to-service divergence, unused endpoints (with confidence and evidence), all with “no breaking changes” constraint.

## 3. Endpoint Conflicts and Ambiguities

| Issue Type | HTTP Method | Endpoint Path | Service(s) Involved | Description of Conflict/Ambiguity | Recommendation |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Ambiguous canonical path | GET/POST/PUT/DELETE | `/api/projects` and `/api/projects/` | API Gateway | Both trailing and non-trailing slash variants documented. Duplicates are benign but increase surface area. | Keep both but make non-slash canonical; add 308 redirect from `/api/projects/` to `/api/projects` to avoid breaking clients. Document canonical form. |
| Overlapping “analysis” domain | POST/GET | Document Service: `/{project_id}/analysis*` vs Analytics Service: `/api/analysis*` | Document Service, Analytics Service | Two services expose “analysis” endpoints with potentially overlapping intent (doc-level vs. cross-project analytics). | Clarify scope and naming in paths: keep existing endpoints but add aliasing: Document Service → `/api/documents/{project_id}/analysis*` (alias); Analytics → keep `/api/analysis*`. Update docs to differentiate. |
| Potential confusion: content vs. download | GET | Document Service: `/{project_id}/content/{filename}` vs Storage Service: `/api/storage/.../download/.../{filename}` | Document, Storage | One returns content details, the other returns file bytes, but names are similar. | Add explicit alias and docs: Document → `/api/documents/{project_id}/content/{filename}/details` (alias); keep original. Update descriptions to emphasize semantics. |
| Non-/api prefix vs /api prefixed | multiple | Document Service endpoints at root (e.g., `/{project_id}/upload`) | Document Service | All other services use `/api/...`; Document Service is inconsistent, causing client and proxy rules complexity. | Add `/api/documents` alias for all Document Service endpoints; keep original paths for compatibility. Document canonical use. |
| LLM operation surfaces in two places | POST | Document Service: `/{project_id}/llm-analyze/{filename}` vs LLM Service: `/api/llm/analyze` | Document, LLM | Similar logical action (LLM analysis) exposed via two services; different payloads (doc vs text), can confuse consumers. | Keep both, clarify contract: Document = document-scoped LLM workflows; LLM = text-level operations. Add explicit names/aliases: Document → `/api/documents/{project_id}/llm-analyze/{filename}` (alias). |

## 4. Duplicate Endpoints and Redundancies

| Issue Type | HTTP Method | Endpoint Path(s) (Primary) | Service(s) Involved | Other Redundant Paths/Methods | Description of Redundancy | Recommendation |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| Canonical duplication via gateway | All | Gateway `/api/projects*` | API Gateway, Project Service | Project Service `/api/projects*` | Same resources via gateway and direct service (by design). | Document gateway as the canonical public interface; keep service endpoints for internal/service-to-service use. Consider network policy to restrict external access to service ports. |
| Health endpoints replicated | GET | `/health` | Most services | Gateway `/api/health` (aggregate) | Multiple `/health` across services is expected, but schemas may vary. | Keep service `/health` but standardize JSON schema and add `/healthz` alias; keep gateway `/api/health` aggregator. |
| Trailing slash duplicates | GET | `/api/projects` and `/api/projects/` | Gateway | Same route semantics | Duplicate route forms. | Prefer one canonical route and 308 redirect from the other, as above. |

## 5. Similar Endpoints and Naming Inconsistencies

| Current Endpoint Examples (Method + Path) | Problem Description | Proposed Standardization / Best Practice |
| :-- | :-- | :-- |
| Document Service `POST /{project_id}/process-all`, `POST /{project_id}/process-selected`, Gateway `POST /api/projects/{id}/process-documents` | Mixed naming verbs and scope (“process-all/selected” vs. “process-documents”) | Adopt a single resource: `POST /api/documents/process` with body `{ projectId, mode: all|selected, files?: [...] }`. Keep all existing endpoints, add new alias in Gateway and Document Service, document canonical form. |
| Document Service lacks `/api` prefix (e.g., `/{project_id}/upload`) | Inconsistent with other services using `/api/...` | Add non-breaking aliases under `/api/documents/...` to mirror existing ones; update docs to promote `/api/documents/...` canonical naming. |
| Graph vs Vector vs Stats names use plural forms consistently; Document uses mixed nouns (`content`, `insights`, `analysis`) | Category conventions vary, increasing cognitive load | Resource-oriented naming with plural where appropriate, e.g., `/api/documents/{project_id}/files`, `/api/documents/{project_id}/analyses`, `/api/documents/{project_id}/insights`. Add aliases; keep originals. |
| LLM endpoints: Document’s `llm-analyze` vs LLM service `analyze` | Redundant “llm-” qualifier on one, not the other | Keep both; consider aliasing Document to `/api/documents/{project_id}/analysis/llm/{filename}` to clarify domain-specific action. |
| Storage download vs document content | Similar terms for different semantics | Use explicit suffixes (`/download/...` vs `/content/.../details`) and document clearly, add alias as above. |

## 6. Inconsistent Service-to-Service Communication Patterns

| Calling Service | Called Service | Functionality | Inconsistent Call Pattern 1 | Inconsistent Call Pattern 2 | Recommendation |
| :-- | :-- | :-- | :-- | :-- | :-- |
| Gateway | Project Service | Project CRUD | `GET /api/projects{,/}` | also accepts both trailing/non-trailing | Normalize Gateway to call a single canonical form (no trailing slash). Internally keep service tolerant. |
| Document Service | LLM Service | Text/doc analysis | Exposes `/{project_id}/llm-analyze/{filename}` (proxy-ish) | Directly calling `POST /api/llm/analyze` for raw text | Keep service-to-service calls direct to LLM service. If Document exposes a higher-level endpoint, ensure it orchestrates internally and doesn’t duplicate LLM logic. |
| Various services | Storage Service | File I/O | Some craft storage URLs directly; others route via Gateway | Mixed patterns risk bypassing auth/caching | Define policy: Service-to-service calls should go direct to the owning service (Storage), not via Gateway, unless cross-cutting concerns (auth, audit) are required. Document this and enforce in clients. |

Note: To finalize pattern checks, query the Service Registry for the active service list and (optionally) scrape each service’s OpenAPI to verify URL usage is consistent.

## 7. Unused Endpoints (Candidates for Safe Removal)

Caveat: These are candidates based on (a) no reference in documented frontend mappings, and (b) typical service responsibilities. Before action, confirm via code search and Service Registry/OpenAPI usage logs. No deletions recommended without alias+deprecation cycle.

| HTTP Method | Endpoint Path | Service(s) Defined In | Justification for Removal (Evidence of Non-Usage) | Confidence |
| :-- | :-- | :-- | :-- | :-- |
| GET | `/api/gateway/debug` | API Gateway | Listed as “Development only”; not referenced in frontend mappings; typically unsafe for prod. | High (retain behind dev flag if needed) |
| GET | `/{project_id}/insights` | Document Service | Not referenced in frontend mapping; may be legacy. No obvious dependency from other services in docs. | Medium |
| GET | `/workflow-config` | Document Service | No frontend references; purpose overlaps with internal configs. | Medium |
| POST | `/{project_id}/analyze-batch`, GET `/{project_id}/content-analysis/{analysis_id}` | Document Service | Not referenced in frontend; could be internal batch flows; verify scheduler/workers. | Low |
| POST | `/api/llm/models/{model_id}/load` | LLM Service | Dynamic model load not referenced in frontend; could be used by admin/internal jobs. | Low |
| GET | `/api/projects/{project_id}/files` (and related) | Project Service | Frontend uses Storage Service for file listing; Project Service file endpoints look redundant/legacy. | Medium (validate no service calls) |
| GET | `/api/stats/projects/{project_id}/activity` | Stats Service | Only “stats-fast” appears in Dashboard mapping via Gateway; activity endpoint may be unused. | Low |

Action path for each “candidate”:
- Instrument and log usage for 2–4 weeks.
- If zero hits, mark deprecated in docs and telemetry.
- Add 410 Gone feature flag path behind config in non-prod.
- Remove after deprecation window; keep aliases if warranted.

## 8. General Recommendations and Best Practices

- Canonical interface
  - External clients: API Gateway only.
  - Service-to-service: call owning services directly (not via Gateway) unless you need gateway cross-cutting concerns; document exceptions.
- Path normalization
  - Add `/api/documents/...` aliases for all Document Service routes; keep legacy paths.
  - Enforce a trailing-slash policy with 308 redirects (keep both forms working).
  - Prefer plural, resource-oriented names; add explicit action subresources where needed.
- Versioning
  - Introduce non-breaking `/api/v1/...` aliases at Gateway for all public endpoints; keep unversioned as legacy. Start publishing changelogs for v2 plans.
- Health and readiness
  - Standardize service health to `/healthz` (readiness) and `/livez` (liveness) with a consistent JSON schema; keep `/health` as alias.
  - Gateway aggregates remain at `/api/health` and `/api/services/health`.
- Documentation governance
  - Generate OpenAPI per service and aggregate via Gateway; publish a single Portal page.
  - Add “canonical/alias/legacy” labels beside each endpoint in docs.
  - Automate drift checks (CI step that compares OpenAPI to docs).
- Deprecation policy
  - 1–2 release cycles with deprecation headers (`Deprecation`, `Sunset`), response warnings, and docs badges.
  - Provide compatibility redirects/aliases to avoid breaks.
- Service Registry usage
  - On startup, each service registers its base URL and OpenAPI URL with the Service Registry.
  - Gateway periodically refreshes service routes from the registry for health and discovery.
- Security
  - Ensure Gateway-only exposure on public networks; restrict direct service ports at the edge/VNet.
  - Unify auth headers and correlation ID propagation across all intra-service calls.

---

Notes and next steps
- To finalize “unused” classification, query the local Service Registry for the active services and scrape each service’s OpenAPI; correlate with gateway logs and frontend ApiService usage to compute real call frequency.
- If desired, add the non-breaking `/api/documents/...` aliases and the 308 redirects in the Document Service and Gateway, plus a doc patch marking canonical vs. legacy paths.
