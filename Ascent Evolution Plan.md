# Nagarro's Ascent: Cloud Migration Command Center - Refactoring Master Plan (Executable Version)

## 1. Executive Vision: From Report Generator to AI Co‑pilot

This plan evolves Ascent from document assessment into an AI-powered Cloud Migration Command Center.

Architecture principles
- Knowledge-first, microservice-oriented.
- Hybrid agentic model:
  - CrewAI (or crews) for deterministic deliverables.
  - Microsoft AutoGen (AgentChat) for interactive co-pilot with HITL via WebSocket.
- Ground-truth data ingestion:
  - AWS Migration Evaluator, Azure Migrate (later), AWS Documentation MCP server.
- Alignment with platform standards:
  - Centralized logging/metrics, WebSocket streaming, environment-configurable settings in UI, service health/readiness, JWT/CORS.

Global cross-cutting concerns
- Configuration (populate .env and expose to UI settings):
  - GRAPH_SERVICE_URL, LLM_SERVICE_URL, MINIO_*, NEO4J_*, AUTOGEN_MODEL, WEBSOCKET_MAX_CLIENTS, CORS_ALLOWED_ORIGINS, SERVICE_TOKEN (svc-to-svc), DOC_MAX_FILE_MB
- Logging/metrics:
  - JSON logs; /health and /metrics (Prometheus) on all services.
- Security:
  - JWT or service-token for importer and sync jobs.
  - CORS/WS origins restricted to frontend hostnames.
  - Secrets only via env; no commits.
- Testing:
  - Unit and integration tests for new services.
  - New end-to-end tests for ingest → graph → agent → IaC path.
- CI:
  - Build, lint, test all services and new submodule; run contract tests for HTTP/WS.

Note on LLM
- llm-service exists in services and is the single gateway for all model calls. All agent/tool code must call llm-service over HTTP (no direct provider calls from other services). Prefer an OpenAI-compatible /v1/chat/completions surface.

---

## Phase 1: Supercharge the Knowledge Core

Objective
- Improve knowledge quality by ingesting structured data and high-fidelity document parsing.

Key files and services
- services/document-service/app/core/document_processor.py
- services/document-service/requirements.txt
- New: services/data-importer-service/
- New: services/aws-data-service/ (wrapper around AWS Documentation MCP)
- services/graph-service/app/core/graph_processor.py (ensure idempotent upserts)
- docker-compose.yml (add new services, health checks)
- scripts/bootstrap_mcp.(sh|ps1), scripts/sync/aws_data_sync.(py|ps1)

Step-by-step

1) Upgrade Document Intake Engine
- Change:
  - Add unstructured[all] to services/document-service/requirements.txt.
  - Replace markitdown/PDF fallback in _perform_conversion_sync with unstructured.partition.auto to preserve headers, lists, tables.
- Verification:
  - Complex PDFs produce clean Markdown in MinIO, including tables and lists.
- Risks:
  - unstructured[all] increases image size; consider slim extras for production.

2) Data Importer Microservice
- New service: services/data-importer-service (FastAPI).
- Endpoints:
  - POST /importers/aws/migration-evaluator (CSV upload).
  - POST /importers/azure/migrate (CSV/JSON; Phase 1 can stub or defer).
- Behavior:
  - Parse rows and call graph-service to upsert nodes/edges:
    - POST /graph/assets (servers/apps), POST /graph/dependencies, optional POST /graph/metrics.
  - Service-to-service auth via SERVICE_TOKEN.
- Graph model minimums:
  - Asset node fields: hostname, os, cpu, memory_gb, storage_gb, avg_cpu, avg_mem, env/tags.
  - Dependency edges: source → target, type, weight.
- Verification:
  - Upload an AWS Migration Evaluator CSV; servers appear in Neo4j with metrics.

3) AWS Documentation MCP server as data source
- New service: services/aws-data-service
  - Bring in awslabs/aws-documentation-mcp-server as a git submodule or use the official container image.
  - Expose an HTTP-compatible adapter or wrapper to fetch service/pricing/spec data needed.
- Daily sync job:
  - New lightweight service or scheduled script: services/aws-data-sync (Python) that:
    - Calls aws-data-service to fetch latest pricing/specs.
    - Updates graph via GRAPH_SERVICE_URL (e.g., set current_price_per_hour, graviton_upgrade_equivalent).
  - Schedule: cron in container or external scheduler.
- Verification:
  - After sync, sample EC2 families have current_price_per_hour set on graph nodes.

Dependency changes
- Add: unstructured[all] in document-service.

Deliverables created/modified
- Graph-service endpoints (idempotent upserts).
- Data-importer-service container with health check.
- aws-data-service wrapper and aws-data-sync job with health check and logs.
- Bootstrap scripts to init the MCP submodule or pull container.

---

## Phase 2: Implement the Interactive Architect’s Co‑pilot

Objective
- Introduce Microsoft AutoGen (AgentChat) and create the interactive Strategy & Design team with WebSocket-based chat.

Key files and services
- services/ai-agent-service/requirements.txt
- services/ai-agent-service/app/core/autogen_teams.py (new)
- services/ai-agent-service/app/core/ws_session.py (new session manager)
- services/ai-agent-service/app/routers/agents.py (add WS endpoint)
- frontend/src/views/ProjectDetailView.tsx
- frontend/src/components/project-detail/CoPilotChat.tsx (new)

Step-by-step

1) Add AutoGen dependency (Microsoft AutoGen)
- Add to services/ai-agent-service/requirements.txt:
  - autogen>=0.2.28,<0.3
  - httpx, websockets
- Assume llm-service exposes an OpenAI-compatible API. Configure AutoGen with:
  - config_list: [{ model: AUTOGEN_MODEL, api_key: SERVICE_TOKEN (or dummy), base_url: LLM_SERVICE_URL }]
  - request_timeout, cache_seed as needed.
- If llm-service is not OpenAI-compatible, add a thin adapter in ai-agent-service to proxy OpenAI-style requests to llm-service.

2) Implement “Strategy & Design” AutoGen team
- Agents: UserProxyAgent, AssistantAgent instances: CloudStrategistAgent, LeadArchitectAgent, FinOpsAgent, SecurityAgent.
- Register tool bridges to existing tools where applicable:
  - CloudServiceCatalogTool (service mapping, prerequisites, risks).
  - InfrastructureAnalysisTool (component assessment).
- All LLM calls go through llm-service via AutoGen’s config_list.

3) Co‑pilot WebSocket endpoint
- Path: WEBSOCKET /api/agents/projects/{project_id}/copilot-chat
- Lifecycle:
  - On connect, spin up team and stream messages from all agents.
  - Accept human responses routed to UserProxyAgent.
  - Enforce WEBSOCKET_MAX_CLIENTS; cleanup on disconnect.

4) Co‑pilot UI
- New component CoPilotChat.tsx
  - Connect to WS, render streaming messages, input with send/debounce, backpressure handling, reconnect logic.
- Integrate into ProjectDetailView with feature flag.

Verification
- Opening Co‑pilot connects successfully (101 Switching Protocols).
- Sending a message triggers multi-agent exchange; logs show tool calls.
- User prompts for HITL are rendered correctly.

---

## Phase 3: Automate Migration & Operations

Objective
- Make outputs executable by generating IaC and detailed migration/optimization plans.

Key files and services
- services/ai-agent-service/app/core/autogen_teams.py (extend)
- services/ai-agent-service/app/tools/iac_generator_tool.py (new)
- services/ai-agent-service/app/tools/graph_query_tool.py (new)
- frontend/src/views/ProjectDetailView.tsx
- frontend component(s) for IaC generation viewer

Step-by-step

1) “Implementation” team
- Add IaCExpertAgent and MigrationPlannerAgent to autogen_teams.py (AutoGen agents).
- Inputs: architecture JSON (from prior analysis/team output/graph).
- Outputs: Terraform .tf text and plan summary.

2) IaC Generation Tool
- iac_generator_tool.py:
  - Accepts structured architecture JSON.
  - Calls llm-service with few-shot prompt to produce Terraform following best practices (modules, variables, tags, naming, region).
  - Validates basic syntax pre-return (optional tflint in CI).
- Use LLM_SERVICE_URL; no direct provider SDKs elsewhere.

3) “Optimization” crew
- FinOpsAgent + OpsAdvisor using graph_query_tool.py.
- Reads cost and performance data (from importer + MCP sync) to propose savings:
  - Rightsizing, Graviton upgrades, storage tiering, reserved/savings plans candidates, idle assets.
- Output structured optimization recommendations, with projected savings.

Verification
- IaC generation yields a valid .tf (passes formatter/lint in CI).
- Optimization crew identifies concrete savings when MCP data present.

---

## Phase 4: Evolve the User Interface for the Full Lifecycle

Objective
- Provide a seamless user journey across phases.

Key files
- frontend/src/views/ProjectDetailView.tsx
- New frontend components per phase

Step-by-step

1) Phase Selector UI
- Component to switch between the six phases with persistent URL state.

2) Contextual workspaces
- Phases 1–2: CoPilotChat.tsx.
- Phases 3–4: IaC workspace
  - Buttons: “Generate Terraform Plan”, “Download”, “Copy”, “Validate”.
  - Read-only code viewer for generated IaC.
- Phases 5–6: MCP report upload + optimization dashboard (top savings, actions).

Verification
- Phase switching updates content; proper API/WS calls fire.
- IaC actions invoke Implementation team and render code.

---

## New and changed endpoints (contract)

graph-service
- POST /graph/assets: upsert asset node (idempotent by hostname or external_id).
- POST /graph/dependencies: upsert dependency edge.
- POST /graph/metrics: attach time-sliced metrics to asset.
- GET /graph/assets/{id}: retrieve asset with properties.
- Auth: Bearer SERVICE_TOKEN.

data-importer-service
- POST /importers/aws/migration-evaluator (multipart/form-data: file)
- POST /importers/azure/migrate (optional for Phase 1)
- Health: GET /health
- Auth: Bearer SERVICE_TOKEN.

aws-data-service (MCP wrapper)
- GET /health
- Internal APIs or wrapper endpoints to fetch service/pricing/spec data required by sync job.

ai-agent-service
- WEBSOCKET /api/agents/projects/{project_id}/copilot-chat
- POST /api/agents/projects/{project_id}/iac (optional REST trigger)
- GET /health

llm-service
- POST /v1/chat/completions (OpenAI-compatible), with {model, messages, temperature, tools?}
- Health: GET /health

---

## Docker and ops

docker-compose.yml
- Add services:
  - data-importer-service (uvicorn, port 8095)
  - aws-data-service (MCP server wrapper, port e.g. 8081)
  - aws-data-sync (cron-like sidecar or simple loop with sleep)
- Health checks for all services, network aliases, persistent volumes as needed.
- Environment:
  - GRAPH_SERVICE_URL, LLM_SERVICE_URL, SERVICE_TOKEN, etc.

Bootstrap scripts
- scripts/bootstrap_mcp.sh or .ps1:
  - Initialize git submodule awslabs/aws-documentation-mcp-server or pull official image.
  - Build/start aws-data-service.
- scripts/sync/aws_data_sync.py:
  - Fetch pricing/specs → upsert into graph.
  - Log summary and errors; exit non-zero on failures (for CI observability).

---

## Testing and CI

Test suites to add (you removed old tests)
- Unit tests:
  - document-service: conversion of representative PDFs to Markdown.
  - data-importer-service: CSV parsing to API payloads; graph upsert calls mocked.
  - ai-agent-service: tools (IaCGeneratorTool, graph_query_tool) logic with llm-service mocked.
- Integration tests:
  - Importer → graph roundtrip using a test Neo4j or mocked persistence layer.
  - ai-agent-service WebSocket flow (AutoGen team): open WS, exchange a few messages, assert content shape.
  - IaC generation endpoint: returns .tf and passes a basic regex/syntax check.
- End-to-end (optional CI job):
  - Start minimal stack; upload sample CSV → check asset exists; invoke IaC → receive TF.

CI updates
- Initialize submodules.
- Build all images.
- Run black/flake8/mypy (Python), ESLint (frontend).
- Run tests; publish coverage.

---

## Files to create or modify (summary)

Backend
- services/document-service/requirements.txt (add unstructured[all])
- services/document-service/app/core/document_processor.py (switch to unstructured)
- services/data-importer-service/ (new FastAPI service: main.py, routers, tests, Dockerfile, requirements.txt)
- services/aws-data-service/ (MCP wrapper: Dockerfile, submodule init or image reference)
- services/aws-data-sync/ (new: sync job code, Dockerfile, requirements)
- services/graph-service/app/core/graph_processor.py (ensure idempotent upserts + new endpoints)
- services/ai-agent-service/requirements.txt (add autogen>=0.2.28,<0.3, websockets, httpx)
- services/ai-agent-service/app/core/autogen_teams.py (new; Microsoft AutoGen AgentChat)
- services/ai-agent-service/app/core/ws_session.py (new)
- services/ai-agent-service/app/tools/iac_generator_tool.py (new)
- services/ai-agent-service/app/tools/graph_query_tool.py (new)
- services/ai-agent-service/app/routers/agents.py (add WS route)
- services/llm-service/ (confirm OpenAI-compatible /v1/chat/completions; document contract)
- docker-compose.yml (add services, envs, health checks)
- scripts/bootstrap_mcp.(sh|ps1) (new)
- scripts/sync/aws_data_sync.py (new)

Frontend
- frontend/src/views/ProjectDetailView.tsx (phase selector/workspaces; hook CoPilotChat and IaC views)
- frontend/src/components/project-detail/CoPilotChat.tsx (new)
- Optional new components for IaC viewer and optimization dashboard

Tests
- tests/ (new tree for unit/integration)
  - tests/document-service/
  - tests/data-importer-service/
  - tests/ai-agent-service/
  - tests/e2e/

---

## Verification checklist

Phase 1
- PDF → Markdown fidelity improved (tables/lists/headings).
- AWS Migration Evaluator CSV import creates/updates assets with metrics.
- Graph nodes enriched with pricing/specs after MCP sync.

Phase 2
- WebSocket connects; multi-agent messages stream; tool usage appears in logs.
- Human-in-the-loop prompts visible and actionable in UI.

Phase 3
- IaC .tf generated via llm-service; passes basic validation in CI.
- Optimization crew outputs ranked, actionable savings.

Phase 4
- Phase selector toggles workspaces; correct components render and call APIs.
- IaC workspace supports generate/copy/download/validate.

---

Design notes and trade-offs
- Microsoft AutoGen (AgentChat) used instead of pyautogen; pinned to >=0.2.28,<0.3 to align with current APIs and maintenance.
- MCP server integrated via submodule or official image to avoid copying code; wrapper adds health/observability.
- All LLM calls centralized via llm-service to control cost, tracing, and provider configuration.