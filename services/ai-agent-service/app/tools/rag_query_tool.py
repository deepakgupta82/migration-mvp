"""
RAG Query Tool for ai-agent-service
Uses API Gateway/vector-service where available; falls back to local RAGService if injected.
"""
from crewai.tools import BaseTool
import logging
from typing import Optional, Any
import os

try:
    import requests
except Exception:
    requests = None

logger = logging.getLogger(__name__)

class RAGQueryTool(BaseTool):
    name: str = "Project Knowledge Base Query Tool"
    description: str = (
        "Use this tool to answer any questions about the client's project. "
        "It queries a vector database containing the contents of all uploaded documents."
    )

    def __init__(self, rag_service=None, **kwargs):
        super().__init__(**kwargs)
        self._rag_service = rag_service

    @property
    def rag_service(self):
        return self._rag_service

    class Config:
        arbitrary_types_allowed = True

    def run(self, question: str) -> str:
        if not self.rag_service:
            # Gateway path: /api/projects/{project_id}/query
            use_ms = os.getenv("RAG_TOOL_USE_VECTOR_SERVICE", "true").lower() in ("1", "true", "yes")
            project_id = os.getenv("CURRENT_PROJECT_ID")
            api_base = os.getenv("API_GATEWAY_URL", "http://localhost:8000")
            if use_ms and requests is not None and project_id:
                try:
                    url = f"{api_base}/api/projects/{project_id}/query"
                    headers = {
                        "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
                        "Content-Type": "application/json",
                    }
                    resp = requests.post(url, headers=headers, json={"query": question}, timeout=10)
                    if resp.ok:
                        data = resp.json()
                        return data.get("answer") or str(data)[:5000]
                except Exception as e:
                    logger.warning(f"Gateway query failed: {e}")
            return "Error: RAG service not initialized and gateway unavailable"

        try:
            return self.rag_service.query(question)
        except Exception as e:
            logger.error(f"RAGQueryTool error: {e}")
            return f"Error querying knowledge base: {str(e)}"

    def _run(self, question: str) -> str:
        return self.run(question)

    def _arun(self, question: str) -> str:
        return self.run(question)
