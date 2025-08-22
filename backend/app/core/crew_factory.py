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

# Check if enhanced tools are available
try:
    from ..tools.hybrid_search_tool import HybridSearchTool
    from ..tools.lessons_learned_tool import LessonsLearnedTool
    from ..tools.project_knowledge_base_tool import ProjectKnowledgeBaseQueryTool
    from ..tools.cloud_catalog_tool import CloudServiceCatalogTool
    from ..tools.compliance_tool import ComplianceFrameworkTool
    from ..tools.infrastructure_analysis_tool import InfrastructureAnalysisTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Enhanced tools not available: {e}")
    TOOLS_AVAILABLE = False

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

        # Initialize services and tools with process-specific LLMs
        from app.core.llm_factory import llm_factory, LLMProcessType

        # Get process-specific LLM for assessment crew
        project = None
        try:
            # Try to get project object for process-specific LLMs
            project = self._get_project_from_id(project_id)

            # Get assessment-specific LLM
            assessment_llm = llm_factory.get_process_llm(
                project, LLMProcessType.CREW_ASSESSMENT, fallback_to_project_default=True
            ) if project else None

            # Use assessment LLM if available, otherwise fallback to passed LLM
            crew_llm = assessment_llm or llm
        except Exception as e:
            logger.warning(f"Could not get process-specific LLM for assessment crew: {e}")
            crew_llm = llm

        # Initialize RAG service with RAG-specific LLM
        try:
            rag_llm = llm_factory.get_process_llm(
                project, LLMProcessType.RAG_SYNTHESIS, fallback_to_project_default=True
            ) if project else None
            rag_service = RAGService(project_id, rag_llm or llm)
        except Exception as e:
            logger.warning(f"Could not get RAG-specific LLM: {e}")
            rag_service = RAGService(project_id, llm)

        rag_tool = RAGQueryTool(rag_service=rag_service)
        graph_tool = GraphQueryTool(project_id=project_id)

        # Initialize enhanced tools (if available)
        hybrid_search_tool = None
        project_kb_tool = None
        cloud_catalog_tool = None
        compliance_tool = None
        infrastructure_tool = None
        lessons_learned_tool = None
        if TOOLS_AVAILABLE:
            try:
                # Provide process-specific/default LLM to tools that can use it
                from app.core.llm_factory import llm_factory, LLMProcessType
                tool_llm = None
                try:
                    tool_llm = llm_factory.get_process_llm(
                        project, LLMProcessType.HYBRID_SEARCH, fallback_to_project_default=True
                    ) if project else None
                except Exception:
                    tool_llm = None

                hybrid_search_tool = HybridSearchTool(project_id=project_id, llm=tool_llm or crew_llm)
                lessons_learned_tool = LessonsLearnedTool()
                project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id, llm=tool_llm or crew_llm)
                cloud_catalog_tool = CloudServiceCatalogTool()
                compliance_tool = ComplianceFrameworkTool()
                infrastructure_tool = InfrastructureAnalysisTool()
            except Exception as e:
                logger.warning(f"Failed to initialize some tools: {e}")

        # Always convert LLM to CrewAI-compatible format for reliable execution
        logger.info("🔧 Converting LLM to CrewAI-compatible format for assessment crew")
        crewai_llm_config = self._prepare_crewai_llm(crew_llm, project)
        logger.info(f"✅ Assessment crew LLM format: {crewai_llm_config}")

        # Create agents using centralized definitions with CrewAI-compatible LLM
        # Build tool lists excluding None values
        def _tool_list(*tools):
            return [t for t in tools if t is not None]

        engagement_analyst = AgentDefinitions.create_engagement_analyst(_tool_list(rag_tool, graph_tool, hybrid_search_tool, project_kb_tool), llm=crewai_llm_config)
        principal_cloud_architect = AgentDefinitions.create_principal_cloud_architect(_tool_list(rag_tool, graph_tool, cloud_catalog_tool, infrastructure_tool), llm=crewai_llm_config)
        risk_compliance_officer = AgentDefinitions.create_risk_compliance_officer(_tool_list(rag_tool, graph_tool, compliance_tool), llm=crewai_llm_config)
        lead_planning_manager = AgentDefinitions.create_lead_planning_manager(_tool_list(rag_tool, graph_tool, lessons_learned_tool, project_kb_tool), llm=crewai_llm_config)

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
        uploaded documents, and knowledge graph relationships with AI agent collaboration.
        """
        # Initialize logging callback handler
        log_handler = AgentLogStreamHandler(websocket=websocket) if websocket else None

        # Initialize services and tools with process-specific LLMs
        from app.core.llm_factory import llm_factory, LLMProcessType

        project = None
        try:
            # Get project object for process-specific LLMs
            project = self._get_project_from_id(project_id)

            # Get documentation-specific LLM
            documentation_llm = llm_factory.get_process_llm(
                project, LLMProcessType.CREW_DOCUMENTATION, fallback_to_project_default=True
            ) if project else None

            # Use documentation LLM if available, otherwise fallback to passed LLM
            crew_llm = documentation_llm or llm

            # Get RAG-specific LLM for document research
            rag_llm = llm_factory.get_process_llm(
                project, LLMProcessType.RAG_SYNTHESIS, fallback_to_project_default=True
            ) if project else None

            rag_service = RAGService(project_id, rag_llm or llm)
        except Exception as e:
            logger.warning(f"Could not get process-specific LLMs for document generation: {e}")
            crew_llm = llm
            rag_service = RAGService(project_id, llm)

        # Broadcast crew initialization
        if websocket:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(websocket.broadcast(project_id, f"🔧 Initializing AI agent tools and services..."))
            except Exception:
                pass

        rag_tool = RAGQueryTool(rag_service=rag_service)
        graph_tool = GraphQueryTool(project_id=project_id)

        # Initialize enhanced tools for document generation with process-specific LLMs
        hybrid_search_llm = llm_factory.get_process_llm(
            project, LLMProcessType.HYBRID_SEARCH, fallback_to_project_default=True
        ) if project else None

        hybrid_search_tool = HybridSearchTool(project_id=project_id, llm=hybrid_search_llm or crew_llm)
        lessons_learned_tool = LessonsLearnedTool()
        # Pass LLM to project knowledge base tool to avoid separate LLM initialization
        project_kb_tool = ProjectKnowledgeBaseQueryTool(project_id=project_id, llm=crew_llm)

        # Broadcast agent creation
        if websocket:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(websocket.broadcast(project_id, f"👥 Creating specialized AI agents: Research, Architecture, Quality Review..."))
            except Exception:
                pass

        # Always convert LLM to CrewAI-compatible format for reliable execution
        # Direct LangChain LLM usage can cause runtime failures with LiteLLM
        logger.info("🔧 Converting LLM to CrewAI-compatible format for reliable execution")
        logger.info(f"Original LLM type: {type(crew_llm)}")
        if hasattr(crew_llm, 'model'):
            logger.info(f"Original LLM model: {crew_llm.model}")

        crewai_llm_config = self._prepare_crewai_llm(crew_llm, project)

        logger.info(f"✅ Converted LLM format: {type(crewai_llm_config)}")
        logger.info(f"✅ Converted LLM value: {crewai_llm_config}")

        # Create document generation agents using centralized definitions with CrewAI-compatible LLM
        document_researcher = AgentDefinitions.create_document_researcher([rag_tool, graph_tool, hybrid_search_tool, project_kb_tool], llm=crewai_llm_config)
        content_architect = AgentDefinitions.create_content_architect([rag_tool, graph_tool, project_kb_tool], llm=crewai_llm_config)
        quality_reviewer = AgentDefinitions.create_quality_reviewer([rag_tool, graph_tool], llm=crewai_llm_config)

        logger.info("✅ All agents created with converted LLM format")

        # Create template-specific tasks with enhanced descriptions
        research_task = self._create_enhanced_research_task(document_researcher, document_type, document_description)
        content_structure_task = self._create_enhanced_content_structure_task(content_architect, document_type, document_description, output_format)
        quality_review_task = self._create_enhanced_quality_review_task(quality_reviewer, document_type, output_format)

        # Broadcast crew assembly
        if websocket:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(websocket.broadcast(project_id, f"🎯 Assembling AI agent crew with collaborative workflow..."))
            except Exception:
                pass

        logger.info(f"🤖 Created document generation crew with {len([document_researcher, content_architect, quality_reviewer])} agents for {document_type}")

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

    def _create_enhanced_research_task(self, agent, document_type: str, document_description: str) -> Task:
        """Create enhanced research task with template-specific guidance"""
        return Task(
            description=(
                f"🔍 Research and gather comprehensive information for {document_type} generation.\n\n"
                f"Template Guidance: {document_description}\n\n"
                "Your mission as the Research Agent:\n"
                "1. Use RAG Query Tool to search project documents for relevant information\n"
                "2. Use Graph Query Tool to explore relationships and dependencies\n"
                "3. Use Hybrid Search Tool for advanced semantic and graph-based queries\n"
                "4. Use Project Knowledge Base Tool to access structured project data\n\n"
                "Focus areas:\n"
                "- Infrastructure components and architecture patterns\n"
                "- Technology stack and integration points\n"
                "- Business requirements and constraints\n"
                "- Migration-relevant findings and insights\n\n"
                "Provide thorough, evidence-based research that will inform the content architecture."
            ),
            expected_output=(
                f"📋 Comprehensive research report for {document_type} including:\n"
                "1. **Document Analysis Summary**: Key insights from uploaded project documents\n"
                "2. **Infrastructure Inventory**: Detailed technical components and systems\n"
                "3. **Relationship Mapping**: Dependencies and integration patterns from graph analysis\n"
                "4. **Business Context**: Requirements, constraints, and strategic objectives\n"
                "5. **Supporting Evidence**: Quotes, data points, and references from source materials\n"
                "6. **Research Recommendations**: Suggested focus areas for document development"
            ),
            agent=agent
        )

    def _create_enhanced_content_structure_task(self, agent, document_type: str, document_description: str, output_format: str) -> Task:
        """Create enhanced content structure task with template requirements"""
        return Task(
            description=(
                f"🏗️ Architect and structure the {document_type} based on research findings.\n\n"
                f"Template Requirements: {document_description}\n"
                f"Output Format: {output_format}\n\n"
                "Your mission as the Content Architect:\n"
                "1. Analyze the research findings from the Research Agent\n"
                "2. Design a logical document structure that follows template guidance\n"
                "3. Organize content into clear, professional sections\n"
                "4. Ensure information flows logically and supports business objectives\n"
                "5. Use RAG and Graph tools to fill content gaps if needed\n\n"
                "Structure Requirements:\n"
                "- Executive Summary with key recommendations\n"
                "- Technical analysis based on research findings\n"
                "- Implementation guidance and next steps\n"
                "- Professional formatting appropriate for stakeholders\n\n"
                "Create content that is actionable, evidence-based, and aligned with template guidance."
            ),
            expected_output=(
                f"📄 Well-structured {document_type} in {output_format} format containing:\n"
                "1. **Executive Summary**: High-level overview and key recommendations\n"
                "2. **Technical Analysis**: Infrastructure assessment based on research\n"
                "3. **Strategic Recommendations**: Actionable next steps and priorities\n"
                "4. **Implementation Roadmap**: Phased approach with timelines\n"
                "5. **Risk Assessment**: Identified challenges and mitigation strategies\n"
                "6. **Supporting Appendices**: Technical details and reference materials\n\n"
                "Document must be professionally formatted, logically organized, and ready for stakeholder review."
            ),
            agent=agent
        )

    def _create_enhanced_quality_review_task(self, agent, document_type: str, output_format: str) -> Task:
        """Create enhanced quality review task with comprehensive validation"""
        return Task(
            description=(
                f"🔍 Conduct comprehensive quality assurance for the {document_type}.\n\n"
                "Your mission as the Quality Reviewer:\n"
                "1. Validate accuracy of all technical information against source documents\n"
                "2. Ensure completeness - verify all required sections are included\n"
                "3. Check professional formatting and presentation standards\n"
                "4. Verify logical flow and coherence of arguments\n"
                "5. Confirm alignment with template requirements\n"
                "6. Use RAG and Graph tools to fact-check critical assertions\n\n"
                "Quality Criteria:\n"
                "- Technical accuracy and completeness\n"
                "- Professional presentation and formatting\n"
                "- Clear, actionable recommendations\n"
                "- Proper citation of source materials\n"
                "- Stakeholder-appropriate language and tone\n\n"
                "Provide final, publication-ready document with quality assurance report."
            ),
            expected_output=(
                f"✅ Quality-assured {document_type} in {output_format} format with:\n"
                "1. **Final Document**: Polished, professional document ready for delivery\n"
                "2. **Quality Assurance Report**: \n"
                "   - Accuracy verification results\n"
                "   - Completeness checklist confirmation\n"
                "   - Formatting and presentation assessment\n"
                "   - Any revisions made during review\n"
                "3. **Validation Summary**: Confirmation that document meets all requirements\n"
                "4. **Stakeholder Readiness**: Confirmation document is appropriate for intended audience\n\n"
                "Document must pass all quality gates and be ready for immediate use by project stakeholders."
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

    def _get_project_from_id(self, project_id: str):
        """Helper method to get project object from project ID"""
        try:
            from app.core.project_service import get_project_service
            project_service = get_project_service()
            return project_service.get_project(project_id)
        except Exception as e:
            logger.warning(f"Could not retrieve project {project_id}: {e}")
            return None

    def _prepare_crewai_llm(self, llm_instance, project):
        """
        Prepare LLM for CrewAI using the same configuration approach as LLMFactory.
        Instead of environment variables, use the project's LLM configuration.
        CrewAI 0.150.0 expects string model names or CrewAI BaseLLM instances.
        """
        import os
        
        # If it's already a string, return as-is
        if isinstance(llm_instance, str):
            return llm_instance
            
        # Extract configuration from the LangChain LLM instance
        class_name = str(llm_instance.__class__)
        logger.info(f"Debug: LLM class type: {class_name}")
        logger.info(f"Debug: Has model attribute: {hasattr(llm_instance, 'model')}")
        if hasattr(llm_instance, 'model'):
            logger.info(f"Debug: Model value: {llm_instance.model}")
        
        # Try using CrewAI LLM class directly for better compatibility
        try:
            from crewai import LLM as CrewAI_LLM
            logger.info("Attempting to create CrewAI LLM instance directly")
            
            # Handle Gemini models
            is_gemini = any([
                'gemini' in class_name.lower(),
                'google' in class_name.lower(),
                'ChatGoogleGenerativeAI' in class_name
            ])
            
            if hasattr(llm_instance, 'model') and is_gemini:
                model_name = llm_instance.model
                
                # Get API key from LangChain instance
                api_key = None
                if hasattr(llm_instance, 'google_api_key') and llm_instance.google_api_key:
                    api_key = llm_instance.google_api_key
                    # Handle SecretStr objects from pydantic
                    if hasattr(api_key, 'get_secret_value'):
                        api_key = api_key.get_secret_value()
                    else:
                        api_key = str(api_key)
                
                # Clean and format model name for CrewAI
                clean_model = model_name
                if clean_model.startswith('models/'):
                    clean_model = clean_model.replace('models/', '')
                if clean_model.startswith('gemini/'):
                    clean_model = clean_model.replace('gemini/', '')
                    
                # Add gemini/ prefix for CrewAI
                crewai_model = f'gemini/{clean_model}'
                
                # Set environment variable for CrewAI
                if api_key:
                    os.environ['GEMINI_API_KEY'] = api_key
                    logger.info(f"Set GEMINI_API_KEY for CrewAI (key length: {len(api_key)})")
                
                # Create CrewAI LLM instance
                crewai_llm = CrewAI_LLM(
                    model=crewai_model,
                    temperature=getattr(llm_instance, 'temperature', 0.1)
                )
                
                logger.info(f"Successfully created CrewAI LLM instance with model: {crewai_model}")
                return crewai_llm
                
        except ImportError:
            logger.info("CrewAI LLM class not available, falling back to string format")
        except Exception as e:
            logger.warning(f"Failed to create CrewAI LLM instance directly: {e}, falling back to string format")
        
        # Fallback to string format approach
        logger.info("Using fallback string format approach for CrewAI LLM")
            
        # Handle LangChain ChatGoogleGenerativeAI - check for multiple possible indicators
        is_gemini = any([
            'gemini' in class_name.lower(),
            'google' in class_name.lower(),
            'ChatGoogleGenerativeAI' in class_name
        ])
        
        if hasattr(llm_instance, 'model') and is_gemini:
            model_name = llm_instance.model
            
            # Instead of setting environment variables, let CrewAI handle the API key
            # by ensuring it can access it through the same method as LangChain
            
            # Set the API key for CrewAI (uses GEMINI_API_KEY, not GOOGLE_API_KEY)
            api_key_set = False
            original_gemini_key = os.environ.get('GEMINI_API_KEY')
            original_google_key = os.environ.get('GOOGLE_API_KEY')
            
            try:
                # Get the API key from the LangChain instance
                if hasattr(llm_instance, 'google_api_key') and llm_instance.google_api_key:
                    api_key = llm_instance.google_api_key
                    # Handle SecretStr objects from pydantic
                    if hasattr(api_key, 'get_secret_value'):
                        api_key_value = api_key.get_secret_value()
                    else:
                        api_key_value = str(api_key)
                    
                    # Set both GEMINI_API_KEY (for CrewAI) and GOOGLE_API_KEY (backup)
                    if not original_gemini_key or original_gemini_key != api_key_value:
                        os.environ['GEMINI_API_KEY'] = api_key_value
                        api_key_set = True
                    
                    if not original_google_key or original_google_key != api_key_value:
                        os.environ['GOOGLE_API_KEY'] = api_key_value
                        
                    logger.info(f"Set GEMINI_API_KEY for CrewAI (key length: {len(api_key_value)})")
                
                # Clean and format model name for CrewAI
                # LangChain uses 'models/gemini-2.5-flash', CrewAI expects 'gemini/gemini-2.5-flash'
                clean_model = model_name
                logger.info(f"Debug: Original model name: {model_name}")
                
                if clean_model.startswith('models/'):
                    clean_model = clean_model.replace('models/', '')
                    logger.info(f"Debug: Removed models/ prefix: {clean_model}")
                    
                if clean_model.startswith('gemini/'):
                    clean_model = clean_model.replace('gemini/', '')
                    logger.info(f"Debug: Removed gemini/ prefix: {clean_model}")
                    
                # Add gemini/ prefix for CrewAI
                crewai_model = f'gemini/{clean_model}'
                logger.info(f"Debug: Final CrewAI model format: {crewai_model}")
                        
                logger.info(f"Converted LangChain Gemini LLM to CrewAI format: {model_name} -> {crewai_model}")
                return crewai_model
                
            except Exception as e:
                logger.error(f"Error configuring Gemini for CrewAI: {e}")
                # Restore original keys if we changed them
                if api_key_set and original_gemini_key:
                    os.environ['GEMINI_API_KEY'] = original_gemini_key
                elif api_key_set:
                    os.environ.pop('GEMINI_API_KEY', None)
                    
                if original_google_key:
                    os.environ['GOOGLE_API_KEY'] = original_google_key
                raise
            
        # Handle LangChain ChatOpenAI
        elif hasattr(llm_instance, 'model') and 'openai' in str(llm_instance.__class__).lower():
            model_name = llm_instance.model or 'gpt-4'
            
            # Set OpenAI API key from the LLM instance
            if hasattr(llm_instance, 'api_key') and llm_instance.api_key:
                # Check if it's a valid API key (not placeholder)
                if llm_instance.api_key and not llm_instance.api_key.startswith('your-'):
                    os.environ['OPENAI_API_KEY'] = llm_instance.api_key
                    logger.info("Set OPENAI_API_KEY environment variable for CrewAI")
                else:
                    logger.warning(f"Invalid OpenAI API key detected: {llm_instance.api_key}")
            
            logger.info(f"Converted LangChain OpenAI LLM to CrewAI format: {model_name}")
            return model_name
            
        # Fallback: try to extract model name or use default
        elif hasattr(llm_instance, 'model'):
            model_name = llm_instance.model
            logger.warning(f"Using model name from unknown LLM type: {model_name}")
            return model_name
        else:
            # Default fallback
            logger.warning("Could not identify LLM type, using default gpt-4")
            return "gpt-4"

# Global factory instance
crew_factory = CrewFactory()
