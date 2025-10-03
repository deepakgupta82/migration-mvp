# Entity Extraction Architecture

## Overview

The entity extraction system uses a **2-stage adaptive approach** to intelligently extract infrastructure entities and relationships from any document type. The system is designed to handle diverse infrastructure data (servers, databases, networks, cloud resources, applications, etc.) with automatic retry logic and progressive prompt enhancement.

## Architecture Principles

### 1. **Centralized LLM Routing**
- **ALL LLM calls** MUST route through `llm-service` via `/api/llm/process` endpoint
- NO service should make direct calls to OpenAI, Gemini, or Anthropic APIs
- This ensures:
  - Centralized usage tracking
  - Consistent configuration management
  - Unified error handling and retry logic
  - Easier debugging and monitoring

### 2. **Multi-Provider Support**
Supports three LLM providers with automatic normalization:
- **OpenAI** (GPT-4, GPT-3.5-turbo)
- **Google Gemini** (gemini-pro, gemini-1.5-pro)
- **Anthropic Claude** (claude-3, claude-2)

Response formats are normalized across all providers to ensure consistent behavior.

### 3. **Adaptive Extraction Strategy**
The system adapts its extraction strategy based on document analysis:
- Tabular data → Structured extraction with column mapping
- Hierarchical data → Nested entity extraction
- Relationship-heavy data → Focus on connections
- Attribute-heavy data → Detailed property extraction

## 2-Stage Extraction Process

### Stage 1: Document Analysis

**Purpose**: Understand the document structure, type, and optimal extraction strategy.

**Process**:
1. Extract first 2000 characters for analysis
2. Send to LLM with analysis prompt
3. Receive structured analysis:
   ```json
   {
     "document_type": "server_inventory",
     "suggested_entities": ["server", "application", "database"],
     "extraction_strategy": "tabular_structured",
     "confidence": 0.95,
     "key_indicators": ["hostname", "IP address", "OS"],
     "complexity": "medium"
   }
   ```

**Supported Document Types**:
- `server_inventory` - Server/VM inventories with hardware specs
- `network_diagram` - Network topology and device configurations
- `database_schema` - Database catalogs and schemas
- `application_manifest` - Application dependencies and configs
- `cloud_resources` - Cloud infrastructure (AWS, Azure, GCP)
- `storage_config` - Storage systems and volumes
- `security_policy` - Security appliances and policies
- `monitoring_config` - Monitoring and observability systems
- `infrastructure_general` - General infrastructure data
- `mixed_content` - Multiple infrastructure types
- `unknown` - Unable to determine specific type

**Extraction Strategies**:
- `tabular_structured` - CSV/Excel with clear column headers
- `hierarchical_nested` - Nested JSON/YAML configurations
- `relationship_focused` - Emphasis on connections between entities
- `attribute_heavy` - Detailed properties for each entity
- `timeline_based` - Temporal relationships
- `location_based` - Geographic/datacenter distribution
- `mixed_strategy` - Combination approach

### Stage 2: Adaptive Entity Extraction

**Purpose**: Extract entities and relationships using the optimal strategy with retry logic.

**Process**:
1. **Attempt 1**: Use base prompt optimized for detected document type
   - If entities found → SUCCESS
   - If 0 entities → Go to Attempt 2

2. **Attempt 2**: Enhanced prompt with examples
   - Add concrete examples of expected entities
   - More detailed instructions
   - If entities found → SUCCESS
   - If 0 entities → Go to Attempt 3

3. **Attempt 3**: Simplified extraction
   - Ask for ANY entities found (relaxed requirements)
   - Extract even partial information
   - Final attempt

**Progressive Enhancement**:
```
Attempt 1: "Extract all server entities with hostname, IP, OS..."
Attempt 2: "Previous attempt found 0 entities. Here are examples of what to extract: {...} Now extract ALL entities."
Attempt 3: "Extract anything that looks like: servers, databases, applications, networks. Return even partial information."
```

## Component Architecture

### Core Components

#### 1. **LLMServiceClient** (`services/graph-service/app/shared/llm_client.py`)
- Centralized client for all LLM communication
- Handles retry logic (up to 3 attempts with exponential backoff)
- Automatic service discovery via service registry
- Response format normalization (dict vs list handling)
- Timeout management

**Key Methods**:
```python
async def process_request(
    process_type: str,
    prompt: str,
    project_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    timeout: Optional[int] = None
) -> Dict[str, Any]

async def extract_entities(
    content: str,
    document_type: str,
    project_id: Optional[str],
    correlation_id: Optional[str]
) -> Dict[str, Any]

async def analyze_document(
    content: str,
    project_id: Optional[str],
    correlation_id: Optional[str]
) -> Dict[str, Any]
```

#### 2. **AdaptiveEntityExtractor** (`services/graph-service/app/core/entity_extractor.py`)
- Orchestrates 2-stage extraction process
- Manages retry logic with progressive enhancement
- Validates and normalizes extraction results
- Tracks all extraction attempts with detailed metrics

**Key Methods**:
```python
async def extract_from_content(
    content: str,
    project_id: Optional[str],
    filename: Optional[str],
    correlation_id: Optional[str]
) -> EntityExtractionResult
```

**Returns**:
```python
EntityExtractionResult(
    success: bool,
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    total_entities: int,
    total_relationships: int,
    attempts: List[EntityExtractionAttempt],  # All attempts with details
    final_strategy: Optional[str],
    document_analysis: Optional[DocumentAnalysis],
    total_processing_time_ms: int,
    correlation_id: Optional[str]
)
```

#### 3. **Infrastructure Prompts** (`services/graph-service/app/prompts/infrastructure_prompts.py`)
Comprehensive prompt templates for all infrastructure types:

**Document Types**:
- Server Inventory
- Network Infrastructure
- Database Infrastructure
- Cloud Resources
- Applications
- Storage Systems
- Security Infrastructure
- Monitoring Systems

**Prompt Building**:
```python
def build_extraction_prompt(
    document_type: str,
    content: str,
    focus_entities: Optional[List[str]],
    strategy: Optional[str],
    attempt: int = 1,
    max_chars: int = 20000
) -> str
```

#### 4. **Extraction Models** (`services/graph-service/app/models/extraction_models.py`)
Pydantic models for type safety and validation:

- `DocumentAnalysis` - Stage 1 analysis results
- `ExtractionStrategy` - Strategy configuration
- `EntityExtractionAttempt` - Individual attempt record
- `EntityExtractionResult` - Final extraction results
- `InfrastructureEntity` - Standardized entity model
- `InfrastructureRelationship` - Standardized relationship model
- `PromptEnhancement` - Progressive enhancement config

## Entity and Relationship Types

### Supported Entity Types

**Infrastructure Entities**:
- `server` - Physical/virtual servers
- `database` - Database instances
- `application` - Applications and services
- `network_device` - Network equipment
- `storage_system` - Storage arrays and volumes
- `cloud_resource` - Cloud infrastructure
- `container` - Containers and pods
- `virtual_machine` - VMs
- `cluster` - Clusters (K8s, etc.)
- `load_balancer` - Load balancers
- `firewall` - Firewalls and security appliances
- `switch` / `router` - Network devices
- `backup_system` - Backup and DR systems
- `monitoring_system` - Monitoring and observability
- `security_appliance` - Security infrastructure
- `middleware` - Middleware components
- `service` - Microservices
- `endpoint` - API endpoints
- `other` - Other infrastructure types

### Supported Relationship Types

- `connects_to` - Network/application connections
- `depends_on` - Dependencies
- `hosts` - Hosting relationships (server hosts app)
- `runs_on` - Execution relationships (app runs on server)
- `contains` - Containment (cluster contains nodes)
- `backed_up_by` - Backup relationships
- `monitored_by` - Monitoring relationships
- `protected_by` - Security relationships
- `routes_through` - Routing relationships
- `replicates_to` - Replication relationships
- `manages` - Management relationships
- `communicates_with` - Communication relationships
- `part_of` - Membership relationships

## Integration Points

### 1. Graph Processor Integration
Updated `graph_processor.py` to use adaptive extractor:
```python
async def extract_entities_from_document(
    self,
    project_id: str,
    document_content: str,
    filename: str,
    document_id: str,
    correlation_id: Optional[str] = None
) -> EntityExtractionResult:
    # Uses AdaptiveEntityExtractor
    extractor = get_entity_extractor()
    result = await extractor.extract_from_content(...)
    # Converts to legacy Entity/Relationship format
    return EntityExtractionResult(...)
```

### 2. LLM Service Integration
All extraction requests flow through:
```
graph-service → llm_client → llm-service → LLM providers
```

### 3. WebSocket Progress Updates
Real-time progress now flows to Assessment UI:
```
FileUpload.tsx → handleProcessingMessage → addLog (Assessment Context)
```

All processing events now update both:
- Log viewer (existing)
- Assessment UI (NEW - Fix #9)

## Configuration

### Environment Variables

**Graph Service**:
```bash
# LLM Client Configuration
SERVICE_REGISTRY_URL=http://localhost:8011
LLM_SERVICE_URL=http://localhost:8007  # Optional, can use service registry

# Entity Extraction
GRAPH_MAX_RETRIES=3
GRAPH_BASE_TIMEOUT_SECONDS=180
GRAPH_MAX_TIMEOUT_SECONDS=600
```

**LLM Service**:
```bash
# Provider Configuration
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...

# Enforcement
ENFORCE_PROJECT_LLM=false  # Set to true to require project-scoped configs

# Usage Tracking
USAGE_PROMPT_MAX_CHARS=12000
USAGE_RESPONSE_MAX_CHARS=12000
```

## Usage Tracking

### Enhanced Usage Records
All LLM calls now include:
```json
{
  "project_id": "...",
  "correlation_id": "...",
  "provider": "openai",
  "model": "gpt-4",
  "prompt": "truncated prompt (12k chars)",
  "response": "truncated response (12k chars)",
  "prompt_text": "FULL prompt text for quality review",
  "response_text": "FULL response text for debugging",
  "messages": [...],  // Complete conversation history
  "input_tokens": 1250,
  "output_tokens": 450,
  "total_tokens": 1700,
  "cost_usd_cents": 5,
  "duration_ms": 2345,
  "status": "success",
  "metadata": {
    "process_type": "entity_extraction",
    "document_type": "server_inventory",
    "extraction_strategy": "tabular_structured",
    "attempts": 1
  }
}
```

## Error Handling

### Retry Strategy
1. **Network Errors**: Retry up to 3 times with exponential backoff (2^attempt seconds)
2. **4xx Errors**: No retry (client error, likely bad prompt)
3. **5xx Errors**: Retry with backoff
4. **Timeout**: Increase timeout on retry (base + 60s per attempt)

### Fallback Behavior
1. **Attempt 1 fails** → Enhance prompt with examples, retry
2. **Attempt 2 fails** → Simplify prompt, ask for any entities, retry
3. **Attempt 3 fails** → Return empty result with detailed failure metadata

### Error Logging
All failures logged with:
- Correlation ID for tracing
- Attempt number
- Error type and message
- Prompt used (truncated)
- Processing time
- Provider and model

## Best Practices

### For Document Processing Services

1. **Always pass correlation_id** for request tracing
2. **Use specific document types** when known (improves extraction quality)
3. **Truncate large content** before sending (max 20k chars recommended)
4. **Handle empty results gracefully** (some documents may have 0 extractable entities)
5. **Check extraction metadata** for attempt count and strategy used

### For Prompt Engineering

1. **Be specific about entity attributes** (especially for infrastructure data)
2. **Provide examples** in prompts for better accuracy
3. **Use structured output format** (JSON with clear schema)
4. **Test with various document types** to validate robustness
5. **Monitor extraction success rate** and adjust prompts

### For Multi-Provider Support

1. **Normalize response formats** (some providers return dict, others list)
2. **Handle markdown code blocks** in LLM responses
3. **Set appropriate timeouts** per provider (Claude is slower)
4. **Test with all 3 providers** to ensure compatibility
5. **Use provider-specific optimizations** when needed

## Monitoring and Debugging

### Key Metrics
- **Entity extraction success rate** (attempts = 1 vs > 1)
- **Average entities per document type**
- **Processing time by document type and strategy**
- **Retry rate** (what % need multiple attempts)
- **Provider usage distribution**
- **Error rate by provider**

### Correlation ID Tracing
Every request has a correlation ID that flows through:
1. Document Service → Graph Service
2. Graph Service → LLM Service  
3. LLM Service → LLM Provider
4. Usage tracking records
5. WebSocket progress updates
6. Assessment UI logs

Use correlation ID to:
- Trace end-to-end request flow
- Debug extraction failures
- Analyze processing times
- Review LLM usage for specific documents

### Debug Logging
Enable debug logging to see:
```python
logger.debug(f"[{correlation_id}] Document analysis: type={doc_type}, strategy={strategy}")
logger.debug(f"[{correlation_id}] Attempt {attempt}: entities={len(entities)}, rels={len(relationships)}")
logger.debug(f"[{correlation_id}] Extraction complete: success={success}, time_ms={time_ms}")
```

## Migration from Old System

### Changes Required

**Before (Direct LLM Calls)**:
```python
# DON'T DO THIS
response = await openai_client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)
```

**After (Centralized Routing)**:
```python
# DO THIS
from app.shared.llm_client import get_llm_client

llm_client = get_llm_client()
result = await llm_client.extract_entities(
    content=content,
    document_type="server_inventory",
    project_id=project_id,
    correlation_id=correlation_id
)
```

### Backward Compatibility

The new system maintains backward compatibility by:
1. Converting new extraction results to legacy `Entity` and `Relationship` models
2. Preserving existing `EntityExtractionResult` interface
3. Supporting existing cache keys and Redis storage
4. Maintaining same Neo4j graph structure

## Future Enhancements

### Planned Improvements
1. **Fine-tuned models** for infrastructure entity extraction
2. **Streaming extraction** for very large documents
3. **Multi-document context** for better relationship extraction
4. **Custom entity types** per project
5. **Confidence scoring** for entities and relationships
6. **Human-in-the-loop** validation for low-confidence extractions
7. **Active learning** to improve prompts based on user feedback

### Under Consideration
- Graph-based relationship inference
- Entity deduplication and canonicalization
- Cross-document entity linking
- Temporal relationship tracking
- Cost optimization (provider selection based on document complexity)

## References

### Related Documentation
- [LLM Service Architecture](./LLM_SERVICE.md)
- [Graph Service Architecture](./GRAPH_SERVICE.md)
- [WebSocket Events](./WEBSOCKET_EVENTS.md)
- [Usage Tracking](./USAGE_TRACKING.md)

### Code Locations
- LLM Client: `services/graph-service/app/shared/llm_client.py`
- Entity Extractor: `services/graph-service/app/core/entity_extractor.py`
- Prompts: `services/graph-service/app/prompts/infrastructure_prompts.py`
- Models: `services/graph-service/app/models/extraction_models.py`
- Graph Integration: `services/graph-service/app/core/graph_processor.py`
- UI Integration: `frontend/src/components/FileUpload.tsx`

---

**Last Updated**: October 3, 2025  
**Version**: 2.0 (2-Stage Adaptive Extraction)
