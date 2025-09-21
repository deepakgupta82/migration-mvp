"""
AI Agent Service Crew Factory (parity)
Creates assessment and document-generation crews using full toolset and process-aware LLM selection.
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

logger = logging.getLogger(__name__)


class CrewFactory:
    def __init__(self) -> None:
        self.logger = logger

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
        """Create the full-feature document generation crew (research, architecture, QA)."""
        callbacks = [AgentLogStreamHandler(websocket=websocket)] if websocket else []

        # Tools including process-aware ones
        rag_tool = RAGQueryTool()
        graph_tool = GraphQueryTool(project_id=project_id)
        hybrid_tool = HybridSearchTool(project_id=project_id, llm=llm)
        lessons_tool = LessonsLearnedTool()
        project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id, llm=llm)

        # Convert LLM to CrewAI-friendly value if needed (string or CrewAI LLM)
        crewai_llm = self._prepare_crewai_llm(llm)

        # Agents
        researcher = AgentDefinitions.create_document_researcher([rag_tool, graph_tool, hybrid_tool, project_kb_tool], llm=crewai_llm)
        architect = AgentDefinitions.create_content_architect([rag_tool, graph_tool, project_kb_tool], llm=crewai_llm)
        reviewer = AgentDefinitions.create_quality_reviewer([rag_tool, graph_tool], llm=crewai_llm)

        # Tasks with enhanced guidance
        research_task = Task(
            description=(
                f"Research and gather comprehensive information for {document_type}.\n\n"
                f"Template Guidance: {document_description}\n\n"
                "Use Hybrid Search, RAG, Graph, and Project KB tools to collect evidence."
            ),
            expected_output=f"Comprehensive research report for {document_type}",
            agent=researcher,
        )

        structure_task = Task(
            description=(
                f"Architect the {document_type} in {output_format} format based on research."
            ),
            expected_output=f"Well-structured {document_type} in {output_format}",
            agent=architect,
        )

        quality_task = Task(
            description=(
                f"Review and validate the {document_type} for accuracy, completeness, and presentation."
            ),
            expected_output=f"Finalized {document_type} in {output_format}",
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

        crewai_llm = self._prepare_crewai_llm(llm)

        # Agents
        engagement_analyst = AgentDefinitions.create_document_researcher([rag_tool, graph_tool, hybrid_tool, project_kb_tool], llm=crewai_llm)
        principal_cloud_architect = Agent(
            role="Principal Cloud Architect",
            goal="Design target cloud architecture and migration patterns",
            backstory="Experienced enterprise cloud architect.",
            tools=[rag_tool, graph_tool, cloud_catalog_tool, infra_tool],
            llm=crewai_llm,
            allow_delegation=False,
            verbose=True,
        )
        risk_compliance_officer = Agent(
            role="Risk & Compliance Officer",
            goal="Validate architecture against compliance and security",
            backstory="Senior compliance expert.",
            tools=[rag_tool, graph_tool, compliance_tool],
            llm=crewai_llm,
            allow_delegation=False,
            verbose=True,
        )
        lead_planning_manager = Agent(
            role="Lead Migration Program Manager",
            goal="Synthesize findings into an executive-ready assessment report",
            backstory="Program manager with large-scale migrations.",
            tools=[rag_tool, graph_tool, lessons_tool, project_kb_tool],
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
