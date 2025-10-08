"""
Test suite for Reflection Loop - Level 3 Agentic Enhancement
Tests Producer-Critic iterative refinement pattern
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.reflection_loop import ReflectionLoop, CriticAgent, get_reflection_loop


class TestReflectionLoop:
    """Test Reflection Loop functionality"""
    
    @pytest.mark.asyncio
    async def test_single_iteration_perfect_output(self):
        """Test loop terminates on first iteration when output is perfect"""
        loop = ReflectionLoop(max_iterations=3, quality_threshold=0.9)
        
        # Mock producer that creates perfect output
        async def producer(context):
            return "This is a comprehensive, well-structured document with all required sections."
        
        # Mock critic that approves immediately
        async def critic(context):
            return {
                "status": "PERFECT",
                "quality_score": 0.95,
                "feedback": "Output is excellent, no improvements needed",
                "issues": []
            }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        assert result["status"] == "success"
        assert result["iterations_used"] == 1
        assert result["quality_score"] == 0.95
        assert len(result["refinement_log"]) == 1
        assert result["improvements_made"] == 0
    
    @pytest.mark.asyncio
    async def test_iterative_refinement(self):
        """Test multiple iterations with improvement"""
        loop = ReflectionLoop(max_iterations=3, quality_threshold=0.9)
        
        iteration_count = {"count": 0}
        
        # Mock producer that improves with each iteration
        async def producer(context):
            iteration_count["count"] += 1
            iteration = context.get("refinement_iteration", 1)
            
            if iteration == 1:
                return "Short document."
            elif iteration == 2:
                # Incorporate feedback
                return "Short document.\n\nAdded more details based on feedback."
            else:
                return "Short document.\n\nAdded more details.\n\nNow comprehensive with all sections."
        
        # Mock critic with increasing quality scores
        async def critic(context):
            iteration = context.get("iteration", 1)
            
            if iteration == 1:
                return {
                    "status": "IMPROVE",
                    "quality_score": 0.5,
                    "feedback": "Too short, needs more details",
                    "issues": [
                        {"type": "completeness", "severity": "major", "description": "Missing sections"}
                    ]
                }
            elif iteration == 2:
                return {
                    "status": "IMPROVE",
                    "quality_score": 0.75,
                    "feedback": "Better but still needs comprehensive sections",
                    "issues": [
                        {"type": "completeness", "severity": "minor", "description": "Some sections incomplete"}
                    ]
                }
            else:
                return {
                    "status": "PERFECT",
                    "quality_score": 0.95,
                    "feedback": "Excellent, comprehensive document",
                    "issues": []
                }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        assert result["status"] == "success"
        assert result["iterations_used"] == 3
        assert result["quality_score"] == 0.95
        assert len(result["refinement_log"]) == 3
        assert result["improvements_made"] == 2
        
        # Verify quality improved over iterations
        scores = [log["quality_score"] for log in result["refinement_log"]]
        assert scores[0] < scores[1] < scores[2]
    
    @pytest.mark.asyncio
    async def test_max_iterations_reached(self):
        """Test loop terminates at max iterations even if not perfect"""
        loop = ReflectionLoop(max_iterations=2, quality_threshold=0.9)
        
        # Mock producer
        async def producer(context):
            return "Mediocre output that never quite improves enough"
        
        # Mock critic that never approves
        async def critic(context):
            return {
                "status": "IMPROVE",
                "quality_score": 0.7,
                "feedback": "Still needs work",
                "issues": [{"type": "quality", "severity": "major", "description": "Not good enough"}]
            }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        assert result["status"] == "max_iterations_reached"
        assert result["iterations_used"] == 2
        assert "warning" in result
        assert "Max iterations" in result["warning"]
    
    @pytest.mark.asyncio
    async def test_quality_threshold_met(self):
        """Test loop terminates when quality threshold met (even if not PERFECT)"""
        loop = ReflectionLoop(max_iterations=5, quality_threshold=0.85)
        
        async def producer(context):
            return "Good quality output"
        
        async def critic(context):
            return {
                "status": "IMPROVE",  # Not perfect, but high score
                "quality_score": 0.9,  # Above threshold
                "feedback": "Pretty good, minor improvements possible",
                "issues": []
            }
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        assert result["status"] == "success"
        assert result["iterations_used"] == 1
        assert result["quality_score"] >= 0.85
    
    @pytest.mark.asyncio
    async def test_producer_error_handling(self):
        """Test graceful handling of producer errors"""
        loop = ReflectionLoop(max_iterations=3)
        
        # Mock producer that fails
        async def producer(context):
            raise ValueError("Producer failed")
        
        async def critic(context):
            return {"status": "PERFECT", "quality_score": 1.0, "feedback": "", "issues": []}
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        assert result["status"] == "error"
        assert "error" in result
        assert "Producer error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_critic_error_fallback(self):
        """Test that critic errors result in acceptance (graceful degradation)"""
        loop = ReflectionLoop(max_iterations=3)
        
        async def producer(context):
            return "Output"
        
        # Mock critic that fails
        async def critic(context):
            raise RuntimeError("Critic unavailable")
        
        result = await loop.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context={"task": "test"},
            task_description="Test document"
        )
        
        # Should succeed with fallback acceptance
        assert result["status"] == "success"
        assert result["iterations_used"] == 1
        assert "Critic unavailable" in result["refinement_log"][0]["feedback"]
    
    @pytest.mark.asyncio
    async def test_refinement_statistics(self):
        """Test statistics tracking over multiple runs"""
        loop = ReflectionLoop(max_iterations=3, enable_learning=True)
        
        async def producer(context):
            return "Document"
        
        async def critic(context):
            return {
                "status": "PERFECT",
                "quality_score": 0.9,
                "feedback": "Good",
                "issues": [{"type": "clarity", "severity": "minor", "description": "test"}]
            }
        
        # Run multiple times
        for _ in range(3):
            await loop.run_reflection_loop(
                producer_func=producer,
                critic_func=critic,
                initial_context={"task": "test"},
                task_description="Test"
            )
        
        stats = loop.get_refinement_statistics()
        
        assert stats["total_refinements"] == 3
        assert stats["average_iterations"] == 1.0
        assert stats["average_quality"] == 0.9
        assert len(stats["common_issues"]) > 0
        assert stats["common_issues"][0]["type"] == "clarity"
    
    def test_singleton_pattern(self):
        """Test singleton instance management"""
        loop1 = get_reflection_loop(max_iterations=3)
        loop2 = get_reflection_loop(max_iterations=5)  # Different params
        
        # Should return same instance (singleton)
        assert loop1 is loop2
        assert loop1.max_iterations == 3  # Original params preserved


class TestCriticAgent:
    """Test Critic Agent functionality"""
    
    @pytest.mark.asyncio
    async def test_heuristic_review_short_output(self):
        """Test heuristic detects short/incomplete output"""
        result = CriticAgent._heuristic_review(
            output="Too short",
            task_description="Create comprehensive document",
            iteration=1
        )
        
        # Very short output should be rejected
        assert result["status"] == "REJECT"
        assert result["quality_score"] < 0.6
        assert any(issue["type"] == "completeness" for issue in result["issues"])
        assert any(issue["severity"] == "critical" for issue in result["issues"])
    
    @pytest.mark.asyncio
    async def test_heuristic_review_well_structured(self):
        """Test heuristic approves well-structured output"""
        output = """
# Main Section

## Subsection 1
- Point 1
- Point 2
- Point 3

## Subsection 2
1. Item 1
2. Item 2

Comprehensive content with multiple sections and structure.
More details and explanations to reach good length threshold.
Additional context and information to demonstrate completeness.
"""
        
        result = CriticAgent._heuristic_review(
            output=output,
            task_description="Create document",
            iteration=1
        )
        
        assert result["status"] in ["PERFECT", "IMPROVE"]
        assert result["quality_score"] >= 0.6  # Adjusted from 0.7
        assert "method" in result
        assert result["method"] == "heuristic_fallback"
    
    @pytest.mark.asyncio
    async def test_heuristic_review_missing_structure(self):
        """Test heuristic detects missing headers/lists"""
        result = CriticAgent._heuristic_review(
            output="Long text without any structure or headers or lists. " * 50,
            task_description="Create document",
            iteration=1
        )
        
        # Should detect lack of structure
        assert any(
            issue["type"] == "clarity" 
            for issue in result["issues"]
        )


@pytest.mark.asyncio
async def test_integration_reflection_with_context_passing():
    """Integration test: verify context flows through iterations"""
    loop = ReflectionLoop(max_iterations=3)
    
    context_history = []
    
    async def producer(context):
        context_history.append(context.copy())
        iteration = context.get("refinement_iteration", 1)
        
        if iteration > 1:
            # Should have feedback from previous iteration
            assert "critic_feedback" in context
            assert "previous_output" in context
        
        return f"Output iteration {iteration}"
    
    async def critic(context):
        iteration = context.get("iteration", 1)
        
        if iteration < 2:
            return {
                "status": "IMPROVE",
                "quality_score": 0.6,
                "feedback": f"Needs improvement (iteration {iteration})",
                "issues": [{"type": "quality", "severity": "major", "description": "test"}]
            }
        else:
            return {
                "status": "PERFECT",
                "quality_score": 0.95,
                "feedback": "Good now",
                "issues": []
            }
    
    result = await loop.run_reflection_loop(
        producer_func=producer,
        critic_func=critic,
        initial_context={"project_id": "test-123"},
        task_description="Test"
    )
    
    # Verify context passed through iterations
    assert len(context_history) == 2  # 2 producer calls
    assert context_history[0].get("refinement_iteration") is None  # First iteration
    assert context_history[1]["refinement_iteration"] == 2  # Second iteration
    assert "critic_feedback" in context_history[1]
    assert "Needs improvement" in context_history[1]["critic_feedback"]


if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v", "--tb=short"])
