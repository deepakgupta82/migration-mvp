# Two-Stage Knowledge Architecture Implementation

## Overview

This document describes the implementation of the **Two-Stage Knowledge Architecture** for the Nagarro Ascent Platform. This architecture fundamentally transforms how knowledge is captured, processed, and utilized across the platform, enabling more intelligent, traceable, and evolvable AI agent interactions.

## Architecture Overview

### Stage 1: Foundational Fact Extraction
**Purpose**: Extract and curate foundational facts from documents
**Components**:
- Enhanced `graph-service` with fact extraction capabilities
- `:Discovery` nodes in Neo4j knowledge graph
- Automatic fact extraction during document processing
- LLM-powered fact identification and categorization

**Key Features**:
- Extracts 3-5 most critical facts per document
- Categorizes facts (infrastructure, technology, business, security, performance, compliance)
- Assigns confidence scores to facts
- Links facts to source documents for traceability

### Stage 2: Layered Insights Synthesis
**Purpose**: Build higher-level insights on top of foundational facts
**Components**:
- `QueryInsightsTool` for layered queries
- `RecordInsightTool` for insight persistence with traceability
- `:Insight` nodes in Neo4j with full lineage tracking
- Agent prompts updated to utilize the knowledge architecture

**Key Features**:
- Layered query processing (facts first, then insights)
- Full traceability from insights back to source facts
- Knowledge evolution through insight chaining
- Agent-driven insight generation and recording

## Implementation Details

### Stage 1 Implementation

#### Enhanced Graph Processor (`services/graph-service/app/core/graph_processor.py`)

```python
# Added fact extraction methods
async def _extract_and_store_key_facts(self, ...)
async def _llm_extract_key_facts(self, ...)
async def _store_discovery_nodes(self, ...)
```

**Key Changes**:
- Fact extraction integrated into document processing pipeline
- Automatic execution after entity extraction
- Facts stored as `:Discovery` nodes with metadata
- Links to source documents maintained

#### API Endpoints (`services/graph-service/app/routers/graphs.py`)

```python
# New discovery endpoints
@router.get("/projects/{project_id}/discoveries")
@router.get("/projects/{project_id}/discoveries/{discovery_id}")
@router.post("/projects/{project_id}/discoveries/search")
```

**Features**:
- List discoveries with filtering and search
- Get detailed discovery information
- Search across discovery text
- Category-based filtering

### Stage 2 Implementation

#### QueryInsightsTool (`services/ai-agent-service/app/tools/query_insights_tool.py`)

```python
class QueryInsightsTool(BaseTool):
    def _run(self, query: str) -> str:
        # 1. Get foundational facts
        facts = self._get_foundational_facts(query)

        # 2. Synthesize insights using facts
        insights = self._synthesize_insights(query, facts)

        # 3. Format layered response
        return self._format_layered_response(query, facts, insights)
```

**Capabilities**:
- Two-stage query processing
- Fact-based insight synthesis
- Layered response formatting
- Fallback to basic RAG when facts unavailable

#### RecordInsightTool (`services/ai-agent-service/app/tools/record_insight_tool.py`)

```python
class RecordInsightTool(BaseTool):
    def _run(self, insight_text: str, ...) -> str:
        # Store insight with full traceability
        result = self._store_insight_in_graph(insight_record)

        # Link to source facts
        if source_facts:
            self._link_insight_to_facts(result["insight_id"], source_facts)
```

**Features**:
- Full traceability metadata
- Links to source facts (`DERIVED_FROM` relationships)
- Agent and query context tracking
- Confidence scoring and categorization

#### Insight API Endpoints

```python
# Insight management endpoints
@router.post("/projects/{project_id}/insights")
@router.get("/projects/{project_id}/insights")
@router.get("/projects/{project_id}/insights/{insight_id}")
@router.post("/projects/{project_id}/insights/{insight_id}/link-fact")
```

### Frontend Implementation

#### Knowledge Tab (`frontend/src/components/project-detail/KnowledgeTab.tsx`)

```typescript
export const KnowledgeTab: React.FC<KnowledgeTabProps> = ({ projectId }) => {
  // Display discoveries and insights
  // Search and filter capabilities
  // Category-based organization
}
```

**Features**:
- Browse foundational facts (Stage 1)
- View synthesized insights (Stage 2)
- Search across knowledge base
- Category filtering and statistics

#### Project Detail View Integration

- Added "Knowledge" tab to project detail view
- Integrated with existing tab structure
- Maintains consistency with other tabs

### Agent Integration

#### Updated Agent Prompts (`services/ai-agent-service/app/agents/agent_definitions.py`)

**Enhanced Agent Instructions**:
```python
goal=(
    'Perform analysis using the two-stage knowledge architecture. '
    'First consult foundational facts (discoveries) from Stage 1, '
    'then synthesize higher-level insights using QueryInsightsTool. '
    'Use RecordInsightTool to persist valuable findings with traceability.'
)
```

**Key Agent Updates**:
- `create_engagement_analyst`: Infrastructure discovery with fact foundation
- `create_principal_cloud_architect`: Migration planning grounded in facts
- `create_post_processing_agent`: Lessons learned with knowledge evolution

## Data Model

### Neo4j Schema Extensions

#### Discovery Nodes
```cypher
(:Discovery {
  id: "discovery_doc123_456",
  text: "The system contains 25 Windows servers",
  category: "infrastructure",
  confidence: 0.95,
  source_document: "infra_report.pdf",
  extracted_at: "2025-08-31T12:00:00Z",
  project_id: "project_123"
})
```

#### Insight Nodes
```cypher
(:Insight {
  id: "insight_proj123_789",
  text: "Server consolidation can reduce costs by 30%",
  category: "infrastructure",
  confidence: 0.85,
  agent_name: "Principal Cloud Architect",
  tags: ["cost_optimization", "consolidation"],
  traceability: {
    stage_1_facts_used: 3,
    query_context: "cost optimization analysis",
    agent_context: "architect_analysis",
    processing_timestamp: "2025-08-31T12:30:00Z"
  },
  created_at: "2025-08-31T12:30:00Z",
  project_id: "project_123"
})
```

#### Relationships
```cypher
// Document contains discoveries
(:Document)-[:CONTAINS_DISCOVERY]->(:Discovery)

// Insights derived from facts
(:Insight)-[:DERIVED_FROM]->(:Discovery)

// Project contains all knowledge
(:Project)-[:CONTAINS]->(:Document)
(:Project)-[:CONTAINS]->(:Insight)
```

## API Reference

### Discovery Endpoints

#### GET `/api/graphs/projects/{project_id}/discoveries`
List discoveries for a project
- **Query Parameters**:
  - `category`: Filter by category
  - `limit`: Maximum results (default: 50)

#### GET `/api/graphs/projects/{project_id}/discoveries/{discovery_id}`
Get detailed discovery information

#### POST `/api/graphs/projects/{project_id}/discoveries/search`
Search discoveries by text
- **Body**: `{"q": "search query", "category": "optional_filter"}`

### Insight Endpoints

#### POST `/api/graphs/projects/{project_id}/insights`
Create a new insight
- **Body**: Insight data with traceability

#### GET `/api/graphs/projects/{project_id}/insights`
List insights for a project
- **Query Parameters**:
  - `category`: Filter by category
  - `agent_name`: Filter by agent
  - `limit`: Maximum results

#### GET `/api/graphs/projects/{project_id}/insights/{insight_id}`
Get detailed insight information including source facts

## Usage Examples

### Basic Fact Query
```python
# Query foundational facts
discoveries = await graph_service.get_project_discoveries(
    project_id="project_123",
    category="infrastructure"
)
```

### Layered Insight Query
```python
# Use QueryInsightsTool for layered analysis
tool = QueryInsightsTool(project_id="project_123")
result = tool.run("What infrastructure optimization opportunities exist?")

# Returns both facts and synthesized insights
```

### Recording Insights
```python
# Record insight with traceability
tool = RecordInsightTool(project_id="project_123", agent_name="architect")
result = tool.run(
    insight_text="Consolidate servers to reduce costs by 30%",
    category="infrastructure",
    confidence=0.85,
    source_facts=["fact_1", "fact_2", "fact_3"],
    related_query="cost optimization analysis"
)
```

## Testing

### Integration Tests (`services/graph-service/tests/test_knowledge_architecture.py`)

**Test Coverage**:
- Stage 1 fact extraction
- Discovery storage and retrieval
- Stage 2 layered queries
- Insight recording with traceability
- Error handling and fallbacks
- API endpoint integration
- Frontend component integration
- Agent prompt integration

**Running Tests**:
```bash
cd services/graph-service
python -m pytest tests/test_knowledge_architecture.py -v
```

## Benefits

### For Users
- **Better Insights**: Layered analysis provides more comprehensive understanding
- **Traceability**: Every insight can be traced back to source facts
- **Knowledge Evolution**: Insights build upon each other over time
- **Consistency**: Facts provide consistent foundation for all analysis

### For Agents
- **Grounded Analysis**: All insights based on actual discovered facts
- **Improved Accuracy**: Fact verification reduces hallucinations
- **Knowledge Sharing**: Insights persist and can be reused
- **Collaboration**: Multiple agents can build upon shared knowledge

### For Platform
- **Scalability**: Knowledge graph enables efficient querying at scale
- **Auditability**: Full traceability for compliance and debugging
- **Evolution**: Knowledge base grows and improves over time
- **Integration**: Clean APIs enable integration with other tools

## Future Enhancements

### Stage 3: Knowledge Reasoning
- Automated insight validation
- Contradiction detection
- Knowledge gap identification
- Automated research suggestions

### Advanced Features
- Insight confidence evolution
- Cross-project knowledge sharing
- Temporal knowledge analysis
- Predictive insights based on patterns

### Integration Opportunities
- External knowledge base integration
- Industry benchmark comparison
- Automated compliance checking
- Predictive maintenance insights

## Migration Guide

### For Existing Projects
1. **Document Reprocessing**: Re-run document processing to extract facts
2. **Agent Updates**: Update agent workflows to use new tools
3. **Frontend Updates**: Enable Knowledge tab in project views
4. **API Integration**: Update any custom integrations to use new endpoints

### For New Projects
1. **Enable Knowledge Architecture**: Automatically enabled for new projects
2. **Configure Categories**: Customize fact categories as needed
3. **Set Up Agents**: Use updated agent definitions
4. **Monitor Insights**: Track insight generation and quality

## Monitoring and Maintenance

### Key Metrics
- **Fact Extraction Rate**: Facts extracted per document
- **Insight Generation Rate**: Insights created per query
- **Traceability Coverage**: Percentage of insights with source links
- **Knowledge Growth**: Rate of knowledge base expansion

### Maintenance Tasks
- **Fact Validation**: Periodic review of fact accuracy
- **Insight Quality**: Monitor and improve insight quality
- **Category Optimization**: Refine fact categories based on usage
- **Performance Tuning**: Optimize query performance as knowledge grows

---

## Conclusion

The Two-Stage Knowledge Architecture represents a fundamental advancement in how the Nagarro Ascent Platform processes, stores, and utilizes knowledge. By separating foundational fact extraction from higher-level insight synthesis, the platform achieves:

- **Improved Accuracy**: Facts provide verified foundation for insights
- **Full Traceability**: Every insight can be traced to its sources
- **Knowledge Evolution**: Insights build upon each other over time
- **Agent Intelligence**: More informed and consistent agent behavior
- **User Trust**: Transparent knowledge generation process

This architecture positions the platform as a leader in enterprise knowledge management and AI-driven analysis.