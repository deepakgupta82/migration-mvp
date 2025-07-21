from crewai import Agent, Task, Crew, Process
from crewai_tools import BaseTool
from .rag_service import RAGService
import os

# =====================================================================================
#  Define the Custom Tool for RAG
# =====================================================================================
class RAGKnowledgeBaseTool(BaseTool):
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
#  Function to Create the Expert Nagarro Crew
# =====================================================================================
def create_assessment_crew(project_id: str):
    """
    Initializes and assembles the expert crew for the client readiness assessment.
    """
    rag_service = RAGService(project_id)
    knowledge_base_tool = RAGKnowledgeBaseTool(rag_service=rag_service)

    # --- AGENT DEFINITIONS ---

    # Agent 1: The Engagement Analyst (Data Gatherer)
    analyst = Agent(
        role="Lead Engagement Analyst",
        goal=(
            "To meticulously extract and synthesize all critical business and technical information "
            "from the client's provided documents. Your focus is on facts and requirements."
        ),
        backstory=(
            "You are a seasoned analyst at Nagarro, known for your ability to dive into a new client's "
            "documentation and emerge with a perfectly structured, comprehensive brief. You are the "
            "foundation of every successful project, ensuring no detail is overlooked. You leave the "
            "strategizing to others; your job is to provide them with unimpeachable data."
        ),
        tools=[knowledge_base_tool],
        verbose=True,
        allow_delegation=False,
        # Use a powerful but cost-effective model for this structured task
        llm=os.environ.get("OPENAI_MODEL_NAME", "gpt-4o") 
    )

    # Agent 2: The Principal Cloud Architect (Strategist)
    architect = Agent(
        role="Principal Cloud Architect",
        goal=(
            "To interpret the analyst's findings and devise a high-level, business-aware cloud "
            "transformation strategy. Your output must be a professional, client-facing report that "
            "inspires confidence and outlines a clear path forward."
        ),
        backstory=(
            "You are a top-tier Cloud Architect at Nagarro, a 'Thinking-in-systems' expert. You translate complex "
            "technical details and vague business goals into robust, scalable, and secure cloud solutions. "
            "Clients trust you to not just migrate their systems, but to transform their business. "
            "Your reports are known for their clarity, strategic insight, and professional polish."
        ),
        tools=[knowledge_base_tool],  # The architect can also query the KB to verify details
        verbose=True,
        allow_delegation=False,
        llm=os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
    )

    # --- TASK DEFINITIONS ---

    # Task 1: Comprehensive Analysis Task
    analysis_task = Task(
        description=(
            "1. **Initiate Discovery**: Begin by using the 'Project Knowledge Base Query Tool' to ask broad questions to understand the scope. Good starting questions are 'Provide a summary of all documents' and 'What are the main applications or systems mentioned?'.\n"
            "2. **Extract Technical Details**: Systematically query the knowledge base for all technical assets. Ask specific questions like 'List all server hostnames and their specifications', 'Describe the database technologies in use', and 'What are the dependencies between the applications?'.\n"
            "3. **Extract Business Context**: Query the knowledge base for all business drivers. Ask questions like 'What are the primary business goals for this initiative?', 'What is the budget and timeline?', and 'List all stated compliance, security, or regulatory requirements (e.g., GDPR, DORA, HIPAA)'.\n"
            "4. **Synthesize Findings**: Compile all extracted information into a single, structured summary. This summary is your final output. It will be passed to the Principal Cloud Architect for strategic planning."
        ),
        expected_output=(
            "A comprehensive, well-structured summary document containing two main sections:\n"
            "**Section 1: Technical Asset Inventory** (listing servers, applications, databases, and known dependencies).\n"
            "**Section 2: Business & Compliance Drivers** (listing goals, budget, timeline, and security/compliance rules)."
        ),
        agent=analyst
    )

    # Task 2: Strategic Planning and Report Generation Task
    planning_task = Task(
        description=(
            "You have received a detailed summary from the Engagement Analyst. Your task is to act as a Principal Cloud Architect and create the official 'Nagarro Cloud Readiness Assessment' report.\n"
            "1. **Analyze the Brief**: Carefully review the provided technical and business context from the previous task.\n"
            "2. **Formulate Strategy**: Based on the findings, determine a high-level cloud strategy. Consider the business goals (e.g., cost reduction vs. innovation) and technical constraints (e.g., legacy databases).\n"
            "3. **Author the Report**: Write the final report in **Markdown format**. The report must be professional, client-facing, and adhere strictly to the following structure."
        ),
        expected_output=(
            "A polished, client-ready Markdown report with the following exact sections:\n\n"
            "## Nagarro Cloud Readiness Assessment\n\n"
            "### 1. Executive Summary\n"
            "A brief, high-level overview of the project's current state and our strategic recommendation. (2-3 sentences)\n\n"
            "### 2. Analysis of Key Findings\n"
            "A summary of the most important technical and business findings from the provided documents.\n\n"
            "### 3. Identified Risks & Proposed Mitigations\n"
            "A bulleted list of the top 3-4 potential risks (e.g., security gaps, technical debt, unclear requirements) and a brief mitigation strategy for each.\n\n"
            "### 4. Recommended Strategic Approach\n"
            "Recommend a primary cloud provider (AWS, Azure, or GCP) with a clear justification. Recommend a migration approach (e.g., Lift & Shift, Re-platform, Phased Modernization) and explain why it's the best fit for the client's goals.\n\n"
            "### 5. High-Level Transformation Roadmap\n"
            "Outline a simple 3-phase plan:\n"
            "   - **Phase 1: Foundation (Weeks 1-4):** Detailed discovery, landing zone setup, and pilot selection.\n"
            "   - **Phase 2: Migration & Validation (Weeks 5-12):** Execute the migration of pilot applications and validate performance.\n"
            "   - **Phase 3: Scale & Optimize (Weeks 13+):** Scale the migration across the portfolio and implement continuous optimization (FinOps/SecOps).\n"
        ),
        agent=architect,
        context=[analysis_task]  # This task depends on the output of the analysis_task
    )

    # --- ASSEMBLE THE CREW ---
    
    return Crew(
        agents=[analyst, architect],
        tasks=[analysis_task, planning_task],
        process=Process.sequential,  # The tasks will run one after the other
        verbose=2  # Use verbose=2 for detailed, step-by-step logging in the console
    )