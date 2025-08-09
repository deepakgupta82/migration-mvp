"""
Centralized Statistics Service for real-time stats management
Handles calculation and broadcasting of project and platform statistics
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StatsService:
    """Centralized service for managing and broadcasting statistics"""
    
    def __init__(self):
        self.websocket_manager = None
        logger.info("Stats Service initialized")
    
    def _get_websocket_manager(self):
        """Lazy load websocket manager to avoid circular imports"""
        if self.websocket_manager is None:
            from app.core.websocket_stats_manager import get_websocket_stats_manager
            self.websocket_manager = get_websocket_stats_manager()
        return self.websocket_manager
    
    async def update_project_stats(self, project_id: str, event_type: str, additional_data: Optional[Dict] = None):
        """Update project stats and broadcast to connected clients"""
        try:
            logger.info(f"Updating project {project_id} stats due to event: {event_type}")
            
            # Calculate fresh project stats
            stats = await self.calculate_project_stats(project_id)
            
            # Prepare broadcast message
            message = {
                "type": "project_stats_update",
                "project_id": project_id,
                "event_type": event_type,
                "data": stats,
                "timestamp": datetime.now().isoformat(),
                "additional_data": additional_data or {}
            }
            
            # Broadcast to project-specific listeners
            websocket_manager = self._get_websocket_manager()
            await websocket_manager.broadcast_to_project(project_id, message)
            
            # Also update platform stats for certain events
            platform_affecting_events = [
                "document_uploaded", "document_deleted", "documents_processed", 
                "data_cleared", "project_created", "project_deleted"
            ]
            
            if event_type in platform_affecting_events:
                await self.update_platform_stats(event_type, {"project_id": project_id})
            
            logger.info(f"Successfully updated and broadcasted project {project_id} stats")
            
        except Exception as e:
            logger.error(f"Error updating project stats: {e}")
    
    async def update_platform_stats(self, event_type: str, additional_data: Optional[Dict] = None):
        """Update platform-wide stats and broadcast"""
        try:
            logger.info(f"Updating platform stats due to event: {event_type}")
            
            # Calculate fresh platform stats
            stats = await self.calculate_platform_stats()
            
            # Prepare broadcast message
            message = {
                "type": "platform_stats_update",
                "event_type": event_type,
                "data": stats,
                "timestamp": datetime.now().isoformat(),
                "additional_data": additional_data or {}
            }
            
            # Broadcast to dashboard listeners
            websocket_manager = self._get_websocket_manager()
            await websocket_manager.broadcast_to_dashboard(message)
            
            logger.info("Successfully updated and broadcasted platform stats")
            
        except Exception as e:
            logger.error(f"Error updating platform stats: {e}")
    
    async def calculate_project_stats(self, project_id: str) -> Dict[str, Any]:
        """Calculate comprehensive project statistics"""
        try:
            # Import project service client directly to avoid circular imports
            from app.core.project_service import ProjectServiceClient
            from app.core.rag_service import RAGService
            from app.core.graph_service import GraphService
            
            stats = {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "last_updated": datetime.now().isoformat()
            }
            
            # Get project files count
            try:
                project_service = ProjectServiceClient()
                project = project_service.get_project(project_id)
                if project:
                    # Get files from project service
                    import requests
                    response = requests.get(
                        f"{project_service.base_url}/projects/{project_id}/files",
                        headers=project_service._get_auth_headers(),
                        timeout=5
                    )
                    if response.ok:
                        files = response.json()
                        stats["files_count"] = len(files)
            except Exception as e:
                logger.warning(f"Error getting project files count: {e}")
            
            # Get embeddings count from ChromaDB
            try:
                rag_service = RAGService(project_id)
                if rag_service.collection:
                    stats["embeddings_count"] = rag_service.collection.count()
                rag_service.cleanup()
            except Exception as e:
                logger.warning(f"Error getting embeddings count: {e}")
            
            # Get graph statistics from Neo4j
            try:
                graph_service = GraphService()
                
                # Count nodes for this project
                nodes_result = graph_service.execute_query(
                    "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                    {"project_id": project_id}
                )
                if nodes_result:
                    stats["graph_nodes"] = nodes_result[0]["node_count"]
                
                # Count relationships for this project
                rels_result = graph_service.execute_query(
                    "MATCH (n {project_id: $project_id})-[r]-(m {project_id: $project_id}) RETURN count(r) as rel_count",
                    {"project_id": project_id}
                )
                if rels_result:
                    stats["graph_relationships"] = rels_result[0]["rel_count"]
                
                graph_service.close()
            except Exception as e:
                logger.warning(f"Error getting graph statistics: {e}")
            
            logger.info(f"Calculated project {project_id} stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating project stats: {e}")
            return {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def calculate_platform_stats(self) -> Dict[str, Any]:
        """Calculate comprehensive platform statistics"""
        try:
            # Use existing platform stats logic
            from app.core.platform_stats import get_platform_stats
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, get_platform_stats)
            
            # Add timestamp
            stats["last_updated"] = datetime.now().isoformat()
            
            logger.info(f"Calculated platform stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating platform stats: {e}")
            return {
                "total_projects": 0,
                "total_documents": 0,
                "total_embeddings": 0,
                "total_neo4j_nodes": 0,
                "total_neo4j_relationships": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }


# Global instance
_stats_service = None


def get_stats_service() -> StatsService:
    """Get the global stats service instance"""
    global _stats_service
    if _stats_service is None:
        _stats_service = StatsService()
    return _stats_service
