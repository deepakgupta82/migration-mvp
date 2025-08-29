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
import tempfile, json

logger = logging.getLogger(__name__)


class StatsService:
    """Centralized service for managing and broadcasting statistics"""
    
    def __init__(self):
        self.websocket_manager = None
        logger.info("Stats Service initialized")
        # Cache structures
        self.project_cache: Dict[str, Dict[str, Any]] = {}
        self.platform_cache: Optional[Dict[str, Any]] = None
        # Make TTLs configurable to control recompute frequency
        # Default to 15 minutes (900 seconds) for project stats as per requirements
        self.project_ttl_seconds = int(os.getenv("STATS_PROJECT_TTL_SECONDS", "900"))
        self.platform_ttl_seconds = int(os.getenv("STATS_PLATFORM_TTL_SECONDS", "600"))
        self.refresh_in_progress: Dict[str, bool] = {}
        self.platform_refreshing = False
        self.dirty_projects: set[str] = set()  # phase 6 persistence tracking
        self.persistence_enabled = False  # flip true when DB migration applied
        # Snapshot storage for cold-start fast responses
        self.snapshot_dir = os.path.join(tempfile.gettempdir(), "ascent_stats")
        os.makedirs(self.snapshot_dir, exist_ok=True)
        # Throttle noisy timing logs per project (15 minutes = 900 seconds)
        self.timing_log_min_interval = float(os.getenv("STATS_TIMING_LOG_MIN_INTERVAL_SEC", "900"))
        self._last_timing_log: Dict[str, float] = {}

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
        # No cache: try snapshot for instant response, then refresh in background
        snap_path = os.path.join(self.snapshot_dir, f"project_{project_id}.json")
        try:
            if os.path.exists(snap_path):
                with open(snap_path, 'r', encoding='utf-8') as f:
                    snap = json.load(f)
                if isinstance(snap, dict):
                    self.project_cache[project_id] = snap
                    if not self.refresh_in_progress.get(project_id):
                        asyncio.create_task(self._refresh_project_stats(project_id))
                    return {**snap, "stale": True, "cache": True}
        except Exception:
            pass
        # Fallback: compute synchronously once
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
        """Update project stats with event-driven incremental updates (enhanced for real-time performance)."""
        try:
            logger.info(f"Updating project {project_id} stats due to event: {event_type}")
            
            # Get current cached stats or initialize
            current_stats = self.project_cache.get(project_id, {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "last_updated": datetime.now().isoformat()
            })
            
            # Apply incremental updates based on event type (event-driven approach)
            updated_stats = current_stats.copy()
            stats_changed = False
            
            if event_type == "documents_processed":
                # Increment file count and trigger microservice stats refresh
                files_processed = additional_data.get("files_processed", 0) if additional_data else 0
                if files_processed > 0:
                    updated_stats["files_count"] = max(0, updated_stats.get("files_count", 0) + files_processed)
                    stats_changed = True
                # Schedule async refresh of embeddings and graph counts from microservices
                asyncio.create_task(self._refresh_microservice_counts(project_id))
                
            elif event_type == "document_uploaded":
                # Increment file count immediately
                uploaded_count = additional_data.get("uploaded_count", 1) if additional_data else 1
                updated_stats["files_count"] = updated_stats.get("files_count", 0) + uploaded_count
                stats_changed = True
                
            elif event_type == "document_deleted":
                # Decrement file count
                deleted_count = additional_data.get("deleted_count", 1) if additional_data else 1
                updated_stats["files_count"] = max(0, updated_stats.get("files_count", 0) - deleted_count)
                stats_changed = True
                
            elif event_type == "embeddings_added":
                # Update embeddings count from vector service
                embeddings_count = additional_data.get("embeddings_count", 0) if additional_data else 0
                if embeddings_count > 0:
                    updated_stats["embeddings_count"] = embeddings_count
                    stats_changed = True
                    
            elif event_type == "graph_updated":
                # Update graph counts from graph service
                if additional_data:
                    if "nodes" in additional_data:
                        updated_stats["graph_nodes"] = additional_data["nodes"]
                        stats_changed = True
                    if "relationships" in additional_data:
                        updated_stats["graph_relationships"] = additional_data["relationships"]
                        stats_changed = True
                        
            elif event_type in ["data_cleared", "project_deleted"]:
                # Reset all counts
                updated_stats.update({
                    "files_count": 0,
                    "embeddings_count": 0,
                    "graph_nodes": 0,
                    "graph_relationships": 0
                })
                stats_changed = True
            
            # Update cache and timestamp if changes occurred
            if stats_changed:
                updated_stats["last_updated"] = datetime.now().isoformat()
                self.project_cache[project_id] = updated_stats
                
                # Persist snapshot for cold-starts
                try:
                    snap_path = os.path.join(self.snapshot_dir, f"project_{project_id}.json")
                    with open(snap_path, 'w', encoding='utf-8') as f:
                        json.dump(updated_stats, f)
                except Exception:
                    pass  # Don't fail on snapshot write
            
            # Publish event to Redis pub/sub for stats-service
            await self._publish_stats_event_to_redis(project_id, event_type, additional_data)
            
            # Prepare and broadcast real-time update
            message = {
                "type": "project_stats_update",
                "project_id": project_id,
                "event_type": event_type,
                "data": updated_stats,
                "timestamp": datetime.now().isoformat(),
                "additional_data": additional_data or {},
                "incremental_update": True
            }
            websocket_manager = self._get_websocket_manager()
            await websocket_manager.broadcast_to_project(project_id, message)
            
            # Schedule platform recompute in background if this affects platform totals
            platform_affecting_events = [
                "document_uploaded", "document_deleted", "documents_processed", 
                "data_cleared", "project_created", "project_deleted", "embeddings_added"
            ]
            if event_type in platform_affecting_events and not self.platform_refreshing:
                asyncio.create_task(self._refresh_platform_stats())
                
            logger.info(f"Applied incremental update and sent real-time delta for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error updating project stats: {e}")
    
    async def _publish_stats_event_to_redis(self, project_id: str, event_type: str, additional_data: Optional[Dict] = None):
        """Publish stats events to Redis pub/sub channels for stats-service consumption"""
        try:
            import redis.asyncio as redis
            
            # Get Redis connection (reuse existing connection if available)
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = redis.from_url(redis_url)
            
            # Map event types to Redis channels
            channel_mapping = {
                "documents_processed": "platform.document.processed",
                "document_uploaded": "platform.document.processed", 
                "document_deleted": "platform.document.processed",
                "embeddings_added": "platform.embeddings.updated",
                "graph_updated": "platform.graph.updated",
                "data_cleared": "platform.project.deleted",
                "project_created": "platform.project.created",
                "project_deleted": "platform.project.deleted"
            }
            
            channel = channel_mapping.get(event_type)
            if not channel:
                logger.debug(f"No Redis channel mapping for event type: {event_type}")
                return
            
            # Prepare event data for stats-service
            event_data = {
                "project_id": project_id,
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "additional_data": additional_data or {}
            }
            
            # Add specific data based on event type
            if event_type in ["documents_processed", "document_uploaded"]:
                event_data["document"] = {
                    "project_id": project_id,
                    "processing_time_ms": additional_data.get("processing_time_ms", 0) if additional_data else 0
                }
            elif event_type == "embeddings_added":
                event_data["embeddings"] = {
                    "project_id": project_id,
                    "count": additional_data.get("embeddings_count", 0) if additional_data else 0
                }
            elif event_type == "graph_updated":
                event_data["graph"] = {
                    "project_id": project_id,
                    "nodes": additional_data.get("nodes", 0) if additional_data else 0,
                    "relationships": additional_data.get("relationships", 0) if additional_data else 0
                }
            
            # Publish to Redis channel
            await redis_client.publish(channel, json.dumps(event_data))
            logger.debug(f"Published stats event to Redis channel {channel}: {event_data}")
            
            # Close Redis connection
            await redis_client.close()
            
        except Exception as e:
            logger.error(f"Failed to publish stats event to Redis: {e}")
            # Don't fail the whole operation if Redis publishing fails
    
    async def _refresh_microservice_counts(self, project_id: str):
        """Asynchronously refresh embeddings and graph counts from microservices (non-blocking)."""
        try:
            from app.core.project_service import ProjectServiceClient
            project_service = ProjectServiceClient()
            
            # Get updated counts from microservices
            embeddings_count = 0
            graph_nodes = 0
            graph_relationships = 0
            
            # Vector service embeddings count
            try:
                count = project_service.get_vector_count(project_id)
                if isinstance(count, int):
                    embeddings_count = count
            except Exception as e:
                logger.debug(f"Vector count refresh failed for {project_id}: {e}")
            
            # Graph service counts
            try:
                counts = project_service.get_graph_counts(project_id)
                if isinstance(counts, dict):
                    graph_nodes = int(counts.get("nodes", 0) or 0)
                    graph_relationships = int(counts.get("relationships", 0) or 0)
            except Exception as e:
                logger.debug(f"Graph counts refresh failed for {project_id}: {e}")
            
            # Update cache with refreshed microservice data
            if project_id in self.project_cache:
                self.project_cache[project_id].update({
                    "embeddings_count": embeddings_count,
                    "graph_nodes": graph_nodes,
                    "graph_relationships": graph_relationships,
                    "last_updated": datetime.now().isoformat()
                })
                
                # Broadcast updated microservice counts
                message = {
                    "type": "project_stats_update",
                    "project_id": project_id,
                    "event_type": "microservice_counts_refreshed",
                    "data": self.project_cache[project_id],
                    "timestamp": datetime.now().isoformat(),
                    "incremental_update": True
                }
                websocket_manager = self._get_websocket_manager()
                await websocket_manager.broadcast_to_project(project_id, message)
                
        except Exception as e:
            logger.error(f"Microservice counts refresh failed for {project_id}: {e}")
    
    async def update_platform_stats(self, event_type: str, additional_data: Optional[Dict] = None):
        """Update platform-wide stats and broadcast (non-blocking)."""
        try:
            logger.info(f"Updating platform stats due to event: {event_type}")
            # Schedule background recompute
            if not self.platform_refreshing:
                asyncio.create_task(self._refresh_platform_stats())
            # Broadcast current cache immediately as a delta
            message = {
                "type": "platform_stats_update",
                "event_type": event_type,
                "data": self.platform_cache or {},
                "timestamp": datetime.now().isoformat(),
                "additional_data": additional_data or {}
            }
            websocket_manager = self._get_websocket_manager()
            await websocket_manager.broadcast_to_dashboard(message)
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

            stats = {
                "project_id": project_id,
                "files_count": 0,
                "embeddings_count": 0,
                "graph_nodes": 0,
                "graph_relationships": 0,
                "agent_interactions": 0,
                "deliverables": 0,
                "last_updated": datetime.now().isoformat()
            }

            # Prefer object storage for files count when available
            with self._timed("object_storage_ms", timings):
                try:
                    from app.core.storage_service import get_storage
                    storage = get_storage()
                    stats["files_count"] = len(storage.list_files(project_id, "uploads_raw"))
                except Exception as e:
                    logger.debug(f"Object storage file count unavailable: {e}")
            
            # Fallback: Check local file system for file count
            if stats.get("files_count", 0) == 0:
                with self._timed("filesystem_scan_ms", timings):
                    try:
                        upload_root = os.getenv("UPLOAD_ROOT_TMP") or tempfile.gettempdir()
                        project_dir = os.path.join(upload_root, f"project_{project_id}")
                        if os.path.exists(project_dir):
                            files = [f for f in os.listdir(project_dir)
                                    if os.path.isfile(os.path.join(project_dir, f))
                                    and not f.endswith('.json')
                                    and os.path.getsize(os.path.join(project_dir, f)) > 0]
                            stats["files_count"] = len(files)
                    except Exception as e:
                        logger.warning(f"Fallback file count failed: {e}")
            
            # Get project files count via lightweight endpoint (optional)
            with self._timed("project_service_files_ms", timings):
                try:
                    use_remote = os.getenv("STATS_USE_PROJECT_SERVICE", "false").lower() in ("1","true","yes")
                    if use_remote or stats.get("files_count", 0) == 0:
                        project_service = ProjectServiceClient()
                        timeout_s = float(os.getenv("STATS_PROJECT_FILES_TIMEOUT", "0.7"))
                        stats["files_count"] = project_service.get_project_file_count(project_id, timeout=timeout_s)
                except Exception as e:
                    logger.warning(f"Error getting project files count: {e}")
            
            # Get embeddings count via vector-service endpoint (Weaviate-backed)
            with self._timed("embeddings_count_ms", timings):
                try:
                    project_service = ProjectServiceClient()
                    count = project_service.get_vector_count(project_id)
                    if isinstance(count, int):
                        stats["embeddings_count"] = count
                    else:
                        stats["embeddings_count"] = 0
                        logger.warning(f"Invalid vector count response for project {project_id}")
                except Exception as e:
                    logger.warning(f"Vector service count unavailable for project {project_id}: {e}")
                    stats["embeddings_count"] = 0
            
            # Get graph statistics via graph-service when available; skip local neo4j imports
            with self._timed("graph_counts_ms", timings):
                try:
                    project_service = ProjectServiceClient()
                    counts = project_service.get_graph_counts(project_id)
                    if isinstance(counts, dict):
                        stats["graph_nodes"] = int(counts.get("nodes", 0) or 0)
                        stats["graph_relationships"] = int(counts.get("relationships", 0) or 0)
                except Exception as e:
                    logger.debug(f"Graph counts via service unavailable: {e}")
            
            # Get agent interactions and deliverables count via project analysis endpoint
            with self._timed("analysis_stats_ms", timings):
                try:
                    import requests
                    timeout_s = float(os.getenv("STATS_ANALYSIS_TIMEOUT", "1.0"))
                    response = requests.get(
                        f"http://localhost:8000/api/projects/{project_id}/stats",
                        timeout=timeout_s
                    )
                    if response.ok:
                        analysis_data = response.json()
                        stats["agent_interactions"] = int(analysis_data.get("agent_interactions", 0) or 0)
                        stats["deliverables"] = int(analysis_data.get("deliverables", 0) or 0)
                except Exception as e:
                    logger.debug(f"Analysis stats unavailable for project {project_id}: {e}")
            
            total_dur = (time.perf_counter() - total_start) * 1000.0
            timings["total_compute_ms"] = round(total_dur, 2)
            stats["timings"] = timings
            # Throttled logging of timing line
            now_ts = time.time()
            last_ts = self._last_timing_log.get(project_id, 0)
            if (now_ts - last_ts) >= self.timing_log_min_interval:
                logger.info(f"Calculated project {project_id} stats timings={timings}")
                self._last_timing_log[project_id] = now_ts
            else:
                logger.debug(f"Calculated project {project_id} stats timings={timings}")

            # Persist snapshot for cold-starts
            try:
                snap_path = os.path.join(self.snapshot_dir, f"project_{project_id}.json")
                with open(snap_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f)
            except Exception as e:
                logger.debug(f"Failed to write stats snapshot for {project_id}: {e}")

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
                "agent_interactions": 0,
                "deliverables": 0,
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
                # Defensive: ensure dict to avoid NoneType issues
                if not isinstance(stats, dict):
                    logger.warning("get_platform_stats returned non-dict/None; defaulting to empty stats")
                    stats = {}
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
