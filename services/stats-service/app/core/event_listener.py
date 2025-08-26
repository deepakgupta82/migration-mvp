"""
Event Listener - Listens for platform events and updates statistics
Handles Redis pub/sub and HTTP webhooks for real-time updates
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
from .stats_processor import StatsProcessor

logger = logging.getLogger("event-listener")

class EventListener:
    """Listens for platform events and triggers stats updates"""
    
    def __init__(self, stats_processor: StatsProcessor):
        self.stats_processor = stats_processor
        self.redis = stats_processor.redis
        self.is_listening = False
        self.subscriptions = []
        
        # Event channel mappings
        self.event_channels = [
            "platform.document.processed",
            "platform.embeddings.updated", 
            "platform.graph.updated",
            "platform.assessment.status_changed",
            "platform.project.created",
            "platform.project.deleted",
            "platform.service.health_check"
        ]
        
    async def start_listening(self):
        """Start listening for events on all channels"""
        if self.is_listening:
            logger.warning("Event listener is already running")
            return
            
        self.is_listening = True
        logger.info("Starting event listener for platform events")
        
        try:
            # Subscribe to Redis pub/sub channels
            pubsub = self.redis.pubsub()
            
            # Subscribe to all event channels
            for channel in self.event_channels:
                await pubsub.subscribe(channel)
                logger.info(f"Subscribed to event channel: {channel}")
            
            # Start listening loop
            await self._listen_loop(pubsub)
            
        except Exception as e:
            logger.error(f"Failed to start event listener: {e}")
            self.is_listening = False
            
    async def _listen_loop(self, pubsub):
        """Main event listening loop"""
        logger.info("Event listener started successfully")
        
        try:
            async for message in pubsub.listen():
                if not self.is_listening:
                    break
                    
                try:
                    # Skip subscription confirmation messages
                    if message["type"] != "message":
                        continue
                        
                    channel = message["channel"].decode()
                    data = message["data"]
                    
                    # Parse event data
                    if isinstance(data, bytes):
                        event_data = json.loads(data.decode())
                    else:
                        event_data = data
                        
                    await self._handle_event(channel, event_data)
                    
                except Exception as e:
                    logger.error(f"Error processing event message: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Event listening loop failed: {e}")
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
            logger.info("Event listener stopped")
            
    async def _handle_event(self, channel: str, event_data: Dict[str, Any]):
        """Route events to appropriate handlers"""
        try:
            logger.debug(f"Received event on channel {channel}: {event_data}")
            
            if channel == "platform.document.processed":
                await self._handle_document_processed(event_data)
                
            elif channel == "platform.embeddings.updated":
                await self._handle_embeddings_updated(event_data)
                
            elif channel == "platform.graph.updated":
                await self._handle_graph_updated(event_data)
                
            elif channel == "platform.assessment.status_changed":
                await self._handle_assessment_status_changed(event_data)
                
            elif channel == "platform.project.created":
                await self._handle_project_created(event_data)
                
            elif channel == "platform.project.deleted":
                await self._handle_project_deleted(event_data)
                
            elif channel == "platform.service.health_check":
                await self._handle_service_health_check(event_data)
                
            else:
                logger.warning(f"Unknown event channel: {channel}")
                
        except Exception as e:
            logger.error(f"Failed to handle event {channel}: {e}")
            
    # =================================================================================
    # Event handlers
    # =================================================================================
    
    async def _handle_document_processed(self, event_data: Dict[str, Any]):
        """Handle document processing completion event"""
        try:
            project_id = event_data.get("project_id")
            document_info = event_data.get("document", {})
            
            if not project_id:
                logger.warning("Document processed event missing project_id")
                return
                
            await self.stats_processor.handle_document_processed(project_id, document_info)
            logger.info(f"Handled document processed event for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error handling document processed event: {e}")
            
    async def _handle_embeddings_updated(self, event_data: Dict[str, Any]):
        """Handle embeddings update event"""
        try:
            project_id = event_data.get("project_id")
            embeddings_info = event_data.get("embeddings", {})
            
            if not project_id:
                logger.warning("Embeddings updated event missing project_id")
                return
                
            await self.stats_processor.handle_embeddings_updated(project_id, embeddings_info)
            logger.info(f"Handled embeddings updated event for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error handling embeddings updated event: {e}")
            
    async def _handle_graph_updated(self, event_data: Dict[str, Any]):
        """Handle graph update event"""
        try:
            project_id = event_data.get("project_id")
            graph_info = event_data.get("graph", {})
            
            if not project_id:
                logger.warning("Graph updated event missing project_id")
                return
                
            await self.stats_processor.handle_graph_updated(project_id, graph_info)
            logger.info(f"Handled graph updated event for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error handling graph updated event: {e}")
            
    async def _handle_assessment_status_changed(self, event_data: Dict[str, Any]):
        """Handle assessment status change event"""
        try:
            project_id = event_data.get("project_id")
            status = event_data.get("status")
            
            if not project_id or not status:
                logger.warning("Assessment status changed event missing project_id or status")
                return
                
            await self.stats_processor.handle_assessment_status_changed(project_id, status)
            logger.info(f"Handled assessment status change for project {project_id}: {status}")
            
        except Exception as e:
            logger.error(f"Error handling assessment status change event: {e}")
            
    async def _handle_project_created(self, event_data: Dict[str, Any]):
        """Handle project creation event"""
        try:
            project_id = event_data.get("project_id")
            project_info = event_data.get("project", {})
            
            if not project_id:
                logger.warning("Project created event missing project_id")
                return
                
            # Initialize project stats
            await self.stats_processor._initialize_project_stats(project_id, project_info)
            
            # Update platform project count
            await self.stats_processor.update_platform_metric("total_projects", 1, delta=True)
            
            logger.info(f"Handled project created event: {project_id}")
            
        except Exception as e:
            logger.error(f"Error handling project created event: {e}")
            
    async def _handle_project_deleted(self, event_data: Dict[str, Any]):
        """Handle project deletion event"""
        try:
            project_id = event_data.get("project_id")
            
            if not project_id:
                logger.warning("Project deleted event missing project_id")
                return
                
            # Remove project stats from cache
            cache_key = f"project_stats:{project_id}"
            await self.redis.delete(cache_key)
            
            # Update platform project count
            await self.stats_processor.update_platform_metric("total_projects", -1, delta=True)
            
            logger.info(f"Handled project deleted event: {project_id}")
            
        except Exception as e:
            logger.error(f"Error handling project deleted event: {e}")
            
    async def _handle_service_health_check(self, event_data: Dict[str, Any]):
        """Handle service health check event"""
        try:
            service_name = event_data.get("service_name")
            status = event_data.get("status", "unknown")
            
            if not service_name:
                logger.warning("Service health check event missing service_name")
                return
                
            await self.stats_processor.update_service_health(service_name, status)
            logger.debug(f"Updated service health: {service_name} = {status}")
            
        except Exception as e:
            logger.error(f"Error handling service health check event: {e}")
            
    # =================================================================================
    # Control methods
    # =================================================================================
    
    async def stop(self):
        """Stop the event listener"""
        logger.info("Stopping event listener")
        self.is_listening = False
        
    async def publish_event(self, channel: str, event_data: Dict[str, Any]):
        """Publish an event to a channel (for testing or manual triggers)"""
        try:
            await self.redis.publish(channel, json.dumps(event_data))
            logger.debug(f"Published event to {channel}: {event_data}")
        except Exception as e:
            logger.error(f"Failed to publish event to {channel}: {e}")
            
    def is_running(self) -> bool:
        """Check if the event listener is running"""
        return self.is_listening
