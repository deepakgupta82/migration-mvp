"""
Stats Processor - Core statistics calculation and caching engine
Handles real-time stats updates with Redis caching
"""

import redis.asyncio as redis
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
import httpx
import os

logger = logging.getLogger("stats-processor")

class StatsProcessor:
    """Core processor for platform and project statistics"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes default TTL
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self.document_service_url = os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8003")
        self.vector_service_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        self.graph_service_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")
        
    async def initialize(self):
        """Initialize stats processor with baseline data"""
        logger.info("Initializing stats processor")
        
        # Initialize platform stats
        await self._initialize_platform_stats()
        
        # Load existing projects from project service
        await self._sync_project_list()
        
        logger.info("Stats processor initialized successfully")
        
    async def _initialize_platform_stats(self):
        """Initialize platform-wide statistics"""
        initial_stats = {
            "platform": {
                "total_projects": 0,
                "active_projects": 0,
                "total_documents": 0,
                "total_embeddings": 0,
                "total_graph_nodes": 0,
                "total_agents": 0,
                "active_assessments": 0,
                "last_updated": datetime.utcnow().isoformat(),
                "uptime_seconds": 0
            },
            "services": {
                "project_service": {"status": "unknown", "last_ping": None},
                "document_service": {"status": "unknown", "last_ping": None},
                "vector_service": {"status": "unknown", "last_ping": None},
                "graph_service": {"status": "unknown", "last_ping": None},
                "ai_agent_service": {"status": "unknown", "last_ping": None}
            },
            "performance": {
                "avg_document_processing_time": 0,
                "avg_query_response_time": 0,
                "cache_hit_ratio": 0.0
            }
        }
        await self.redis.set("platform_stats", json.dumps(initial_stats), ex=self.cache_ttl)
        
    async def _sync_project_list(self):
        """Sync project list from project service"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.project_service_url}/api/projects")
                if response.status_code == 200:
                    projects = response.json()
                    
                    # Update project count
                    await self.update_platform_metric("total_projects", len(projects))
                    
                    # Initialize stats for each project
                    for project in projects:
                        project_id = project.get("id") or project.get("project_id")
                        if project_id:
                            await self._initialize_project_stats(project_id, project)
                            
        except Exception as e:
            logger.error(f"Failed to sync project list: {e}")
            
    async def _initialize_project_stats(self, project_id: str, project_data: Dict = None):
        """Initialize statistics for a specific project"""
        project_stats = {
            "project_id": project_id,
            "name": project_data.get("name", "") if project_data else "",
            "status": project_data.get("status", "unknown") if project_data else "unknown",
            "files_count": 0,
            "embeddings_count": 0,
            "graph_nodes": 0,
            "graph_relationships": 0,
            "assessment_status": "not_started",
            "last_activity": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "processing_stats": {
                "documents_processed": 0,
                "processing_errors": 0,
                "avg_processing_time": 0
            }
        }
        
        cache_key = f"project_stats:{project_id}"
        await self.redis.set(cache_key, json.dumps(project_stats), ex=self.cache_ttl)
        
    # =================================================================================
    # Event-driven update methods
    # =================================================================================
    
    async def update_platform_metric(self, metric_name: str, value: Any, delta: bool = False):
        """Update a platform-wide metric"""
        try:
            stats = await self.get_platform_stats()
            
            if delta:
                # Incremental update
                current_value = stats["platform"].get(metric_name, 0)
                if isinstance(current_value, (int, float)) and isinstance(value, (int, float)):
                    stats["platform"][metric_name] = current_value + value
                else:
                    logger.warning(f"Cannot apply delta to non-numeric metric {metric_name}")
                    stats["platform"][metric_name] = value
            else:
                # Absolute update
                stats["platform"][metric_name] = value
            
            stats["platform"]["last_updated"] = datetime.utcnow().isoformat()
            
            await self.redis.set("platform_stats", json.dumps(stats), ex=self.cache_ttl)
            logger.debug(f"Updated platform metric {metric_name} = {stats['platform'][metric_name]}")
            
        except Exception as e:
            logger.error(f"Failed to update platform metric {metric_name}: {e}")
            
    async def update_project_metric(self, project_id: str, metric_name: str, value: Any, delta: bool = False):
        """Update a project-specific metric"""
        try:
            stats = await self.get_project_stats(project_id)
            
            if delta:
                # Incremental update
                current_value = stats.get(metric_name, 0)
                if isinstance(current_value, (int, float)) and isinstance(value, (int, float)):
                    stats[metric_name] = current_value + value
                else:
                    logger.warning(f"Cannot apply delta to non-numeric project metric {metric_name}")
                    stats[metric_name] = value
            else:
                # Absolute update
                stats[metric_name] = value
            
            stats["last_updated"] = datetime.utcnow().isoformat()
            stats["last_activity"] = datetime.utcnow().isoformat()
            
            cache_key = f"project_stats:{project_id}"
            await self.redis.set(cache_key, json.dumps(stats), ex=self.cache_ttl)
            logger.debug(f"Updated project {project_id} metric {metric_name} = {stats[metric_name]}")
            
        except Exception as e:
            logger.error(f"Failed to update project metric {metric_name} for {project_id}: {e}")
            
    async def handle_document_processed(self, project_id: str, document_info: Dict):
        """Handle document processing event"""
        try:
            # Update project document count
            await self.update_project_metric(project_id, "files_count", 1, delta=True)
            
            # Update platform document count
            await self.update_platform_metric("total_documents", 1, delta=True)
            
            # Update processing stats
            processing_time = document_info.get("processing_time_ms", 0)
            if processing_time > 0:
                await self.update_project_metric(project_id, "processing_stats.documents_processed", 1, delta=True)
                
            logger.info(f"Processed document event for project {project_id}")
            
        except Exception as e:
            logger.error(f"Failed to handle document processed event: {e}")
            
    async def handle_embeddings_updated(self, project_id: str, embeddings_info: Dict):
        """Handle embeddings update event"""
        try:
            embeddings_count = embeddings_info.get("count", 0)
            await self.update_project_metric(project_id, "embeddings_count", embeddings_count)
            
            # Update platform total
            platform_stats = await self.get_platform_stats()
            total_embeddings = sum(
                (await self.get_project_stats(pid)).get("embeddings_count", 0)
                for pid in await self._get_all_project_ids()
            )
            await self.update_platform_metric("total_embeddings", total_embeddings)
            
            logger.info(f"Updated embeddings for project {project_id}: {embeddings_count}")
            
        except Exception as e:
            logger.error(f"Failed to handle embeddings updated event: {e}")
            
    async def handle_graph_updated(self, project_id: str, graph_info: Dict):
        """Handle graph update event"""
        try:
            nodes_count = graph_info.get("nodes", 0)
            relationships_count = graph_info.get("relationships", 0)
            
            await self.update_project_metric(project_id, "graph_nodes", nodes_count)
            await self.update_project_metric(project_id, "graph_relationships", relationships_count)
            
            # Update platform total
            platform_stats = await self.get_platform_stats()
            total_nodes = sum(
                (await self.get_project_stats(pid)).get("graph_nodes", 0)
                for pid in await self._get_all_project_ids()
            )
            await self.update_platform_metric("total_graph_nodes", total_nodes)
            
            logger.info(f"Updated graph for project {project_id}: {nodes_count} nodes, {relationships_count} relationships")
            
        except Exception as e:
            logger.error(f"Failed to handle graph updated event: {e}")
            
    async def handle_assessment_status_changed(self, project_id: str, status: str):
        """Handle assessment status change event"""
        try:
            await self.update_project_metric(project_id, "assessment_status", status)
            
            # Update platform active assessments count
            platform_stats = await self.get_platform_stats()
            active_count = 0
            for pid in await self._get_all_project_ids():
                project_stats = await self.get_project_stats(pid)
                if project_stats.get("assessment_status") in ["running", "processing"]:
                    active_count += 1
                    
            await self.update_platform_metric("active_assessments", active_count)
            
            logger.info(f"Assessment status changed for project {project_id}: {status}")
            
        except Exception as e:
            logger.error(f"Failed to handle assessment status change: {e}")
            
    # =================================================================================
    # Data retrieval methods
    # =================================================================================
    
    async def get_platform_stats(self) -> Dict[str, Any]:
        """Get current platform statistics"""
        try:
            stats_json = await self.redis.get("platform_stats")
            if stats_json:
                return json.loads(stats_json)
            else:
                # Initialize if missing
                await self._initialize_platform_stats()
                return await self.get_platform_stats()
        except Exception as e:
            logger.error(f"Failed to get platform stats: {e}")
            return {"error": "Failed to retrieve platform statistics"}
            
    async def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        """Get statistics for a specific project"""
        try:
            cache_key = f"project_stats:{project_id}"
            stats_json = await self.redis.get(cache_key)
            if stats_json:
                return json.loads(stats_json)
            else:
                # Initialize if missing
                await self._initialize_project_stats(project_id)
                return await self.get_project_stats(project_id)
        except Exception as e:
            logger.error(f"Failed to get project stats for {project_id}: {e}")
            return {"error": f"Failed to retrieve statistics for project {project_id}"}
            
    async def get_all_project_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all projects"""
        try:
            project_ids = await self._get_all_project_ids()
            project_stats = []
            
            for project_id in project_ids:
                stats = await self.get_project_stats(project_id)
                if "error" not in stats:
                    project_stats.append(stats)
                    
            return project_stats
        except Exception as e:
            logger.error(f"Failed to get all project stats: {e}")
            return []
            
    async def _get_all_project_ids(self) -> List[str]:
        """Get all project IDs from Redis cache"""
        try:
            # Get all project stats keys
            keys = await self.redis.keys("project_stats:*")
            project_ids = [key.decode().replace("project_stats:", "") for key in keys]
            return project_ids
        except Exception as e:
            logger.error(f"Failed to get project IDs: {e}")
            return []
            
    async def update_service_health(self, service_name: str, status: str):
        """Update service health status"""
        try:
            stats = await self.get_platform_stats()
            stats["services"][service_name] = {
                "status": status,
                "last_ping": datetime.utcnow().isoformat()
            }
            
            await self.redis.set("platform_stats", json.dumps(stats), ex=self.cache_ttl)
            logger.debug(f"Updated service health: {service_name} = {status}")
            
        except Exception as e:
            logger.error(f"Failed to update service health for {service_name}: {e}")
