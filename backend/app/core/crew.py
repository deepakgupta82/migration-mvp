from crewai import Agent, Task, Crew, Process
from crewai.language_models.base import BaseLanguageModel
from crewai_tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_vertexai import ChatVertexAI
from .rag_service import RAGService
from .graph_service import GraphService
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
    Creates and new assessment crew.
    This function now aligns with the production vision outlined in overview_and_mvp.md,
    defining specialized agent roles for deep analysis and strategic planning.
    """
    rag_service = RAGService(project_id, llm)
    rag_tool = RAGQueryTool(rag_service=rag_service)
    graph_service = GraphService()
    graph_tool = GraphQueryTool(graph_service=graph_service)

    # Crew 1: Discovery & Strategy Agents (as per overview_and_mvp.md)
    # In the MVP, we combine the Ingestor and Analyst roles into a single agent.
    engagement_analyst = Agent(
        role='Engagement Analyst for Cross-Modal Synthesis',
        goal='To transform raw client data into a structured, queryable knowledge base. You must identify all IT assets (servers, apps, databases), their relationships, and the business context they operate in.',
        backstory=(
            "You are a meticulous analyst. Your strength is in synthesizing information from multiple modalities. "
            "You first use semantic search (the RAG tool) to find entities and context in unstructured text. "
            "You then mentally construct a graph of how these entities connect. Your mission is to create a complete, factual brief of the client's current state."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool],
        llm=llm,
        allow_delegation=False
    )

    # Crew 2: Design & Planning Agents (as per overview_and_mvp.md)
    principal_cloud_architect = Agent(
        role='Principal Cloud Architect',
        goal='To design a high-level target cloud architecture and migration strategy based on the Engagement Analyst\'s brief. You must propose a suitable cloud provider and migration pattern (e.g., Rehost, Replatform).',
        backstory=(
            "You are a world-class cloud architect with 15 years of experience. You live and breathe cloud-native principles, IaC, and migration methodologies. "
            "You are pragmatic and always balance the ideal architecture with the client's constraints (cost, timeline, risk)."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # In the future, this will include tools for pricing APIs and IaC templates.
        llm=llm,
        allow_delegation=False
    )

    lead_planning_manager = Agent(
        role='Lead Planning Manager',
        goal='To synthesize all findings and architectural designs into a single, client-ready "Cloud Readiness & Migration Plan". Your plan must be actionable and include a preliminary wave plan.',
        backstory=(
            "You are an expert project manager specializing in complex IT transformations. You excel at dependency analysis and sequencing. "
            "Your primary job is to create a logical migration wave plan that minimizes business disruption. You take the technical details and frame them in a strategic project plan."
        ),
        verbose=True,
        tools=[], # This agent synthesizes the work of others.
        llm=llm,
        allow_delegation=True # This agent can delegate back to the architect for clarifications.
    )

    # --- TASKS ---

    # Task 1: Current-State Synthesis
    # This task guides the analyst to build the foundational knowledge base.
    current_state_synthesis_task = Task(
        description=(
            f'For the project "{project_id}", perform a comprehensive analysis of all provided documents. '
            "Your primary goal is to create a structured 'Current-State Brief'. "
            "You must perform the following steps:\n"
            "1. **Graph Query:** Use the Graph tool to query the Neo4j database to understand the explicit structure and dependencies of the IT assets. Start with broad queries like 'MATCH (n) RETURN n' to get an overview of the graph.\n"
            "2. **Semantic Query:** Use the context from the graph to formulate more intelligent, targeted semantic queries against the Weaviate vector store to uncover business goals, compliance needs, and other implicit information. For example, if you find a 'Billing' application in the graph, you can ask the RAG tool 'What are the business requirements for the Billing application?'.\n"
            "3. **Synthesize Findings:** Combine the information from both the graph and vector stores to create a comprehensive 'Current-State Brief'. The brief must include:\n"
            "   - All servers (with OS, CPU, RAM if available).\n"
            "   - All applications and software.\n"
            "   - All databases (type and version).\n"
            "   - Explicitly stated business goals or pain points.\n"
            "   - Any mention of compliance, security, or regulatory constraints (e.g., GDPR, DORA, HIPAA).\n"
            "   - A detailed description of the relationships between these components, supported by evidence from both the graph and vector stores."
        ),
        expected_output='A detailed, structured text document titled "Current-State Brief" containing categorized lists of all findings and their relationships.',
        agent=engagement_analyst
    )

    # Task 2: Target Architecture Design
    # This task uses the brief to create a forward-looking plan.
    target_architecture_design_task = Task(
        description=(
            "Based on the 'Current-State Brief', design a high-level target cloud architecture. You must:\n"
            "1. Recommend a primary cloud provider (AWS, Azure, or GCP) and justify your choice.\n"
            "2. Propose a primary migration strategy (e.g., Rehost, Replatform, Refactor) for the key applications.\n"
            "3. Identify the top 3-5 risks for this migration project."
        ),
        expected_output='A document section titled "Target Architecture & Strategy" with your recommendations and risk assessment.',
        agent=principal_cloud_architect,
        context=[current_state_synthesis_task]
    )

    # Task 3: Final Report Generation
    # This task assembles the final, client-facing deliverable.
    report_generation_task = Task(
        description=(
            "Compile the 'Current-State Brief' and the 'Target Architecture & Strategy' into a single, polished, client-facing 'Cloud Readiness & Migration Plan' in Markdown format. "
            "The report must have a logical flow, starting with an Executive Summary and ending with a preliminary Migration Wave Plan. "
            "For the wave plan, group applications logically based on their dependencies described in the brief. For example: 'Wave 1: Foundational Services (e.g., Active Directory, shared databases)', 'Wave 2: App-Group-A'."
        ),
        expected_output='A final, comprehensive "Cloud Readiness & Migration Plan" in well-formatted Markdown.',
        agent=lead_planning_manager,
        context=[current_state_synthesis_task, target_architecture_design_task]
    )

    return Crew(
        agents=[engagement_analyst, principal_cloud_architect, lead_planning_manager],
        tasks=[current_state_synthesis_task, target_architecture_design_task, report_generation_task],
        process=Process.sequential,
        verbose=2
    )
