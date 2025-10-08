"""
Tests for Hierarchical Supervision Pattern
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from crewai import Agent, Task

from app.core.hierarchical_crew import (
    HierarchicalSupervision,
    ReviewDecision,
    QualityCriteria,
    ReviewFeedback,
    WorkSubmission,
    SeniorAgentRole,
)


def create_mock_agent(role: str, goal: str = "Mock goal", backstory: str = "Mock backstory"):
    """Helper to create a mock agent with all required attributes."""
    agent = MagicMock(spec=Agent)
    agent.role = role
    agent.goal = goal
    agent.backstory = backstory
    agent.verbose = True
    agent.allow_delegation = False
    agent.max_rpm = None
    agent._rpm_controller = None
    return agent


class TestQualityCriteria:
    """Test quality assessment criteria."""
    
    def test_overall_score_calculation(self):
        """Test weighted average calculation."""
        criteria = QualityCriteria(
            completeness=0.9,
            accuracy=0.8,
            clarity=0.7,
            alignment=0.6,
        )
        
        expected = 0.9 * 0.3 + 0.8 * 0.3 + 0.7 * 0.2 + 0.6 * 0.2
        assert abs(criteria.overall_score - expected) < 0.01
    
    def test_meets_threshold_pass(self):
        """Test quality threshold check - passing."""
        criteria = QualityCriteria(
            completeness=0.8,
            accuracy=0.8,
            clarity=0.8,
            alignment=0.8,
        )
        
        assert criteria.meets_threshold(0.75) is True
        assert criteria.overall_score == 0.8
    
    def test_meets_threshold_fail(self):
        """Test quality threshold check - failing."""
        criteria = QualityCriteria(
            completeness=0.6,
            accuracy=0.6,
            clarity=0.6,
            alignment=0.6,
        )
        
        assert criteria.meets_threshold(0.75) is False
        assert criteria.overall_score == 0.6


class TestReviewFeedback:
    """Test review feedback structure."""
    
    def test_review_feedback_creation(self):
        """Test creating review feedback."""
        criteria = QualityCriteria(
            completeness=0.9,
            accuracy=0.85,
            clarity=0.8,
            alignment=0.9,
        )
        
        feedback = ReviewFeedback(
            decision=ReviewDecision.APPROVE,
            quality_scores=criteria,
            strengths=["Well structured", "Comprehensive coverage"],
            improvements=[],
            reviewer_role="Principal Cloud Architect",
            iteration=1,
        )
        
        assert feedback.decision == ReviewDecision.APPROVE
        assert feedback.quality_scores.overall_score > 0.85
        assert len(feedback.strengths) == 2
        assert feedback.iteration == 1


class TestHierarchicalSupervision:
    """Test hierarchical supervision system."""
    
    def test_initialization(self):
        """Test system initialization with defaults."""
        supervision = HierarchicalSupervision()
        
        assert supervision.max_iterations == 3
        assert supervision.quality_threshold == 0.75
        assert supervision.enable_mentorship is True
    
    def test_initialization_custom(self):
        """Test system initialization with custom values."""
        supervision = HierarchicalSupervision(
            max_iterations=5,
            quality_threshold=0.85,
            enable_mentorship=False,
        )
        
        assert supervision.max_iterations == 5
        assert supervision.quality_threshold == 0.85
        assert supervision.enable_mentorship is False
    
    def test_create_senior_agent_architect(self):
        """Test creating principal architect senior agent."""
        supervision = HierarchicalSupervision()
        tools = []
        
        agent = supervision.create_senior_agent(
            role=SeniorAgentRole.PRINCIPAL_ARCHITECT,
            tools=tools,
        )
        
        assert "Principal Cloud Architect" in agent.role
        assert "Senior Reviewer" in agent.role
        assert "20+ years" in agent.backstory
        assert agent.allow_delegation is False
    
    def test_create_senior_agent_security(self):
        """Test creating chief security officer senior agent."""
        supervision = HierarchicalSupervision()
        tools = []
        
        agent = supervision.create_senior_agent(
            role=SeniorAgentRole.CHIEF_SECURITY_OFFICER,
            tools=tools,
        )
        
        assert "Chief Security Officer" in agent.role
        assert "18+ years" in agent.backstory
        assert "CISSP" in agent.backstory
    
    def test_create_senior_agent_program_manager(self):
        """Test creating lead program manager senior agent."""
        supervision = HierarchicalSupervision()
        tools = []
        
        agent = supervision.create_senior_agent(
            role=SeniorAgentRole.LEAD_PROGRAM_MANAGER,
            tools=tools,
        )
        
        assert "Lead Migration Program Manager" in agent.role
        assert "15+ years" in agent.backstory
        assert "PMP" in agent.backstory
    
    def test_create_review_task_initial(self):
        """Test creating initial review task."""
        supervision = HierarchicalSupervision()
        senior_agent = create_mock_agent("Principal Cloud Architect")
        
        submission = WorkSubmission(
            content="Architecture design for cloud migration...",
            task_description="Design cloud architecture",
            agent_role="Cloud Architect",
            iteration=1,
        )
        
        # Patch Task creation to avoid agent validation
        with patch("app.core.hierarchical_crew.Task") as MockTask:
            mock_task = Mock()
            MockTask.return_value = mock_task
            
            task = supervision.create_review_task(
                senior_agent=senior_agent,
                submission=submission,
                quality_threshold=0.75,
            )
            
            # Verify Task was called with correct arguments
            MockTask.assert_called_once()
            call_kwargs = MockTask.call_args[1]
            
            assert "Review the following work" in call_kwargs["description"]
            assert "Cloud Architect" in call_kwargs["description"]
            assert "Iteration 1" in call_kwargs["description"]
            assert call_kwargs["agent"] == senior_agent
    
    def test_create_review_task_with_feedback(self):
        """Test creating review task with previous feedback."""
        supervision = HierarchicalSupervision()
        senior_agent = create_mock_agent("Principal Cloud Architect")
        
        previous_feedback = ReviewFeedback(
            decision=ReviewDecision.REVISE,
            quality_scores=QualityCriteria(
                completeness=0.7,
                accuracy=0.6,
                clarity=0.65,
                alignment=0.7,
            ),
            strengths=["Good structure"],
            improvements=["Add more detail", "Improve accuracy"],
            revision_guidance="Please expand section 3",
            reviewer_role="Principal Architect",
            iteration=1,
        )
        
        submission = WorkSubmission(
            content="Revised architecture...",
            task_description="Design cloud architecture",
            agent_role="Cloud Architect",
            iteration=2,
            previous_feedback=previous_feedback,
        )
        
        # Patch Task creation to avoid agent validation
        with patch("app.core.hierarchical_crew.Task") as MockTask:
            mock_task = Mock()
            MockTask.return_value = mock_task
            
            task = supervision.create_review_task(
                senior_agent=senior_agent,
                submission=submission,
                quality_threshold=0.75,
            )
            
            # Verify Task was called with feedback context
            MockTask.assert_called_once()
            call_kwargs = MockTask.call_args[1]
            
            assert "Previous Review" in call_kwargs["description"]
            assert "Iteration 1" in call_kwargs["description"]
            assert "Add more detail" in call_kwargs["description"]
    
    def test_parse_review_feedback_json(self):
        """Test parsing review feedback from JSON output."""
        supervision = HierarchicalSupervision()
        
        review_output = """
```json
{
    "decision": "approve",
    "quality_scores": {
        "completeness": 0.9,
        "accuracy": 0.85,
        "clarity": 0.8,
        "alignment": 0.9
    },
    "strengths": ["Excellent coverage", "Clear structure"],
    "improvements": [],
    "revision_guidance": null,
    "escalation_reason": null
}
```
"""
        
        feedback = supervision.parse_review_feedback(
            review_output=review_output,
            reviewer_role="Principal Architect",
            iteration=1,
        )
        
        assert feedback.decision == ReviewDecision.APPROVE
        assert feedback.quality_scores.completeness == 0.9
        assert feedback.quality_scores.accuracy == 0.85
        assert len(feedback.strengths) == 2
        assert feedback.reviewer_role == "Principal Architect"
    
    def test_parse_review_feedback_revise(self):
        """Test parsing revise decision feedback."""
        supervision = HierarchicalSupervision()
        
        review_output = """
{
    "decision": "revise",
    "quality_scores": {
        "completeness": 0.7,
        "accuracy": 0.75,
        "clarity": 0.65,
        "alignment": 0.7
    },
    "strengths": ["Good foundation"],
    "improvements": ["Add security section", "Expand cost analysis"],
    "revision_guidance": "Please add a dedicated security architecture section",
    "escalation_reason": null
}
"""
        
        feedback = supervision.parse_review_feedback(
            review_output=review_output,
            reviewer_role="Security Officer",
            iteration=2,
        )
        
        assert feedback.decision == ReviewDecision.REVISE
        assert len(feedback.improvements) == 2
        assert "security" in feedback.revision_guidance.lower()
    
    def test_parse_review_feedback_escalate(self):
        """Test parsing escalate decision feedback."""
        supervision = HierarchicalSupervision()
        
        review_output = """
{
    "decision": "escalate",
    "quality_scores": {
        "completeness": 0.4,
        "accuracy": 0.3,
        "clarity": 0.5,
        "alignment": 0.4
    },
    "strengths": [],
    "improvements": ["Fundamental redesign needed"],
    "revision_guidance": null,
    "escalation_reason": "Architecture does not meet basic security requirements"
}
"""
        
        feedback = supervision.parse_review_feedback(
            review_output=review_output,
            reviewer_role="Chief Security Officer",
            iteration=3,
        )
        
        assert feedback.decision == ReviewDecision.ESCALATE
        assert feedback.escalation_reason is not None
        assert "security" in feedback.escalation_reason.lower()
    
    def test_parse_review_feedback_invalid_json(self):
        """Test parsing invalid JSON returns escalation."""
        supervision = HierarchicalSupervision()
        
        review_output = "This is not valid JSON"
        
        feedback = supervision.parse_review_feedback(
            review_output=review_output,
            reviewer_role="Reviewer",
            iteration=1,
        )
        
        # Should return escalation when parsing fails
        assert feedback.decision == ReviewDecision.ESCALATE
        assert "parsing failed" in feedback.escalation_reason.lower()
    
    @pytest.mark.asyncio
    async def test_supervise_workflow_approve_first_iteration(self):
        """Test workflow approved on first iteration."""
        supervision = HierarchicalSupervision()
        junior_agent = create_mock_agent("Cloud Architect")
        senior_agent = create_mock_agent("Principal Architect")
        
        # Mock task
        task = Mock(spec=Task)
        task.description = "Design cloud architecture"
        task.expected_output = "Architecture document"
        
        # Mock crew execution and Task creation
        with patch("app.core.hierarchical_crew.Crew") as MockCrew, \
             patch("app.core.hierarchical_crew.Task") as MockTask:
            
            # Mock Task creation
            MockTask.return_value = Mock(spec=Task)
            
            # First execution: junior work
            work_crew_instance = Mock()
            work_crew_instance.kickoff.return_value = "Excellent architecture design..."
            
            # Second execution: senior review
            review_crew_instance = Mock()
            review_crew_instance.kickoff.return_value = """
{
    "decision": "approve",
    "quality_scores": {
        "completeness": 0.9,
        "accuracy": 0.9,
        "clarity": 0.85,
        "alignment": 0.9
    },
    "strengths": ["Comprehensive", "Well structured"],
    "improvements": [],
    "revision_guidance": null,
    "escalation_reason": null
}
"""
            
            MockCrew.side_effect = [work_crew_instance, review_crew_instance]
            
            result = await supervision.supervise_workflow(
                junior_agent=junior_agent,
                senior_agent=senior_agent,
                initial_task=task,
            )
        
        assert result["status"] == "approved"
        assert result["iterations"] == 1
        assert result["final_quality_score"] > 0.85
        assert len(result["review_history"]) == 1
    
    @pytest.mark.asyncio
    async def test_supervise_workflow_revise_then_approve(self):
        """Test workflow with revision then approval."""
        supervision = HierarchicalSupervision()
        junior_agent = create_mock_agent("Cloud Architect")
        senior_agent = create_mock_agent("Principal Architect")
        
        task = Mock(spec=Task)
        task.description = "Design cloud architecture"
        task.expected_output = "Architecture document"
        
        with patch("app.core.hierarchical_crew.Crew") as MockCrew, \
             patch("app.core.hierarchical_crew.Task") as MockTask:
            
            MockTask.return_value = Mock(spec=Task)
            
            # First iteration: work + review (revise)
            work1 = Mock()
            work1.kickoff.return_value = "Initial design..."
            
            review1 = Mock()
            review1.kickoff.return_value = """
{
    "decision": "revise",
    "quality_scores": {"completeness": 0.7, "accuracy": 0.7, "clarity": 0.7, "alignment": 0.7},
    "strengths": ["Good start"],
    "improvements": ["Add security"],
    "revision_guidance": "Add security section",
    "escalation_reason": null
}
"""
            
            # Second iteration: revised work + review (approve)
            work2 = Mock()
            work2.kickoff.return_value = "Revised design with security..."
            
            review2 = Mock()
            review2.kickoff.return_value = """
{
    "decision": "approve",
    "quality_scores": {"completeness": 0.9, "accuracy": 0.9, "clarity": 0.85, "alignment": 0.9},
    "strengths": ["Complete", "Secure"],
    "improvements": [],
    "revision_guidance": null,
    "escalation_reason": null
}
"""
            
            MockCrew.side_effect = [work1, review1, work2, review2]
            
            result = await supervision.supervise_workflow(
                junior_agent=junior_agent,
                senior_agent=senior_agent,
                initial_task=task,
            )
        
        assert result["status"] == "approved"
        assert result["iterations"] == 2
        assert len(result["review_history"]) == 2
        assert result["review_history"][0]["decision"] == "revise"
        assert result["review_history"][1]["decision"] == "approve"
    
    @pytest.mark.asyncio
    async def test_supervise_workflow_escalation(self):
        """Test workflow with escalation."""
        supervision = HierarchicalSupervision()
        junior_agent = create_mock_agent("Cloud Architect")
        senior_agent = create_mock_agent("Principal Architect")
        
        task = Mock(spec=Task)
        task.description = "Design"
        task.expected_output = "Document"
        
        with patch("app.core.hierarchical_crew.Crew") as MockCrew, \
             patch("app.core.hierarchical_crew.Task") as MockTask:
            
            MockTask.return_value = Mock(spec=Task)
            
            work = Mock()
            work.kickoff.return_value = "Poor design..."
            
            review = Mock()
            review.kickoff.return_value = """
{
    "decision": "escalate",
    "quality_scores": {"completeness": 0.3, "accuracy": 0.3, "clarity": 0.3, "alignment": 0.3},
    "strengths": [],
    "improvements": ["Complete redesign"],
    "revision_guidance": null,
    "escalation_reason": "Fundamental issues require senior review"
}
"""
            
            MockCrew.side_effect = [work, review]
            
            result = await supervision.supervise_workflow(
                junior_agent=junior_agent,
                senior_agent=senior_agent,
                initial_task=task,
            )
        
        assert result["status"] == "escalated"
        assert result["escalation_reason"] is not None
        assert "senior" in result["escalation_reason"].lower()
    
    @pytest.mark.asyncio
    async def test_supervise_workflow_max_iterations(self):
        """Test workflow reaching max iterations."""
        supervision = HierarchicalSupervision(max_iterations=2)
        junior_agent = create_mock_agent("Cloud Architect")
        senior_agent = create_mock_agent("Principal Architect")
        
        task = Mock(spec=Task)
        task.description = "Design"
        task.expected_output = "Document"
        
        with patch("app.core.hierarchical_crew.Crew") as MockCrew, \
             patch("app.core.hierarchical_crew.Task") as MockTask:
            
            MockTask.return_value = Mock(spec=Task)
            
            # Always return revise decision
            work = Mock()
            work.kickoff.return_value = "Design..."
            
            review = Mock()
            review.kickoff.return_value = """
{
    "decision": "revise",
    "quality_scores": {"completeness": 0.7, "accuracy": 0.7, "clarity": 0.7, "alignment": 0.7},
    "strengths": ["Decent"],
    "improvements": ["More detail"],
    "revision_guidance": "Add more",
    "escalation_reason": null
}
"""
            
            MockCrew.side_effect = [work, review, work, review]
            
            result = await supervision.supervise_workflow(
                junior_agent=junior_agent,
                senior_agent=senior_agent,
                initial_task=task,
            )
        
        assert result["status"] == "max_iterations_reached"
        assert result["iterations"] == 2
        assert len(result["review_history"]) == 2
