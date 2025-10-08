"""
Hierarchical Supervision Pattern for AI Agent Service
Implements senior-junior agent workflow with review cycles, quality gates, and mentorship.

This module provides a hierarchical supervision framework where senior agents review
and approve work from junior agents, providing feedback and ensuring quality standards.
The pattern supports approve/revise/escalate decision gates with configurable criteria.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Literal
from enum import Enum
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process

from app.agents.agent_definitions import AgentDefinitions
from app.core.agent_logs import AgentLogStreamHandler

logger = logging.getLogger(__name__)


class ReviewDecision(str, Enum):
    """Possible review decisions from senior agents."""
    APPROVE = "approve"
    REVISE = "revise"
    ESCALATE = "escalate"


class QualityCriteria(BaseModel):
    """Quality assessment criteria for work review."""
    completeness: float = Field(ge=0.0, le=1.0, description="Coverage of all required elements")
    accuracy: float = Field(ge=0.0, le=1.0, description="Technical correctness and factual accuracy")
    clarity: float = Field(ge=0.0, le=1.0, description="Clear communication and organization")
    alignment: float = Field(ge=0.0, le=1.0, description="Alignment with objectives and requirements")
    
    @property
    def overall_score(self) -> float:
        """Calculate weighted average quality score."""
        return (
            self.completeness * 0.3 +
            self.accuracy * 0.3 +
            self.clarity * 0.2 +
            self.alignment * 0.2
        )
    
    def meets_threshold(self, threshold: float = 0.75) -> bool:
        """Check if quality meets approval threshold."""
        return self.overall_score >= threshold


class ReviewFeedback(BaseModel):
    """Feedback from senior agent review."""
    decision: ReviewDecision
    quality_scores: QualityCriteria
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    revision_guidance: Optional[str] = None
    escalation_reason: Optional[str] = None
    reviewer_role: str
    iteration: int


class WorkSubmission(BaseModel):
    """Work submitted by junior agent for review."""
    content: str
    task_description: str
    agent_role: str
    iteration: int = 0
    previous_feedback: Optional[ReviewFeedback] = None


class SeniorAgentRole(str, Enum):
    """Senior agent roles for specialized review."""
    PRINCIPAL_ARCHITECT = "principal_architect"
    CHIEF_SECURITY_OFFICER = "chief_security_officer"
    LEAD_PROGRAM_MANAGER = "lead_program_manager"
    SENIOR_RESEARCHER = "senior_researcher"


class HierarchicalSupervision:
    """
    Hierarchical supervision framework for senior-junior agent workflows.
    
    Implements a review cycle where:
    1. Junior agent performs initial work
    2. Senior agent reviews with quality criteria
    3. Decision: approve, revise (with guidance), or escalate
    4. If revise, junior agent incorporates feedback and resubmits
    5. Continue until approval or max iterations reached
    
    Configuration:
    - max_iterations: Maximum review cycles before escalation
    - quality_threshold: Minimum quality score for approval
    - enable_mentorship: Include learning guidance in feedback
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        quality_threshold: float = 0.75,
        enable_mentorship: bool = True,
    ):
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.enable_mentorship = enable_mentorship
        self.logger = logger
    
    def create_senior_agent(
        self,
        role: SeniorAgentRole,
        tools: List[Any],
        llm: Optional[Any] = None,
    ) -> Agent:
        """
        Create a senior agent for specialized review.
        
        Args:
            role: Senior agent specialization
            tools: Available tools for review
            llm: Optional language model
            
        Returns:
            Configured senior agent
        """
        role_configs = {
            SeniorAgentRole.PRINCIPAL_ARCHITECT: {
                "role": "Principal Cloud Architect (Senior Reviewer)",
                "goal": (
                    "Review cloud architecture and migration designs for technical excellence, "
                    "scalability, and alignment with best practices. Provide actionable feedback "
                    "to junior architects to improve design quality and ensure successful implementation."
                ),
                "backstory": (
                    "You are a Principal Cloud Architect with 20+ years of experience leading "
                    "large-scale cloud transformations for Fortune 500 companies. You have architected "
                    "systems handling millions of transactions per day across AWS, Azure, and GCP. "
                    "Your expertise includes distributed systems, microservices, security architecture, "
                    "and cost optimization. You are known for your mentorship abilities, having trained "
                    "over 100 architects. You provide clear, constructive feedback that helps junior "
                    "team members grow while ensuring deliverables meet the highest standards. You can "
                    "quickly identify architectural risks, scalability bottlenecks, and security gaps."
                ),
            },
            SeniorAgentRole.CHIEF_SECURITY_OFFICER: {
                "role": "Chief Security Officer (Senior Reviewer)",
                "goal": (
                    "Review security implementations, compliance assessments, and risk analyses for "
                    "thoroughness and alignment with security best practices. Provide expert guidance "
                    "to ensure all security considerations are addressed comprehensively."
                ),
                "backstory": (
                    "You are a Chief Security Officer with 18+ years of experience in cybersecurity, "
                    "compliance, and risk management across multiple industries. You hold CISSP, CISM, "
                    "and other security certifications. You have led security programs for organizations "
                    "handling sensitive data under GDPR, HIPAA, PCI-DSS, and SOC2 frameworks. Your "
                    "expertise includes threat modeling, security architecture review, penetration testing, "
                    "and incident response. You excel at identifying security gaps that others miss and "
                    "providing practical remediation guidance. You balance security rigor with business "
                    "pragmatism, mentoring security professionals to think strategically about risk."
                ),
            },
            SeniorAgentRole.LEAD_PROGRAM_MANAGER: {
                "role": "Lead Migration Program Manager (Senior Reviewer)",
                "goal": (
                    "Review migration plans, timelines, and resource allocations for feasibility, "
                    "completeness, and risk management. Provide feedback to ensure plans are "
                    "executable and aligned with stakeholder expectations."
                ),
                "backstory": (
                    "You are a Lead Program Manager with 15+ years managing enterprise IT transformations "
                    "worth hundreds of millions of dollars. You have successfully delivered over 50 major "
                    "migration programs with complex stakeholder environments and tight deadlines. Your "
                    "expertise includes project governance, risk management, resource planning, and change "
                    "management. You are certified in PMP, PRINCE2, and agile methodologies. You excel at "
                    "identifying unrealistic timelines, resource constraints, and hidden dependencies. You "
                    "provide actionable feedback that helps junior program managers create robust, "
                    "executable plans with appropriate contingencies."
                ),
            },
            SeniorAgentRole.SENIOR_RESEARCHER: {
                "role": "Senior Research Analyst (Senior Reviewer)",
                "goal": (
                    "Review research findings, document analysis, and information synthesis for accuracy, "
                    "completeness, and insight quality. Provide feedback to improve research rigor and "
                    "ensure all relevant information is captured."
                ),
                "backstory": (
                    "You are a Senior Research Analyst with 12+ years in enterprise information analysis "
                    "and knowledge synthesis. You have analyzed thousands of complex technical documents "
                    "for major consulting firms and technology companies. Your expertise includes advanced "
                    "search methodologies, pattern recognition, data validation, and insight extraction. "
                    "You excel at identifying missing information, inconsistencies, and opportunities for "
                    "deeper analysis. You mentor junior researchers on effective information gathering, "
                    "source validation, and synthesis techniques. Your reviews ensure research deliverables "
                    "are thorough, accurate, and actionable."
                ),
            },
        }
        
        config = role_configs[role]
        agent_kwargs = {
            "role": config["role"],
            "goal": config["goal"],
            "backstory": config["backstory"],
            "tools": tools,
            "verbose": True,
            "allow_delegation": False,
        }
        
        if llm is not None:
            agent_kwargs["llm"] = llm
        
        return Agent(**agent_kwargs)
    
    def create_review_task(
        self,
        senior_agent: Agent,
        submission: WorkSubmission,
        quality_threshold: float,
    ) -> Task:
        """
        Create a review task for senior agent.
        
        Args:
            senior_agent: Reviewing agent
            submission: Work to review
            quality_threshold: Minimum acceptable quality score
            
        Returns:
            Configured review task
        """
        feedback_context = ""
        if submission.previous_feedback:
            feedback_context = f"""

Previous Review (Iteration {submission.previous_feedback.iteration}):
Decision: {submission.previous_feedback.decision.value}
Quality Score: {submission.previous_feedback.quality_scores.overall_score:.2f}
Improvements Requested:
{chr(10).join(f"- {item}" for item in submission.previous_feedback.improvements)}

Revision Guidance:
{submission.previous_feedback.revision_guidance or "N/A"}
"""
        
        description = f"""
Review the following work from {submission.agent_role} (Iteration {submission.iteration}):

TASK: {submission.task_description}

SUBMITTED WORK:
{submission.content}
{feedback_context}

REVIEW CRITERIA:
1. Completeness (30%): All required elements present and thoroughly addressed
2. Accuracy (30%): Technical correctness, factual accuracy, no errors
3. Clarity (20%): Clear communication, logical organization, professional presentation
4. Alignment (20%): Meets objectives, follows requirements and best practices

QUALITY THRESHOLD: {quality_threshold:.0%}

REVIEW INSTRUCTIONS:
1. Assess work against each criterion (0.0-1.0 score)
2. Calculate overall quality score (weighted average)
3. Make decision:
   - APPROVE: Quality score >= {quality_threshold:.0%} and meets all critical requirements
   - REVISE: Quality score < {quality_threshold:.0%} but improvable with guidance
   - ESCALATE: Fundamental issues requiring senior leadership intervention
4. Provide specific, actionable feedback:
   - List 2-3 key strengths
   - List specific improvements needed (if revise)
   - Provide clear revision guidance (if revise)
   - Explain escalation reason (if escalate)

OUTPUT FORMAT (JSON):
{{
    "decision": "approve|revise|escalate",
    "quality_scores": {{
        "completeness": 0.0-1.0,
        "accuracy": 0.0-1.0,
        "clarity": 0.0-1.0,
        "alignment": 0.0-1.0
    }},
    "strengths": ["strength 1", "strength 2", ...],
    "improvements": ["improvement 1", "improvement 2", ...],
    "revision_guidance": "Specific actionable guidance for revision",
    "escalation_reason": "Reason for escalation (if applicable)"
}}
"""
        
        return Task(
            description=description,
            agent=senior_agent,
            expected_output="Structured review feedback in JSON format with decision and quality scores",
        )
    
    def parse_review_feedback(
        self,
        review_output: str,
        reviewer_role: str,
        iteration: int,
    ) -> ReviewFeedback:
        """
        Parse review output into structured feedback.
        
        Args:
            review_output: Raw review output from senior agent
            reviewer_role: Role of reviewing agent
            iteration: Current iteration number
            
        Returns:
            Structured review feedback
        """
        import json
        
        try:
            # Extract JSON from output (handle markdown code blocks)
            if "```json" in review_output:
                start = review_output.find("```json") + 7
                end = review_output.find("```", start)
                json_str = review_output[start:end].strip()
            elif "```" in review_output:
                start = review_output.find("```") + 3
                end = review_output.find("```", start)
                json_str = review_output[start:end].strip()
            else:
                json_str = review_output.strip()
            
            data = json.loads(json_str)
            
            return ReviewFeedback(
                decision=ReviewDecision(data["decision"]),
                quality_scores=QualityCriteria(**data["quality_scores"]),
                strengths=data.get("strengths", []),
                improvements=data.get("improvements", []),
                revision_guidance=data.get("revision_guidance"),
                escalation_reason=data.get("escalation_reason"),
                reviewer_role=reviewer_role,
                iteration=iteration,
            )
        except Exception as e:
            logger.error(f"Failed to parse review feedback: {e}")
            # Return default escalation if parsing fails
            return ReviewFeedback(
                decision=ReviewDecision.ESCALATE,
                quality_scores=QualityCriteria(
                    completeness=0.0,
                    accuracy=0.0,
                    clarity=0.0,
                    alignment=0.0,
                ),
                strengths=[],
                improvements=["Review output could not be parsed"],
                escalation_reason=f"Review parsing failed: {str(e)}",
                reviewer_role=reviewer_role,
                iteration=iteration,
            )
    
    async def supervise_workflow(
        self,
        junior_agent: Agent,
        senior_agent: Agent,
        initial_task: Task,
        project_id: Optional[str] = None,
        websocket_callback = None,
    ) -> Dict[str, Any]:
        """
        Execute supervised workflow with review cycles.
        
        Args:
            junior_agent: Agent performing initial work
            senior_agent: Agent reviewing work
            initial_task: Task to complete
            project_id: Optional project context
            websocket_callback: Optional async callback(event_type, data) for streaming
            
        Returns:
            Final approved work with review history
        """
        iteration = 0
        current_submission = None
        review_history = []
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Starting iteration {iteration}/{self.max_iterations}")
            
            # Stream review cycle start
            if websocket_callback:
                try:
                    await websocket_callback("review_cycle_start", {
                        "cycle": iteration,
                        "max_cycles": self.max_iterations
                    })
                except Exception as e:
                    logger.warning(f"WebSocket callback failed: {e}")
            
            # Junior agent performs work
            if iteration == 1:
                # Initial work
                work_crew = Crew(
                    agents=[junior_agent],
                    tasks=[initial_task],
                    process=Process.sequential,
                    verbose=True,
                )
                work_result = work_crew.kickoff()
                work_content = str(work_result)
            else:
                # Revision based on feedback
                revision_task = Task(
                    description=f"""
{initial_task.description}

REVISION REQUIRED (Iteration {iteration})
Previous quality score: {current_submission.previous_feedback.quality_scores.overall_score:.2f}

FEEDBACK FROM {current_submission.previous_feedback.reviewer_role}:
Strengths:
{chr(10).join(f"- {item}" for item in current_submission.previous_feedback.strengths)}

Improvements Needed:
{chr(10).join(f"- {item}" for item in current_submission.previous_feedback.improvements)}

REVISION GUIDANCE:
{current_submission.previous_feedback.revision_guidance}

Incorporate this feedback and submit revised work.
""",
                    agent=junior_agent,
                    expected_output=initial_task.expected_output,
                )
                
                revision_crew = Crew(
                    agents=[junior_agent],
                    tasks=[revision_task],
                    process=Process.sequential,
                    verbose=True,
                )
                work_result = revision_crew.kickoff()
                work_content = str(work_result)
            
            # Create submission
            current_submission = WorkSubmission(
                content=work_content,
                task_description=initial_task.description,
                agent_role=junior_agent.role,
                iteration=iteration,
                previous_feedback=current_submission.previous_feedback if iteration > 1 else None,
            )
            
            # Senior agent reviews
            review_task = self.create_review_task(
                senior_agent=senior_agent,
                submission=current_submission,
                quality_threshold=self.quality_threshold,
            )
            
            review_crew = Crew(
                agents=[senior_agent],
                tasks=[review_task],
                process=Process.sequential,
                verbose=True,
            )
            review_result = review_crew.kickoff()
            
            # Parse feedback
            feedback = self.parse_review_feedback(
                review_output=str(review_result),
                reviewer_role=senior_agent.role,
                iteration=iteration,
            )
            review_history.append(feedback)
            
            logger.info(
                f"Review decision: {feedback.decision.value}, "
                f"quality score: {feedback.quality_scores.overall_score:.2f}"
            )
            
            # Stream review feedback
            if websocket_callback:
                try:
                    await websocket_callback("review_feedback", {
                        "cycle": iteration,
                        "decision": feedback.decision.value,
                        "quality_score": feedback.quality_scores.overall_score,
                        "completeness": feedback.quality_scores.completeness,
                        "accuracy": feedback.quality_scores.accuracy,
                        "clarity": feedback.quality_scores.clarity,
                        "actionability": feedback.quality_scores.actionability,
                        "comments": feedback.comments,
                    })
                except Exception as e:
                    logger.warning(f"WebSocket callback failed: {e}")
            
            # Check decision
            if feedback.decision == ReviewDecision.APPROVE:
                logger.info("Work approved, workflow complete")
                
                # Stream completion
                if websocket_callback:
                    try:
                        await websocket_callback("review_complete", {
                            "status": "approved",
                            "iterations": iteration,
                            "final_quality_score": feedback.quality_scores.overall_score
                        })
                    except Exception as e:
                        logger.warning(f"WebSocket callback failed: {e}")
                
                return {
                    "status": "approved",
                    "final_work": work_content,
                    "iterations": iteration,
                    "final_quality_score": feedback.quality_scores.overall_score,
                    "review_history": [f.model_dump() for f in review_history],
                }
            elif feedback.decision == ReviewDecision.ESCALATE:
                logger.warning(f"Work escalated: {feedback.escalation_reason}")
                
                # Stream escalation
                if websocket_callback:
                    try:
                        await websocket_callback("review_escalated", {
                            "status": "escalated",
                            "iterations": iteration,
                            "reason": feedback.escalation_reason
                        })
                    except Exception as e:
                        logger.warning(f"WebSocket callback failed: {e}")
                
                return {
                    "status": "escalated",
                    "final_work": work_content,
                    "iterations": iteration,
                    "escalation_reason": feedback.escalation_reason,
                    "review_history": [f.model_dump() for f in review_history],
                }
            else:
                # Revise - continue loop
                current_submission.previous_feedback = feedback
                logger.info("Work requires revision, continuing to next iteration")
        
        # Max iterations reached
        logger.warning("Max iterations reached without approval")
        return {
            "status": "max_iterations_reached",
            "final_work": work_content,
            "iterations": iteration,
            "final_quality_score": feedback.quality_scores.overall_score,
            "review_history": [f.model_dump() for f in review_history],
        }
