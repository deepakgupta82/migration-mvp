from crewai.tools import BaseTool
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

class ProjectKnowledgeBaseQueryTool(BaseTool):
    name: str = "Project Knowledge Base Query Tool"
    description: str = "Queries the project-specific knowledge base using RAG to find relevant information from uploaded documents and project data."
    project_id: Optional[str] = None
    llm: Optional[Any] = None

    def __init__(self, project_id: Optional[str] = None, llm=None, **kwargs):
        super().__init__(project_id=project_id, llm=llm, **kwargs)
        self.llm = llm

    def _run(self, query: str) -> str:
        try:
            if not self.project_id:
                return "Error: No project ID specified for knowledge base query"
            project_info = self._get_project_info()
            rag_results = self._query_rag(query)
            files_info = self._get_project_files()
            return self._format_response(query, project_info, rag_results, files_info)
        except Exception as e:
            logger.error(f"Error in project knowledge base query: {e}")
            return f"Knowledge base query error: {str(e)}"

    def _project_base(self) -> Optional[str]:
        return os.getenv("PROJECT_SERVICE_URL") or os.getenv("API_GATEWAY_URL")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"
        }
        corr = os.getenv("X_CORRELATION_ID")
        if corr:
            headers["X-Correlation-ID"] = corr
        return headers

    def _get_project_info(self) -> Dict[str, Any]:
        try:
            import requests
            base = self._project_base()
            if not base:
                return {}
            resp = requests.get(f"{base}/projects/{self.project_id}", headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Failed to fetch project info: {resp.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching project info: {e}")
            return {}

    def _query_rag(self, query: str) -> str:
        try:
            # Reuse existing tool which already supports gateway fallback
            from app.tools.rag_query_tool import RAGQueryTool
            tool = RAGQueryTool()
            return tool.run(query)
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return f"RAG query error: {str(e)}"

    def _get_project_files(self) -> list:
        try:
            import requests
            base = self._project_base()
            if not base:
                return []
            resp = requests.get(f"{base}/projects/{self.project_id}/files", headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json() or []
            logger.warning(f"Failed to fetch project files: {resp.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching project files: {e}")
            return []

    def _format_response(self, query: str, project_info: Dict[str, Any], rag_results: str, files_info: list) -> str:
        response = f"# Project Knowledge Base Query: {query}\n\n"
        if project_info:
            response += "## Project Context:\n"
            response += f"- **Project**: {project_info.get('name', 'Unknown')}\n"
            response += f"- **Client**: {project_info.get('client_name', 'Unknown')}\n"
            response += f"- **Status**: {project_info.get('status', 'Unknown')}\n"
            response += f"- **Description**: {project_info.get('description', 'No description available')}\n\n"
            def _sec(title, key):
                val = project_info.get(key)
                if val and isinstance(val, str) and val.strip():
                    return f"### {title}\n\n{val}\n\n"
                return ""
            response += _sec("Project Overview", "project_overview")
            response += _sec("Project Intent", "project_intent")
            response += _sec("Client Summary", "client_summary")
            response += _sec("RFP Summary", "rfp_summary")
            response += _sec("RFP Responses", "rfp_responses")
            response += _sec("Expectations", "expectations")
            response += _sec("Deliverables Summary", "deliverables_summary")
            response += _sec("Timeline Notes", "timeline_notes")
        if files_info:
            response += f"## Available Documents ({len(files_info)} files):\n"
            for file_info in files_info[:10]:
                filename = file_info.get('filename', 'Unknown file')
                file_type = file_info.get('file_type', 'Unknown type')
                response += f"- {filename} ({file_type})\n"
            if len(files_info) > 10:
                response += f"- ... and {len(files_info) - 10} more files\n"
            response += "\n"
        response += "## Knowledge Base Search Results:\n"
        if rag_results and "error" not in rag_results.lower():
            response += f"{rag_results}\n\n"
        else:
            response += f"⚠️ {rag_results}\n\n"
        response += "## How to Use This Information:\n"
        response += "- The search results above are based on the uploaded project documents\n"
        response += "- For more specific information, try refining your query with technical terms\n"
        response += "- If no relevant results are found, consider uploading additional documentation\n"
        return response

# Alias for backward compatibility
ProjectKnowledgeBaseQuery = ProjectKnowledgeBaseQueryTool
