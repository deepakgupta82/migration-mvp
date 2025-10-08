"""
Phase 1 Integration Tests: Supervisor + Reflection Loop
Tests end-to-end workflow of Level 3 enhancements
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.supervisor_agent import SupervisorAgent
from app.core.reflection_loop import ReflectionLoop
from app.core.crew_factory import CrewFactory


class TestPhase1Integration:
    """Integration tests for Supervisor + Reflection Loop workflow"""
    
    @pytest.mark.asyncio
    async def test_supervisor_routes_to_reflection_loop(self):
        """Test supervisor correctly identifies document generation tasks and routes to reflection loop"""
        supervisor = SupervisorAgent()
        
        # Document generation query
        query = "Generate a comprehensive migration assessment report for the project"
        project_id = "test-project-123"
        
        intent = await supervisor.analyze_intent(query, {"project_id": project_id})
        
        assert intent["intent_type"] == "comprehensive_assessment"
        routing = await supervisor.route_query(query, intent)
        assert routing["execution_path"] == "full_assessment_crew"
        assert len(routing["agents_selected"]) >= 1
    
    @pytest.mark.asyncio
    async def test_supervisor_simple_query_bypasses_reflection(self):
        """Test supervisor routes simple queries directly, bypassing reflection loop"""
        supervisor = SupervisorAgent()
        
        query = "What OS is server-01 running?"
        project_id = "test-project-123"
        
        intent = await supervisor.analyze_intent(query, {"project_id": project_id})
        
        assert intent["intent_type"] == "simple_fact"
        routing = await supervisor.route_query(query, intent)
        assert routing["execution_path"] == "direct_service_call"
        # Simple queries should not trigger reflection loop
    
    @pytest.mark.asyncio
    async def test_reflection_loop_with_mock_crew(self):
        """Test reflection loop works with mock crew execution"""
        loop = ReflectionLoop(max_iterations=3, quality_threshold=0.9)
        
        iteration_tracker = {"count": 0}
        
        async def mock_producer(context):
            iteration_tracker["count"] += 1
            iteration = context.get("refinement_iteration", 1)
            
            if iteration == 1:
                return "# Migration Assessment\n\nInitial draft with basic content."
            else:
                feedback = context.get("critic_feedback", "")
                return f"# Migration Assessment\n\nImproved draft based on: {feedback}"
        
        async def mock_critic(context):
            iteration = context.get("iteration", 1)
            output = context.get("output", "")
            
            if iteration == 1 and "basic content" in output:
                return {
                    "status": "IMPROVE",
                    "quality_score": 0.7,
                    "feedback": "Add more detailed analysis sections",
                    "issues": [
                        {"type": "completeness", "severity": "major", "description": "Missing detailed sections"}
                    ]
                }
            else:
                return {
                    "status": "PERFECT",
                    "quality_score": 0.95,
                    "feedback": "Excellent comprehensive document",
                    "issues": []
                }
        
        result = await loop.run_reflection_loop(
            producer_func=mock_producer,
            critic_func=mock_critic,
            initial_context={"project_id": "test-123"},
            task_description="Migration Assessment Document"
        )
        
        assert result["status"] == "success"
        assert result["iterations_used"] == 2
        assert result["quality_score"] >= 0.9
        assert iteration_tracker["count"] == 2
    
    @pytest.mark.asyncio
    async def test_crew_factory_reflection_disabled(self):
        """Test crew factory works with reflection disabled"""
        factory = CrewFactory()
        
        # Mock environment variable
        with patch.dict('os.environ', {'ENABLE_REFLECTION_LOOP': 'false'}):
            factory_disabled = CrewFactory()
            
            # Mock LLM and crew
            mock_llm = MagicMock()
            mock_crew = MagicMock()
            mock_crew.kickoff = MagicMock(return_value="Document output")
            
            with patch.object(factory_disabled, 'create_document_generation_crew', return_value=mock_crew):
                result = await factory_disabled.run_document_generation_with_reflection(
                    project_id="test-123",
                    llm=mock_llm,
                    document_type="Migration Assessment",
                    document_description="Comprehensive assessment",
                )
            
            assert result["status"] == "success"
            assert result["method"] == "single_pass"
            assert result["iterations_used"] == 1
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow_simulation(self):
        """Simulate complete workflow: User query → Supervisor → Reflection Loop → Final output"""
        
        # Step 1: User query
        user_query = "Create a detailed cloud migration strategy document"
        project_id = "migration-project-456"
        
        # Step 2: Supervisor analyzes intent
        supervisor = SupervisorAgent()
        intent = await supervisor.analyze_intent(user_query, {"project_id": project_id})
        
        assert intent["intent_type"] in ["focused_analysis", "comprehensive_assessment"]
        
        # Step 3: Route decision
        routing = await supervisor.route_query(user_query, intent)
        assert routing["execution_path"] in ["mini_crew", "full_assessment_crew"]
        
        should_use_reflection = routing["execution_path"] in ["mini_crew", "full_assessment_crew"]
        assert should_use_reflection is True
        
        # Step 4: Mock reflection loop execution
        loop = ReflectionLoop(max_iterations=3)
        
        async def producer(ctx):
            return "# Cloud Migration Strategy\n\n## Overview\nComprehensive strategy document."
        
        async def critic(ctx):
            return {
                "status": "PERFECT",
                "quality_score": 0.92,
                "feedback": "High quality document",
                "issues": []
            }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"project_id": project_id, "intent": intent},
            task_description="Cloud Migration Strategy"
        )
        
        # Step 5: Verify final output
        assert result["status"] == "success"
        assert result["quality_score"] >= 0.9
        assert "Cloud Migration Strategy" in result["final_output"]
    
    @pytest.mark.asyncio
    async def test_supervisor_statistics_tracking(self):
        """Test supervisor tracks query statistics over multiple requests"""
        supervisor = SupervisorAgent()
        
        queries = [
            "What OS is server-01?",
            "Analyze security risks for the database tier",
            "Generate complete migration roadmap with 6Rs analysis",
            "Find all Windows servers",
        ]
        
        for query in queries:
            await supervisor.analyze_intent(query, {"project_id": "test-project"})
        
        # Verify routing history tracked
        assert len(supervisor.routing_history) == 4
        
        # Verify different intent types detected
        intent_types = [entry["intent_type"] for entry in supervisor.routing_history]
        assert "simple_fact" in intent_types
        assert "comprehensive_assessment" in intent_types or "focused_analysis" in intent_types
    
    @pytest.mark.asyncio
    async def test_reflection_loop_statistics_tracking(self):
        """Test reflection loop tracks refinement patterns"""
        loop = ReflectionLoop(max_iterations=3, enable_learning=True)
        
        async def producer(ctx):
            return "Document output"
        
        async def critic(ctx):
            return {
                "status": "PERFECT",
                "quality_score": 0.9,
                "feedback": "Good",
                "issues": [{"type": "clarity", "severity": "minor", "description": "test"}]
            }
        
        # Run multiple times
        for _ in range(5):
            await loop.run_reflection_loop(
                producer_func=producer,
                critic_func=critic,
                initial_context={},
                task_description="Test"
            )
        
        stats = loop.get_refinement_statistics()
        
        assert stats["total_refinements"] == 5
        assert stats["average_iterations"] == 1.0
        assert stats["average_quality"] == 0.9
        assert len(stats["common_issues"]) > 0


class TestPhase1ErrorRecovery:
    """Test error recovery and graceful degradation"""
    
    @pytest.mark.asyncio
    async def test_supervisor_llm_failure_fallback(self):
        """Test supervisor falls back to heuristics when LLM unavailable"""
        supervisor = SupervisorAgent()
        
        # Mock LLM service failure
        with patch.object(supervisor, '_call_llm_for_intent', side_effect=Exception("LLM unavailable")):
            intent = await supervisor.analyze_intent(
                "What is server-01?",  # Shorter query to match simple_fact heuristic
                {"project_id": "test-project"}
            )
            
            # Should still work with heuristic
            assert intent["intent_type"] == "simple_fact"
            assert "method" in intent
            assert intent["method"] == "heuristic_fallback"
    
    @pytest.mark.asyncio
    async def test_reflection_loop_producer_failure_recovery(self):
        """Test reflection loop handles producer failures gracefully"""
        loop = ReflectionLoop(max_iterations=3)
        
        async def failing_producer(ctx):
            raise ValueError("Producer error")
        
        async def critic(ctx):
            return {"status": "PERFECT", "quality_score": 1.0, "feedback": "", "issues": []}
        
        result = await loop.run_reflection_loop(
            producer_func=failing_producer,
            critic_func=critic,
            initial_context={},
            task_description="Test"
        )
        
        assert result["status"] == "error"
        assert "Producer error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_reflection_loop_critic_failure_acceptance(self):
        """Test reflection loop accepts output when critic fails"""
        loop = ReflectionLoop(max_iterations=3)
        
        async def producer(ctx):
            return "Good output"
        
        async def failing_critic(ctx):
            raise RuntimeError("Critic failure")
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=failing_critic,
            initial_context={},
            task_description="Test"
        )
        
        # Should succeed with graceful degradation
        assert result["status"] == "success"
        assert "Critic unavailable" in result["refinement_log"][0]["feedback"]


class TestPhase1PerformanceOptimization:
    """Test performance optimization features"""
    
    @pytest.mark.asyncio
    async def test_supervisor_heuristic_performance(self):
        """Test supervisor heuristic is faster than LLM calls"""
        import time
        
        supervisor = SupervisorAgent()
        
        # Heuristic only (mock LLM to never be called)
        with patch.object(supervisor, '_call_llm_for_intent', side_effect=Exception("Should not be called")):
            start = time.time()
            intent = await supervisor.analyze_intent("What is server-01?", "test")
            heuristic_time = time.time() - start
            
            # Heuristic should complete very quickly (< 0.1 seconds)
            assert heuristic_time < 0.1
            assert intent["method"] == "heuristic_fallback"
    
    @pytest.mark.asyncio
    async def test_reflection_loop_early_termination(self):
        """Test reflection loop terminates early when quality met"""
        loop = ReflectionLoop(max_iterations=10, quality_threshold=0.9)
        
        call_count = {"producer": 0, "critic": 0}
        
        async def producer(ctx):
            call_count["producer"] += 1
            return "Perfect output from start"
        
        async def critic(ctx):
            call_count["critic"] += 1
            return {
                "status": "PERFECT",
                "quality_score": 0.95,
                "feedback": "Perfect",
                "issues": []
            }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={},
            task_description="Test"
        )
        
        # Should terminate after 1 iteration (not 10)
        assert result["iterations_used"] == 1
        assert call_count["producer"] == 1
        assert call_count["critic"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
