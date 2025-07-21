from crewai import Crew, Agent, Task, Process
from crewai_tools import BaseTool
from .rag_service import RAGService

class RAGQueryTool(BaseTool):
    def __init__(self, rag_service: RAGService):
        super().__init__(name="RAGQueryTool", description="Tool for querying project documents")
        self.rag_service = rag_service

    def run(self, query: str):
        return self.rag_service.query(query)

def create_assessment_crew(project_id: str):
    rag_service = RAGService(project_id)
    rag_tool = RAGQueryTool(rag_service)

    document_analyst = Agent(
        role="Document Analyst",
        goal="Extract technical and business requirements from uploaded documents using RAGQueryTool.",
        tools=[rag_tool]
    )

    cloud_strategist = Agent(
        role="Cloud Strategist",
        goal="Create a migration strategy and Cloud Readiness Report using RAGQueryTool.",
        tools=[rag_tool]
    )

    analysis_task = Task(
        description=(
            "Analyze uploaded documents to extract information about servers, business goals, and compliance rules. "
            "Use RAGQueryTool to answer specific queries."
        ),
        agent=document_analyst
    )

    planning_task = Task(
        description=(
            "Generate a Markdown-formatted Cloud Readiness Report with sections: Executive Summary, Key Risks, "
            "Recommended Approach, and High-Level Plan. Use the output of the analysis task as context."
        ),
        agent=cloud_strategist,
        context=analysis_task
    )

    crew = Crew(
        agents=[document_analyst, cloud_strategist],
        tasks=[analysis_task, planning_task],
        process=Process.sequential
    )
    return crew
