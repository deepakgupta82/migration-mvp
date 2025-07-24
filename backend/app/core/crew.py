from crewai import Agent, Task, Crew, Process
from crewai.language_models.base import BaseLanguageModel
from crewai_tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_vertexai import ChatVertexAI
from .rag_service import RAGService
from .graph_service import GraphService
from .diagramming_agent import create_diagramming_agent
import os
import logging

# LLM selection
def get_llm_and_model():
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return ChatOpenAI(model=model_name, api_key=api_key, temperature=0.1)
    elif provider == "anthropic":
        model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return ChatAnthropic(model=model_name, api_key=api_key, temperature=0.1)
    elif provider == "google":
        model_name = os.environ.get("GOOGLE_MODEL_NAME", "gemini-1.5-pro-latest")
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        return ChatVertexAI(model=model_name, temperature=0.1)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

# Agent logging setup
os.makedirs("logs", exist_ok=True)
agent_logger = logging.getLogger("agents")
agent_handler = logging.FileHandler("logs/agents.log")
agent_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not agent_logger.hasHandlers():
    agent_logger.addHandler(agent_handler)
agent_logger.setLevel(logging.INFO)

# =====================================================================================
#  Define the Custom Tool for RAG
# =====================================================================================
class RAGQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific knowledge base.
    This is the only way for them to access information from the uploaded documents.
    """
    name: str = "Project Knowledge Base Query Tool"
    description: str = (
        "Use this tool to answer any questions about the client's project. "
        "It queries a vector database containing the contents of all uploaded documents "
        "(architecture diagrams, project charters, security audits, server lists, etc.). "
        "Formulate clear, specific questions to get the best results."
    )
    rag_service: RAGService

    def _run(self, question: str) -> str:
        """Executes the query against the RAG service."""
        print(f"DEBUG: RAGKnowledgeBaseTool received query: '{question}'")
        return self.rag_service.query(question)

# =====================================================================================
#  Define the Custom Tool for Graph
# =====================================================================================
class GraphQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific graph database.
    """
    name: str = "Project Graph Database Query Tool"
    description: str = (
        "Use this tool to query the graph database for relationships between entities. "
        "Formulate clear, specific Cypher queries to get the best results."
    )
    graph_service: GraphService

    def _run(self, query: str) -> str:
        """Executes the query against the Graph service."""
        print(f"DEBUG: GraphQueryTool received query: '{query}'")
        return str(self.graph_service.execute_query(query))


# =====================================================================================
#  Function to Create the Expert Nagarro Crew
# =====================================================================================
def create_assessment_crew(project_id: str, llm: BaseLanguageModel):
    """
    Creates an enhanced assessment crew with comprehensive enterprise capabilities.

    This implementation fully aligns with the sophisticated vision outlined in overview_and_mvp.md:
    - Senior Infrastructure Discovery Analyst (12+ years experience)
    - Principal Cloud Architect & Migration Strategist (50+ enterprise migrations)
    - Risk & Compliance Officer (10+ years regulatory expertise)
    - Lead Migration Program Manager (30+ cloud migrations)

    Enhanced capabilities include:
    - Cross-modal synthesis (graph + semantic search)
    - 6Rs migration pattern analysis
    - Comprehensive compliance validation (GDPR, SOX, HIPAA, PCI-DSS)
    - Landing zone architecture design
    - 3-year TCO cost modeling
    - Wave planning with dependency analysis
    - Executive-ready deliverables
    """
    rag_service = RAGService(project_id, llm)
    rag_tool = RAGQueryTool(rag_service=rag_service)
    graph_service = GraphService()
    graph_tool = GraphQueryTool(graph_service=graph_service)

    # Enhanced Engagement Analyst with deeper expertise
    engagement_analyst = Agent(
        role='Senior Infrastructure Discovery Analyst',
        goal='Perform comprehensive cross-modal synthesis to create a complete digital twin of the client\'s current IT landscape, identifying all assets, dependencies, and business context.',
        backstory=(
            "You are a seasoned infrastructure analyst with 12+ years in enterprise IT discovery. "
            "You specialize in dependency mapping, application portfolio analysis, and business-IT alignment. "
            "Your methodology: First query the graph database for explicit relationships, then use semantic search "
            "to uncover implicit dependencies and business context. You excel at identifying hidden technical debt, "
            "compliance gaps, and modernization opportunities that others miss."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool],
        llm=llm,
        allow_delegation=False
    )

    # Enhanced Principal Cloud Architect
    principal_cloud_architect = Agent(
        role='Principal Cloud Architect & Migration Strategist',
        goal='Design optimal target cloud architecture considering cost, performance, security, and compliance. Recommend specific migration patterns (6Rs) for each application workload.',
        backstory=(
            "You are a distinguished cloud architect with deep expertise across AWS, Azure, and GCP. "
            "You hold multiple cloud certifications and have led 50+ enterprise migrations. "
            "Your approach: Analyze current state, apply cloud-native principles, optimize for cost and performance. "
            "You consider the full spectrum: lift-and-shift vs. re-platforming vs. refactoring. "
            "You always factor in compliance requirements, data residency, and business continuity."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add pricing APIs, service catalogs
        llm=llm,
        allow_delegation=False
    )

    # NEW: Risk & Compliance Officer (Missing from current implementation)
    risk_compliance_officer = Agent(
        role='Risk & Compliance Officer',
        goal='Audit proposed architecture against regulatory requirements (GDPR, SOX, HIPAA, etc.) and enterprise security policies. Force architectural iterations until fully compliant.',
        backstory=(
            "You are a cybersecurity and compliance expert with deep knowledge of global regulations. "
            "You have 10+ years in risk assessment and regulatory compliance across industries. "
            "You are adversarial by design - your job is to find flaws, gaps, and risks that others miss. "
            "You enforce zero-trust principles, data protection laws, and industry-specific compliance frameworks. "
            "You will reject any architecture that doesn't meet the highest security and compliance standards."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add compliance frameworks tool
        llm=llm,
        allow_delegation=False
    )

    # Create diagramming agent
    diagramming_agent = create_diagramming_agent(llm)

    # Enhanced Lead Planning Manager
    lead_planning_manager = Agent(
        role='Lead Migration Program Manager',
        goal='Create a detailed, risk-minimized migration execution plan with wave sequencing, timeline estimation, and stakeholder communication strategy.',
        backstory=(
            "You are an expert program manager specializing in complex IT transformations. "
            "You have successfully managed 30+ cloud migrations with budgets exceeding $10M. "
            "Your expertise: Dependency analysis, critical path planning, risk mitigation, and stakeholder management. "
            "You excel at wave planning - grouping applications to minimize business disruption. "
            "You always include rollback plans, testing strategies, and communication frameworks."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add project planning tools
        llm=llm,
        allow_delegation=True # This agent can delegate back to the architect for clarifications.
    )

    # --- TASKS ---

    # Enhanced discovery task
    current_state_synthesis_task = Task(
        description=(
            "Perform comprehensive discovery and analysis of the client's current IT landscape:\n"
            "1. INFRASTRUCTURE DISCOVERY: Query the graph database to map all servers, applications, databases, and their relationships\n"
            "2. BUSINESS CONTEXT ANALYSIS: Use semantic search to understand business processes, compliance requirements, and strategic objectives\n"
            "3. DEPENDENCY MAPPING: Identify critical dependencies, single points of failure, and integration patterns\n"
            "4. TECHNICAL DEBT ASSESSMENT: Evaluate legacy systems, outdated technologies, and modernization opportunities\n"
            "5. COMPLIANCE LANDSCAPE: Document regulatory requirements, data classification, and security policies\n"
            "6. RISK ASSESSMENT: Identify operational, security, and business continuity risks\n\n"
            "Deliver a comprehensive JSON brief covering: IT inventory, business context, dependencies, risks, and modernization readiness."
        ),
        expected_output='Detailed JSON object with complete current state analysis including infrastructure inventory, business context, dependencies, compliance requirements, and risk assessment.',
        agent=engagement_analyst
    )

    # Enhanced architecture design task
    target_architecture_design_task = Task(
        description=(
            "Design optimal target cloud architecture based on the current state analysis:\n"
            "1. CLOUD STRATEGY: Recommend primary cloud provider and multi-cloud considerations\n"
            "2. MIGRATION PATTERNS: Apply 6Rs framework (Rehost, Replatform, Refactor, etc.) to each application\n"
            "3. LANDING ZONE DESIGN: Define network architecture, security zones, and connectivity patterns\n"
            "4. SERVICE MAPPING: Map current services to cloud-native equivalents\n"
            "5. COST OPTIMIZATION: Recommend instance types, storage tiers, and cost management strategies\n"
            "6. SECURITY ARCHITECTURE: Design identity management, encryption, and monitoring frameworks\n"
            "7. DISASTER RECOVERY: Plan backup, replication, and business continuity strategies\n\n"
            "Include specific cloud services, estimated costs, and implementation complexity."
        ),
        expected_output='Comprehensive target architecture document with cloud service recommendations, migration patterns, cost estimates, and security framework.',
        agent=principal_cloud_architect,
        context=[current_state_synthesis_task]
    )

    # NEW: Compliance validation task
    compliance_validation_task = Task(
        description=(
            "Audit the proposed target architecture for compliance and security:\n"
            "1. REGULATORY COMPLIANCE: Validate against GDPR, SOX, HIPAA, PCI-DSS as applicable\n"
            "2. SECURITY ASSESSMENT: Review encryption, access controls, and monitoring capabilities\n"
            "3. DATA GOVERNANCE: Ensure data residency, classification, and retention policies\n"
            "4. RISK MITIGATION: Identify security gaps and recommend remediation\n"
            "5. COMPLIANCE GAPS: Document any non-compliance issues and required changes\n\n"
            "CRITICAL: If any compliance violations are found, REJECT the architecture and demand revisions."
        ),
        expected_output='Compliance audit report with pass/fail assessment and required architectural changes.',
        agent=risk_compliance_officer,
        context=[target_architecture_design_task]
    )

    # Task 4: Diagram Generation
    # This task creates a visual representation of the architecture
    diagram_generation_task = Task(
        description=(
            "Analyze the JSON architecture description from the Principal Cloud Architect. "
            "Extract the JSON portion and use the DiagramGeneratorTool to create a visual representation of the target architecture. "
            "Your output must be the public URL of the generated diagram image."
        ),
        expected_output='The public URL of the generated architecture diagram image.',
        agent=diagramming_agent,
        context=[target_architecture_design_task]
    )

    # Enhanced final report generation task
    report_generation_task = Task(
        description=(
            "Create a comprehensive, executive-ready Cloud Migration Strategy & Execution Plan:\n"
            "1. EXECUTIVE SUMMARY: High-level overview with ROI projections and strategic benefits\n"
            "2. CURRENT STATE ANALYSIS: Synthesize infrastructure discovery findings\n"
            "3. TARGET ARCHITECTURE: Present cloud strategy with embedded architecture diagram\n"
            "4. COMPLIANCE & SECURITY: Include compliance validation results and security framework\n"
            "5. MIGRATION ROADMAP: Detailed wave planning with timelines and dependencies\n"
            "6. RISK MITIGATION: Comprehensive risk assessment with mitigation strategies\n"
            "7. COST-BENEFIT ANALYSIS: 3-year TCO comparison and ROI projections\n"
            "8. IMPLEMENTATION PLAN: Detailed project plan with milestones and deliverables\n\n"
            "Format as professional Markdown suitable for C-level presentation."
        ),
        expected_output='Executive-ready Cloud Migration Strategy & Execution Plan in professional Markdown format with embedded diagrams and comprehensive analysis.',
        agent=lead_planning_manager,
        context=[current_state_synthesis_task, target_architecture_design_task, compliance_validation_task, diagram_generation_task]
    )

    return Crew(
        agents=[engagement_analyst, principal_cloud_architect, risk_compliance_officer, diagramming_agent, lead_planning_manager],
        tasks=[current_state_synthesis_task, target_architecture_design_task, compliance_validation_task, diagram_generation_task, report_generation_task],
        process=Process.sequential,
        verbose=2,
        memory=True  # Enable memory for better collaboration between agents
    )
