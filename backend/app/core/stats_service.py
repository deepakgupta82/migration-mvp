"""
Centralized Statistics Service for real-time stats management
Handles calculation and broadcasting of project and platform statistics
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import time
from contextlib import contextmanager
from app.core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


class StatsService:
    """Centralized service for managing and broadcasting statistics"""
    
    def __init__(self):
        self.websocket_manager = None
        logger.info("Stats Service initialized")
        # Cache structures
        self.project_cache: Dict[str, Dict[str, Any]] = {}
        self.platform_cache: Optional[Dict[str, Any]] = None
        self.project_ttl_seconds = 15
        self.platform_ttl_seconds = 10
        self.refresh_in_progress: Dict[str, bool] = {}
        self.platform_refreshing = False
        self.dirty_projects: set[str] = set()  # phase 6 persistence tracking
        self.persistence_enabled = False  # flip true when DB migration applied

    def _get_websocket_manager(self):
        """Lazy load websocket manager to avoid circular imports"""
        if self.websocket_manager is None:
            from app.core.websocket_stats_manager import get_websocket_stats_manager
            self.websocket_manager = get_websocket_stats_manager()
        return self.websocket_manager
    
    def _is_stale(self, cached: Dict[str, Any], ttl: int) -> bool:
        try:
            ts = cached.get("last_updated")
            if not ts:
                return True
            from datetime import datetime, timezone
            updated = datetime.fromisoformat(ts.replace('Z',''))
            age = (datetime.now(updated.tzinfo or timezone.utc) - updated).total_seconds()
            return age > ttl
        except Exception:
            return True

    async def get_project_stats_cached(self, project_id: str) -> Dict[str, Any]:
        cached = self.project_cache.get(project_id)
        if cached and not self._is_stale(cached, self.project_ttl_seconds):
            return {**cached, "stale": False, "cache": True}
        # Return stale immediately and trigger async refresh if not already
        if cached:
            if not self.refresh_in_progress.get(project_id):
                asyncio.create_task(self._refresh_project_stats(project_id))
            return {**cached, "stale": True, "cache": True}
        # No cache: compute synchronously once
        stats = await self.calculate_project_stats(project_id)
        self.project_cache[project_id] = stats
        return {**stats, "stale": False, "cache": False}

    async def _refresh_project_stats(self, project_id: str):
        self.refresh_in_progress[project_id] = True
        try:
            stats = await self.calculate_project_stats(project_id)
            self.project_cache[project_id] = stats
        except Exception as e:
            logger.error(f"Background refresh project {project_id} failed: {e}")
        finally:
            self.refresh_in_progress[project_id] = False

    async def get_platform_stats_cached(self) -> Dict[str, Any]:
        if self.platform_cache and not self._is_stale(self.platform_cache, self.platform_ttl_seconds):
            return {**self.platform_cache, 'stale': False, 'cache': True}
        if self.platform_cache:
            # async refresh
            if not self.platform_refreshing:
                asyncio.create_task(self._refresh_platform_stats())
            return {**self.platform_cache, 'stale': True, 'cache': True}
        stats = await self.calculate_platform_stats()
        self.platform_cache = stats
        return {**stats, 'stale': False, 'cache': False}

    async def _refresh_platform_stats(self):
        if self.platform_refreshing:
            return
        self.platform_refreshing = True
        try:
            stats = await self.calculate_platform_stats()
            self.platform_cache = stats
        except Exception as e:
            logger.error(f"Background refresh platform stats failed: {e}")
        finally:
            self.platform_refreshing = False

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
    
    async def broadcast_stats_delta(self, scope: str, changes: Dict[str, Any], project_id: Optional[str] = None, event_type: str = 'delta'):
        try:
            msg = {
                'type': f'{scope}_stats_delta',
                'scope': scope,
                'project_id': project_id,
                'changes': changes,
                'event_type': event_type,
                'timestamp': datetime.now().isoformat()
            }
            wm = self._get_websocket_manager()
            if scope == 'platform':
                await wm.broadcast_to_dashboard(msg)
            elif scope == 'project' and project_id:
                await wm.broadcast_to_project(project_id, msg)
        except Exception as e:
            logger.warning(f"Failed broadcasting stats delta: {e}")

    @contextmanager
    def _timed(self, label: str, timings: dict):
        start = time.perf_counter()
        try:
            yield
        finally:
            dur = (time.perf_counter() - start) * 1000.0
            timings[label] = round(dur, 2)

    async def calculate_project_stats(self, project_id: str) -> Dict[str, Any]:
        """Calculate comprehensive project statistics with fallback mechanisms (instrumented)."""
        timings = {}
        total_start = time.perf_counter()
        try:
            # Import project service client directly to avoid circular imports
            from app.core.project_service import ProjectServiceClient
            from app.core.rag_service import RAGService  # noqa: F401 (kept for future deeper stats)
            from app.core.graph_service import GraphService

            stats = {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "last_updated": datetime.now().isoformat()
            }

            # Fallback: Check local file system for file count
            with self._timed("filesystem_scan_ms", timings):
                try:
                    project_dir = os.path.join(os.getenv("UPLOAD_ROOT", "./uploads"), f"project_{project_id}")
                    if os.path.exists(project_dir):
                        files = [f for f in os.listdir(project_dir)
                                if os.path.isfile(os.path.join(project_dir, f))
                                and not f.endswith('.json')
                                and os.path.getsize(os.path.join(project_dir, f)) > 0]
                        stats["files_count"] = len(files)
                except Exception as e:
                    logger.warning(f"Fallback file count failed: {e}")
            
            # Get project files count
            with self._timed("project_service_files_ms", timings):
                try:
                    project_service = ProjectServiceClient()
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
            
            # Get embeddings count from ChromaDB directly (without loading models)
            with self._timed("chroma_count_ms", timings):
                try:
                    import chromadb
                    chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
                    chroma_client = chromadb.PersistentClient(path=chroma_path)
                    collection_name = f"project_{project_id}"
                    try:
                        collection = chroma_client.get_collection(name=collection_name)
                        stats["embeddings_count"] = collection.count()
                    except Exception:
                        stats["embeddings_count"] = 0  # Collection doesn't exist
                except Exception as e:
                    logger.warning(f"Error getting embeddings count: {e}")
            
            # Get graph statistics from Neo4j
            with self._timed("neo4j_counts_ms", timings):
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
            
            total_dur = (time.perf_counter() - total_start) * 1000.0
            timings["total_compute_ms"] = round(total_dur, 2)
            stats["timings"] = timings
            logger.info(f"Calculated project {project_id} stats timings={timings}")
            return stats
            
        except Exception as e:
            total_dur = (time.perf_counter() - total_start) * 1000.0
            timings["total_compute_ms"] = round(total_dur, 2)
            logger.error(f"Error calculating project stats: {e}")
            return {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e),
                "timings": timings
            }
    
    async def calculate_platform_stats(self) -> Dict[str, Any]:
        """Calculate comprehensive platform statistics (instrumented)."""
        timings = {}
        total_start = time.perf_counter()
        try:
            with self._timed("platform_compute_ms", timings):
                from app.core.platform_stats import get_platform_stats
                loop = asyncio.get_event_loop()
                stats = await loop.run_in_executor(None, get_platform_stats)
            stats["last_updated"] = datetime.now().isoformat()
            timings["total_compute_ms"] = timings.get("platform_compute_ms", round((time.perf_counter() - total_start) * 1000.0, 2))
            stats["timings"] = timings
            logger.info(f"Calculated platform stats timings={timings}")
            return stats
        except Exception as e:
            timings["total_compute_ms"] = round((time.perf_counter() - total_start) * 1000.0, 2)
            logger.error(f"Error calculating platform stats: {e}")
            return {
                "total_projects": 0,
                "total_documents": 0,
                "total_embeddings": 0,
                "total_neo4j_nodes": 0,
                "total_neo4j_relationships": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e),
                "timings": timings
            }

    def register_event_handlers(self):
        bus = get_event_bus()
        bus.subscribe("project_created", self._on_project_created)
        bus.subscribe("project_deleted", self._on_project_deleted)
        bus.subscribe("document_uploaded", self._on_document_uploaded)
        bus.subscribe("document_deleted", self._on_document_deleted)
        bus.subscribe("embeddings_added", self._on_embeddings_added)

    def _on_project_created(self, payload: dict):
        # Invalidate platform cache
        self.platform_cache = None
        asyncio.create_task(self.broadcast_stats_delta('platform', {'total_projects': '++'}, event_type='project_created'))
    def _on_project_deleted(self, payload: dict):
        pid = payload.get('project_id')
        if pid in self.project_cache:
            del self.project_cache[pid]
        self.platform_cache = None
        asyncio.create_task(self.broadcast_stats_delta('platform', {'total_projects': '--'}, event_type='project_deleted'))
    def _on_document_uploaded(self, payload: dict):
        pid = payload.get('project_id')
        if not pid:
            return
        entry = self.project_cache.get(pid)
        if entry:
            entry['files_count'] = (entry.get('files_count') or 0) + 1
            entry['last_updated'] = datetime.now().isoformat()
            asyncio.create_task(self.broadcast_stats_delta('project', {'files_count': entry['files_count']}, project_id=pid, event_type='document_uploaded'))
        self.platform_cache = None
        asyncio.create_task(self.broadcast_stats_delta('platform', {'total_documents': '++'}, event_type='document_uploaded'))
    def _on_document_deleted(self, payload: dict):
        pid = payload.get('project_id')
        entry = self.project_cache.get(pid)
        if entry and (entry.get('files_count') or 0) > 0:
            entry['files_count'] -= 1
            entry['last_updated'] = datetime.now().isoformat()
            asyncio.create_task(self.broadcast_stats_delta('project', {'files_count': entry['files_count']}, project_id=pid, event_type='document_deleted'))
        self.platform_cache = None
        asyncio.create_task(self.broadcast_stats_delta('platform', {'total_documents': '--'}, event_type='document_deleted'))
    def _on_embeddings_added(self, payload: dict):
        pid = payload.get('project_id')
        added = payload.get('count', 0) or 0
        entry = self.project_cache.get(pid)
        if entry:
            entry['embeddings_count'] = (entry.get('embeddings_count') or 0) + added
            entry['last_updated'] = datetime.now().isoformat()
            asyncio.create_task(self.broadcast_stats_delta('project', {'embeddings_count': entry['embeddings_count']}, project_id=pid, event_type='embeddings_added'))
        self.platform_cache = None
        asyncio.create_task(self.broadcast_stats_delta('platform', {'total_embeddings': f'+{added}'}, event_type='embeddings_added'))


# Global instance
_stats_service = None


def get_stats_service() -> StatsService:
    """Get the global stats service instance"""
    global _stats_service
    if _stats_service is None:
        _stats_service = StatsService()
    return _stats_service
