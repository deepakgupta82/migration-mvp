from crewai_tools import BaseTool

class LessonsLearnedTool(BaseTool):
    name: str = "Lessons Learned Tool"
    description: str = "Queries a database of past project insights to find relevant lessons."

    def _run(self, query: str) -> str:
        # In a real implementation, this would query a vector database.
        # For now, it returns a placeholder.
        return f"Based on past projects, the key lesson for '{query}' is to prioritize modular design."
