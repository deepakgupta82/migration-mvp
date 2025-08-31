import os
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger("document-service.progress-tracker")

class ProgressTracker:
    """
    Tracks document processing progress and broadcasts real-time updates
    via WebSocket service for UI synchronization
    """
    
    def __init__(self):
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        self.auth_token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')
        self.http_timeout = httpx.Timeout(5.0, connect=2.0)
        
        # In-memory tracking for active operations
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Progress Tracker initialized")
    
    async def start_operation(
        self,
        project_id: str,
        correlation_id: str,
        operation_name: str,
        total_steps: int
    ) -> str:
        """
        Start tracking a new operation
        """
        event_id = str(uuid.uuid4())
        
        operation_data = {
            "event_id": event_id,
            "project_id": project_id,
            "correlation_id": correlation_id,
            "operation_name": operation_name,
            "total_steps": total_steps,
            "current_step": 0,
            "status": "started",
            "start_time": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "progress_messages": [],
            "completed": False,
            "success": None,
            "error_message": None
        }
        
        self.active_operations[event_id] = operation_data
        
        # Send initial WebSocket notification
        await self._send_websocket_notification(
            project_id, correlation_id, "operation_started",
            {
                "event_id": event_id,
                "operation_name": operation_name,
                "total_steps": total_steps,
                "current_step": 0,
                "progress_percentage": 0.0
            }
        )
        
        logger.info(f"Started tracking operation: {operation_name} [event_id={event_id}]")
        return event_id
    
    async def update_operation_progress(
        self,
        event_id: str,
        message: str,
        step_number: int,
        sub_step: Optional[str] = None,
        sub_step_progress: Optional[float] = None
    ):
        """
        Update progress for an active operation with optional sub-step tracking
        """
        if event_id not in self.active_operations:
            logger.warning(f"Attempted to update unknown operation: {event_id}")
            return

        operation = self.active_operations[event_id]

        if operation["completed"]:
            logger.warning(f"Attempted to update completed operation: {event_id}")
            return

        # Update operation data
        operation["current_step"] = step_number
        operation["last_update"] = datetime.now().isoformat()

        # Add sub-step information if provided
        progress_entry = {
            "step": step_number,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        if sub_step:
            progress_entry["sub_step"] = sub_step
        if sub_step_progress is not None:
            progress_entry["sub_step_progress"] = sub_step_progress

        operation["progress_messages"].append(progress_entry)

        # Calculate progress percentage
        progress_percentage = min(100.0, (step_number / operation["total_steps"]) * 100)

        # Adjust percentage if sub-step progress is provided
        if sub_step_progress is not None and step_number < operation["total_steps"]:
            # Interpolate between current step and next step based on sub-step progress
            step_progress = (step_number / operation["total_steps"]) * 100
            next_step_progress = ((step_number + 1) / operation["total_steps"]) * 100
            progress_percentage = step_progress + (sub_step_progress / 100) * (next_step_progress - step_progress)

        # Send WebSocket notification
        notification_data = {
            "event_id": event_id,
            "operation_name": operation["operation_name"],
            "current_step": step_number,
            "total_steps": operation["total_steps"],
            "progress_percentage": round(progress_percentage, 1),
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

        if sub_step:
            notification_data["sub_step"] = sub_step
        if sub_step_progress is not None:
            notification_data["sub_step_progress"] = sub_step_progress

        await self._send_websocket_notification(
            operation["project_id"],
            operation["correlation_id"],
            "operation_progress",
            notification_data
        )

        logger.debug(f"Updated progress for {event_id}: Step {step_number}/{operation['total_steps']} - {message}")
        if sub_step:
            logger.debug(f"Sub-step: {sub_step} ({sub_step_progress}%)")
    
    async def complete_operation(
        self,
        event_id: str,
        success: bool,
        error_message: Optional[str] = None
    ):
        """
        Mark an operation as completed
        """
        if event_id not in self.active_operations:
            logger.warning(f"Attempted to complete unknown operation: {event_id}")
            return
        
        operation = self.active_operations[event_id]
        
        if operation["completed"]:
            logger.warning(f"Attempted to complete already completed operation: {event_id}")
            return
        
        # Update operation data
        operation["completed"] = True
        operation["success"] = success
        operation["error_message"] = error_message
        operation["completion_time"] = datetime.now().isoformat()
        
        # Calculate final progress percentage
        final_percentage = 100.0 if success else 0.0
        
        # Send completion WebSocket notification
        event_type = "operation_completed" if success else "operation_failed"
        
        notification_data = {
            "event_id": event_id,
            "operation_name": operation["operation_name"],
            "total_steps": operation["total_steps"],
            "final_step": operation["current_step"],
            "progress_percentage": final_percentage,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        if error_message:
            notification_data["error_message"] = error_message
        
        await self._send_websocket_notification(
            operation["project_id"],
            operation["correlation_id"],
            event_type,
            notification_data
        )
        
        # Clean up from active operations after a delay
        async def cleanup_operation():
            await asyncio.sleep(300)  # Keep for 5 minutes for debugging
            if event_id in self.active_operations:
                del self.active_operations[event_id]
                logger.debug(f"Cleaned up completed operation: {event_id}")
        
        # Schedule cleanup
        asyncio.create_task(cleanup_operation())
        
        status_msg = "successfully" if success else f"with error: {error_message}"
        logger.info(f"Completed operation {event_id}: {operation['operation_name']} {status_msg}")
    
    async def get_operation_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an operation
        """
        return self.active_operations.get(event_id)
    
    async def start_sub_operation(
        self,
        parent_event_id: str,
        sub_operation_name: str,
        sub_steps: int
    ) -> Optional[str]:
        """
        Start a sub-operation within a parent operation
        """
        if parent_event_id not in self.active_operations:
            logger.warning(f"Attempted to start sub-operation for unknown parent: {parent_event_id}")
            return None

        parent_operation = self.active_operations[parent_event_id]
        sub_event_id = f"{parent_event_id}_sub_{len(parent_operation.get('sub_operations', []))}"

        sub_operation = {
            "sub_event_id": sub_event_id,
            "parent_event_id": parent_event_id,
            "sub_operation_name": sub_operation_name,
            "sub_steps": sub_steps,
            "current_sub_step": 0,
            "status": "started",
            "start_time": datetime.now().isoformat(),
            "progress_messages": []
        }

        if "sub_operations" not in parent_operation:
            parent_operation["sub_operations"] = []
        parent_operation["sub_operations"].append(sub_operation)

        # Send sub-operation start notification
        await self._send_websocket_notification(
            parent_operation["project_id"],
            parent_operation["correlation_id"],
            "sub_operation_started",
            {
                "parent_event_id": parent_event_id,
                "sub_event_id": sub_event_id,
                "sub_operation_name": sub_operation_name,
                "sub_steps": sub_steps,
                "timestamp": datetime.now().isoformat()
            }
        )

        logger.info(f"Started sub-operation: {sub_operation_name} [sub_event_id={sub_event_id}]")
        return sub_event_id

    async def update_sub_operation_progress(
        self,
        sub_event_id: str,
        message: str,
        sub_step_number: int
    ):
        """
        Update progress for a sub-operation
        """
        # Find the parent operation containing this sub-operation
        parent_operation = None
        for op in self.active_operations.values():
            if "sub_operations" in op:
                for sub_op in op["sub_operations"]:
                    if sub_op["sub_event_id"] == sub_event_id:
                        parent_operation = op
                        break
                if parent_operation:
                    break

        if not parent_operation:
            logger.warning(f"Attempted to update unknown sub-operation: {sub_event_id}")
            return

        # Find the specific sub-operation
        sub_operation = None
        for sub_op in parent_operation["sub_operations"]:
            if sub_op["sub_event_id"] == sub_event_id:
                sub_operation = sub_op
                break

        if not sub_operation:
            logger.warning(f"Sub-operation not found: {sub_event_id}")
            return

        # Update sub-operation data
        sub_operation["current_sub_step"] = sub_step_number
        sub_operation["progress_messages"].append({
            "sub_step": sub_step_number,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

        # Calculate sub-operation progress percentage
        sub_progress_percentage = min(100.0, (sub_step_number / sub_operation["sub_steps"]) * 100)

        # Send sub-operation progress notification
        await self._send_websocket_notification(
            parent_operation["project_id"],
            parent_operation["correlation_id"],
            "sub_operation_progress",
            {
                "parent_event_id": parent_operation["event_id"],
                "sub_event_id": sub_event_id,
                "sub_operation_name": sub_operation["sub_operation_name"],
                "current_sub_step": sub_step_number,
                "total_sub_steps": sub_operation["sub_steps"],
                "sub_progress_percentage": round(sub_progress_percentage, 1),
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        )

        logger.debug(f"Updated sub-operation progress for {sub_event_id}: Sub-step {sub_step_number}/{sub_operation['sub_steps']} - {message}")

    async def list_active_operations(self, project_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        List all active operations, optionally filtered by project
        """
        if project_id:
            return {
                event_id: op
                for event_id, op in self.active_operations.items()
                if op["project_id"] == project_id and not op["completed"]
            }
        else:
            return {
                event_id: op
                for event_id, op in self.active_operations.items()
                if not op["completed"]
            }
    
    async def _send_websocket_notification(
        self,
        project_id: str,
        correlation_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Send progress update via WebSocket service
        """
        if not self.websocket_url:
            logger.debug("WebSocket URL not configured, skipping notification")
            return
        
        try:
            payload = {
                "project_id": project_id,
                "correlation_id": correlation_id,
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.post(
                    f"{self.websocket_url}/api/websocket/broadcast",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.debug(f"WebSocket notification sent: {event_type}")
                else:
                    logger.warning(f"WebSocket notification failed: {response.status_code} - {response.text[:200]}")
        
        except Exception as e:
            logger.debug(f"WebSocket notification error (non-critical): {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get progress tracker statistics"""
        total_operations = len(self.active_operations)
        active_operations = sum(1 for op in self.active_operations.values() if not op["completed"])
        completed_operations = sum(1 for op in self.active_operations.values() if op["completed"])
        
        return {
            "total_operations": total_operations,
            "active_operations": active_operations,
            "completed_operations": completed_operations,
            "websocket_url": self.websocket_url
        }