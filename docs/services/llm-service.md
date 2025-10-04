# LLM Service

## Service Overview

The LLM Service is a centralized language model orchestration service that operates on port 8007. It provides unified access to multiple LLM providers, handles request routing, rate limiting, caching, and response processing. The service supports both streaming and non-streaming responses, with comprehensive logging and monitoring.

### Key Features

- **Multi-Provider Support**: Integration with OpenAI, Anthropic, Google Gemini, and local models
- **Project-Level LLM Configuration**: Each project configures its own LLM provider, model, and API keys
- **Process-Specific Overrides**: Support for different models per process type (entity extraction, RAG synthesis, etc.)
- **Intelligent Orchestration**: Smart model selection based on task type, content characteristics, and complexity
- **Request Orchestration**: Dynamic routing based on project configuration
- **Rate Limiting**: Configurable rate limits per user/tenant
- **Response Caching**: Redis-based caching for repeated queries
- **Streaming Support**: Real-time streaming responses
- **Cost Tracking**: Usage monitoring and cost analysis with per-request cost calculation
- **Fallback Handling**: Graceful degradation to system defaults when project config unavailable
- **Structured Logging**: JSON logging with correlation IDs

## Functionality

### Core Capabilities

1. **LLM Provider Management**
   - Project-level provider configuration (OpenAI, Anthropic, Google Gemini, Ollama)
   - Dynamic provider switching based on project settings
   - Process-specific model selection (e.g., GPT-4o for entity extraction, Claude for synthesis)
   - Cost optimization through intelligent model routing
   - Model version management

2. **Project LLM Configuration (Phase 1)**
   - **3-Tier Configuration Priority**:
     1. Process-specific override (e.g., use Claude for `entity_extraction` in Project A)
     2. Project default LLM config (e.g., GPT-4o for all processes in Project A)
     3. System fallback (environment variables: `DEFAULT_LLM_PROVIDER`, `DEFAULT_LLM_MODEL`)
   - **API Integration**:
     - `GET /api/projects/{project_id}/llm-config` - Fetch project's default LLM configuration
     - `GET /api/llm-config/{project_id}/llm-process-configs` - Fetch process-specific overrides
   - **Configuration Fields**: provider, model, api_key, temperature, max_tokens, config_id, source
   - **ModelConfigFetcher**: Async HTTP client for fetching project configs with 5s timeout

3. **New Process Types (Phase 1)**
   - `schema_discovery`: Discover document structure and schema (recommended: Claude 3.5 Sonnet, GPT-4o)
   - `adaptive_extraction`: Extract entities adaptively based on document type (recommended: GPT-4o, Claude 3.5 Sonnet)
   - `relationship_inference`: Infer relationships between entities (recommended: Claude 3.5 Sonnet, GPT-4o)
   - `domain_classification`: Classify migration documents by type (recommended: GPT-4o-mini, Claude Haiku)
   - Plus existing: `entity_extraction`, `crew_assessment`, `crew_documentation`, `rag_synthesis`, `hybrid_search`

4. **Request Processing**
   - Prompt engineering and optimization
   - Context window management
   - Token counting and limits
   - Response post-processing

5. **Caching and Performance**
   - Semantic caching for similar queries
   - Response compression and optimization
   - Background processing for heavy operations

6. **Monitoring and Analytics**
   - Usage statistics and performance metrics
   - Cost tracking per user/project (calculated per-request based on token usage)
   - Error rate monitoring
   - Response quality analysis

#### Usage Tracking (Implemented)
- All LLM calls executed via `LLMProcessor.process_llm_request` emit best‑effort usage records to the Project Service (`/api/usage/llm-calls`).
- Fields: provider, model, prompt/response (truncated), token estimates, total tokens, duration_ms, status, error_message, correlation_id, project_id (when available), metadata (e.g., process_type).
- Non‑blocking client with short timeouts; failures are swallowed to avoid impacting request latency.
- Configure via environment:
  - `PROJECT_SERVICE_URL` (default `http://localhost:8002`)
  - `SERVICE_AUTH_TOKEN` (default `service-backend-token`)
  - `USAGE_PROMPT_MAX_CHARS` (default `12000`)
  - `USAGE_RESPONSE_MAX_CHARS` (default `12000`)

Verification on Windows PowerShell:
- Ensure project-service (8002) and llm-service (8007) are running.
- Run `test_llm_usage.ps1` from repo root. It calls `/api/llm/process` and then queries `/api/usage/llm-calls` by correlation_id.

### Dependencies

- **PostgreSQL**: Configuration and usage data storage
- **Redis**: Caching and rate limiting
- **LLM Providers**: OpenAI, Anthropic, etc. (configured per project)
- **Stats Service**: Usage statistics reporting

## APIs/Endpoints

### Core LLM Operations
- `POST /api/llm/process` - Process LLM requests (requires `project_id`)
- `POST /api/llm/orchestrate` - **NEW (Phase 1)**: Intelligent multi-model orchestration with cost optimization
- `POST /api/llm/stream` - Streaming LLM responses
- `GET /api/llm/models` - List available models
- `GET /api/llm/providers` - List configured providers
- `GET /api/llm/providers/status` - Get provider status and configuration info

### Intelligent Orchestration (Phase 1)
`POST /api/llm/orchestrate` - Smart model selection and optimization

**Request**:
```json
{
  "task_type": "entity_extraction",
  "content": "Document text to process...",
  "project_id": "project-123",  // REQUIRED
  "context_size": 5000,
  "has_images": false,
  "has_diagrams": false,
  "complexity": "moderate",  // simple|moderate|complex|very_complex
  "preferred_model": null,  // Optional: override project config
  "temperature": 0.1,
  "max_tokens": 4000
}
```

**Response**:
```json
{
  "success": true,
  "result": { /* extracted entities */ },
  "model_used": "gpt-4o",
  "provider": "openai",
  "tokens": {
    "prompt": 1200,
    "completion": 350,
    "total": 1550
  },
  "cost_usd": 0.00465,
  "duration_ms": 2350,
  "attempts": 1,
  "error": null
}
```

**Features**:
- Fetches project LLM config automatically
- Supports process-specific model overrides
- Calculates cost per request (OpenAI, Anthropic, Gemini pricing)
- Automatic retry on failure (configurable)
- Performance tracking and logging

### Configuration Management
- `POST /api/llm/config` - Update LLM configuration
- `GET /api/llm/config/{project_id}` - Get project configuration
- `GET /api/llm/resolve` - Resolve process configuration without instantiating LLM
- `POST /api/llm/providers/{provider}/health` - Check provider health

### Analytics and Monitoring
- `GET /api/llm/usage` - Get usage statistics
- `GET /api/llm/costs` - Get cost analytics
- `GET /api/llm/performance` - Get performance metrics
  
Note: Usage records are queried from Project Service (`/api/usage/llm-calls`), not from llm-service.

## Data Models

### LLM Request Structure
```json
{
  "process_type": "rag_synthesis",
  "prompt": "Analyze this document...",
  "project_id": "project_123",
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

### LLM Response Structure
```json
{
  "success": true,
  "response": "Analysis result...",
  "model": "gpt-4",
  "tokens_used": 150,
  "processing_time": 2.3,
  "cost": 0.003,
  "cached": false
}
```

### Configuration Structure
```json
{
  "project_id": "project_123",
  "provider": "openai",
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 2000,
  "rate_limit": 100,
  "cache_enabled": true,
  "fallback_providers": ["anthropic"]
}
```

## Key Components

### ModelConfigFetcher (`app/core/model_router.py`) - **NEW (Phase 1)**

**Project LLM configuration fetcher**

- **Responsibilities**:
  - Fetch project-level LLM configuration from backend/project services
  - Support process-specific model overrides
  - Implement 3-tier fallback strategy (process → project → system)
  - Async HTTP client with timeout handling

- **Key Methods**:
  - `get_project_llm_config(project_id, process_type)` - Fetch config with fallback chain
  - `select_model(project_id, process_type, fallback_model)` - Select optimal model
  - Returns `LLMConfig` dataclass with provider, model, api_key, temperature, max_tokens

- **Integration**:
  - Uses `httpx.AsyncClient` for non-blocking API calls
  - 5-second timeout for config fetching
  - Service-to-service auth via `SERVICE_AUTH_TOKEN`
  - Graceful fallback to environment variables if API unavailable

### LLMOrchestrator (`app/core/llm_orchestrator.py`) - **UPDATED (Phase 1)**

**Intelligent LLM orchestration engine**

- **Responsibilities**:
  - Coordinate LLM calls with project configuration
  - Smart model selection based on task type and complexity
  - Automatic retry logic with configurable attempts
  - Cost calculation and performance tracking
  - Token usage monitoring

- **Key Changes (Phase 1)**:
  - **Removed**: Hardcoded `ModelRouter` with MODEL_PROFILES and TASK_PREFERENCES
  - **Added**: `ModelConfigFetcher` for dynamic project config
  - **Required**: `project_id` parameter for all orchestrate calls
  - **Enhanced**: Per-request cost calculation based on provider pricing

### LLMProcessor (`app/core/llm_processor.py`)

**Core LLM orchestration engine**

- **Responsibilities**:
  - Provider management and request routing
  - Rate limiting and quota management
  - Response caching and optimization
  - Error handling and fallback logic

### LLM Router (`app/routers/llm.py`)

**FastAPI router for LLM operations**

- **Responsibilities**:
  - HTTP endpoint definitions
  - Request validation and authentication
  - Response streaming and formatting
  - Error handling and logging

### Config Client (`app/core/config_client.py`)

**Configuration management**

- **Responsibilities**:
  - Centralized configuration retrieval
  - Environment-specific settings
  - Dynamic configuration updates

## Data Flow

### Request Processing Flow

1. **Request Reception**: LLM request received via API
2. **Authentication**: User/project validation
3. **Configuration Lookup**: Project-specific LLM settings retrieved
4. **Rate Limiting**: Check and enforce rate limits
5. **Cache Check**: Check for cached responses
6. **Provider Selection**: Choose appropriate LLM provider
7. **Request Execution**: Send request to LLM provider
8. **Response Processing**: Format and cache response
9. **Usage Tracking**: Record usage statistics
10. **Response Delivery**: Return result to client

## Complete Working Details

### Configuration

**Environment Variables**:
- `LLM_DEFAULT_PROVIDER`: Default LLM provider
- `LLM_CACHE_TTL`: Cache TTL in seconds
- `LLM_RATE_LIMIT`: Default rate limit per minute
- `LLM_MAX_TOKENS`: Maximum tokens per request

### Supported Providers

- **OpenAI**: GPT-3.5, GPT-4, GPT-4-turbo
- **Anthropic**: Claude-2, Claude-instant
- **Local Models**: Self-hosted model support

### Performance Characteristics

- **Response Time**: 1-5 seconds for typical requests
- **Throughput**: Configurable rate limits per user
- **Caching**: Up to 80% cache hit rate for repeated queries
- **Concurrent Requests**: Async processing for high concurrency

### Error Handling

- **Provider Failures**: Automatic fallback to alternative providers
- **Rate Limits**: Graceful throttling with retry logic
- **Invalid Requests**: Detailed validation and error messages
- **Network Issues**: Retry logic with exponential backoff

### Monitoring and Observability

- **Health Checks**: Provider connectivity monitoring
- **Metrics**: Response times, error rates, usage statistics
- **Logging**: Structured JSON logging with correlation IDs
- **Cost Tracking**: Real-time cost monitoring per project

### Security Considerations

- **API Key Management**: Secure key storage and rotation
- **Input Validation**: Prompt sanitization and safety checks
- **Access Control**: Project-scoped LLM access
- **Audit Logging**: All LLM interactions logged

### Scaling Considerations

- **Horizontal Scaling**: Stateless design supports multiple instances
- **Provider Load Balancing**: Intelligent request distribution
- **Caching**: Redis cluster support for high availability
- **Rate Limiting**: Distributed rate limiting across instances

## Prompt Templates (New)

Phase 1 externalized templates are stored under `services/llm-service/prompts/` and loaded at runtime via `app/core/prompt_loader.py`.

- `rag_synthesis.json` — variables: `question`, `context_block`
- `content_summarization.json` — variables: `focus_type`, `evidence_block`, `max_summary_tokens`
- `table_extraction.json` — variables: `hint`, `context_text`, `vision_segment`, `image_urls_block`
- `diagram_understanding.json` — variables: `hint`, `context_text`, `vision_segment`, `image_urls_block`
- `enrich_header.json` — base header for `/enrich` endpoint enforcing strict JSON output (no variables)

Notes:
- If a template is missing, the router (`app/routers/llm.py`) uses a resilient inline fallback to preserve behavior.
- Edit these templates from the UI: Settings → LLM Prompts → select `llm-service`.

### Loader and Reload

- Loader: `app/core/prompt_loader.py` maintains an in-memory cache.
- Reload endpoint: `POST /admin/prompts/reload` to hot-reload files into memory.
- The central backend also supports `POST /api/prompts/llm-service/reload` which forwards to this service.

## APIs/Endpoints

Core endpoints unchanged. Prompt-driven flows include:
- `process_type = "rag_synthesis"` → uses `rag_synthesis.json`
- Card summarization (internal): uses `content_summarization.json`
- Multimodal tables: uses `table_extraction.json`
- Multimodal diagrams: uses `diagram_understanding.json`
- Enrich endpoint: prepends `enrich_header.json` and appends mode-specific JSON schema inline

## Configuration

Environment variables commonly used with these templates:
- `LLM_MAX_TOKENS` (global cap)
- Per-request variables are injected by the router when composing final prompts.

## How to Edit Prompts

- Open Settings → LLM Prompts → Service: `llm-service`.
- Select a template, click Edit, update purpose/description/variables/text.
- Save: Writes JSON atomically and best-effort commits to git.
- The UI triggers a reload so changes apply without restart.

## File Structure

- Templates: `services/llm-service/prompts/*.json`
- Loader: `services/llm-service/app/core/prompt_loader.py`
- Router using templates: `services/llm-service/app/routers/llm.py`

## Observability

- Health: `GET /health`
- Logs include correlation ids and prompt-template ids used for traceability.