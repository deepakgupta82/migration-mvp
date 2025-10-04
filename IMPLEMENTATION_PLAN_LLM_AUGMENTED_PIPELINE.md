# 🚀 Implementation Plan: LLM-Augmented Intelligent Document Processing Pipeline

**Version:** 1.0  
**Date:** October 4, 2025  
**Status:** Planning Phase  

---

## 📋 **Executive Summary**

This document outlines the detailed implementation plan for upgrading our document processing pipeline to an intelligent, LLM-augmented system that can:

1. **Handle ANY document format/domain** dynamically
2. **Extract entities and relationships** intelligently
3. **Build cross-document knowledge graphs** automatically
4. **Maintain service separation** and clean architecture
5. **Track and optimize costs** through smart model routing

---

## 🎯 **Architecture Principles**

### **Service Separation of Concerns**

```
┌─────────────────────────────────────────────────────────┐
│ LLM-SERVICE                                             │
│ • ALL LLM interactions (GPT, Claude, Gemini)           │
│ • Model routing and selection                           │
│ • Prompt construction and optimization                  │
│ • Usage tracking and cost monitoring                    │
│ • Response parsing and validation                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ GRAPH-SERVICE                                           │
│ • Document profiling and classification                 │
│ • Schema discovery and ontology building                │
│ • Entity extraction orchestration                       │
│ • Relationship inference                                │
│ • Cross-document entity resolution                      │
│ • Neo4j graph operations                                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ DOCUMENT-SERVICE                                        │
│ • Document upload and storage                           │
│ • Format detection and parsing                          │
│ • JSONL generation                                      │
│ • Service integration orchestration                     │
└─────────────────────────────────────────────────────────┘
```

---

## 📅 **Phase-Wise Implementation Schedule**

### **PHASE 1: Foundation & Multi-Model LLM Infrastructure** (Week 1-2)
**Goal:** Enable intelligent, multi-model LLM capabilities with smart routing

### **PHASE 2: Adaptive Entity Extraction** (Week 3)
**Goal:** Dynamic entity extraction that adapts to any document domain

### **PHASE 3: Cross-Document Entity Resolution** (Week 4)
**Goal:** Link and deduplicate entities across multiple documents

### **PHASE 4: Intelligent Relationship Inference** (Week 5)
**Goal:** Build rich, multi-level relationships automatically

### **PHASE 5: Testing & Documentation** (Week 6)
**Goal:** Comprehensive testing and documentation

---

## 📝 **PHASE 1: Foundation & Multi-Model LLM Infrastructure**

### **Objectives**
1. ✅ Create multi-model LLM orchestrator in llm-service
2. ✅ Implement document domain classification
3. ✅ Build adaptive prompt system
4. ✅ Add usage tracking for multi-model support
5. ✅ Update API contracts

### **Deliverables**

#### **1.1: Multi-Model LLM Orchestrator**
**Location:** `services/llm-service/app/core/llm_orchestrator.py`

**Features:**
- Support for Claude 4.5 Sonnet, GPT-4o, Gemini 2.5 Pro
- Smart model routing based on task type and context size
- Cost optimization logic
- Failover and retry mechanisms
- Performance monitoring

**API Endpoint:**
```python
POST /api/llm/orchestrate
{
  "task_type": "entity_extraction | relationship_inference | domain_classification",
  "content": "document content",
  "context_size": 50000,
  "has_images": false,
  "prefer_model": "claude-4.5-sonnet" (optional)
}

Response:
{
  "result": {...},
  "model_used": "claude-4.5-sonnet",
  "tokens": {
    "prompt": 1200,
    "completion": 800,
    "total": 2000
  },
  "cost": 0.0084,
  "duration_ms": 2500
}
```

#### **1.2: Document Domain Classifier**
**Location:** `services/graph-service/app/core/document_classifier.py`

**Features:**
- LLM-based domain detection (infrastructure, HR, finance, legal, process)
- Structure analysis (tabular, narrative, mixed, diagram)
- Entity density estimation
- Confidence scoring

**API Endpoint:**
```python
POST /api/graphs/classify-document
{
  "project_id": "uuid",
  "document_content": "...",
  "document_metadata": {...}
}

Response:
{
  "primary_domain": "infrastructure",
  "secondary_domains": ["network", "security"],
  "confidence": 0.92,
  "structure_type": "tabular",
  "estimated_entity_count": 150,
  "recommended_strategy": "spreadsheet_extraction"
}
```

#### **1.3: Adaptive Prompt Builder**
**Location:** `services/llm-service/app/core/adaptive_prompts.py`

**Features:**
- Dynamic prompt construction based on document profile
- Domain-specific examples injection
- Schema-guided extraction
- Few-shot learning support

**Methods:**
```python
class AdaptivePromptBuilder:
    def build_entity_extraction_prompt(
        domain: str,
        doc_type: str,
        content: str,
        discovered_schema: Optional[Dict] = None
    ) -> str
    
    def build_relationship_inference_prompt(
        entities: List[Entity],
        domain: str
    ) -> str
    
    def build_domain_classification_prompt(
        content: str
    ) -> str
```

#### **1.4: Usage Tracking Enhancement**
**Location:** `services/llm-service/app/core/usage_tracker.py`

**Features:**
- Track usage per model (GPT, Claude, Gemini)
- Cost calculation per model
- Performance metrics (latency, success rate)
- Project-level cost aggregation

**Database Schema:**
```sql
-- Add to llm_usage_logs table
ALTER TABLE llm_usage_logs ADD COLUMN model_provider VARCHAR(50);
ALTER TABLE llm_usage_logs ADD COLUMN model_name VARCHAR(100);
ALTER TABLE llm_usage_logs ADD COLUMN cost_usd DECIMAL(10, 6);
ALTER TABLE llm_usage_logs ADD COLUMN latency_ms INTEGER;
```

### **Files to Create/Modify**

#### **New Files:**
1. `services/llm-service/app/core/llm_orchestrator.py`
2. `services/llm-service/app/core/model_router.py`
3. `services/llm-service/app/core/adaptive_prompts.py`
4. `services/llm-service/app/models/llm_request.py`
5. `services/graph-service/app/core/document_classifier.py`
6. `services/graph-service/app/models/domain_profile.py`

#### **Modified Files:**
1. `services/llm-service/app/routers/llm_router.py` (add /orchestrate endpoint)
2. `services/llm-service/app/core/usage_tracker.py` (multi-model tracking)
3. `services/graph-service/app/routers/graph_router.py` (add /classify-document)

### **Documentation Updates**
1. `docs/llm-service.md` - Add multi-model orchestration section
2. `docs/graph-service.md` - Add document classification section
3. `docs/architecture.md` - Update with new components

### **Testing Requirements**
1. Unit tests for model router logic
2. Integration tests for each LLM provider
3. Cost calculation verification
4. Performance benchmarks (latency, throughput)

### **Git Commits**
```bash
# Commit 1
git add services/llm-service/app/core/llm_orchestrator.py
git add services/llm-service/app/core/model_router.py
git commit -m "feat(llm-service): Add multi-model LLM orchestrator with smart routing"

# Commit 2
git add services/llm-service/app/core/adaptive_prompts.py
git commit -m "feat(llm-service): Add adaptive prompt builder for dynamic extraction"

# Commit 3
git add services/graph-service/app/core/document_classifier.py
git commit -m "feat(graph-service): Add LLM-based document domain classifier"

# Commit 4
git add docs/
git commit -m "docs: Update architecture and service documentation for Phase 1"
```

---

## 📝 **PHASE 2: Adaptive Entity Extraction**

### **Objectives**
1. ✅ Implement schema discovery engine
2. ✅ Build adaptive entity extractor
3. ✅ Create multi-strategy extraction pipeline
4. ✅ Add confidence scoring

### **Deliverables**

#### **2.1: Schema Discovery Engine**
**Location:** `services/graph-service/app/core/schema_discovery.py`

**Features:**
- Detect entity types from document content
- Infer attribute schemas
- Discover relationship patterns
- Build domain-specific ontology

**API Endpoint:**
```python
POST /api/graphs/discover-schema
{
  "project_id": "uuid",
  "document_content": "...",
  "domain_profile": {...}
}

Response:
{
  "discovered_entity_types": [
    {
      "type_name": "Server",
      "confidence": 0.95,
      "required_attributes": ["name", "ip_address"],
      "optional_attributes": ["os", "location", "environment"],
      "identifier_fields": ["name", "ip_address"]
    }
  ],
  "discovered_relationships": [
    {
      "source_type": "Application",
      "target_type": "Server",
      "relationship_type": "RUNS_ON",
      "confidence": 0.88
    }
  ],
  "ontology": {...}
}
```

#### **2.2: Adaptive Entity Extractor**
**Location:** `services/graph-service/app/core/adaptive_entity_extractor.py`

**Features:**
- Use discovered schema for extraction
- Multi-strategy extraction (LLM + patterns + rules)
- Confidence scoring per entity
- Source tracking (where in document)

**Process Flow:**
```
1. Get domain profile (from Phase 1 classifier)
2. Discover schema (if not exists for domain)
3. Build adaptive prompt with schema
4. Call LLM via llm-service
5. Augment with pattern-based extraction (IPs, emails, dates)
6. Merge and deduplicate results
7. Score confidence
8. Return enriched entities
```

#### **2.3: Multi-Strategy Extraction Pipeline**
**Location:** `services/graph-service/app/core/extraction_strategies.py`

**Strategies:**
1. **LLM-based extraction** (primary, 90% of work)
2. **Pattern-based extraction** (regex for structured data)
3. **Table column mapping** (for spreadsheets)
4. **Named Entity Recognition** (optional, for people/orgs)

**Implementation:**
```python
class ExtractionStrategyManager:
    async def extract_with_strategies(
        content: str,
        domain_profile: DomainProfile,
        discovered_schema: Ontology
    ) -> ExtractionResult:
        
        # Strategy 1: LLM extraction
        llm_entities = await self.llm_strategy.extract(...)
        
        # Strategy 2: Pattern extraction
        pattern_entities = await self.pattern_strategy.extract(...)
        
        # Strategy 3: Table mapping (if tabular)
        if domain_profile.is_tabular:
            table_entities = await self.table_strategy.extract(...)
        
        # Merge strategies
        merged = self.merge_extraction_results([
            llm_entities,
            pattern_entities,
            table_entities
        ])
        
        return merged
```

### **Files to Create/Modify**

#### **New Files:**
1. `services/graph-service/app/core/schema_discovery.py`
2. `services/graph-service/app/core/adaptive_entity_extractor.py`
3. `services/graph-service/app/core/extraction_strategies.py`
4. `services/graph-service/app/core/pattern_extractors.py`
5. `services/graph-service/app/models/ontology.py`
6. `services/graph-service/app/models/extraction_result.py`

#### **Modified Files:**
1. `services/graph-service/app/core/graph_processor.py` (integrate adaptive extraction)
2. `services/graph-service/app/routers/graph_router.py` (add schema discovery endpoint)

### **Documentation Updates**
1. `docs/graph-service.md` - Add adaptive extraction section
2. `docs/entity-extraction.md` - New document explaining extraction strategies

### **Testing Requirements**
1. Test schema discovery with diverse documents
2. Validate extraction accuracy across domains
3. Test confidence scoring calibration
4. Performance benchmarks

### **Git Commits**
```bash
# Commit 1
git add services/graph-service/app/core/schema_discovery.py
git commit -m "feat(graph-service): Add schema discovery engine for dynamic entity types"

# Commit 2
git add services/graph-service/app/core/adaptive_entity_extractor.py
git add services/graph-service/app/core/extraction_strategies.py
git commit -m "feat(graph-service): Add adaptive entity extraction with multi-strategy pipeline"

# Commit 3
git add docs/
git commit -m "docs: Add entity extraction strategy documentation"
```

---

## 📝 **PHASE 3: Cross-Document Entity Resolution**

### **Objectives**
1. ✅ Implement entity matching and deduplication
2. ✅ Build cross-document linking
3. ✅ Create conflict resolution strategies
4. ✅ Add graph state management

**NOTE:** This phase EXCLUDES validation. We match and link entities but do NOT validate or modify their attributes.

### **Deliverables**

#### **3.1: Entity Resolution Engine**
**Location:** `services/graph-service/app/core/entity_resolver.py`

**Features:**
- Multi-stage matching (exact → rule-based → semantic)
- Fuzzy name matching
- Attribute-based similarity
- LLM-powered semantic matching for edge cases
- **NO VALIDATION** - preserve all attributes as-is

**Matching Stages:**
```
Stage 1: Exact Match (deterministic)
  - Exact hostname/IP/email match
  - Unique identifier match
  
Stage 2: Rule-Based Match (high confidence)
  - Fuzzy name matching (Levenshtein distance)
  - Overlapping attributes (3+ matches)
  - Same type + location + identifier pattern
  
Stage 3: Semantic Match (LLM-powered)
  - Use LLM to compare entity descriptions
  - Handle abbreviations (RHEL = Red Hat Enterprise Linux)
  - Resolve name variations (John Doe = J. Doe)
```

**API Endpoint:**
```python
POST /api/graphs/resolve-entities
{
  "project_id": "uuid",
  "new_entities": [...],
  "similarity_threshold": 0.85
}

Response:
{
  "merged": [
    {
      "new_entity_id": "temp_123",
      "existing_entity_id": "server_prod_web_01",
      "confidence": 0.92,
      "match_reason": "exact_hostname_match"
    }
  ],
  "new": [...],
  "ambiguous": [
    {
      "new_entity": {...},
      "candidates": [...]
    }
  ]
}
```

#### **3.2: Graph State Manager**
**Location:** `services/graph-service/app/core/graph_state_manager.py`

**Features:**
- Track graph evolution over time
- Incremental updates (add new entities without reprocessing all)
- Version control for entities (track changes)
- Audit trail for merges

**Methods:**
```python
class GraphStateManager:
    async def get_existing_entities(project_id: str, entity_type: str) -> List[Entity]
    
    async def add_new_entities(project_id: str, entities: List[Entity]) -> None
    
    async def merge_entities(
        project_id: str,
        new_entity: Entity,
        existing_entity: Entity,
        merge_strategy: str
    ) -> Entity
    
    async def track_entity_version(
        entity_id: str,
        changes: Dict,
        source_document: str
    ) -> None
```

#### **3.3: Conflict Resolution (Attribute Merging)**
**Location:** `services/graph-service/app/core/conflict_resolver.py`

**Features:**
- Merge attributes from multiple sources
- Preserve all values (no validation/rejection)
- Use LLM for intelligent merging when conflicts occur
- Track source of each attribute

**Strategies:**
```python
class ConflictResolver:
    async def resolve_attribute_conflicts(
        entity_type: str,
        attribute_name: str,
        existing_value: Any,
        new_value: Any,
        source_docs: List[str]
    ) -> Any:
        """
        Resolution strategies (NO VALIDATION):
        1. If same value → keep it
        2. If null + non-null → use non-null
        3. If both non-null and different:
           - For lists: merge both
           - For strings: use LLM to decide which is more complete
           - For numbers: keep both with source tracking
        """
```

### **Files to Create/Modify**

#### **New Files:**
1. `services/graph-service/app/core/entity_resolver.py`
2. `services/graph-service/app/core/graph_state_manager.py`
3. `services/graph-service/app/core/conflict_resolver.py`
4. `services/graph-service/app/core/similarity_matcher.py`
5. `services/graph-service/app/models/entity_match.py`
6. `services/graph-service/app/models/resolution_result.py`

#### **Modified Files:**
1. `services/graph-service/app/core/graph_processor.py` (integrate entity resolution)
2. `services/graph-service/app/routers/graph_router.py` (add resolution endpoint)

### **Documentation Updates**
1. `docs/graph-service.md` - Add entity resolution section
2. `docs/entity-resolution.md` - New document explaining matching strategies

### **Testing Requirements**
1. Test exact matching accuracy
2. Validate fuzzy matching thresholds
3. Test LLM semantic matching
4. Test conflict resolution strategies
5. Performance tests for large entity sets

### **Git Commits**
```bash
# Commit 1
git add services/graph-service/app/core/entity_resolver.py
git add services/graph-service/app/core/similarity_matcher.py
git commit -m "feat(graph-service): Add cross-document entity resolution engine"

# Commit 2
git add services/graph-service/app/core/graph_state_manager.py
git commit -m "feat(graph-service): Add graph state management for incremental updates"

# Commit 3
git add services/graph-service/app/core/conflict_resolver.py
git commit -m "feat(graph-service): Add attribute conflict resolution with LLM support"

# Commit 4
git add docs/
git commit -m "docs: Add entity resolution and conflict resolution documentation"
```

---

## 📝 **PHASE 4: Intelligent Relationship Inference**

### **Objectives**
1. ✅ Implement multi-level relationship inference
2. ✅ Build relationship strength scoring
3. ✅ Create transitive relationship discovery
4. ✅ Add relationship type taxonomy

### **Deliverables**

#### **4.1: Relationship Inference Engine**
**Location:** `services/graph-service/app/core/relationship_inference.py`

**Features:**
- 5 levels of relationship inference
- Domain-specific relationship patterns
- Confidence scoring
- Bidirectional relationship support

**Inference Levels:**
```python
class RelationshipInferenceEngine:
    # Level 1: Explicit (from document text)
    async def extract_explicit_relationships(entities: List[Entity], content: str)
    
    # Level 2: Structural (from document hierarchy)
    async def infer_hierarchical_relationships(entities: List[Entity])
    
    # Level 3: Semantic (from co-occurrence)
    async def infer_cooccurrence_relationships(entities: List[Entity], context: str)
    
    # Level 4: Network (from topology)
    async def infer_network_relationships(entities: List[Entity])
    
    # Level 5: Transitive (from existing graph)
    async def infer_transitive_relationships(entities: List[Entity], graph: Neo4jGraph)
```

**API Endpoint:**
```python
POST /api/graphs/infer-relationships
{
  "project_id": "uuid",
  "entities": [...],
  "document_content": "...",
  "domain_profile": {...}
}

Response:
{
  "relationships": [
    {
      "source_id": "server_123",
      "target_id": "app_456",
      "type": "HOSTS",
      "confidence": 0.95,
      "inference_level": "explicit",
      "properties": {
        "port": 8080,
        "protocol": "HTTP"
      }
    }
  ],
  "stats": {
    "explicit": 15,
    "hierarchical": 8,
    "semantic": 5,
    "network": 12,
    "transitive": 3
  }
}
```

#### **4.2: Relationship Type Taxonomy**
**Location:** `services/graph-service/app/models/relationship_taxonomy.py`

**Taxonomy:**
```python
RELATIONSHIP_TAXONOMY = {
    "infrastructure": {
        "structural": ["CONTAINS", "PART_OF", "BELONGS_TO"],
        "operational": ["HOSTS", "RUNS_ON", "CONNECTS_TO", "DEPENDS_ON"],
        "network": ["IN_SUBNET", "ROUTES_TO", "LOAD_BALANCES", "PROXIES"]
    },
    "organizational": {
        "hierarchy": ["REPORTS_TO", "MANAGES", "SUPERVISES"],
        "membership": ["WORKS_IN", "MEMBER_OF", "ASSIGNED_TO"],
        "collaboration": ["COLLABORATES_WITH", "WORKS_WITH"]
    },
    "process": {
        "temporal": ["PRECEDES", "FOLLOWS", "DURING", "TRIGGERS"],
        "flow": ["LEADS_TO", "REQUIRES", "PRODUCES", "CONSUMES"]
    },
    "semantic": {
        "association": ["RELATED_TO", "SIMILAR_TO", "ALTERNATIVE_TO"],
        "reference": ["REFERENCES", "MENTIONS", "LINKS_TO"]
    }
}
```

#### **4.3: Relationship Strength Scorer**
**Location:** `services/graph-service/app/core/relationship_scorer.py`

**Scoring Factors:**
```python
class RelationshipScorer:
    def score_relationship(
        relationship: Relationship,
        entities: List[Entity],
        document_context: str
    ) -> float:
        """
        Scoring factors:
        1. Entity confidence (source + target confidence)
        2. Evidence strength (how clearly stated)
        3. Context consistency (fits document pattern)
        4. Cross-validation (confirmed by other sources)
        5. Inference method (explicit > inferred)
        
        Returns: 0.0 - 1.0 confidence score
        """
```

#### **4.4: Transitive Relationship Builder**
**Location:** `services/graph-service/app/core/transitive_relationships.py`

**Features:**
- Discover multi-hop relationships
- Build dependency chains
- Identify indirect connections
- Rank paths by relevance

**Example:**
```
Direct: App A → Server X
Direct: Server X → Datacenter Y

Inferred Transitive: App A → LOCATED_IN → Datacenter Y
```

### **Files to Create/Modify**

#### **New Files:**
1. `services/graph-service/app/core/relationship_inference.py`
2. `services/graph-service/app/core/relationship_scorer.py`
3. `services/graph-service/app/core/transitive_relationships.py`
4. `services/graph-service/app/models/relationship_taxonomy.py`
5. `services/graph-service/app/models/relationship_result.py`

#### **Modified Files:**
1. `services/graph-service/app/core/graph_processor.py` (integrate relationship inference)
2. `services/graph-service/app/routers/graph_router.py` (add inference endpoint)

### **Documentation Updates**
1. `docs/graph-service.md` - Add relationship inference section
2. `docs/relationship-inference.md` - New document explaining inference levels

### **Testing Requirements**
1. Test each inference level independently
2. Validate relationship taxonomy coverage
3. Test scoring accuracy
4. Test transitive relationship discovery
5. Performance benchmarks

### **Git Commits**
```bash
# Commit 1
git add services/graph-service/app/core/relationship_inference.py
git add services/graph-service/app/models/relationship_taxonomy.py
git commit -m "feat(graph-service): Add multi-level relationship inference engine"

# Commit 2
git add services/graph-service/app/core/relationship_scorer.py
git commit -m "feat(graph-service): Add relationship strength scoring"

# Commit 3
git add services/graph-service/app/core/transitive_relationships.py
git commit -m "feat(graph-service): Add transitive relationship discovery"

# Commit 4
git add docs/
git commit -m "docs: Add relationship inference documentation"
```

---

## 📝 **PHASE 5: Testing & Documentation**

### **Objectives**
1. ✅ End-to-end integration testing
2. ✅ Performance benchmarking
3. ✅ Cost analysis and optimization
4. ✅ Comprehensive documentation
5. ✅ Example workflows

### **Deliverables**

#### **5.1: Integration Test Suite**
**Location:** `tests/integration/test_intelligent_pipeline.py`

**Test Scenarios:**
1. Infrastructure document (Excel server inventory)
2. HR document (org chart)
3. Network diagram (Visio/PowerPoint)
4. Mixed document set (cross-document linking)
5. Large-scale processing (100+ documents)

#### **5.2: Performance Benchmarks**
**Location:** `tests/benchmarks/`

**Metrics:**
- Processing time per document type
- LLM cost per document
- Entity extraction accuracy
- Relationship inference accuracy
- Cross-document matching accuracy

#### **5.3: Documentation Updates**

**Files to Update:**
1. `docs/architecture.md` - Complete architecture overview
2. `docs/llm-service.md` - Multi-model orchestration
3. `docs/graph-service.md` - All new features
4. `docs/api-reference.md` - All new endpoints
5. `docs/user-guide.md` - How to use new features

**New Documents:**
6. `docs/intelligent-pipeline-guide.md` - Complete guide
7. `docs/entity-extraction.md` - Extraction strategies
8. `docs/entity-resolution.md` - Resolution process
9. `docs/relationship-inference.md` - Inference levels
10. `docs/cost-optimization.md` - Model selection guide

#### **5.4: Example Workflows**
**Location:** `examples/intelligent_pipeline/`

**Examples:**
1. Single document processing
2. Batch document processing
3. Cross-document entity linking
4. Custom domain configuration
5. Cost optimization strategies

### **Git Commits**
```bash
# Commit 1
git add tests/
git commit -m "test: Add comprehensive integration tests for intelligent pipeline"

# Commit 2
git add docs/
git commit -m "docs: Complete documentation for LLM-augmented pipeline"

# Commit 3
git add examples/
git commit -m "docs: Add example workflows and use cases"
```

---

## 📊 **Success Metrics**

### **Quantitative Goals**

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|--------|---------|---------|---------|---------|---------|---------|
| **Entity Extraction Accuracy** | 85% | 85% | 92% | 92% | 92% | 95% |
| **Relationship Accuracy** | 75% | 75% | 75% | 80% | 90% | 92% |
| **Cross-Doc Matching** | 0% | 0% | 0% | 85% | 85% | 88% |
| **Domain Coverage** | 1 | 1 | Unlimited | Unlimited | Unlimited | Unlimited |
| **Processing Speed** | 1x | 1.1x | 1.2x | 1.3x | 1.4x | 1.5x |
| **Cost per Document** | $0.10 | $0.12 | $0.15 | $0.15 | $0.15 | $0.12 |

### **Qualitative Goals**

✅ **Phase 1:** Multi-model LLM support with smart routing  
✅ **Phase 2:** Adaptive extraction for any document domain  
✅ **Phase 3:** Cross-document entity linking working  
✅ **Phase 4:** Rich, multi-level relationships discovered  
✅ **Phase 5:** Production-ready with full documentation  

---

## 🔄 **Implementation Workflow**

### **For Each Phase:**

1. **Create feature branch**
   ```bash
   git checkout -b feature/phase-N-description
   ```

2. **Implement deliverables**
   - Create new files
   - Modify existing files
   - Add tests
   - Update documentation

3. **Test thoroughly**
   - Unit tests
   - Integration tests
   - Manual testing

4. **Commit with clear messages**
   ```bash
   git add <files>
   git commit -m "feat(service): Description of change"
   ```

5. **Update docs folder**
   ```bash
   git add docs/
   git commit -m "docs: Update documentation for Phase N"
   ```

6. **Merge to main branch**
   ```bash
   git checkout enhance_doc_processing
   git merge feature/phase-N-description
   ```

---

## ⚠️ **Important Notes**

### **What We're NOT Doing (Per User Request)**

❌ **NO Data Validation:**
- Will NOT validate IP addresses for RFC compliance
- Will NOT validate OS versions against known releases
- Will NOT validate port/protocol combinations
- Will NOT validate CIDR notation
- Will NOT modify or reject any data from documents

### **What We ARE Doing**

✅ **Data Ingestion As-Is:**
- Accept all data from client documents without modification
- Preserve original values exactly as provided
- Track data source for traceability
- Let downstream systems/users handle validation if needed

✅ **Intelligent Processing:**
- Classify documents by domain
- Extract entities adaptively
- Infer relationships intelligently
- Link entities across documents
- Build comprehensive knowledge graph

---

## 🎯 **Ready to Start?**

This plan provides:
- ✅ Clear phase-wise breakdown
- ✅ Specific deliverables for each phase
- ✅ Service separation maintained
- ✅ All LLM calls via llm-service
- ✅ Proper logging and tracking
- ✅ Git commit strategy
- ✅ Documentation updates
- ✅ Testing requirements

**Estimated Total Time:** 6 weeks
**Estimated Lines of Code:** ~5,000 new lines
**Estimated Files:** ~30 new files, ~15 modified files

---

**Shall we proceed with Phase 1 implementation?**
