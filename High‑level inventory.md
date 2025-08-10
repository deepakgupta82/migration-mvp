High‑level inventory
Core services
backend (FastAPI, agent orchestration, RAG, graph, docs): backend/app/main.py (large monolith), core services in backend/app/core/*
project-service (FastAPI, SQLAlchemy/PostgreSQL, JWT, platform settings, templates, LLM configs): project-service/main.py (+ auth.py, database.py, schemas.py)
reporting-service (FastAPI, Pandoc via pypandoc, MinIO): reporting-service/main.py
MegaParse (third-party doc parsing service): MegaParse/Dockerfile and own project
Frontend
React + TypeScript (Mantine UI), multiple views and contexts under frontend/src
Infra and tooling
docker-compose.yml (all services), docker-compose.*.yml variants
k8s manifests (k8s/*.yaml)
terraform skeleton for aws/azure
Windows-first scripts: build/start/setup/health-check PowerShell and batch scripts
Common package (for enterprise patterns): common/* folders (auth, adapters, CQRS, DI, logging, middleware)
Extensive docs: PROJECT_STRUCTURE.md, README.md, WINDOWS_SETUP.md, OVERVIEW, ENTERPRISE_ARCHITECTURE.md, etc.
Tests/diagnostics scripts: multiple Python and PowerShell “test_*” utilities for services, LLM configs, end-to-end checks
Logs directory wired through services; platform.log, agents.log, database.log, etc.
Architecture alignment with your stated preferences
Windows-first development: Yes (PowerShell scripts, health checks, optimized build scripts)
Real services, no mocks: Yes (PostgreSQL, Neo4j, Weaviate, MinIO, MegaParse)
Document generation with Pandoc/LaTeX and MinIO placement: Yes (reporting-service, pypandoc, LaTeX path tweaks), though see issues below
Event-driven/logging: Good logging to files; stats/event pattern present in backend (websocket_stats_manager.py, stats_service.py)
Command Center UI with Mantine tabs, logs, graph, templates, LLM configuration: Present in frontend structure
JWT and service-to-service: project-service has JWT; service tokens supported for S2S; backend client currently uses a static service token; see gaps below
Correlation IDs: Not fully implemented/visible; source for correlation middleware is missing (only .pyc present)
Key strengths
Clear separation of services with Docker Compose orchestration
Rich logging strategy (platform, agents, database, docker-streaming to files, WebSocket updates)
Database-backed LLM configurations with CRUD and cache endpoints in project-service
Reporting service writes to MinIO and updates project state; sanitizes LaTeX content
Semantic chunking and embedding service implementations exist and are reasonably sophisticated
Frontend thoughtfully split into views/contexts/components aligned with Command Center UX
Priority findings and risks
Inconsistent vector database strategy (Weaviate vs ChromaDB)
Compose runs Weaviate (+ transformers inference), README/docs describe Weaviate.
Backend data‑clearing endpoint explicitly manipulates ChromaDB collections on disk (./data/chroma_db).
RAGService likely diverges from Weaviate usage; this mismatch will confuse deployments, tests, and maintenance, and breaks the “never downgrade” principle.
Reporting → Project-service authorization missing
reporting-service updates the project via PUT /projects/{id} without Authorization header.
project-service endpoints use Depends(get_current_user) and will reject unauthenticated requests.
Current behavior likely fails except in legacy unsecured modes; violates your JWT/S2S policy. Suggested minimal fix:
Add Authorization header when reporting-service calls project-service (use SERVICE_AUTH_TOKEN or a proper signed service JWT). Example:

main.py
reporting-service
  headers = {"Content-Type": "application/json",
             "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN','service-backend-token')}"}
  resp = requests.put(f"{PROJECT_SERVICE_URL}/projects/{project_id}", json=update_data, headers=headers, timeout=30)
Correlation ID missing end-to-end
common/middleware only has compiled .pyc; correlation.py source is absent and I do not see middleware being added to FastAPI apps.
No propagation of X-Correlation-ID headers from backend client calls to other services.
This gaps your stated requirement: end-to-end transaction tracking via correlation IDs.
Backend main.py is very large and monolithic
~4,800 lines; endpoints, logging, WebSocket log fanout, service checks, LLM testing, graph calls, and data-clearing all in one file.
Risks maintainability and correctness; hard to test. Router modularization is recommended.
Reporting service LaTeX dependency path is user-specific
It injects a Windows user-local MiKTeX path into PATH. This will break in containers and other machines.
Dockerfile should install a LaTeX engine (e.g., texlive) and rely on PATH in the container, not a host-specific path.
Duplicate function definitions in reporting-service
_update_project_report_url is defined twice with different signatures; later definition overrides the earlier one.
This is harmless at runtime but confusing; remove the earlier one.
JWT/service-to-service strategy incomplete
project-service/auth supports both new jwt_service and legacy tokens, and creates a service user for S2S.
backend ProjectServiceClient uses a static SERVICE_AUTH_TOKEN. reporting-service does not use Authorization at all.
To align with your policy, switch S2S to signed JWTs (short-lived) and deprecate static tokens cleanly.
Frontend/node_modules committed
frontend/node_modules is present in the repo. Your preference is to keep dependencies out of git via .gitignore; this repo should be cleaned to avoid heavy clones and conflicts.
Graph tooling and MCP integrations verification pending
Your preferences mention GraphQueryTool/HybridSearchTool/LessonsLearnedTool and AWS/Azure MCP Server integration. I didn’t find these specific classes by name in the quick pass. This likely needs verification/implementation or updating references.
MegaParse integration surface
Compose and service entries exist, and backend references MegaParse ports; we should verify the precise workflow from document upload → parse → embeddings → graph to ensure it’s wired consistently with chosen vector store and stats/events.
Additional observations
project-service
Uses SQLAlchemy models and migrations folder; also creates tables on startup. Ensure migrations are authoritative (avoid both create_tables on boot and Alembic-style migrations fighting each other).
LLM model cache endpoints and seeding present. Good for immediate UX.
Backend LLM test endpoint
Dynamically uses openai, google.generativeai, anthropic libraries. Ensure these are in backend/requirements.txt.
Graph API
Direct cypher usage in GraphService; node/edge mapping uses relationship.type. Validate driver API for relationship type accesses.
Recommendations (prioritized)
Decide and unify the vector store
Option A (Weaviate): Ensure RAGService and all embed/search/clear-data paths use Weaviate clients; remove ChromaDB references, or keep Chroma as optional fallback behind a feature flag. Keep Compose with Weaviate.
Option B (ChromaDB): Remove Weaviate services from Compose, update docs; standardize RAGService, indexing, clearing, and search to ChromaDB and reflect in UI copy.
Given your stated preference for a stable alternative to Weaviate, Option B may align better, but confirm before changes.
Enforce service-to-service auth and correlation IDs
Implement correlation ID middleware in all FastAPI apps, ensure each outbound request includes X-Correlation-ID; log it everywhere.
Switch backend and reporting-service clients to include Authorization: Bearer , signed by a shared issuer with short TTL and service roles.
Keep legacy service token temporarily only for backward compatibility during transition.
Fix reporting-service → project-service authorization immediately
Add Authorization header to update calls (minimal change). Later swap to proper service JWT.
Make reporting-service container-safe for LaTeX/Pandoc
Install texlive/latex packages in the reporting-service Dockerfile; remove hardcoded user PATH injection. Add a start-up self-check that logs pypandoc and latex availability.
Backend refactor to routers
Extract:
/api/projects/* routers (query, graphs, clear-data, service-status)
/api/llm/* router (llm-configurations, test-llm)
WebSocket/log streaming manager into a separate module/service class
Improves testability and separation of concerns.
Confirm/implement missing tool integrations
Verify existence and usage of GraphQueryTool, HybridSearchTool, LessonsLearnedTool; confirm MCP Server integration for InfrastructureAnalysisTool; implement if missing or update code/docs to remove stale references.
Frontend repo hygiene and UX issues from your preferences
Remove node_modules and build from git; ensure .gitignore configured.
Ensure LLM Config loads immediately (LLMConfigContext already suggests this path); confirm no flicker of deleted state.
System logs UI spacing and control sizes; tabs on same line, reduced whitespace; can be implemented with Mantine props.
Test strategy
Convert key Python “test_*.py” scripts into pytest suites with fixtures for local services.
Add a minimal smoke test per service in CI, plus an end-to-end “quick” mode.
Quick code excerpts for high-impact fixes
reporting-service: add Authorization header (as above)
backend ProjectServiceClient already sets Authorization via SERVICE_AUTH_TOKEN; keep until JWT is in place
Correlation ID propagation pattern (sample client header injection):

project_service.py
backend/app/core
Suggested next steps
Confirm vector DB direction (Weaviate vs Chroma). I recommend we first align code and compose with your chosen option and update the RAGService and clear-data paths accordingly.
Approve minimal auth fix for reporting-service so document generation updates project records reliably.
Approve correlation ID middleware rollout across services and header propagation in all inter-service calls.
Approve plan for backend router refactor (incremental, no behavior change).
Decide whether to remove Weaviate from docker-compose if moving to Chroma, or conversely remove Chroma usage from code.
If you want, I can implement items 2 and 3 (auth header + correlation ID scaffolding) first—they’re small, high-value changes that stabilize cross-service workflows.

Progress and next tasks
Completed: Initial investigation/triage of the codebase.
Immediate next (proposed):
Align on vector store choice and auth/correlation plan.
Implement minimal reporting-service Authorization header.
Add correlation ID middleware and propagate headers in backend and reporting-service clients.