# REVISED Implementation Plan: Migration-Focused LLM-Augmented Document Processing

**Date**: October 4, 2025  
**Status**: Revised based on platform requirements  
**Branch**: `enhance_doc_processing`

---

## 🎯 Alignment with Migration Assessment Platform

### Key Changes from Original Plan:

1. **LLM Configuration Integration**
   - ❌ Remove hardcoded multi-model routing
   - ✅ Integrate with existing project-level LLM configuration system
   - ✅ Support process-specific LLM configs (entity_extraction, crew_assessment, etc.)
   - ✅ Use project's default LLM config unless overridden per-process

2. **Domain Templates Refocus**
   - ❌ Remove generic domains (organizational, financial, legal, process)
   - ✅ Focus on migration assessment document types only
   - ✅ Align with typical client deliverables in migration projects

3. **Prompt Management Integration**
   - ❌ Remove hardcoded prompts in Python files
   - ✅ Surface all prompts via Settings → LLM Prompts UI
   - ✅ Store prompts as JSON files (per existing pattern)
   - ✅ Enable hot-reload when prompts are edited

---

## 📋 Migration Assessment Document Types

Based on typical client deliverables in migration projects:

### 1. **Infrastructure Inventory Documents**
   - Server inventories (Excel, CSV, Word tables)
   - Network diagrams (Visio, PDFs with diagrams)
   - Application catalogs
   - Database lists
   - **Entities**: Server, Application, Database, NetworkDevice, IP, Port

### 2. **Dependency Mapping Documents**
   - Application dependency matrices
   - Integration diagrams
   - Data flow documents
   - API specifications
   - **Entities**: Application, Dependency, Integration, API, DataFlow

### 3. **Assessment Questionnaires**
   - Technical questionnaires
   - Business process questionnaires
   - Security assessment forms
   - Compliance checklists
   - **Entities**: Question, Answer, Requirement, Risk, Compliance

### 4. **As-Is Architecture Documents**
   - Current state architecture diagrams
   - Technical specifications
   - Configuration files
   - Deployment guides
   - **Entities**: Component, Architecture, Configuration, Deployment

### 5. **Migration Strategy Documents**
   - Migration plans
   - Risk assessments
   - Cost estimates
   - Timeline documents
   - **Entities**: MigrationWave, Risk, Cost, Timeline, Milestone

### 6. **Technical Specifications**
   - Infrastructure specs
   - Application requirements
   - Performance baselines
   - Capacity planning
   - **Entities**: Specification, Requirement, Metric, Capacity

---

## 🔧 Existing Systems to Integrate With

### 1. **LLM Configuration System** (Already Exists)

**Location**: `backend/app/routers/llm_config_router.py`

**Current Process-Specific Configurations**:
```python
class LLMProcessType(Enum):
    ENTITY_EXTRACTION = "entity_extraction"
    CREW_ASSESSMENT = "crew_assessment"
    CREW_DOCUMENTATION = "crew_documentation"
    RAG_SYNTHESIS = "rag_synthesis"
    HYBRID_SEARCH = "hybrid_search"
```

**How It Works**:
- Each project has a default LLM configuration (`llm_provider`, `llm_model`, `llm_api_key_id`)
- Projects can have process-specific overrides stored in `llm_process_configs` field
- API endpoints:
  - `GET /api/{project_id}/llm-process-configs` - Get all process configs
  - `PUT /api/{project_id}/llm-process-configs` - Update process configs
  - `GET /api/llm-recommendations/{process_type}` - Get recommended models for process

**Integration Plan**:
- Add new process types for schema discovery and adaptive extraction
- Orchestrator should fetch project's LLM config instead of routing to different models
- Support process-specific overrides per project

### 2. **Prompt Management System** (Already Exists)

**Location**: `backend/app/routers/prompts_router.py`

**Current Prompt Structure** (JSON files):
```json
{
  "id": "prompt_id",
  "service": "service-name",
  "purpose": "Brief description",
  "description": "Detailed description",
  "variables": ["var1", "var2"],
  "text": "The actual prompt template with {{variable}} placeholders",
  "version": 1
}
```

**Prompt Locations**:
- `services/graph-service/prompts/*.json`
- `services/document-service/prompts/*.json`
- `services/llm-service/prompts/*.json` (to be added)

**UI Access**: Settings → LLM Prompts (`/settings/llm-prompts`)

**Integration Plan**:
- Move all Phase 1 & 2 prompts to JSON files
- Create prompt JSONs for:
  - Schema discovery
  - Entity extraction (per document type)
  - Relationship inference
  - Domain classification
- Enable editing via UI

---

## 📝 Revised Phase Breakdown

### Phase 1 (REVISED): LLM Configuration Integration

**Goal**: Integrate orchestrator with existing LLM configuration system

#### 1.1 Remove Hardcoded Model Routing

**Files to Modify**:
- `services/llm-service/app/core/model_router.py`
  - Remove hardcoded routing rules
  - Simplify to: get project's LLM config → use that model
  - Keep failover logic (same model, retry with backoff)

**Changes**:
```python
# OLD:
if task_type == "entity_extraction":
    return "claude-3-5-sonnet-20241022"
elif has_images:
    return "gpt-4o"

# NEW:
# Get project's LLM config (with optional process-specific override)
config = await get_project_llm_config(project_id, process_type="entity_extraction")
return config["model"]
```

#### 1.2 Add New Process Types

**Files to Modify**:
- `backend/app/core/llm_factory.py`
- Add new process types:
  - `SCHEMA_DISCOVERY = "schema_discovery"`
  - `ADAPTIVE_EXTRACTION = "adaptive_extraction"`
  - `RELATIONSHIP_INFERENCE = "relationship_inference"`

#### 1.3 Update Orchestrator to Use Project Config

**Files to Modify**:
- `services/llm-service/app/core/llm_orchestrator.py`
  - Add `project_id` parameter (required)
  - Add `process_type` parameter (optional)
  - Fetch project's LLM config via HTTP call to backend
  - Use configured model instead of routing logic

**New Flow**:
```python
async def orchestrate(
    task_type: str,
    content: str,
    project_id: str,  # NEW: Required
    process_type: Optional[str] = None,  # NEW: Optional override
    ...
):
    # 1. Fetch project's LLM config
    config = await fetch_project_llm_config(project_id, process_type)
    
    # 2. Use configured model
    model = config["model"]
    provider = config["provider"]
    api_key = config["api_key"]
    
    # 3. Call LLM with project's config
    result = await call_llm(provider, model, api_key, content)
```

#### 1.4 Expose Process-Specific Config in UI

**Frontend Changes** (Optional - can be Phase 6):
- Add UI to configure process-specific LLM models in Project Settings
- Show available processes: schema_discovery, adaptive_extraction, etc.
- Allow users to override default for specific processes

---

### Phase 2 (REVISED): Migration-Focused Domain Templates

**Goal**: Refocus domain templates on migration assessment document types

#### 2.1 Replace Generic Domains with Migration Domains

**Files to Modify**:
- `services/llm-service/app/core/adaptive_prompts.py`

**Old Domains**:
```python
DOMAIN_TEMPLATES = {
    "infrastructure": ...,
    "organizational": ...,
    "financial": ...,
    "legal": ...,
    "process": ...
}
```

**New Domains** (Migration-Focused):
```python
MIGRATION_DOCUMENT_TYPES = {
    "infrastructure_inventory": {
        "description": "Server inventories, network diagrams, application catalogs",
        "typical_entities": ["Server", "Application", "Database", "NetworkDevice"],
        "typical_attributes": ["name", "ip_address", "os", "environment", "location"],
        "examples": [...]
    },
    "dependency_mapping": {
        "description": "Application dependencies, integration diagrams, data flows",
        "typical_entities": ["Application", "Dependency", "Integration", "API"],
        "typical_attributes": ["name", "depends_on", "integration_type", "protocol"],
        "examples": [...]
    },
    "assessment_questionnaire": {
        "description": "Technical questionnaires, assessment forms, compliance checklists",
        "typical_entities": ["Question", "Answer", "Requirement", "Risk"],
        "typical_attributes": ["question_id", "category", "response", "severity"],
        "examples": [...]
    },
    "architecture_document": {
        "description": "As-is architecture diagrams, technical specs, deployment guides",
        "typical_entities": ["Component", "Architecture", "Configuration", "Deployment"],
        "typical_attributes": ["component_type", "configuration", "deployment_model"],
        "examples": [...]
    },
    "migration_strategy": {
        "description": "Migration plans, risk assessments, cost estimates, timelines",
        "typical_entities": ["MigrationWave", "Risk", "Cost", "Timeline", "Milestone"],
        "typical_attributes": ["wave_number", "risk_level", "estimated_cost", "target_date"],
        "examples": [...]
    },
    "technical_specification": {
        "description": "Infrastructure specs, performance baselines, capacity planning",
        "typical_entities": ["Specification", "Requirement", "Metric", "Capacity"],
        "typical_attributes": ["spec_type", "requirement", "baseline", "capacity"],
        "examples": [...]
    }
}
```

#### 2.2 Update Document Classifier

**Files to Modify**:
- `services/graph-service/app/core/document_classifier.py`

**Changes**:
```python
class DocumentDomain(str, Enum):
    # Old: infrastructure, organizational, financial, legal, process
    
    # New (Migration-Focused):
    INFRASTRUCTURE_INVENTORY = "infrastructure_inventory"
    DEPENDENCY_MAPPING = "dependency_mapping"
    ASSESSMENT_QUESTIONNAIRE = "assessment_questionnaire"
    ARCHITECTURE_DOCUMENT = "architecture_document"
    MIGRATION_STRATEGY = "migration_strategy"
    TECHNICAL_SPECIFICATION = "technical_specification"
    UNKNOWN = "unknown"
```

---

### Phase 3 (NEW): Prompt Management Integration

**Goal**: Move all prompts to JSON files and surface via Settings UI

#### 3.1 Create Prompt JSON Files

**Location**: `services/llm-service/prompts/`

Create JSON files for each prompt:

1. **`schema_discovery_base.json`**:
```json
{
  "id": "schema_discovery_base",
  "service": "llm-service",
  "purpose": "Discover entity schema from migration documents",
  "description": "Analyzes migration assessment documents to discover entity types, attributes, and relationships",
  "variables": ["content", "document_type"],
  "text": "Analyze this {{document_type}} document and discover its schema...",
  "version": 1
}
```

2. **`entity_extraction_infrastructure.json`**:
```json
{
  "id": "entity_extraction_infrastructure",
  "service": "llm-service",
  "purpose": "Extract infrastructure entities from inventory documents",
  "description": "Extracts servers, applications, databases, and network devices",
  "variables": ["content", "schema"],
  "text": "Extract infrastructure entities from this document using the schema:\n{{schema}}\n\nDocument:\n{{content}}",
  "version": 1
}
```

3. **`entity_extraction_dependency.json`**
4. **`entity_extraction_questionnaire.json`**
5. **`entity_extraction_architecture.json`**
6. **`entity_extraction_migration.json`**
7. **`entity_extraction_specification.json`**

8. **`relationship_inference.json`**:
```json
{
  "id": "relationship_inference",
  "service": "llm-service",
  "purpose": "Infer relationships between extracted entities",
  "description": "Analyzes entity context to infer implicit relationships",
  "variables": ["entities", "document_type"],
  "text": "Given these entities:\n{{entities}}\n\nInfer relationships between them...",
  "version": 1
}
```

#### 3.2 Create Prompt Loader in LLM Service

**New File**: `services/llm-service/app/utils/prompt_loader.py`

```python
"""Prompt loader for LLM service"""
import os
import json
from typing import Dict, Any, Optional

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

def load_prompt(prompt_id: str) -> Optional[Dict[str, Any]]:
    """Load prompt from JSON file"""
    prompt_file = os.path.join(PROMPTS_DIR, f"{prompt_id}.json")
    if not os.path.exists(prompt_file):
        return None
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_prompt_text(prompt_id: str, variables: Optional[Dict[str, str]] = None) -> str:
    """Load prompt and substitute variables"""
    prompt_data = load_prompt(prompt_id)
    if not prompt_data:
        raise FileNotFoundError(f"Prompt {prompt_id} not found")
    
    text = prompt_data.get("text", "")
    
    if variables:
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            text = text.replace(placeholder, str(var_value))
    
    return text
```

#### 3.3 Update AdaptivePromptBuilder to Use JSON Prompts

**Files to Modify**:
- `services/llm-service/app/core/adaptive_prompts.py`

**Changes**:
```python
# OLD: Hardcoded prompts
DOMAIN_TEMPLATES = {
    "infrastructure": "Extract infrastructure entities...",
    ...
}

# NEW: Load from JSON
from app.utils.prompt_loader import get_prompt_text

class AdaptivePromptBuilder:
    def build_entity_extraction_prompt(
        self,
        content: str,
        domain: str,
        schema: Optional[Dict] = None
    ) -> str:
        # Load prompt from JSON
        prompt_id = f"entity_extraction_{domain}"
        
        variables = {
            "content": content,
            "schema": json.dumps(schema, indent=2) if schema else "No schema provided"
        }
        
        return get_prompt_text(prompt_id, variables)
```

#### 3.4 Enable Hot-Reload of Prompts

**Implementation**:
- Prompts are loaded from disk on each request (no caching)
- Changes to JSON files are immediately reflected
- No service restart needed

---

### Phase 4 (REVISED): Schema Discovery with Configurable LLM

**Goal**: Update schema discovery to use project's LLM config

#### 4.1 Update SchemaDiscoveryEngine

**Files to Modify**:
- `services/graph-service/app/core/schema_discovery.py`

**Changes**:
```python
async def discover_schema(
    self,
    content: str,
    document_type: str,  # NEW: Use migration doc type
    project_id: str,  # NEW: Required for LLM config
    correlation_id: Optional[str] = None
) -> DocumentOntology:
    # 1. Load prompt from JSON
    prompt = get_prompt_text(
        "schema_discovery_base",
        {"content": content, "document_type": document_type}
    )
    
    # 2. Call orchestrator with project_id
    result = await llm_client.orchestrate(
        task_type="schema_discovery",  # Maps to process type
        content=prompt,
        project_id=project_id,  # NEW: Required
        correlation_id=correlation_id
    )
```

#### 4.2 Update API Endpoint

**Files to Modify**:
- `services/graph-service/app/routers/graphs.py`

**Changes**:
```python
@router.post("/api/graphs/discover-schema")
async def discover_schema_endpoint(request: Request):
    data = await request.json()
    
    # Extract request params
    project_id = data["project_id"]  # Required
    content = data["content"]
    document_type = data.get("document_type", "infrastructure_inventory")
    
    # Discover schema
    engine = SchemaDiscoveryEngine()
    ontology = await engine.discover_schema(
        content=content,
        document_type=document_type,
        project_id=project_id
    )
```

---

### Phase 5 (REVISED): Adaptive Extraction with Configurable LLM

**Goal**: Update adaptive extraction to use project's LLM config and JSON prompts

#### 5.1 Update AdaptiveEntityExtractor

**Files to Modify**:
- `services/graph-service/app/core/adaptive_entity_extractor.py`

**Changes**:
```python
async def extract_entities(
    self,
    content: str,
    ontology: DocumentOntology,
    document_type: str,  # NEW: Migration doc type
    project_id: str,  # NEW: Required for LLM config
    correlation_id: Optional[str] = None,
    use_hybrid: bool = True
) -> ExtractionResult:
    # 1. Load document-type-specific prompt
    prompt_id = f"entity_extraction_{document_type}"
    prompt = get_prompt_text(
        prompt_id,
        {
            "content": content,
            "schema": json.dumps(ontology.to_dict(), indent=2)
        }
    )
    
    # 2. Call orchestrator with project_id
    result = await llm_client.orchestrate(
        task_type="adaptive_extraction",
        content=prompt,
        project_id=project_id,
        correlation_id=correlation_id
    )
```

---

### Phase 6: UI Integration (Optional - Can be done later)

**Goal**: Surface new configurations in UI

#### 6.1 Add Process-Specific LLM Config UI

**Location**: Project Settings → LLM Configuration

**Features**:
- Show process types: schema_discovery, adaptive_extraction, etc.
- Allow override of default LLM config per process
- Test configuration per process

#### 6.2 Enhance Prompt Management UI

**Already Exists**: Settings → LLM Prompts

**Enhancements**:
- Group prompts by document type
- Show variables for each prompt
- Preview prompt with sample variables
- Version history (if needed)

---

## 🔄 Migration Path from Current Implementation

### What to Keep

1. ✅ **Core Architecture**:
   - LLM orchestrator structure
   - Schema discovery engine
   - Adaptive entity extractor
   - Pattern extractors
   - Ontology models

2. ✅ **Key Features**:
   - Multi-strategy extraction (LLM + patterns)
   - Hybrid deduplication
   - Confidence scoring
   - Source tracking

### What to Change

1. ❌ **Model Routing** → ✅ **Project LLM Config**:
   - Remove MODEL_PROFILES
   - Remove TASK_PREFERENCES
   - Remove routing rules
   - Add project config fetching

2. ❌ **Hardcoded Prompts** → ✅ **JSON Prompts**:
   - Move DOMAIN_TEMPLATES to JSON files
   - Add prompt_loader utility
   - Update prompt builders to load from JSON

3. ❌ **Generic Domains** → ✅ **Migration Domains**:
   - Replace domain enum
   - Update document classifier
   - Create migration-specific prompts

---

## 📊 Implementation Timeline (Revised)

### Week 1: LLM Configuration Integration
- ✅ Remove hardcoded routing
- ✅ Add project LLM config fetching
- ✅ Update orchestrator to use project config
- ✅ Add new process types
- ✅ Test with existing project configs

### Week 2: Migration Domain Templates
- ✅ Define migration document types
- ✅ Update document classifier
- ✅ Create migration-specific entity schemas
- ✅ Update schema discovery for migration docs

### Week 3: Prompt Management Integration
- ✅ Create JSON prompt files
- ✅ Add prompt_loader utility to llm-service
- ✅ Update adaptive_prompts to load from JSON
- ✅ Test prompt editing via UI

### Week 4: Schema Discovery Updates
- ✅ Update schema discovery to use prompts
- ✅ Update schema discovery to use project LLM config
- ✅ Test with migration documents

### Week 5: Adaptive Extraction Updates
- ✅ Update adaptive extraction to use prompts
- ✅ Update adaptive extraction to use project LLM config
- ✅ Test end-to-end with migration documents

### Week 6: Testing & Documentation
- ✅ Integration tests with real migration documents
- ✅ Performance testing
- ✅ Update documentation
- ✅ User guide for prompt customization

---

## 🎯 Success Criteria (Revised)

### Functional
1. ✅ Orchestrator uses project's LLM configuration (not hardcoded routing)
2. ✅ All prompts editable via Settings → LLM Prompts UI
3. ✅ Schema discovery works for all 6 migration document types
4. ✅ Adaptive extraction uses document-type-specific prompts
5. ✅ Process-specific LLM configs supported (optional per project)

### Technical
1. ✅ No hardcoded models in code
2. ✅ All prompts in JSON files
3. ✅ Hot-reload of prompts without service restart
4. ✅ Integration with existing LLM config system
5. ✅ Backward compatible with existing projects

### User Experience
1. ✅ Users can customize prompts without code changes
2. ✅ Users can configure different models per process (optional)
3. ✅ Clear documentation for prompt variables
4. ✅ Examples for each migration document type

---

## 📋 Next Steps

1. **Review and Approve** this revised plan
2. **Start with Phase 1** (LLM Configuration Integration)
3. **Test incrementally** after each phase
4. **Update documentation** as we go
5. **Deploy to production** after Phase 5

---

## 🤔 Open Questions

1. **Process Types**: Should we add more process types beyond the 5 existing ones?
   - Current: entity_extraction, crew_assessment, crew_documentation, rag_synthesis, hybrid_search
   - Proposed: Add schema_discovery, adaptive_extraction, relationship_inference

2. **Prompt Versioning**: Do we need version control for prompts beyond what's in the JSON?
   - Current: Simple version number in JSON
   - Needed: Git-based versioning (already exists via auto-commit)

3. **Default Prompts**: Should we provide default prompts for all document types, or just examples?
   - Proposal: Provide defaults for all 6 migration document types
   - Users can customize via UI

4. **Multi-Model Support**: Do we want to support having different models for different processes in the same project?
   - Current: Possible via process-specific configs
   - Proposal: Surface this in UI for power users

---

**Ready to proceed with revised implementation?**

I'll start with Phase 1 (LLM Configuration Integration) once you approve this plan.
