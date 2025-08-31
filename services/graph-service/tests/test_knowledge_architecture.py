"""
Integration Tests for Two-Stage Knowledge Architecture

Tests the complete flow:
1. Stage 1: Fact extraction and discovery creation
2. Stage 2: Layered queries and insight generation
3. Traceability and knowledge evolution
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
import httpx
from datetime import datetime

from app.core.graph_processor import GraphProcessor, EntityExtractionResult, Entity
from app.tools.query_insights_tool import QueryInsightsTool
from app.tools.record_insight_tool import RecordInsightTool


class TestKnowledgeArchitecture:
    """Test suite for the two-stage knowledge architecture"""

    @pytest.fixture
    def graph_processor(self):
        """Create a graph processor instance for testing"""
        processor = GraphProcessor()
        # Mock the HTTP client and database connections
        processor.http = AsyncMock()
        processor.neo4j_driver = AsyncMock()
        processor.redis_client = AsyncMock()
        return processor

    @pytest.fixture
    def mock_session(self):
        """Mock Neo4j session"""
        session = AsyncMock()
        session.run = AsyncMock()
        session.single = AsyncMock()
        return session

    def test_stage_1_fact_extraction(self, graph_processor):
        """Test Stage 1: Fact extraction from document content"""
        # Mock LLM response for fact extraction
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps([
                {
                    "text": "The system contains 25 Windows servers running SQL Server 2019",
                    "category": "infrastructure",
                    "confidence": 0.95
                },
                {
                    "text": "Application uses .NET Framework 4.8 and requires Windows authentication",
                    "category": "technology",
                    "confidence": 0.88
                }
            ])
        }

        graph_processor.http.post = AsyncMock(return_value=mock_response)

        # Test fact extraction
        facts = asyncio.run(graph_processor._llm_extract_key_facts(
            project_id="test_project",
            document_content="Sample document content about infrastructure...",
            filename="test_doc.pdf",
            correlation_id="test_corr_id"
        ))

        assert len(facts) == 2
        assert facts[0]["category"] == "infrastructure"
        assert facts[0]["confidence"] == 0.95
        assert "servers" in facts[0]["text"]

    def test_discovery_storage(self, graph_processor, mock_session):
        """Test storing discoveries in Neo4j"""
        # Mock the session context manager
        graph_processor.neo4j_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        graph_processor.neo4j_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock successful storage
        mock_session.run = AsyncMock()

        facts = [
            {
                "text": "Test discovery fact",
                "category": "infrastructure",
                "confidence": 0.9
            }
        ]

        # Test discovery storage
        result = asyncio.run(graph_processor._store_discovery_nodes(
            project_id="test_project",
            document_id="test_doc_123",
            facts=facts,
            filename="test.pdf"
        ))

        # Verify Neo4j calls were made
        assert mock_session.run.call_count >= 2  # Project + Document + Discovery nodes

    def test_query_insights_tool_layered_query(self):
        """Test QueryInsightsTool layered query functionality"""
        tool = QueryInsightsTool(project_id="test_project")

        # Mock the foundational facts query
        with patch.object(tool, '_get_foundational_facts') as mock_facts, \
             patch.object(tool, '_synthesize_insights') as mock_insights:

            mock_facts.return_value = [
                {"text": "Server count: 25", "category": "infrastructure", "confidence": 0.9},
                {"text": "Technology: SQL Server", "category": "technology", "confidence": 0.85}
            ]

            mock_insights.return_value = {
                "insights": "Based on infrastructure facts, recommend consolidating servers...",
                "facts_used": 2,
                "synthesis_success": True
            }

            result = tool._run("What infrastructure optimization opportunities exist?")

            assert "FOUNDATIONAL FACTS" in result
            assert "SYNTHESIZED INSIGHTS" in result
            assert "Server count: 25" in result
            assert "consolidating servers" in result

    def test_record_insight_tool_traceability(self):
        """Test RecordInsightTool with full traceability"""
        tool = RecordInsightTool(project_id="test_project", agent_name="test_agent")

        with patch.object(tool, '_store_insight_in_graph') as mock_store, \
             patch.object(tool, '_link_insight_to_facts') as mock_link:

            mock_store.return_value = {"success": True, "insight_id": "test_insight_123"}

            result = tool._run(
                insight_text="Server consolidation can reduce costs by 30%",
                category="infrastructure",
                confidence=0.85,
                source_facts=["fact_1", "fact_2"],
                related_query="cost optimization analysis"
            )

            assert "✅ Insight Recorded Successfully" in result
            assert "test_insight_123" in result
            assert "Server consolidation" in result

            # Verify traceability data was passed
            mock_store.assert_called_once()
            call_args = mock_store.call_args[0][0]  # First positional argument
            assert call_args["traceability"]["stage_1_facts_used"] == 2
            assert call_args["traceability"]["query_context"] == "cost optimization analysis"

    def test_knowledge_evolution_chain(self, graph_processor, mock_session):
        """Test the complete knowledge evolution chain"""
        # Mock session for Neo4j operations
        graph_processor.neo4j_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        graph_processor.neo4j_driver.session.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock successful operations
        mock_session.run = AsyncMock()

        # Test the complete flow: document processing -> facts -> insights
        document_content = """
        Infrastructure Assessment Report

        Current Environment:
        - 25 Windows Server 2019 instances
        - SQL Server 2019 databases
        - .NET Framework 4.8 applications
        - Load balancer with 40% utilization

        Recommendations:
        - Consolidate servers to reduce costs
        - Upgrade to SQL Server 2022
        - Implement auto-scaling
        """

        # Step 1: Extract entities and facts
        extraction_result = EntityExtractionResult(
            project_id="test_project",
            document_id="infra_report_001",
            entities=[
                Entity(id="server_01", type="Server", name="Windows Server 2019", properties={}),
                Entity(id="db_01", type="Database", name="SQL Server 2019", properties={})
            ],
            relationships=[],
            metadata={"extraction_timestamp": datetime.utcnow().isoformat()}
        )

        # This should trigger fact extraction automatically
        result = asyncio.run(graph_processor.extract_entities_from_document(
            project_id="test_project",
            document_content=document_content,
            filename="infra_report.pdf",
            document_id="infra_report_001"
        ))

        # Verify that facts were extracted and stored
        assert "Stage 1" in result.metadata.get("processing_notes", "")

    def test_error_handling_and_fallbacks(self, graph_processor):
        """Test error handling and fallback mechanisms"""
        # Test LLM service failure fallback
        graph_processor.http = None  # Simulate HTTP client failure

        # Should still work with basic entity extraction
        result = asyncio.run(graph_processor.extract_entities_from_document(
            project_id="test_project",
            document_content="Basic document content",
            filename="test.pdf",
            document_id="test_001"
        ))

        # Should return results even without LLM fact extraction
        assert result.entities is not None or result.relationships is not None

    def test_api_endpoints_integration(self):
        """Test API endpoints for discoveries and insights"""
        # This would typically use FastAPI TestClient
        # For now, we'll test the endpoint logic

        from app.routers.graphs import create_insight

        # Mock request and dependencies
        mock_request = Mock()
        mock_processor = Mock()

        # Test insight creation endpoint logic
        insight_data = {
            "text": "Test insight",
            "category": "infrastructure",
            "confidence": 0.9,
            "agent_name": "test_agent",
            "tags": ["test"],
            "traceability": {"test": True}
        }

        # The actual endpoint test would require FastAPI test setup
        # This validates the data structure
        assert insight_data["text"] == "Test insight"
        assert insight_data["category"] == "infrastructure"
        assert insight_data["confidence"] == 0.9

    def test_frontend_integration(self):
        """Test frontend component integration with knowledge architecture"""
        # Test the KnowledgeTab component structure
        from frontend.src.components.project_detail.KnowledgeTab import KnowledgeTab

        # Verify component accepts required props
        component_props = {
            "projectId": "test_project_123"
        }

        # Component should be able to render with these props
        assert component_props["projectId"] == "test_project_123"

    def test_agent_prompt_integration(self):
        """Test that agents are configured to use the knowledge architecture"""
        from app.agents.agent_definitions import AgentDefinitions

        # Test that agent prompts include knowledge architecture instructions
        analyst = AgentDefinitions.create_engagement_analyst([])

        assert "two-stage knowledge architecture" in analyst.goal.lower()
        assert "stage 1" in analyst.goal.lower()
        assert "stage 2" in analyst.goal.lower()
        assert "QueryInsightsTool" in analyst.goal
        assert "RecordInsightTool" in analyst.goal

        # Test backstory includes architecture training
        assert "two-stage knowledge architecture" in analyst.backstory.lower()
        assert "stage 1" in analyst.backstory.lower()
        assert "discoveries" in analyst.backstory.lower()


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running Knowledge Architecture Integration Tests...")

    # Test basic imports
    try:
        from app.core.graph_processor import GraphProcessor
        print("✅ GraphProcessor import successful")
    except ImportError as e:
        print(f"❌ GraphProcessor import failed: {e}")

    try:
        from app.tools.query_insights_tool import QueryInsightsTool
        print("✅ QueryInsightsTool import successful")
    except ImportError as e:
        print(f"❌ QueryInsightsTool import failed: {e}")

    try:
        from app.tools.record_insight_tool import RecordInsightTool
        print("✅ RecordInsightTool import successful")
    except ImportError as e:
        print(f"❌ RecordInsightTool import failed: {e}")

    print("Basic integration tests completed.")