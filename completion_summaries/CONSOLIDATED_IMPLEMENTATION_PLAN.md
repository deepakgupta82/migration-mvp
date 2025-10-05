# 🚀 CONSOLIDATED Implementation Plan: Migration-Focused LLM-Augmented Document Processing

**Version**: 2.0 (Consolidated)  
**Date**: October 4, 2025  
**Status**: Revised Plan - Ready for Implementation  
**Branch**: `enhance_doc_processing`

---

## 📋 Executive Summary

This consolidated plan merges:
1. **Original 6-Week Plan**: Comprehensive feature roadmap (Phases 1-5)
2. **Revised Migration Focus**: Platform-specific alignment with existing LLM config and prompt management

### Key Consolidation Points

**Original Plan Scope:**
- ✅ Multi-model LLM orchestration
- ✅ Adaptive entity extraction
- ✅ Cross-document entity resolution
- ✅ Intelligent relationship inference
- ✅ Testing & documentation

**Revised Alignment:**
- ✅ Use project-level LLM configuration (not hardcoded multi-model routing)
- ✅ Migration-specific document types (not generic domains)
- ✅ JSON-based prompt management (not hardcoded prompts)
- ✅ Integration with existing Settings → LLM Prompts UI

---

## 🎯 Architecture Principles (Updated)

### Service Separation with Platform Integration

```
┌─────────────────────────────────────────────────────────┐
│ LLM-SERVICE                                             │
│ • ALL LLM interactions via project's configured model   │
│ • Prompt loading from JSON files                        │
│ • Process-specific LLM config support                   │
│ • Usage tracking and cost monitoring                    │
│ • Response parsing and validation                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ PROJECT LLM CONFIGURATION (Existing System)             │
│ • Project default: provider, model, api_key             │
│ • Process-specific overrides:                           │
│   - entity_extraction, crew_assessment, etc.            │
│   - schema_discovery (NEW)                              │
│   - adaptive_extraction (NEW)                           │
│ • API: /api/projects/{id}/llm-config                   │
│ • API: /api/llm-config/{id}/llm-process-configs        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ PROMPT MANAGEMENT (Existing System)                     │
│ • JSON-based prompts: services/{service}/prompts/*.json │
│ • Frontend UI: Settings → LLM Prompts                   │
│ • Hot-reload: No service restart needed                 │
│ • API: /api/prompts/{service}/{prompt_id}              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ GRAPH-SERVICE                                           │
│ • Migration document classification                     │
│ • Schema discovery and ontology building                │
│ • Entity extraction orchestration                       │
│ • Relationship inference                                │
│ • Cross-document entity resolution                      │
│ • Neo4j graph operations                                │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 Migration Assessment Document Types

**Platform Context**: This platform is specifically for **migration assessment, discovery, strategy, planning, and execution**.

### Document Types (Replacing Generic Domains)

| Document Type | Typical Content | Key Entities | Relationships |
|--------------|----------------|--------------|---------------|
| **Infrastructure Inventory** | Server lists, network diagrams, app catalogs, DB lists | Server, Application, Database, NetworkDevice, IP, Port | RUNS_ON, CONNECTS_TO, HOSTS |
| **Dependency Mapping** | App dependency matrices, integration diagrams, data flows, API specs | Application, Dependency, Integration, API, DataFlow | DEPENDS_ON, INTEGRATES_WITH, CALLS |
| **Assessment Questionnaire** | Technical questionnaires, business process forms, security assessments, compliance checklists | Question, Answer, Requirement, Risk, Compliance | RELATES_TO, REQUIRES, MITIGATES |
| **Architecture Document** | Current state architecture, technical specs, config files, deployment guides | Component, Architecture, Configuration, Deployment | PART_OF, CONFIGURED_BY, DEPLOYED_TO |
| **Migration Strategy** | Migration plans, risk assessments, cost estimates, timelines | MigrationWave, Risk, Cost, Timeline, Milestone | SCHEDULED_FOR, AFFECTS, MITIGATED_BY |
| **Technical Specification** | Infrastructure specs, performance baselines, capacity planning | Specification, Requirement, Metric, Capacity | SPECIFIES, MEASURES, REQUIRES |

---

## 📅 Consolidated Phase Schedule

### **PHASE 1: LLM Configuration Integration + Foundation** (Week 1-2)
**Goal**: Integrate with project LLM config + Multi-model infrastructure foundation

**Original**: Multi-model orchestration with hardcoded routing  
**Revised**: Use project's configured LLM with process-specific overrides

### **PHASE 2: Migration-Focused Adaptive Extraction** (Week 3)
**Goal**: Dynamic extraction for migration document types

**Original**: Generic domain extraction  
**Revised**: Migration-specific document types with JSON prompts

### **PHASE 3: Prompt Management Integration + Cross-Document Resolution** (Week 4)
**Goal**: JSON-based prompts + Entity linking across documents

**Original**: Cross-document entity resolution only  
**Revised**: Add prompt management integration

### **PHASE 4: Intelligent Relationship Inference** (Week 5)
**Goal**: Build rich, multi-level relationships automatically

**Original**: ✅ Keep as-is (already migration-focused)  
**Revised**: Use project LLM config for inference calls

### **PHASE 5: Testing & Documentation** (Week 6)
**Goal**: Comprehensive testing and documentation

**Original**: ✅ Keep testing strategy  
**Revised**: Add prompt customization guide

---

## 📝 PHASE 1 (REVISED): LLM Configuration Integration + Foundation

### **Objectives**
1. ✅ Remove hardcoded multi-model routing from model_router.py
2. ✅ Integrate with existing project-level LLM configuration system
3. ✅ Support process-specific LLM configs
4. ✅ Add new process types: schema_discovery, adaptive_extraction
5. ✅ Update orchestrator to fetch project's LLM config
6. ✅ Implement migration document classifier (not generic domains)
7. ✅ Add usage tracking for configured models

### **Key Changes from Original Plan**

| Original | Revised |
|----------|---------|
| ❌ Hardcoded MODEL_PROFILES for GPT-4o, Claude, Gemini | ✅ Fetch from project's LLM config |
| ❌ TASK_PREFERENCES routing logic | ✅ Use process-specific LLM config or project default |
| ❌ Generic domains (infrastructure, org, financial, legal, process) | ✅ Migration document types (6 types) |
| ❌ Hardcoded domain examples | ✅ Migration-specific classification |

### **Deliverables**

#### **1.1: Refactor Model Router to Use Project Config**
**Location**: `services/llm-service/app/core/model_router.py`

**OLD (Remove)**:
```python
MODEL_PROFILES = {
    "gpt-4o": {...},
    "claude-3-5-sonnet-20241022": {...},
    "gemini-2.5-pro": {...}
}

TASK_PREFERENCES = {
    "entity_extraction": ["claude-3-5-sonnet-20241022", "gpt-4o"],
    "relationship_inference": ["gpt-4o", "claude-3-5-sonnet-20241022"]
}

def select_model(task_type: str, context_size: int, ...) -> str:
    # Hardcoded routing logic
```

**NEW (Implement)**:
```python
class ModelConfigFetcher:
    """Fetch LLM config from project settings"""
    
    async def get_project_llm_config(
        self,
        project_id: str,
        process_type: Optional[str] = None
    ) -> LLMConfig:
        """
        Fetch LLM configuration from project settings.
        
        Priority:
        1. Process-specific override (if process_type provided)
        2. Project default LLM config
        3. System fallback (if project has no config)
        
        Returns:
            LLMConfig with provider, model, api_key, temperature, max_tokens
        """
        # Call backend API: GET /api/projects/{project_id}/llm-config
        # If process_type: GET /api/llm-config/{project_id}/llm-process-configs
        pass
    
    async def select_model(
        self,
        project_id: str,
        process_type: str,
        fallback_model: Optional[str] = None
    ) -> LLMConfig:
        """
        Get model for specific process type.
        Uses project's configured model, not hardcoded routing.
        """
        config = await self.get_project_llm_config(project_id, process_type)
        
        if not config and fallback_model:
            # Use fallback if project has no config
            config = self.get_system_default_config()
        
        return config
```

**Integration Points**:
- Backend API: `GET /api/projects/{project_id}/llm-config`
- Backend API: `GET /api/llm-config/{project_id}/llm-process-configs`
- Returns: `{provider, model, api_key, temperature, max_tokens, config_id, source}`

#### **1.2: Update LLM Orchestrator to Use Project Config**
**Location**: `services/llm-service/app/core/llm_orchestrator.py`

**Changes**:
```python
class LLMOrchestrator:
    def __init__(self):
        self.config_fetcher = ModelConfigFetcher()
        # Remove: self.model_router = ModelRouter()
    
    async def orchestrate(
        self,
        task_type: str,
        content: str,
        project_id: str,  # NEW: REQUIRED
        process_type: Optional[str] = None,  # NEW: Optional override
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> OrchestrationResult:
        """
        Orchestrate LLM call using project's configured model.
        
        Args:
            project_id: Required - fetch LLM config from this project
            process_type: Optional - use process-specific config override
        """
        # 1. Get project's LLM configuration
        llm_config = await self.config_fetcher.get_project_llm_config(
            project_id=project_id,
            process_type=process_type or task_type
        )
        
        # 2. Use configured model (not routing logic)
        model = llm_config.model
        provider = llm_config.provider
        api_key = llm_config.api_key
        
        # 3. Call LLM with project's config
        result = await self._call_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            content=content,
            **kwargs
        )
        
        # 4. Track usage with model info
        await self._track_usage(
            project_id=project_id,
            model_provider=provider,
            model_name=model,
            tokens=result.tokens,
            cost=result.cost
        )
        
        return result
```

**API Endpoint Update**:
```python
# OLD
POST /orchestrate
{
  "task_type": "entity_extraction",
  "content": "...",
  "prefer_model": "claude-3-5-sonnet"  # Hardcoded preference
}

# NEW
POST /orchestrate
{
  "task_type": "entity_extraction",
  "content": "...",
  "project_id": "uuid",  # REQUIRED
  "process_type": "entity_extraction"  # Optional override
}
```

#### **1.3: Add New Process Types**
**Location**: `backend/app/core/llm_factory.py`

**Changes**:
```python
class LLMProcessType(Enum):
    ENTITY_EXTRACTION = "entity_extraction"
    CREW_ASSESSMENT = "crew_assessment"
    CREW_DOCUMENTATION = "crew_documentation"
    RAG_SYNTHESIS = "rag_synthesis"
    HYBRID_SEARCH = "hybrid_search"
    
    # NEW: Phase 1 & 2 process types
    SCHEMA_DISCOVERY = "schema_discovery"
    ADAPTIVE_EXTRACTION = "adaptive_extraction"
    RELATIONSHIP_INFERENCE = "relationship_inference"
    DOMAIN_CLASSIFICATION = "domain_classification"
```

**Recommended Models** (defaults, can be overridden per project):
```python
PROCESS_MODEL_RECOMMENDATIONS = {
    "schema_discovery": {
        "recommended": "claude-3-5-sonnet-20241022",
        "reason": "Excellent at structure analysis and schema inference"
    },
    "adaptive_extraction": {
        "recommended": "gpt-4o",
        "reason": "Strong entity extraction with structured output"
    },
    "relationship_inference": {
        "recommended": "claude-3-5-sonnet-20241022",
        "reason": "Superior reasoning for implicit relationships"
    },
    "domain_classification": {
        "recommended": "gpt-4o-mini",
        "reason": "Fast and cost-effective for classification"
    }
}
```

#### **1.4: Migration Document Classifier (Revised)**
**Location**: `services/graph-service/app/core/document_classifier.py`

**OLD Domains (Remove)**:
```python
class DocumentDomain(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    ORGANIZATIONAL = "organizational"
    FINANCIAL = "financial"
    LEGAL = "legal"
    PROCESS = "process"
```

**NEW Migration Document Types**:
```python
class MigrationDocumentType(str, Enum):
    """Migration-specific document types"""
    INFRASTRUCTURE_INVENTORY = "infrastructure_inventory"
    DEPENDENCY_MAPPING = "dependency_mapping"
    ASSESSMENT_QUESTIONNAIRE = "assessment_questionnaire"
    ARCHITECTURE_DOCUMENT = "architecture_document"
    MIGRATION_STRATEGY = "migration_strategy"
    TECHNICAL_SPECIFICATION = "technical_specification"
    UNKNOWN = "unknown"

class DocumentClassifier:
    """Classify documents for migration assessment context"""
    
    async def classify(
        self,
        content: str,
        project_id: str,
        correlation_id: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classify document using project's LLM config.
        Uses prompt from JSON file (not hardcoded).
        """
        # Load prompt from JSON
        prompt = get_prompt_text(
            "domain_classification",
            {"content": content[:3000]}  # Sample
        )
        
        # Call orchestrator with project_id
        result = await llm_client.orchestrate(
            task_type="domain_classification",
            content=prompt,
            project_id=project_id,
            correlation_id=correlation_id
        )
        
        return ClassificationResult(
            document_type=result.document_type,
            confidence=result.confidence,
            structure_type=result.structure_type,
            entity_density=result.entity_density
        )
```

**API Endpoint (Updated)**:
```python
POST /api/graphs/classify-document
{
  "project_id": "uuid",  # REQUIRED
  "content": "...",
  "metadata": {...}
}

Response:
{
  "document_type": "infrastructure_inventory",
  "confidence": 0.92,
  "structure_type": "tabular",
  "estimated_entity_count": 150,
  "recommended_strategy": "spreadsheet_extraction"
}
```

### **Files to Create/Modify**

#### **Modified Files** (Refactoring):
1. ✅ `services/llm-service/app/core/model_router.py`
   - Remove hardcoded MODEL_PROFILES
   - Add ModelConfigFetcher class
   - Integrate with project LLM config API

2. ✅ `services/llm-service/app/core/llm_orchestrator.py`
   - Add project_id parameter (required)
   - Add process_type parameter (optional)
   - Remove hardcoded routing
   - Fetch config via API

3. ✅ `services/graph-service/app/core/document_classifier.py`
   - Replace generic domains with migration document types
   - Update classification logic
   - Use project LLM config

4. ✅ `backend/app/core/llm_factory.py`
   - Add new process types (schema_discovery, adaptive_extraction, etc.)

5. ✅ `services/llm-service/app/routers/llm_router.py`
   - Update /orchestrate endpoint signature
   - Require project_id parameter

#### **New Files**:
1. `services/llm-service/app/utils/config_fetcher.py` - HTTP client for project config
2. `services/llm-service/prompts/domain_classification.json` - Classification prompt (NEW)

### **Testing After Phase 1**
```bash
# Test 1: Project LLM config fetching
curl -X GET "http://localhost:8000/api/projects/{project_id}/llm-config"

# Test 2: Process-specific config
curl -X GET "http://localhost:8000/api/llm-config/{project_id}/llm-process-configs"

# Test 3: Orchestrator with project config
curl -X POST "http://localhost:8007/orchestrate" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "domain_classification",
    "content": "Server inventory document...",
    "project_id": "uuid"
  }'

# Test 4: Migration document classification
curl -X POST "http://localhost:8006/api/graphs/classify-document" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "uuid",
    "content": "Infrastructure inventory..."
  }'
```

### **Git Commits**
```bash
# Commit 1: Remove hardcoded routing
git add services/llm-service/app/core/model_router.py
git commit -m "refactor(llm-service): Remove hardcoded model routing, add project config fetcher"

# Commit 2: Update orchestrator
git add services/llm-service/app/core/llm_orchestrator.py
git add services/llm-service/app/routers/llm_router.py
git commit -m "feat(llm-service): Integrate orchestrator with project LLM configuration"

# Commit 3: Add process types
git add backend/app/core/llm_factory.py
git commit -m "feat(backend): Add new process types for schema discovery and adaptive extraction"

# Commit 4: Migration document classifier
git add services/graph-service/app/core/document_classifier.py
git commit -m "feat(graph-service): Update classifier for migration document types"

# Commit 5: Documentation
git add docs/
git commit -m "docs: Update Phase 1 with project LLM config integration"
```

---

## 📝 PHASE 2 (REVISED): Migration-Focused Adaptive Extraction

### **Objectives**
1. ✅ Implement schema discovery for migration document types
2. ✅ Build adaptive entity extractor with project LLM config
3. ✅ Remove hardcoded generic domain prompts
4. ✅ Create migration-specific extraction strategies
5. ✅ Add confidence scoring

### **Key Changes from Original Plan**

| Original | Revised |
|----------|---------|
| ❌ Generic DOMAIN_TEMPLATES (infrastructure, org, financial, legal, process) | ✅ Migration document type templates |
| ❌ Hardcoded prompts in Python | ✅ Load prompts from JSON files |
| ❌ Hardcoded model routing | ✅ Use project LLM config |

### **Deliverables**

#### **2.1: Schema Discovery Engine (Updated)**
**Location**: `services/graph-service/app/core/schema_discovery.py`

**Changes**:
```python
class SchemaDiscoveryEngine:
    async def discover_schema(
        self,
        content: str,
        document_type: str,  # REVISED: Use migration document type
        project_id: str,  # NEW: Required for LLM config
        correlation_id: Optional[str] = None,
        sample_size: int = 3000
    ) -> DocumentOntology:
        """
        Discover schema using project's LLM config.
        Load prompt from JSON file based on document type.
        """
        # 1. Load document-type-specific prompt from JSON
        prompt_id = f"schema_discovery_{document_type}"
        prompt = get_prompt_text(
            prompt_id,
            {
                "content": content[:sample_size],
                "document_type": document_type
            }
        )
        
        # 2. Call orchestrator with project_id
        result = await llm_client.orchestrate(
            task_type="schema_discovery",
            content=prompt,
            project_id=project_id,  # NEW: Required
            process_type="schema_discovery",  # Optional override
            correlation_id=correlation_id
        )
        
        # 3. Parse and return ontology
        ontology = self._parse_schema_response(result.content)
        return ontology
```

**API Endpoint (Updated)**:
```python
POST /api/graphs/discover-schema
{
  "project_id": "uuid",  # REQUIRED
  "content": "...",
  "document_type": "infrastructure_inventory"  # Migration type
}
```

#### **2.2: Adaptive Entity Extractor (Updated)**
**Location**: `services/graph-service/app/core/adaptive_entity_extractor.py`

**Changes**:
```python
class AdaptiveEntityExtractor:
    async def extract_entities(
        self,
        content: str,
        ontology: DocumentOntology,
        document_type: str,  # REVISED: Migration document type
        project_id: str,  # NEW: Required
        correlation_id: Optional[str] = None,
        use_hybrid: bool = True
    ) -> ExtractionResult:
        """
        Extract entities using project's LLM config.
        Load prompt from JSON based on document type.
        """
        # 1. Load document-type-specific extraction prompt
        prompt_id = f"entity_extraction_{document_type}"
        prompt = get_prompt_text(
            prompt_id,
            {
                "content": content,
                "schema": json.dumps(ontology.to_dict(), indent=2)
            }
        )
        
        # 2. LLM extraction with project config
        llm_result = await llm_client.orchestrate(
            task_type="adaptive_extraction",
            content=prompt,
            project_id=project_id,
            process_type="adaptive_extraction",
            correlation_id=correlation_id
        )
        
        # 3. Parse LLM entities
        llm_entities = self._parse_llm_response(llm_result.content)
        
        # 4. Augment with pattern extraction (if hybrid)
        if use_hybrid:
            pattern_entities = await self.pattern_extractor.extract(
                content, ontology
            )
            
            # Merge and deduplicate
            all_entities = self._merge_entities(
                llm_entities,
                pattern_entities
            )
        else:
            all_entities = llm_entities
        
        return ExtractionResult(
            entities=all_entities,
            relationships=self._extract_relationships(all_entities),
            schema_used=ontology
        )
```

#### **2.3: Remove Hardcoded Domain Templates**
**Location**: `services/llm-service/app/core/adaptive_prompts.py`

**OLD (Remove)**:
```python
DOMAIN_TEMPLATES = {
    "infrastructure": {
        "description": "Infrastructure and network documentation",
        "examples": [...],
        "entity_types": ["Server", "Application", "Network"],
        "prompt_template": "Extract infrastructure entities..."
    },
    "organizational": {...},
    "financial": {...},
    "legal": {...},
    "process": {...}
}

class AdaptivePromptBuilder:
    def build_extraction_prompt(self, domain: str, content: str) -> str:
        template = DOMAIN_TEMPLATES[domain]
        return template["prompt_template"].format(content=content)
```

**NEW (Implement)**:
```python
from app.utils.prompt_loader import get_prompt_text

class AdaptivePromptBuilder:
    """
    Builds prompts by loading from JSON files.
    No hardcoded templates.
    """
    
    def build_extraction_prompt(
        self,
        document_type: str,
        content: str,
        schema: Optional[Dict] = None
    ) -> str:
        """
        Load prompt from JSON file based on document type.
        
        Files:
        - prompts/entity_extraction_infrastructure_inventory.json
        - prompts/entity_extraction_dependency_mapping.json
        - etc.
        """
        prompt_id = f"entity_extraction_{document_type}"
        
        variables = {
            "content": content,
            "schema": json.dumps(schema, indent=2) if schema else "No schema"
        }
        
        return get_prompt_text(prompt_id, variables)
    
    def build_schema_discovery_prompt(
        self,
        content: str,
        document_type: str
    ) -> str:
        """Load schema discovery prompt from JSON"""
        prompt_id = f"schema_discovery_{document_type}"
        
        variables = {
            "content": content,
            "document_type": document_type
        }
        
        return get_prompt_text(prompt_id, variables)
```

### **Files to Create/Modify**

#### **Modified Files**:
1. ✅ `services/graph-service/app/core/schema_discovery.py`
   - Add project_id parameter
   - Use project LLM config
   - Load prompts from JSON

2. ✅ `services/graph-service/app/core/adaptive_entity_extractor.py`
   - Add project_id parameter
   - Use project LLM config
   - Load prompts from JSON

3. ✅ `services/llm-service/app/core/adaptive_prompts.py`
   - Remove DOMAIN_TEMPLATES
   - Implement prompt loading from JSON
   - Update all methods to use JSON prompts

4. ✅ `services/graph-service/app/routers/graphs.py`
   - Update API endpoints to require project_id

#### **New Files**: *(Will be created in Phase 3)*
- Prompt JSON files (Phase 3 - Prompt Management Integration)

### **Git Commits**
```bash
# Commit 1: Update schema discovery
git add services/graph-service/app/core/schema_discovery.py
git commit -m "refactor(graph-service): Integrate schema discovery with project LLM config"

# Commit 2: Update adaptive extractor
git add services/graph-service/app/core/adaptive_entity_extractor.py
git commit -m "refactor(graph-service): Integrate adaptive extraction with project LLM config"

# Commit 3: Remove hardcoded prompts
git add services/llm-service/app/core/adaptive_prompts.py
git commit -m "refactor(llm-service): Remove hardcoded domain templates, prepare for JSON prompts"

# Commit 4: Update API endpoints
git add services/graph-service/app/routers/graphs.py
git commit -m "refactor(graph-service): Update endpoints to require project_id"
```

---

## 📝 PHASE 3 (NEW): Prompt Management Integration + Cross-Document Resolution

### **Objectives**

**Part A: Prompt Management Integration**
1. ✅ Create JSON prompt files for all migration document types
2. ✅ Implement prompt loader in llm-service
3. ✅ Surface prompts via Settings → LLM Prompts UI
4. ✅ Enable hot-reload of prompts

**Part B: Cross-Document Entity Resolution** (From Original Plan)
1. ✅ Implement entity matching and deduplication
2. ✅ Build cross-document linking
3. ✅ Create conflict resolution strategies
4. ✅ Add graph state management

### **Deliverables**

#### **3.1: Create Prompt JSON Files**
**Locations**: 
- `services/llm-service/prompts/*.json`
- `services/graph-service/prompts/*.json`

**Prompt Files to Create**:

**1. Domain Classification**:
```json
// services/llm-service/prompts/domain_classification.json
{
  "id": "domain_classification",
  "service": "llm-service",
  "purpose": "Classify migration assessment documents by type",
  "description": "Analyzes document content to determine migration document type (infrastructure inventory, dependency mapping, assessment questionnaire, architecture, migration strategy, or technical specification)",
  "variables": ["content"],
  "text": "You are a migration assessment expert. Analyze this document and classify it into one of these migration document types:\n\n1. **infrastructure_inventory**: Server inventories, network diagrams, application catalogs, database lists\n2. **dependency_mapping**: Application dependencies, integration diagrams, data flows, API specifications\n3. **assessment_questionnaire**: Technical questionnaires, business process forms, security assessments, compliance checklists\n4. **architecture_document**: As-is architecture diagrams, technical specifications, configuration files, deployment guides\n5. **migration_strategy**: Migration plans, risk assessments, cost estimates, timelines\n6. **technical_specification**: Infrastructure specs, performance baselines, capacity planning\n\nDocument content:\n{{content}}\n\nRespond in JSON format:\n{\n  \"document_type\": \"<type>\",\n  \"confidence\": 0.0-1.0,\n  \"reasoning\": \"<brief explanation>\",\n  \"structure_type\": \"tabular|narrative|mixed|diagram\",\n  \"estimated_entity_count\": <number>\n}",
  "version": 1
}
```

**2. Schema Discovery (per document type)**:
```json
// services/llm-service/prompts/schema_discovery_infrastructure_inventory.json
{
  "id": "schema_discovery_infrastructure_inventory",
  "service": "llm-service",
  "purpose": "Discover entity schema from infrastructure inventory documents",
  "description": "Analyzes infrastructure inventory documents (server lists, network diagrams, app catalogs) to discover entity types, attributes, and relationships",
  "variables": ["content", "document_type"],
  "text": "You are analyzing an infrastructure inventory document for a migration assessment project.\n\nYour task: Discover the entity schema (types, attributes, relationships) present in this document.\n\nDocument type: {{document_type}}\n\nCommon entities in infrastructure inventories:\n- Server (name, ip_address, os, environment, location, owner)\n- Application (name, version, server, port, status)\n- Database (name, type, version, server, size)\n- NetworkDevice (name, ip_address, type, location)\n\nDocument content (sample):\n{{content}}\n\nDiscover and return the schema in JSON format:\n{\n  \"entity_types\": [\n    {\n      \"type_name\": \"Server\",\n      \"required_attributes\": [\"name\", \"ip_address\"],\n      \"optional_attributes\": [\"os\", \"environment\", \"location\"],\n      \"identifier_fields\": [\"name\", \"ip_address\"],\n      \"sample_count\": 10,\n      \"examples\": [{\"name\": \"srv-web-01\", \"ip_address\": \"192.168.1.10\"}]\n    }\n  ],\n  \"relationships\": [\n    {\n      \"source_type\": \"Application\",\n      \"target_type\": \"Server\",\n      \"relationship_type\": \"RUNS_ON\",\n      \"confidence\": 0.9\n    }\n  ]\n}",
  "version": 1
}
```

**3. Entity Extraction (per document type)**:
```json
// services/llm-service/prompts/entity_extraction_infrastructure_inventory.json
{
  "id": "entity_extraction_infrastructure_inventory",
  "service": "llm-service",
  "purpose": "Extract infrastructure entities from inventory documents",
  "description": "Extracts servers, applications, databases, and network devices from infrastructure inventory documents using provided schema",
  "variables": ["content", "schema"],
  "text": "You are extracting entities from an infrastructure inventory document for a migration assessment.\n\nUse this discovered schema to guide extraction:\n{{schema}}\n\nDocument content:\n{{content}}\n\nExtraction rules:\n1. Extract ALL entities of types defined in schema\n2. Preserve attribute values EXACTLY as written (no validation)\n3. Include confidence score (0.0-1.0) per entity\n4. Track source location (page/section/row) for each entity\n5. Extract relationships between entities\n\nReturn in JSON format:\n{\n  \"entities\": [\n    {\n      \"type\": \"Server\",\n      \"attributes\": {\"name\": \"srv-web-01\", \"ip_address\": \"192.168.1.10\"},\n      \"confidence\": 0.95,\n      \"source_location\": \"Row 5, Sheet 1\"\n    }\n  ],\n  \"relationships\": [\n    {\n      \"source_entity\": \"srv-web-01\",\n      \"target_entity\": \"nginx\",\n      \"relationship_type\": \"RUNS\",\n      \"confidence\": 0.9\n    }\n  ]\n}",
  "version": 1
}
```

**Create similar prompts for**:
- `schema_discovery_dependency_mapping.json`
- `schema_discovery_assessment_questionnaire.json`
- `schema_discovery_architecture_document.json`
- `schema_discovery_migration_strategy.json`
- `schema_discovery_technical_specification.json`
- `entity_extraction_dependency_mapping.json`
- `entity_extraction_assessment_questionnaire.json`
- `entity_extraction_architecture_document.json`
- `entity_extraction_migration_strategy.json`
- `entity_extraction_technical_specification.json`
- `relationship_inference.json`

#### **3.2: Implement Prompt Loader**
**Location**: `services/llm-service/app/utils/prompt_loader.py`

```python
"""Prompt loader for LLM service"""
import os
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("prompt_loader")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

def load_prompt(prompt_id: str) -> Optional[Dict[str, Any]]:
    """
    Load prompt from JSON file.
    
    Args:
        prompt_id: Prompt identifier (e.g., "entity_extraction_infrastructure_inventory")
    
    Returns:
        Prompt data dict or None if not found
    """
    prompt_file = os.path.join(PROMPTS_DIR, f"{prompt_id}.json")
    
    if not os.path.exists(prompt_file):
        logger.warning(f"Prompt file not found: {prompt_file}")
        return None
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading prompt {prompt_id}: {e}")
        return None

def get_prompt_text(
    prompt_id: str,
    variables: Optional[Dict[str, str]] = None
) -> str:
    """
    Load prompt and substitute variables.
    
    Args:
        prompt_id: Prompt identifier
        variables: Dict of variable name -> value for substitution
    
    Returns:
        Prompt text with variables substituted
    
    Raises:
        FileNotFoundError: If prompt not found
    """
    prompt_data = load_prompt(prompt_id)
    
    if not prompt_data:
        raise FileNotFoundError(f"Prompt '{prompt_id}' not found in {PROMPTS_DIR}")
    
    text = prompt_data.get("text", "")
    
    # Substitute variables
    if variables:
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"  # {{variable}}
            text = text.replace(placeholder, str(var_value))
    
    return text

def list_prompts() -> Dict[str, Dict[str, Any]]:
    """
    List all available prompts.
    
    Returns:
        Dict of prompt_id -> prompt metadata
    """
    prompts = {}
    
    if not os.path.exists(PROMPTS_DIR):
        return prompts
    
    for filename in os.listdir(PROMPTS_DIR):
        if filename.endswith(".json"):
            prompt_id = filename[:-5]  # Remove .json
            prompt_data = load_prompt(prompt_id)
            if prompt_data:
                prompts[prompt_id] = {
                    "id": prompt_data.get("id"),
                    "service": prompt_data.get("service"),
                    "purpose": prompt_data.get("purpose"),
                    "variables": prompt_data.get("variables", [])
                }
    
    return prompts
```

#### **3.3: Entity Resolution Engine** (From Original Plan)
**Location**: `services/graph-service/app/core/entity_resolver.py`

**Keep implementation from original plan - NO CHANGES**
- Multi-stage matching (exact → rule-based → semantic)
- Fuzzy name matching
- Attribute-based similarity
- LLM-powered semantic matching

**Integration Change**:
```python
class EntityResolver:
    async def semantic_match(
        self,
        entity1: Entity,
        entity2: Entity,
        project_id: str  # NEW: Required
    ) -> float:
        """
        Use LLM for semantic matching.
        Now uses project's LLM config instead of hardcoded model.
        """
        prompt = get_prompt_text(
            "entity_semantic_matching",
            {
                "entity1": json.dumps(entity1.to_dict()),
                "entity2": json.dumps(entity2.to_dict())
            }
        )
        
        result = await llm_client.orchestrate(
            task_type="entity_matching",
            content=prompt,
            project_id=project_id,
            process_type="entity_extraction"
        )
        
        return result.similarity_score
```

### **Files to Create**

#### **New Prompt Files** (13 files):
1. `services/llm-service/prompts/domain_classification.json`
2. `services/llm-service/prompts/schema_discovery_infrastructure_inventory.json`
3. `services/llm-service/prompts/schema_discovery_dependency_mapping.json`
4. `services/llm-service/prompts/schema_discovery_assessment_questionnaire.json`
5. `services/llm-service/prompts/schema_discovery_architecture_document.json`
6. `services/llm-service/prompts/schema_discovery_migration_strategy.json`
7. `services/llm-service/prompts/schema_discovery_technical_specification.json`
8. `services/llm-service/prompts/entity_extraction_infrastructure_inventory.json`
9. `services/llm-service/prompts/entity_extraction_dependency_mapping.json`
10. `services/llm-service/prompts/entity_extraction_assessment_questionnaire.json`
11. `services/llm-service/prompts/entity_extraction_architecture_document.json`
12. `services/llm-service/prompts/entity_extraction_migration_strategy.json`
13. `services/llm-service/prompts/entity_extraction_technical_specification.json`
14. `services/llm-service/prompts/relationship_inference.json`
15. `services/llm-service/prompts/entity_semantic_matching.json`

#### **New Code Files**:
1. `services/llm-service/app/utils/prompt_loader.py`
2. `services/graph-service/app/core/entity_resolver.py` (from original plan)
3. `services/graph-service/app/core/graph_state_manager.py` (from original plan)
4. `services/graph-service/app/core/conflict_resolver.py` (from original plan)

### **Integration with Settings UI**

**Existing System** (No changes needed):
- Frontend: `Settings → LLM Prompts` already exists
- Backend: `/api/prompts/{service}/{prompt_id}` already exists
- Prompts auto-discovered from `services/{service}/prompts/*.json`
- Hot-reload: Changes to JSON files immediately reflected

**What We're Doing**:
- ✅ Adding prompt JSON files to `services/llm-service/prompts/`
- ✅ Files automatically appear in Settings UI
- ✅ Users can edit prompts via UI
- ✅ No service restart needed (hot-reload)

### **Git Commits**
```bash
# Commit 1: Prompt loader utility
git add services/llm-service/app/utils/prompt_loader.py
git commit -m "feat(llm-service): Add prompt loader for JSON-based prompt management"

# Commit 2: Create prompt JSON files (batch 1)
git add services/llm-service/prompts/domain_classification.json
git add services/llm-service/prompts/schema_discovery_*.json
git commit -m "feat(llm-service): Add schema discovery prompts for migration document types"

# Commit 3: Create prompt JSON files (batch 2)
git add services/llm-service/prompts/entity_extraction_*.json
git add services/llm-service/prompts/relationship_inference.json
git commit -m "feat(llm-service): Add entity extraction prompts for migration document types"

# Commit 4: Entity resolution (from original plan)
git add services/graph-service/app/core/entity_resolver.py
git add services/graph-service/app/core/graph_state_manager.py
git add services/graph-service/app/core/conflict_resolver.py
git commit -m "feat(graph-service): Add cross-document entity resolution engine"

# Commit 5: Documentation
git add docs/
git commit -m "docs: Add prompt management and entity resolution documentation"
```

---

## 📝 PHASE 4: Intelligent Relationship Inference (From Original Plan)

**Keep implementation from original plan with ONE change**: Use project LLM config instead of hardcoded routing.

### **Changes from Original**

**Integration Update**:
```python
class RelationshipInferenceEngine:
    async def infer_semantic_relationships(
        self,
        entities: List[Entity],
        context: str,
        project_id: str  # NEW: Required
    ) -> List[Relationship]:
        """
        Infer relationships using LLM.
        Now uses project's LLM config.
        """
        prompt = get_prompt_text(
            "relationship_inference",
            {
                "entities": json.dumps([e.to_dict() for e in entities]),
                "context": context
            }
        )
        
        result = await llm_client.orchestrate(
            task_type="relationship_inference",
            content=prompt,
            project_id=project_id,
            process_type="relationship_inference"
        )
        
        return self._parse_relationships(result.content)
```

**Everything else from original Phase 4 remains the same**:
- ✅ Multi-level relationship inference
- ✅ Relationship type taxonomy
- ✅ Relationship strength scoring
- ✅ Transitive relationship discovery

---

## 📝 PHASE 5: Testing & Documentation (From Original Plan)

**Keep implementation from original plan**.

**Additional Documentation**:
- ✅ Prompt customization guide
- ✅ Project LLM configuration guide
- ✅ Process-specific LLM config examples
- ✅ Migration document type examples

---

## 📊 Success Metrics (Updated)

### **Quantitative Goals**

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|--------|---------|---------|---------|---------|---------|---------|
| **Entity Extraction Accuracy** | 85% | 85% | 92% | 92% | 92% | 95% |
| **Relationship Accuracy** | 75% | 75% | 75% | 80% | 90% | 92% |
| **Cross-Doc Matching** | 0% | 0% | 0% | 85% | 85% | 88% |
| **Migration Doc Coverage** | 0 | 6 types | 6 types | 6 types | 6 types | 6 types |
| **Prompt Customizability** | 0% | 0% | 0% | 100% | 100% | 100% |
| **Project LLM Config Support** | Yes | Yes | Yes | Yes | Yes | Yes |

### **Qualitative Goals**

✅ **Phase 1:** Project LLM config integration + Migration document classification  
✅ **Phase 2:** Adaptive extraction for 6 migration document types  
✅ **Phase 3:** JSON-based prompts + Cross-document entity linking  
✅ **Phase 4:** Rich, multi-level relationships discovered  
✅ **Phase 5:** Production-ready with prompt customization guide  

---

## 🔄 Implementation Workflow

### **For Each Phase:**

1. **Review this consolidated plan** with user
2. **Implement deliverables** per phase
3. **Create prompt JSON files** as needed
4. **Test with project LLM configuration**
5. **Commit incrementally** with clear messages
6. **Update documentation** after each phase
7. **User review and approval** before next phase

---

## 📋 Quick Reference: What Changed

### **From Original Plan → Consolidated Plan**

| Component | Original | Revised |
|-----------|----------|---------|
| **Model Routing** | ❌ Hardcoded MODEL_PROFILES | ✅ Project LLM config |
| **Model Selection** | ❌ TASK_PREFERENCES routing | ✅ Process-specific config |
| **Document Domains** | ❌ Generic (infra, org, financial, legal, process) | ✅ Migration (6 types) |
| **Prompts** | ❌ Hardcoded in Python | ✅ JSON files in prompts/ |
| **Prompt Management** | ❌ Not surfaced | ✅ Settings → LLM Prompts UI |
| **LLM Config** | ❌ Not integrated | ✅ `/api/projects/{id}/llm-config` |
| **Process Types** | 5 existing | 9 total (added 4 new) |
| **Relationship Inference** | ✅ Keep as-is | ✅ Use project LLM config |
| **Entity Resolution** | ✅ Keep as-is | ✅ Use project LLM config |

---

## ⚠️ Important Notes

### **What We're NOT Doing (Per User Request)**

❌ **NO Data Validation:**
- Will NOT validate IP addresses for RFC compliance
- Will NOT validate OS versions against known releases
- Will NOT validate port/protocol combinations
- Will NOT modify or reject any data from documents

### **What We ARE Doing**

✅ **Platform Integration:**
- Use existing project LLM configuration system
- Use existing prompt management UI
- Support process-specific LLM config overrides
- Migration-specific document types only

✅ **Intelligent Processing:**
- Classify migration assessment documents
- Extract entities adaptively
- Infer relationships intelligently
- Link entities across documents
- Build comprehensive knowledge graph

---

## 🎯 Ready to Start?

This consolidated plan provides:
- ✅ **Alignment with platform**: Project LLM config, prompt management UI
- ✅ **Migration focus**: 6 document types specific to migration assessments
- ✅ **All features from original plan**: Phases 1-5 comprehensive roadmap
- ✅ **Clear refactoring path**: Remove hardcoded routing, add JSON prompts
- ✅ **Backward compatibility**: Existing projects continue to work

**Estimated Total Time:** 6 weeks  
**Estimated Lines of Code:** ~4,000 new lines (reduced from 5,000 due to removing hardcoded routing)  
**Estimated Files:**
- ~25 new files (15 prompt JSONs + 10 code files)
- ~15 modified files (refactoring existing code)

---

**Shall we proceed with Phase 1 (Revised) implementation?**
