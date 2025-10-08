"""
AI Agent Service Crew Factory (parity)
Creates assessment and document-generation crews using full toolset and process-aware LLM selection.
Enhanced with Level 3 Reflection Loop for iterative quality improvement.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, List

from crewai import Agent, Task, Crew, Process

from app.tools.rag_query_tool import RAGQueryTool
from app.tools.graph_query_tool import GraphQueryTool
from app.tools.hybrid_search_tool import HybridSearchTool
from app.tools.lessons_learned_tool import LessonsLearnedTool  # ported
from app.tools.project_knowledge_base_tool import ProjectKnowledgeBaseQueryTool  # ported
from app.tools.cloud_catalog_tool import CloudServiceCatalogTool  # ported
from app.tools.compliance_tool import ComplianceFrameworkTool  # ported
from app.tools.infrastructure_analysis_tool import InfrastructureAnalysisTool  # ported
from app.core.agent_logs import AgentLogStreamHandler
from app.agents.agent_definitions import AgentDefinitions
from app.core.crew_loader import crew_loader
from app.core.mcp_adapter import build_crewai_tools
from app.core.reflection_loop import get_reflection_loop, CriticAgent
import os

logger = logging.getLogger(__name__)


class CrewFactory:
    def __init__(self) -> None:
        self.logger = logger
        self.enable_reflection = os.getenv("ENABLE_REFLECTION_LOOP", "true").lower() in ("1", "true", "yes")
        self.reflection_max_iterations = int(os.getenv("REFLECTION_MAX_ITERATIONS", "3"))

    def create_document_generation_crew(
        self,
        project_id: str,
        llm: Optional[Any],
        *,
        document_type: str,
        document_description: str,
        output_format: str = "markdown",
        websocket: Optional[Any] = None,
    ) -> Crew:
        """
        Create the full-feature document generation crew (research, architecture, QA).
        
        Enhanced with Level 3 Reflection Loop for iterative quality improvement.
        The crew now follows Producer-Critic pattern:
        1. Researcher + Architect produce initial document
        2. Quality Reviewer provides feedback
        3. If not perfect, researcher/architect refine based on feedback
        4. Repeat until quality threshold met or max iterations reached
        """
        callbacks = [AgentLogStreamHandler(websocket=websocket)] if websocket else []

        # Tools including process-aware ones
        rag_tool = RAGQueryTool()
        graph_tool = GraphQueryTool(project_id=project_id)
        hybrid_tool = HybridSearchTool(project_id=project_id, llm=llm)
        lessons_tool = LessonsLearnedTool()
        project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id, llm=llm)

        # Optionally include MCP tools discovered via Settings (disabled by default)
        extra_tools: List[Any] = []
        if os.getenv("ENABLE_MCP_TOOLS_FOR_CREW", "false").lower() in ("1", "true", "yes"):
            try:
                extra_tools = build_crewai_tools()
                logger.info(f"Including {len(extra_tools)} MCP tools in crew")
            except Exception as e:
                logger.warning(f"Failed to build MCP CrewAI tools: {e}")

        # Convert LLM to CrewAI-friendly value if needed (string or CrewAI LLM)
        crewai_llm = self._prepare_crewai_llm(llm)

        # Agents
        researcher = AgentDefinitions.create_document_researcher(
            [rag_tool, graph_tool, hybrid_tool, project_kb_tool, *extra_tools], llm=crewai_llm
        )
        architect = AgentDefinitions.create_content_architect(
            [rag_tool, graph_tool, project_kb_tool, *extra_tools], llm=crewai_llm
        )
        reviewer = AgentDefinitions.create_quality_reviewer(
            [rag_tool, graph_tool, *extra_tools], llm=crewai_llm
        )

        # Tasks with enhanced guidance for reflection loop
        research_task = Task(
            description=(
                f"Research and gather comprehensive information for {document_type}.\n\n"
                f"Template Guidance: {document_description}\n\n"
                "Use Hybrid Search, RAG, Graph, and Project KB tools to collect evidence.\n\n"
                "{{context}}"  # Placeholder for refinement context
            ),
            expected_output=f"Comprehensive research report for {document_type}",
            agent=researcher,
        )

        structure_task = Task(
            description=(
                f"Architect the {document_type} in {output_format} format based on research.\n\n"
                "{{context}}"  # Placeholder for refinement context
            ),
            expected_output=f"Well-structured {document_type} in {output_format}",
            agent=architect,
        )

        quality_task = Task(
            description=(
                f"Review and validate the {document_type} for accuracy, completeness, and presentation.\n\n"
                "Provide structured feedback:\n"
                "- Status: PERFECT | IMPROVE | REJECT\n"
                "- Quality Score: 0.0-1.0\n"
                "- Specific issues found\n"
                "- Concrete suggestions for improvement"
            ),
            expected_output=f"Quality review with feedback for {document_type}",
            agent=reviewer,
        )

        return Crew(
            agents=[researcher, architect, reviewer],
            tasks=[research_task, structure_task, quality_task],
            process=Process.sequential,
            verbose=True,
            memory=False,  # Disable memory to avoid CHROMA_OPENAI_API_KEY requirement
            callbacks=callbacks,
        )
    
    async def run_document_generation_with_reflection(
        self,
        project_id: str,
        llm: Optional[Any],
        document_type: str,
        document_description: str,
        output_format: str = "markdown",
        websocket: Optional[Any] = None,
    ) -> dict:
        """
        Execute document generation with reflection loop enabled.
        
        This wraps the traditional crew kickoff with producer-critic iteration:
        1. Create initial document (producer phase)
        2. Quality reviewer critiques (critic phase)
        3. Refine based on feedback if needed
        4. Repeat until quality threshold met
        
        Args:
            project_id: Project context
            llm: LLM instance for crew
            document_type: Type of document to generate
            document_description: Template/guidance for document
            output_format: Output format (default: markdown)
            websocket: Optional websocket for streaming
            
        Returns:
            Dict with:
                - final_output: The refined document
                - iterations_used: Number of refinement cycles
                - quality_score: Final quality assessment
                - refinement_log: History of improvements
        """
        if not self.enable_reflection:
            # Fallback: traditional single-pass execution
            logger.info("Reflection loop disabled, using traditional single-pass execution")
            crew = self.create_document_generation_crew(
                project_id=project_id,
                llm=llm,
                document_type=document_type,
                document_description=document_description,
                output_format=output_format,
                websocket=websocket,
            )
            result = crew.kickoff()
            return {
                "status": "success",
                "final_output": str(result),
                "iterations_used": 1,
                "quality_score": 0.8,
                "refinement_log": [],
                "method": "single_pass"
            }
        
        # Initialize reflection loop
        reflection = get_reflection_loop(
            max_iterations=self.reflection_max_iterations,
            quality_threshold=0.9
        )
        
        # Define producer function (creates/refines document)
        async def producer(context: dict) -> str:
            """Producer phase: researcher + architect create/refine document"""
            iteration = context.get("refinement_iteration", 1)
            
            # Build context-aware task descriptions
            if iteration == 1:
                # Initial production
                logger.info("Producer: Creating initial document")
                crew = self.create_document_generation_crew(
                    project_id=project_id,
                    llm=llm,
                    document_type=document_type,
                    document_description=document_description,
                    output_format=output_format,
                    websocket=websocket,
                )
            else:
                # Refinement based on feedback
                previous_output = context.get("previous_output", "")
                feedback = context.get("critic_feedback", "")
                
                logger.info(f"Producer: Refining document based on feedback (iteration {iteration})")
                
                # Create crew with refinement context
                refinement_guidance = (
                    f"\n\n=== REFINEMENT ITERATION {iteration} ===\n"
                    f"Previous output had issues. Improve based on this feedback:\n\n"
                    f"{feedback}\n\n"
                    f"Previous version:\n{previous_output[:2000]}...\n"
                    f"=== END REFINEMENT CONTEXT ===\n"
                )
                
                crew = self.create_document_generation_crew(
                    project_id=project_id,
                    llm=llm,
                    document_type=document_type,
                    document_description=document_description + refinement_guidance,
                    output_format=output_format,
                    websocket=websocket,
                )
            
            # Execute crew
            result = crew.kickoff()
            return str(result)
        
        # Define critic function (reviews quality)
        async def critic(context: dict) -> dict:
            """Critic phase: quality reviewer evaluates output"""
            output = context.get("output", "")
            task_desc = context.get("task_description", document_type)
            iteration = context.get("iteration", 1)
            
            return await CriticAgent.review_output(
                review_context={
                    "output": output,
                    "task_description": task_desc,
                    "iteration": iteration,
                    "document_type": document_type,
                    "output_format": output_format,
                },
                llm_service=llm,  # Use same LLM for critic
                project_id=project_id
            )
        
        # Execute reflection loop
        initial_context = {
            "project_id": project_id,
            "document_type": document_type,
            "document_description": document_description,
            "output_format": output_format,
        }
        
        logger.info(f"Starting reflection loop for {document_type} (max {self.reflection_max_iterations} iterations)")
        
        result = await reflection.run_reflection_loop(
            producer_func=producer,
            critic_func=critic,
            initial_context=initial_context,
            task_description=f"Generate {document_type} document"
        )
        
        # Log statistics
        stats = reflection.get_refinement_statistics()
        logger.info(f"Reflection loop complete. Stats: {stats}")
        
        return result

    def create_assessment_crew(
        self, project_id: str, llm: Optional[Any], *, websocket: Optional[Any] = None
    ) -> Crew:
        """Create an enhanced assessment crew matching backend behavior."""
        callbacks = [AgentLogStreamHandler(websocket=websocket)] if websocket else []

        # Tools
        rag_tool = RAGQueryTool()
        graph_tool = GraphQueryTool(project_id=project_id)
        hybrid_tool = HybridSearchTool(project_id=project_id, llm=llm)
        cloud_catalog_tool = CloudServiceCatalogTool()
        compliance_tool = ComplianceFrameworkTool()
        infra_tool = InfrastructureAnalysisTool(llm=llm)
        lessons_tool = LessonsLearnedTool()
        project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id, llm=llm)

        extra_tools: List[Any] = []
        if os.getenv("ENABLE_MCP_TOOLS_FOR_CREW", "false").lower() in ("1", "true", "yes"):
            try:
                extra_tools = build_crewai_tools()
                logger.info(f"Including {len(extra_tools)} MCP tools in assessment crew")
            except Exception as e:
                logger.warning(f"Failed to build MCP CrewAI tools: {e}")

        crewai_llm = self._prepare_crewai_llm(llm)

        # Agents
        engagement_analyst = AgentDefinitions.create_document_researcher(
            [rag_tool, graph_tool, hybrid_tool, project_kb_tool, *extra_tools], llm=crewai_llm
        )
        principal_cloud_architect = Agent(
            role="Principal Cloud Architect",
            goal="Design target cloud architecture and migration patterns",
            backstory="Experienced enterprise cloud architect.",
            tools=[rag_tool, graph_tool, cloud_catalog_tool, infra_tool, *extra_tools],
            llm=crewai_llm,
            allow_delegation=False,
            verbose=True,
        )
        risk_compliance_officer = Agent(
            role="Risk & Compliance Officer",
            goal="Validate architecture against compliance and security",
            backstory="Senior compliance expert.",
            tools=[rag_tool, graph_tool, compliance_tool, *extra_tools],
            llm=crewai_llm,
            allow_delegation=False,
            verbose=True,
        )
        lead_planning_manager = Agent(
            role="Lead Migration Program Manager",
            goal="Synthesize findings into an executive-ready assessment report",
            backstory="Program manager with large-scale migrations.",
            tools=[rag_tool, graph_tool, lessons_tool, project_kb_tool, *extra_tools],
            llm=crewai_llm,
            allow_delegation=False,
            verbose=True,
        )

        # Tasks
        current_state = Task(
            description=(
                "Perform comprehensive current state analysis using hybrid search and graph."
            ),
            expected_output="Current state analysis document",
            agent=engagement_analyst,
        )
        target_arch = Task(
            description="Design target architecture with 6Rs and cost/security considerations.",
            expected_output="Target architecture design",
            agent=principal_cloud_architect,
        )
        compliance = Task(
            description="Validate compliance and identify gaps; propose mitigations.",
            expected_output="Compliance assessment",
            agent=risk_compliance_officer,
        )
        report = Task(
            description="Generate executive-ready migration assessment report.",
            expected_output="Assessment report",
            agent=lead_planning_manager,
        )

        return Crew(
            agents=[engagement_analyst, principal_cloud_architect, risk_compliance_officer, lead_planning_manager],
            tasks=[current_state, target_arch, compliance, report],
            process=Process.sequential,
            verbose=True,
            memory=False,  # Disable memory to avoid CHROMA_OPENAI_API_KEY requirement
            callbacks=callbacks,
        )

    def _prepare_crewai_llm(self, llm_instance: Any) -> Any:
        """Minimal compatibility shim: if LC model, try to pass through; else return as-is or model string."""
        try:
            # If already a string or CrewAI LLM-like, return it
            if isinstance(llm_instance, str):
                return llm_instance
            # LangChain models often have .model attribute
            if hasattr(llm_instance, 'model'):
                model_name = getattr(llm_instance, 'model')
                # Normalize Gemini to crewai-friendly format gemini/<name>
                if isinstance(model_name, str):
                    clean = model_name
                    if clean.startswith('models/'):
                        clean = clean.replace('models/', '')
                    if clean.startswith('gemini/'):
                        clean = clean.replace('gemini/', '')
                    if 'gemini' in str(llm_instance.__class__).lower():
                        return f"gemini/{clean}"
                return model_name
            return llm_instance
        except Exception:
            return llm_instance

crew_factory = CrewFactory()
