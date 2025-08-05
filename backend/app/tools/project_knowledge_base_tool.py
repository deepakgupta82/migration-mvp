from crewai_tools import BaseTool
import logging
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

class ProjectKnowledgeBaseQueryTool(BaseTool):
    name: str = "Project Knowledge Base Query Tool"
    description: str = "Queries the project-specific knowledge base using RAG to find relevant information from uploaded documents and project data."

    def __init__(self, project_id: Optional[str] = None):
        super().__init__()
        self.project_id = project_id
        self._rag_service = None
        self._project_service = None

    def _get_rag_service(self):
        """Lazy load RAG service for project-specific queries"""
        if self._rag_service is None:
            try:
                from app.core.rag_service import RAGService
                # Initialize with project-specific LLM if available
                try:
                    from app.core.crew import get_project_llm
                    from app.core.project_service import ProjectServiceClient
                    
                    project_service = ProjectServiceClient()
                    import requests
                    response = requests.get(
                        f"{project_service.base_url}/projects/{self.project_id}",
                        headers=project_service._get_auth_headers(),
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        project_data = response.json()
                        # Create a simple project object for get_project_llm
                        class ProjectObj:
                            def __init__(self, data):
                                self.llm_provider = data.get('llm_provider')
                                self.llm_model = data.get('llm_model')
                                self.llm_api_key_id = data.get('llm_api_key_id')
                                self.llm_temperature = data.get('llm_temperature')
                                self.llm_max_tokens = data.get('llm_max_tokens')
                        
                        project = ProjectObj(project_data)
                        llm = get_project_llm(project)
                        self._rag_service = RAGService(self.project_id, llm)
                        logger.info(f"RAG service initialized with project LLM for project {self.project_id}")
                    else:
                        # Fallback to RAG service without LLM
                        self._rag_service = RAGService(self.project_id)
                        logger.warning(f"RAG service initialized without LLM for project {self.project_id}")
                        
                except Exception as llm_error:
                    logger.warning(f"Failed to get project LLM, using RAG without LLM: {llm_error}")
                    self._rag_service = RAGService(self.project_id)
                    
            except Exception as e:
                logger.error(f"Failed to initialize RAG service: {e}")
                self._rag_service = None
        return self._rag_service

    def _get_project_service(self):
        """Lazy load project service client"""
        if self._project_service is None:
            try:
                from app.core.project_service import ProjectServiceClient
                self._project_service = ProjectServiceClient()
                logger.info("Project service client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize project service: {e}")
                self._project_service = None
        return self._project_service

    def _run(self, query: str) -> str:
        """Query the project knowledge base"""
        try:
            if not self.project_id:
                return "Error: No project ID specified for knowledge base query"
            
            # Get project information
            project_info = self._get_project_info()
            
            # Query RAG service
            rag_results = self._query_rag(query)
            
            # Get project files information
            files_info = self._get_project_files()
            
            # Combine and format results
            return self._format_response(query, project_info, rag_results, files_info)
            
        except Exception as e:
            logger.error(f"Error in project knowledge base query: {e}")
            return f"Knowledge base query error: {str(e)}"

    def _get_project_info(self) -> Dict[str, Any]:
        """Get basic project information"""
        try:
            project_service = self._get_project_service()
            if not project_service:
                return {}
            
            import requests
            response = requests.get(
                f"{project_service.base_url}/projects/{self.project_id}",
                headers=project_service._get_auth_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch project info: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error fetching project info: {e}")
            return {}

    def _query_rag(self, query: str) -> str:
        """Query RAG service for document content"""
        try:
            rag_service = self._get_rag_service()
            if rag_service:
                results = rag_service.query(query)
                logger.info("RAG query completed successfully")
                return results
            else:
                return "RAG service not available"
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return f"RAG query error: {str(e)}"

    def _get_project_files(self) -> list:
        """Get list of project files"""
        try:
            project_service = self._get_project_service()
            if not project_service:
                return []
            
            import requests
            response = requests.get(
                f"{project_service.base_url}/projects/{self.project_id}/files",
                headers=project_service._get_auth_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch project files: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching project files: {e}")
            return []

    def _format_response(self, query: str, project_info: Dict[str, Any], rag_results: str, files_info: list) -> str:
        """Format the comprehensive response"""
        response = f"# Project Knowledge Base Query: {query}\n\n"
        
        # Project context
        if project_info:
            response += "## Project Context:\n"
            response += f"- **Project**: {project_info.get('name', 'Unknown')}\n"
            response += f"- **Client**: {project_info.get('client_name', 'Unknown')}\n"
            response += f"- **Status**: {project_info.get('status', 'Unknown')}\n"
            response += f"- **Description**: {project_info.get('description', 'No description available')}\n\n"
        
        # Available files
        if files_info:
            response += f"## Available Documents ({len(files_info)} files):\n"
            for file_info in files_info[:10]:  # Show first 10 files
                filename = file_info.get('filename', 'Unknown file')
                file_type = file_info.get('file_type', 'Unknown type')
                response += f"- {filename} ({file_type})\n"
            if len(files_info) > 10:
                response += f"- ... and {len(files_info) - 10} more files\n"
            response += "\n"
        
        # RAG results
        response += "## Knowledge Base Search Results:\n"
        if rag_results and "error" not in rag_results.lower():
            response += f"{rag_results}\n\n"
        else:
            response += f"⚠️ {rag_results}\n\n"
        
        # Usage guidance
        response += "## How to Use This Information:\n"
        response += "- The search results above are based on the uploaded project documents\n"
        response += "- For more specific information, try refining your query with technical terms\n"
        response += "- If no relevant results are found, consider uploading additional documentation\n"
        
        return response


# Alias for backward compatibility
ProjectKnowledgeBaseQuery = ProjectKnowledgeBaseQueryTool
