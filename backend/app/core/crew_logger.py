import asyncio
import time
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, desc
from contextlib import asynccontextmanager

from app.models.crew_interaction import CrewInteractionModel, CrewInteraction, TokenUsage, ReasoningStep
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://projectuser:projectpass@localhost:5432/projectdb")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let the caller handle it

class CrewInteractionLogger:
    """
    Comprehensive logger for crew, agent, and tool interactions.
    Provides real-time logging with WebSocket broadcasting and persistent storage.
    """

    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id
        self.conversation_id = f"{task_id}_{int(time.time())}"
        self.sequence = 0
        self.websocket_clients = set()
        self.interaction_stack = []  # For tracking hierarchy

    def _get_next_sequence(self) -> int:
        """Get next sequence number for this conversation"""
        self.sequence += 1
        return self.sequence

    def _calculate_depth(self, parent_id: Optional[str] = None) -> int:
        """Calculate depth based on parent relationship"""
        if not parent_id:
            return 0

        # Find parent in current stack
        for interaction in reversed(self.interaction_stack):
            if interaction.get('id') == parent_id:
                return interaction.get('depth', 0) + 1
        return 0

    async def log_interaction(self, interaction_data: Dict[str, Any]) -> str:
        """
        Log interaction to database and broadcast to WebSocket clients
        Returns the interaction ID
        """
        try:
            # Generate unique ID
            interaction_id = str(uuid.uuid4())

            # Prepare interaction data
            interaction_data.update({
                'id': interaction_id,
                'project_id': self.project_id,
                'task_id': self.task_id,
                'conversation_id': self.conversation_id,
                'sequence': self._get_next_sequence(),
                'timestamp': datetime.now(timezone.utc),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            })

            # Calculate depth if parent_id provided
            if 'parent_id' in interaction_data:
                interaction_data['depth'] = self._calculate_depth(interaction_data['parent_id'])

            # Add to interaction stack for hierarchy tracking
            self.interaction_stack.append(interaction_data)

            # Save to database
            await self._save_to_database(interaction_data)

            # Broadcast to WebSocket clients
            await self._broadcast_to_websockets(interaction_data)

            logger.info(f"Logged interaction: {interaction_data['type']} for {interaction_data.get('agent_name', 'crew')}")
            return interaction_id

        except Exception as e:
            logger.error(f"Failed to log interaction: {str(e)}")
            return ""

    async def _save_to_database(self, interaction_data: Dict[str, Any]):
        """Save interaction to PostgreSQL database"""
        db = None
        try:
            # Get database session
            db = get_db()

            # Create model instance
            interaction_model = CrewInteractionModel(**interaction_data)

            # Save to database
            db.add(interaction_model)
            db.commit()
            db.refresh(interaction_model)

        except Exception as e:
            logger.error(f"Database save failed: {str(e)}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()

    async def _broadcast_to_websockets(self, interaction_data: Dict[str, Any]):
        """Broadcast interaction to all connected WebSocket clients"""
        if not self.websocket_clients:
            return

        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_data = self._make_serializable(interaction_data)
            message = json.dumps(serializable_data, default=str)

            # Broadcast to all connected clients
            disconnected_clients = set()
            for websocket in self.websocket_clients:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket client: {str(e)}")
                    disconnected_clients.add(websocket)

            # Remove disconnected clients
            self.websocket_clients -= disconnected_clients

        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {str(e)}")

    def _make_serializable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert data to JSON-serializable format"""
        serializable = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                serializable[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                serializable[key] = str(value)
            else:
                serializable[key] = value
        return serializable

    def add_websocket_client(self, websocket):
        """Add WebSocket client for real-time updates"""
        self.websocket_clients.add(websocket)

    def remove_websocket_client(self, websocket):
        """Remove WebSocket client"""
        self.websocket_clients.discard(websocket)

    # =====================================================================================
    # CREW LEVEL LOGGING
    # =====================================================================================

    async def log_crew_start(self, crew_name: str, members: List[str], goal: str, description: str = "") -> str:
        """Log crew initialization"""
        return await self.log_interaction({
            'type': 'crew_start',
            'crew_name': crew_name,
            'crew_description': description,
            'crew_members': members,
            'crew_goal': goal,
            'status': 'running',
            'start_time': datetime.now(timezone.utc)
        })

    async def log_crew_complete(self, crew_name: str, success: bool = True, duration_ms: int = None) -> str:
        """Log crew completion"""
        return await self.log_interaction({
            'type': 'crew_complete',
            'crew_name': crew_name,
            'status': 'completed' if success else 'failed',
            'end_time': datetime.now(timezone.utc),
            'duration_ms': duration_ms
        })

    # =====================================================================================
    # AGENT LEVEL LOGGING
    # =====================================================================================

    async def log_agent_start(self, agent_name: str, role: str, goal: str, backstory: str = "",
                             parent_id: str = None) -> str:
        """Log agent activation"""
        return await self.log_interaction({
            'type': 'agent_start',
            'agent_name': agent_name,
            'agent_role': role,
            'agent_goal': goal,
            'agent_backstory': backstory,
            'agent_id': f"{agent_name}_{int(time.time())}",
            'status': 'running',
            'start_time': datetime.now(timezone.utc),
            'parent_id': parent_id
        })

    async def log_agent_reasoning(self, agent_name: str, thought: str, action: str,
                                 action_input: Dict[str, Any] = None, observation: str = None,
                                 final_answer: str = None, scratchpad: str = None,
                                 parent_id: str = None) -> str:
        """Log agent internal reasoning steps"""
        reasoning_step = ReasoningStep(
            thought=thought,
            action=action,
            action_input=action_input,
            observation=observation,
            final_answer=final_answer,
            scratchpad=scratchpad
        )

        return await self.log_interaction({
            'type': 'reasoning_step',
            'agent_name': agent_name,
            'reasoning_step': reasoning_step.dict(),
            'status': 'completed',
            'parent_id': parent_id
        })

    async def log_agent_complete(self, agent_name: str, success: bool = True,
                                duration_ms: int = None, parent_id: str = None) -> str:
        """Log agent completion"""
        return await self.log_interaction({
            'type': 'agent_complete',
            'agent_name': agent_name,
            'status': 'completed' if success else 'failed',
            'end_time': datetime.now(timezone.utc),
            'duration_ms': duration_ms,
            'parent_id': parent_id
        })

    # =====================================================================================
    # TOOL LEVEL LOGGING
    # =====================================================================================

    async def log_tool_call(self, agent_name: str, tool_name: str, function_name: str,
                           params: Dict[str, Any], description: str = "", parent_id: str = None) -> str:
        """Log tool function call"""
        return await self.log_interaction({
            'type': 'tool_call',
            'agent_name': agent_name,
            'tool_name': tool_name,
            'tool_description': description,
            'function_name': function_name,
            'request_data': params,
            'request_text': json.dumps(params, indent=2),
            'message_type': 'input',
            'status': 'running',
            'start_time': datetime.now(timezone.utc),
            'parent_id': parent_id
        })

    async def log_tool_response(self, interaction_id: str, response: Any, success: bool = True,
                               duration_ms: int = None, error_message: str = None) -> str:
        """Log tool response"""
        response_data = response if isinstance(response, dict) else {'result': str(response)}

        return await self.log_interaction({
            'type': 'tool_response',
            'response_data': response_data,
            'response_text': json.dumps(response_data, indent=2) if isinstance(response_data, dict) else str(response),
            'message_type': 'output',
            'status': 'completed' if success else 'failed',
            'end_time': datetime.now(timezone.utc),
            'duration_ms': duration_ms,
            'error_message': error_message,
            'parent_id': interaction_id
        })

    async def log_function_call(self, agent_name: str, tool_name: str, function_name: str,
                               params: Dict[str, Any], result: Any, duration_ms: int = None,
                               parent_id: str = None) -> str:
        """Log individual function call within a tool"""
        return await self.log_interaction({
            'type': 'function_call',
            'agent_name': agent_name,
            'tool_name': tool_name,
            'function_name': function_name,
            'request_data': params,
            'response_data': result if isinstance(result, dict) else {'result': str(result)},
            'status': 'completed',
            'duration_ms': duration_ms,
            'parent_id': parent_id
        })

    # =====================================================================================
    # TOKEN USAGE AND PERFORMANCE LOGGING
    # =====================================================================================

    async def log_token_usage(self, interaction_id: str, prompt_tokens: int, completion_tokens: int,
                             model: str, provider: str, estimated_cost: float = 0.0) -> str:
        """Log token usage for LLM calls"""
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost=estimated_cost,
            model=model,
            provider=provider
        )

        return await self.log_interaction({
            'type': 'token_usage',
            'token_usage': token_usage.dict(),
            'status': 'completed',
            'parent_id': interaction_id
        })

    async def log_performance_metrics(self, interaction_id: str, metrics: Dict[str, Any]) -> str:
        """Log performance metrics"""
        return await self.log_interaction({
            'type': 'performance_metrics',
            'performance_metrics': metrics,
            'status': 'completed',
            'parent_id': interaction_id
        })

    # =====================================================================================
    # ERROR AND RETRY LOGGING
    # =====================================================================================

    async def log_error(self, agent_name: str = None, tool_name: str = None,
                       error_message: str = "", error_details: Dict[str, Any] = None,
                       parent_id: str = None) -> str:
        """Log errors"""
        return await self.log_interaction({
            'type': 'error',
            'agent_name': agent_name,
            'tool_name': tool_name,
            'error_message': error_message,
            'metadata': error_details or {},
            'status': 'failed',
            'parent_id': parent_id
        })

    async def log_retry(self, original_interaction_id: str, retry_count: int,
                       reason: str = "") -> str:
        """Log retry attempts"""
        return await self.log_interaction({
            'type': 'retry',
            'retry_count': retry_count,
            'error_message': reason,
            'status': 'retrying',
            'parent_id': original_interaction_id
        })

# =====================================================================================
# GLOBAL LOGGER REGISTRY
# =====================================================================================

class CrewLoggerRegistry:
    """Registry to manage crew loggers across different tasks"""

    def __init__(self):
        self.loggers: Dict[str, CrewInteractionLogger] = {}

    def get_logger(self, project_id: str, task_id: str) -> CrewInteractionLogger:
        """Get or create logger for a specific task"""
        key = f"{project_id}_{task_id}"
        if key not in self.loggers:
            self.loggers[key] = CrewInteractionLogger(project_id, task_id)
        return self.loggers[key]

    def remove_logger(self, project_id: str, task_id: str):
        """Remove logger when task is complete"""
        key = f"{project_id}_{task_id}"
        if key in self.loggers:
            del self.loggers[key]

# Global registry instance
crew_logger_registry = CrewLoggerRegistry()
