"""
Crew Factory Service - Centralized crew creation and management
Extracted from backend/app/core/crew.py for better organization
"""

from crewai import Task, Crew, Process
from typing import Optional, Dict, Any
import logging
import os

# Import services
from .rag_service import RAGService
from .graph_service import GraphService

# Import tools from tools directory
from ..tools.rag_query_tool import RAGQueryTool
from ..tools.graph_query_tool import GraphQueryTool
from ..tools.hybrid_search_tool import HybridSearchTool
from ..tools.lessons_learned_tool import LessonsLearnedTool
from ..tools.project_knowledge_base_tool import ProjectKnowledgeBaseQueryTool
from ..tools.cloud_catalog_tool import CloudServiceCatalogTool
from ..tools.compliance_tool import ComplianceFrameworkTool
from ..tools.infrastructure_analysis_tool import InfrastructureAnalysisTool

# Import logging handler and agent definitions
from .crew import AgentLogStreamHandler
from ..agents.agent_definitions import AgentDefinitions

logger = logging.getLogger(__name__)

class CrewFactory:
    """Factory class for creating different types of crews"""
    
    def __init__(self):
        self.logger = logger
    
    def create_assessment_crew(self, project_id: str, llm, websocket=None) -> Crew:
        """
        Creates an enhanced assessment crew with comprehensive enterprise capabilities.
        
        Enhanced capabilities include:
        - Cross-modal synthesis (graph + semantic search)
        - 6Rs migration pattern analysis
        - Comprehensive compliance validation (GDPR, SOX, HIPAA, PCI-DSS)
        - Landing zone architecture design
        - 3-year TCO cost modeling
        - Wave planning with dependency analysis
        - Executive-ready deliverables
        """
        # Initialize logging callback handler
        log_handler = AgentLogStreamHandler(websocket=websocket) if websocket else None

        # Initialize services and tools
        rag_service = RAGService(project_id, llm)
        rag_tool = RAGQueryTool(rag_service=rag_service)
        graph_service = GraphService()
        graph_tool = GraphQueryTool(graph_service=graph_service)
        
        # Initialize enhanced tools (if available)
        tools_list = [rag_tool, graph_tool]

        if TOOLS_AVAILABLE:
            try:
                hybrid_search_tool = HybridSearchTool(project_id=project_id)
                lessons_learned_tool = LessonsLearnedTool()
                project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id)
                cloud_catalog_tool = CloudServiceCatalogTool()
                compliance_tool = ComplianceFrameworkTool()
                infrastructure_tool = InfrastructureAnalysisTool()

                enhanced_tools = [hybrid_search_tool, project_kb_tool]
                specialized_tools = [cloud_catalog_tool, infrastructure_tool, compliance_tool]
            except Exception as e:
                logger.warning(f"Failed to initialize some tools: {e}")
                enhanced_tools = []
                specialized_tools = []
                lessons_learned_tool = None
        else:
            enhanced_tools = []
            specialized_tools = []
            lessons_learned_tool = None

        # Create agents using centralized definitions
        engagement_analyst = AgentDefinitions.create_engagement_analyst([rag_tool, graph_tool, hybrid_search_tool, project_kb_tool])
        principal_cloud_architect = AgentDefinitions.create_principal_cloud_architect([rag_tool, graph_tool, cloud_catalog_tool, infrastructure_tool])
        risk_compliance_officer = AgentDefinitions.create_risk_compliance_officer([rag_tool, graph_tool, compliance_tool])
        lead_planning_manager = AgentDefinitions.create_lead_planning_manager([rag_tool, graph_tool, lessons_learned_tool, project_kb_tool])

        # Create tasks
        current_state_synthesis_task = self._create_current_state_synthesis_task(engagement_analyst)
        target_architecture_design_task = self._create_target_architecture_design_task(principal_cloud_architect)
        compliance_validation_task = self._create_compliance_validation_task(risk_compliance_officer)
        report_generation_task = self._create_report_generation_task(lead_planning_manager)

        # Set current agent context for logging
        if log_handler:
            log_handler.set_current_agent(engagement_analyst)

        return Crew(
            agents=[engagement_analyst, principal_cloud_architect, risk_compliance_officer, lead_planning_manager],
            tasks=[current_state_synthesis_task, target_architecture_design_task, compliance_validation_task, report_generation_task],
            process=Process.sequential,
            verbose=True,
            memory=True,  # Enable memory for better collaboration between agents
            callbacks=[log_handler] if log_handler else []
        )
    
    def create_document_generation_crew(self, project_id: str, llm, document_type: str, 
                                      document_description: str, output_format: str = 'markdown', 
                                      websocket=None, crew_logger=None) -> Crew:
        """
        Create a specialized crew for document generation using RAG and knowledge graph.
        
        This crew focuses on creating professional documents based on project data,
        uploaded documents, and knowledge graph relationships.
        """
        # Initialize logging callback handler
        log_handler = AgentLogStreamHandler(websocket=websocket) if websocket else None

        # Initialize services and tools
        rag_service = RAGService(project_id, llm)
        rag_tool = RAGQueryTool(rag_service=rag_service)
        graph_service = GraphService()
        graph_tool = GraphQueryTool(graph_service=graph_service)
        
        # Initialize enhanced tools for document generation
        hybrid_search_tool = HybridSearchTool(project_id=project_id)
        lessons_learned_tool = LessonsLearnedTool()
        project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id)

        # Create document generation agents using centralized definitions
        document_researcher = AgentDefinitions.create_document_researcher([rag_tool, graph_tool, hybrid_search_tool, project_kb_tool])
        content_architect = AgentDefinitions.create_content_architect([rag_tool, graph_tool, project_kb_tool])
        quality_reviewer = AgentDefinitions.create_quality_reviewer([rag_tool, graph_tool])

        # Create document generation tasks
        research_task = self._create_research_task(document_researcher, document_type, document_description)
        content_structure_task = self._create_content_structure_task(content_architect, document_type, output_format)
        quality_review_task = self._create_quality_review_task(quality_reviewer, document_type, output_format)

        return Crew(
            agents=[document_researcher, content_architect, quality_reviewer],
            tasks=[research_task, content_structure_task, quality_review_task],
            process=Process.sequential,
            verbose=True,
            memory=True,
            callbacks=[log_handler] if log_handler else []
        )
    
    # Agent creation methods moved to backend/app/agents/agent_definitions.py
    

    

    
    def _create_current_state_synthesis_task(self, agent) -> Task:
        """Create the current state synthesis task"""
        return Task(
            description=(
                "Perform comprehensive current state analysis using cross-modal synthesis. "
                "Use the Hybrid Search Tool to query both semantic and graph databases. "
                "Extract key technical and business requirements, identify critical dependencies, "
                "and assess the current IT landscape. Focus on application portfolio, "
                "infrastructure components, data flows, and integration patterns."
            ),
            expected_output=(
                "A comprehensive current state analysis document containing: "
                "1. Executive summary of current IT landscape "
                "2. Application portfolio inventory with criticality ratings "
                "3. Infrastructure component mapping "
                "4. Data flow and integration analysis "
                "5. Identified technical debt and modernization opportunities "
                "6. Business impact assessment of current state limitations"
            ),
            agent=agent
        )

    def _create_target_architecture_design_task(self, agent) -> Task:
        """Create the target architecture design task"""
        return Task(
            description=(
                "Design the target cloud architecture using the 6Rs migration framework. "
                "Use the Cloud Service Catalog Tool to recommend optimal cloud services. "
                "Create detailed landing zone specifications, network architecture, "
                "and security controls. Consider cost optimization, performance, and scalability."
            ),
            expected_output=(
                "A detailed target architecture design containing: "
                "1. Cloud service recommendations with justifications "
                "2. Landing zone architecture diagrams "
                "3. Network and security design specifications "
                "4. 6Rs migration strategy for each application "
                "5. Cost optimization recommendations "
                "6. Performance and scalability considerations"
            ),
            agent=agent
        )

    def _create_compliance_validation_task(self, agent) -> Task:
        """Create the compliance validation task"""
        return Task(
            description=(
                "Conduct comprehensive compliance validation using the Compliance Framework Tool. "
                "Assess current state against regulatory requirements (GDPR, SOX, HIPAA, PCI-DSS). "
                "Identify security gaps and provide detailed remediation strategies. "
                "Ensure target architecture meets all compliance requirements."
            ),
            expected_output=(
                "A comprehensive compliance assessment containing: "
                "1. Current state compliance gap analysis "
                "2. Regulatory requirements mapping "
                "3. Security control recommendations "
                "4. Risk assessment and mitigation strategies "
                "5. Compliance validation for target architecture "
                "6. Audit trail and documentation requirements"
            ),
            agent=agent
        )

    def _create_report_generation_task(self, agent) -> Task:
        """Create the report generation task"""
        return Task(
            description=(
                "Synthesize all findings into a comprehensive migration assessment report. "
                "Use the Lessons Learned Tool to incorporate best practices. "
                "Create detailed wave planning, timeline, and risk mitigation strategies. "
                "Ensure executive-ready deliverables with clear recommendations."
            ),
            expected_output=(
                "A comprehensive migration assessment report containing: "
                "1. Executive summary with key recommendations "
                "2. Detailed migration roadmap with wave planning "
                "3. Cost-benefit analysis and ROI projections "
                "4. Risk assessment and mitigation strategies "
                "5. Implementation timeline and resource requirements "
                "6. Success metrics and KPIs for migration tracking"
            ),
            agent=agent
        )

    def _create_research_task(self, agent, document_type: str, document_description: str) -> Task:
        """Create the research task for document generation"""
        return Task(
            description=(
                f"Research and gather information for {document_type} generation. "
                f"Focus on: {document_description}. "
                "Use all available tools to extract relevant information from project documents, "
                "knowledge base, and graph relationships."
            ),
            expected_output=(
                f"Comprehensive research findings for {document_type} including: "
                "1. Relevant information extracted from project documents "
                "2. Key insights from knowledge base queries "
                "3. Relationship analysis from graph database "
                "4. Supporting data and evidence for document creation"
            ),
            agent=agent
        )

    def _create_content_structure_task(self, agent, document_type: str, output_format: str) -> Task:
        """Create the content structure task for document generation"""
        return Task(
            description=(
                f"Structure and organize content for {document_type} in {output_format} format. "
                "Create a well-organized document structure with clear sections, "
                "proper formatting, and logical flow of information."
            ),
            expected_output=(
                f"Well-structured {document_type} in {output_format} format containing: "
                "1. Clear document structure with appropriate sections "
                "2. Properly formatted content with consistent styling "
                "3. Logical information flow and organization "
                "4. Professional presentation suitable for stakeholders"
            ),
            agent=agent
        )

    def _create_quality_review_task(self, agent, document_type: str, output_format: str) -> Task:
        """Create the quality review task for document generation"""
        return Task(
            description=(
                f"Review and validate the quality of the generated {document_type}. "
                "Ensure accuracy, completeness, and professional standards. "
                "Verify all information is correctly represented and properly formatted."
            ),
            expected_output=(
                f"Quality-assured {document_type} in {output_format} format with: "
                "1. Verified accuracy of all information "
                "2. Complete coverage of required topics "
                "3. Professional formatting and presentation "
                "4. Quality assurance report with any recommendations"
            ),
            agent=agent
        )

# Global factory instance
crew_factory = CrewFactory()
