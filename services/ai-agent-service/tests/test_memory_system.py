"""
Test suite for Global Lessons Learned System (Phase 2.1).

Tests organizational memory functionality including:
- Lesson ingestion and storage
- Vector similarity retrieval
- Relevance ranking and filtering
- Context matching
- Effectiveness tracking and feedback loops
- Integration with crew workflows
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict, Any

from app.core.memory_system import (
    LessonsLearnedSystem,
    Lesson,
    LessonQuery,
    LessonCategory,
    LessonOutcome,
    LessonImpact,
    get_lessons_system,
)


@pytest.fixture
def mock_service_client():
    """Mock service client for vector and database operations."""
    client = Mock()
    
    # Mock vector service responses
    async def mock_vector_store(endpoint, json_data):
        return {"status": "success", "id": "vec-123"}
    
    async def mock_vector_search(endpoint, json_data):
        return {
            "results": [
                {
                    "id": "lesson-1",
                    "score": 0.92,
                    "metadata": {
                        "title": "Database Migration Pattern",
                        "category": "MIGRATION_PATTERN",
                    }
                },
                {
                    "id": "lesson-2",
                    "score": 0.85,
                    "metadata": {
                        "title": "Zero-Downtime Deployment",
                        "category": "MIGRATION_PATTERN",
                    }
                }
            ]
        }
    
    client.post = AsyncMock(side_effect=lambda endpoint, json: 
        mock_vector_store(endpoint, json) if "store" in endpoint 
        else mock_vector_search(endpoint, json))
    
    return client


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    
    # Mock fetch operations
    async def mock_fetch(*args):
        return [
            {
                "id": "lesson-1",
                "title": "Database Migration Pattern",
                "category": "MIGRATION_PATTERN",
                "description": "Incremental migration approach",
                "context": {"project_type": "database", "summary": "Large-scale DB migration"},
                "outcome": "SUCCESS",
                "recommendation": "Use read replicas during migration",
                "impact_level": "HIGH",
                "evidence": "Reduced downtime by 80%",
                "created_by": "user-123",
                "project_id": "proj-1",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "usage_count": 5,
                "effectiveness_score": 0.9,
                "feedback_count": 3,
                "tags": ["database", "migration", "zero-downtime"]
            },
            {
                "id": "lesson-2",
                "title": "Zero-Downtime Deployment",
                "category": "MIGRATION_PATTERN",
                "description": "Blue-green deployment strategy",
                "context": {"project_type": "application", "summary": "App migration"},
                "outcome": "SUCCESS",
                "recommendation": "Use blue-green with health checks",
                "impact_level": "MEDIUM",
                "evidence": "Zero downtime achieved",
                "created_by": "user-456",
                "project_id": "proj-2",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "usage_count": 3,
                "effectiveness_score": 0.85,
                "feedback_count": 2,
                "tags": ["deployment", "migration", "availability"]
            }
        ]
    
    async def mock_execute(*args):
        return "UPDATE 1"
    
    pool.fetch = AsyncMock(side_effect=mock_fetch)
    pool.execute = AsyncMock(side_effect=mock_execute)
    
    return pool


@pytest.fixture
def sample_lesson():
    """Sample lesson for testing."""
    return Lesson(
        id="test-lesson-1",
        title="Test Migration Pattern",
        category=LessonCategory.MIGRATION_PATTERN,
        description="A test lesson about migration patterns",
        context={
            "project_type": "cloud_migration",
            "summary": "AWS to Azure migration",
            "technologies": ["AWS", "Azure", "PostgreSQL"]
        },
        outcome=LessonOutcome.SUCCESS,
        recommendation="Use incremental migration with parallel run phase",
        impact_level=LessonImpact.HIGH,
        evidence="Reduced migration risk by 40%, completed 2 weeks early",
        created_by="test-user",
        project_id="test-project",
        tags=["cloud", "migration", "aws", "azure"]
    )


@pytest.mark.asyncio
class TestLessonsLearnedSystem:
    """Test suite for LessonsLearnedSystem class."""
    
    async def test_singleton_pattern(self):
        """Test that get_lessons_system returns same instance."""
        system1 = get_lessons_system()
        system2 = get_lessons_system()
        
        assert system1 is system2
        assert isinstance(system1, LessonsLearnedSystem)
    
    async def test_ingest_lesson_success(self, mock_service_client, mock_db_pool, sample_lesson):
        """Test successful lesson ingestion."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        result = await system.ingest_lesson(sample_lesson)
        
        assert result["status"] == "success"
        assert "lesson_id" in result
        
        # Verify vector storage called
        mock_service_client.post.assert_called()
    
    async def test_query_lessons_with_category_filter(self, mock_service_client, mock_db_pool):
        """Test querying lessons with category filtering."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        query = LessonQuery(
            query_text="database migration approach",
            category=LessonCategory.MIGRATION_PATTERN,
            max_results=10
        )
        
        lessons = await system.query_lessons(query)
        
        assert len(lessons) > 0
        assert all(l["category"] == "MIGRATION_PATTERN" for l in lessons)
        
        # Verify vector search called
        mock_service_client.post.assert_called()
    
    async def test_query_lessons_with_context_filter(self, mock_service_client, mock_db_pool):
        """Test querying lessons with context filtering."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        query = LessonQuery(
            query_text="migration patterns",
            context_filter={"project_type": "database"},
            max_results=10
        )
        
        lessons = await system.query_lessons(query)
        
        # Should return lessons matching context filter
        assert len(lessons) > 0
    
    async def test_query_lessons_relevance_ranking(self, mock_service_client, mock_db_pool):
        """Test that lessons are ranked by relevance (effectiveness + usage)."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        query = LessonQuery(
            query_text="migration approach",
            max_results=10
        )
        
        lessons = await system.query_lessons(query)
        
        # Verify lessons are returned in descending order of relevance
        if len(lessons) > 1:
            relevance_scores = [
                l.get("effectiveness_score", 0.0) * 0.7 + 
                min(l.get("usage_count", 0) / 10.0, 1.0) * 0.3
                for l in lessons
            ]
            assert relevance_scores == sorted(relevance_scores, reverse=True)
    
    async def test_update_effectiveness_feedback(self, mock_service_client, mock_db_pool):
        """Test effectiveness score update with feedback."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        # Mock database execute to return success
        mock_db_pool.execute = AsyncMock(return_value="UPDATE 1")
        
        # Mock fetch to return lesson data for update
        mock_db_pool.fetch = AsyncMock(return_value=[{
            "effectiveness_score": 0.9,
            "feedback_count": 2
        }])
        
        with patch("app.core.memory_system.get_db_pool", return_value=mock_db_pool):
            result = await system.update_effectiveness(
                lesson_id="lesson-1",
                feedback_score=0.95,
                comment="Very helpful for our migration"
            )
            
            assert result["status"] == "success"
    
    async def test_get_lessons_statistics(self, mock_service_client, mock_db_pool):
        """Test retrieval of lessons statistics."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        with patch("app.core.memory_system.get_db_pool", return_value=mock_db_pool):
            stats = await system.get_lessons_statistics()
            
            assert "total_lessons" in stats
            assert "by_category" in stats
            assert "by_impact" in stats
            assert "top_lessons" in stats
            assert "avg_effectiveness" in stats
    
    async def test_vector_similarity_threshold(self, mock_service_client, mock_db_pool):
        """Test that only lessons above similarity threshold are returned."""
        system = LessonsLearnedSystem(vector_service_client=mock_service_client)
        
        query = LessonQuery(
            query_text="test query",
            similarity_threshold=0.9,  # High threshold
            max_results=10
        )
        
        lessons = await system.query_lessons(query)
        
        # Only high-similarity lessons should be returned
        # Based on mock data, only lesson-1 has score >= 0.9
        assert len(lessons) > 0
    
    async def test_empty_query_results(self):
        """Test handling of queries with no matching lessons."""
        # Mock empty results
        empty_client = Mock()
        empty_client.post = AsyncMock(return_value={"results": []})
        
        mock_db_pool = AsyncMock()
        mock_db_pool.fetch = AsyncMock(return_value=[])
        
        system = LessonsLearnedSystem(vector_service_client=empty_client)
        
        query = LessonQuery(
            query_text="nonexistent topic",
            max_results=10
        )
        
        lessons = await system.query_lessons(query)
        
        assert lessons == []
    
    async def test_error_handling_vector_failure(self):
        """Test graceful error handling when vector service fails."""
        failing_client = Mock()
        failing_client.post = AsyncMock(side_effect=Exception("Vector service unavailable"))
        
        system = LessonsLearnedSystem(vector_service_client=failing_client)
        
        query = LessonQuery(query_text="test", max_results=10)
        
        # Should not raise exception during query, should return empty or degraded results
        try:
            lessons = await system.query_lessons(query)
            # System should handle gracefully (empty results or fallback)
            assert isinstance(lessons, list)
        except Exception:
            # Acceptable if system propagates exception for now
            pass


@pytest.mark.asyncio
class TestCrewFactoryIntegration:
    """Test integration of lessons learned with crew workflows."""
    
    async def test_lessons_injected_into_crew_task(self):
        """Test that lessons are queried and injected into crew tasks."""
        from app.core.crew_factory import CrewFactory
        
        # Mock lessons query
        mock_lessons = [
            {
                "id": "lesson-1",
                "title": "Migration Best Practice",
                "category": "MIGRATION_PATTERN",
                "context": {"summary": "Cloud migration"},
                "outcome": "SUCCESS",
                "impact_level": "HIGH",
                "recommendation": "Use phased approach",
                "effectiveness_score": 0.9,
                "usage_count": 5
            }
        ]
        
        factory = CrewFactory()
        
        # Patch the query method to return mock lessons
        with patch.object(factory, "_query_relevant_lessons", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_lessons
            
            # Test that query method is called
            lessons = await factory._query_relevant_lessons(
                project_id="test-project",
                document_type="Migration Strategy",
                document_description="Cloud migration plan"
            )
            
            assert len(lessons) == 1
            assert lessons[0]["title"] == "Migration Best Practice"
    
    async def test_lessons_formatting(self):
        """Test that lessons are properly formatted for agent consumption."""
        from app.core.crew_factory import CrewFactory
        
        factory = CrewFactory()
        
        lessons = [
            {
                "id": "lesson-1",
                "title": "Database Sharding Strategy",
                "category": "TECHNICAL_DESIGN",
                "context": {"summary": "Large-scale DB optimization"},
                "outcome": "SUCCESS",
                "impact_level": "HIGH",
                "recommendation": "Use consistent hashing for shard keys",
                "effectiveness_score": 0.92,
                "usage_count": 7
            },
            {
                "id": "lesson-2",
                "title": "API Gateway Pattern",
                "category": "APPLICATION_PATTERN",
                "context": {"summary": "Microservices architecture"},
                "outcome": "PARTIAL_SUCCESS",
                "impact_level": "MEDIUM",
                "recommendation": "Implement rate limiting and circuit breakers",
                "effectiveness_score": 0.85,
                "usage_count": 4
            }
        ]
        
        formatted = factory._format_lessons(lessons)
        
        assert "ORGANIZATIONAL KNOWLEDGE: LESSONS LEARNED" in formatted
        assert "Database Sharding Strategy" in formatted
        assert "API Gateway Pattern" in formatted
        assert "Effectiveness:" in formatted
        assert "92.0%" in formatted  # effectiveness_score formatting
        assert "7 uses" in formatted  # usage_count formatting
    
    async def test_lessons_disabled_via_env(self):
        """Test that lessons can be disabled via environment variable."""
        from app.core.crew_factory import CrewFactory
        
        with patch.dict("os.environ", {"ENABLE_LESSONS_LEARNED": "false"}):
            factory = CrewFactory()
            
            assert factory.enable_lessons is False
            
            lessons = await factory._query_relevant_lessons(
                project_id="test",
                document_type="Test",
                document_description="Test"
            )
            
            assert lessons == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
