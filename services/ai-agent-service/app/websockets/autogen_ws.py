"""
AutoGen WebSocket Handler
Provides real-time streaming of AutoGen conversations
"""

import json
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from ..core.autogen_copilot import AutoGenCopilot

logger = logging.getLogger("autogen-websocket")

class AutoGenWebSocketManager:
    """Manage WebSocket connections for real-time AutoGen conversations"""
    
    def __init__(self):
        # Active WebSocket connections: session_id -> websocket
        self.connections: Dict[str, WebSocket] = {}
        
        # Conversation states: session_id -> conversation_state
        self.conversation_states: Dict[str, Dict[str, Any]] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect a WebSocket client for a conversation session"""
        await websocket.accept()
        async with self._lock:
            self.connections[session_id] = websocket
            self.conversation_states[session_id] = {
                "status": "connected",
                "start_time": datetime.utcnow().isoformat(),
                "message_count": 0
            }
        
        logger.info(f"WebSocket connected for session {session_id}")
        
        # Send connection confirmation
        await self.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, session_id: str):
        """Disconnect a WebSocket client"""
        async with self._lock:
            if session_id in self.connections:
                del self.connections[session_id]
            if session_id in self.conversation_states:
                del self.conversation_states[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific WebSocket connection"""
        if session_id not in self.connections:
            logger.warning(f"No WebSocket connection found for session {session_id}")
            return
        
        try:
            websocket = self.connections[session_id]
            await websocket.send_text(json.dumps(message))
            
            # Update message count
            if session_id in self.conversation_states:
                self.conversation_states[session_id]["message_count"] += 1
                
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")
            # Remove disconnected websocket
            await self.disconnect(session_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSocket clients"""
        if not self.connections:
            return
        
        disconnected_sessions = []
        
        for session_id, websocket in self.connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to broadcast to session {session_id}: {e}")
                disconnected_sessions.append(session_id)
        
        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            await self.disconnect(session_id)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about current WebSocket connections"""
        return {
            "active_connections": len(self.connections),
            "conversation_sessions": list(self.connections.keys()),
            "conversation_states": self.conversation_states
        }

# Global WebSocket manager
websocket_manager = AutoGenWebSocketManager()

class StreamingAutoGenCopilot:
    """
    Streaming version of AutoGen Copilot for real-time WebSocket communication
    """
    
    def __init__(self, autogen_copilot: AutoGenCopilot):
        self.copilot = autogen_copilot
    
    async def start_streaming_conversation(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        selected_agents: Optional[list] = None
    ):
        """Start a streaming AutoGen conversation with real-time updates"""
        
        try:
            # Send conversation start notification
            await websocket_manager.send_message(session_id, {
                "type": "conversation_starting",
                "session_id": session_id,
                "user_message": user_message,
                "selected_agents": selected_agents or [],
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Create a custom conversation handler that streams updates
            result = await self._run_streaming_conversation(
                session_id,
                user_message,
                context,
                selected_agents
            )
            
            # Send final result
            await websocket_manager.send_message(session_id, {
                "type": "conversation_completed",
                "session_id": session_id,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in streaming conversation: {e}")
            
            # Send error notification
            await websocket_manager.send_message(session_id, {
                "type": "conversation_error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            raise
    
    async def _run_streaming_conversation(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]],
        selected_agents: Optional[list]
    ):
        """Run AutoGen conversation with streaming updates"""
        
        # Initialize streaming conversation state
        conversation_state = {
            "session_id": session_id,
            "start_time": datetime.utcnow(),
            "messages": [],
            "current_speaker": None,
            "agents_active": selected_agents or []
        }
        
        # Send agent initialization updates
        agents = self.copilot.get_available_agents()
        active_agents = selected_agents or list(agents.keys())[:4]  # Default to first 4
        
        for agent_name in active_agents:
            await websocket_manager.send_message(session_id, {
                "type": "agent_initializing",
                "session_id": session_id,
                "agent_name": agent_name,
                "agent_description": agents.get(agent_name, "Unknown agent"),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        await asyncio.sleep(1)  # Give time for agent initialization messages
        
        # Send agents ready notification
        await websocket_manager.send_message(session_id, {
            "type": "agents_ready",
            "session_id": session_id,
            "active_agents": active_agents,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Create a modified AutoGen conversation with streaming callbacks
        try:
            # Use the regular copilot but intercept messages
            result = await self._intercept_autogen_conversation(
                session_id,
                user_message,
                context,
                active_agents
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AutoGen conversation: {e}")
            raise
    
    async def _intercept_autogen_conversation(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]],
        selected_agents: list
    ):
        """Run AutoGen conversation with message interception for streaming"""
        
        # Since AutoGen doesn't natively support streaming, we'll simulate it
        # by running the conversation and sending periodic updates
        
        # Send thinking message
        await websocket_manager.send_message(session_id, {
            "type": "agents_thinking",
            "session_id": session_id,
            "message": "Agents are analyzing your question and preparing responses...",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Simulate agent-by-agent responses
        agents = selected_agents or ["migration_architect", "devops_expert", "security_expert", "cost_optimizer"]
        
        for i, agent_name in enumerate(agents):
            await asyncio.sleep(2)  # Simulate thinking time
            
            await websocket_manager.send_message(session_id, {
                "type": "agent_responding",
                "session_id": session_id,
                "agent_name": agent_name,
                "message": f"{agent_name} is formulating a response...",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Run the actual AutoGen conversation
        await websocket_manager.send_message(session_id, {
            "type": "conversation_processing",
            "session_id": session_id,
            "message": "Running comprehensive multi-agent analysis...",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Execute the real conversation
        result = await self.copilot.start_conversation(
            user_message=user_message,
            session_id=session_id,
            context=context,
            selected_agents=selected_agents
        )
        
        # Stream the results
        if result.get("status") == "success":
            # Send recommendations one by one
            recommendations = result.get("recommendations", [])
            for i, rec in enumerate(recommendations):
                await asyncio.sleep(1)
                await websocket_manager.send_message(session_id, {
                    "type": "recommendation_received",
                    "session_id": session_id,
                    "recommendation": rec,
                    "index": i + 1,
                    "total": len(recommendations),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Send action items
            action_items = result.get("action_items", [])
            for i, action in enumerate(action_items):
                await asyncio.sleep(0.5)
                await websocket_manager.send_message(session_id, {
                    "type": "action_item_received",
                    "session_id": session_id,
                    "action_item": action,
                    "index": i + 1,
                    "total": len(action_items),
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Send summary
            await websocket_manager.send_message(session_id, {
                "type": "summary_ready",
                "session_id": session_id,
                "summary": result.get("summary", {}),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return result

# WebSocket endpoint handler
async def handle_autogen_websocket(
    websocket: WebSocket,
    session_id: str,
    autogen_copilot: AutoGenCopilot
):
    """Handle AutoGen WebSocket connections for real-time conversations"""
    
    # Connect the WebSocket
    await websocket_manager.connect(websocket, session_id)
    
    # Create streaming copilot
    streaming_copilot = StreamingAutoGenCopilot(autogen_copilot)
    
    try:
        while True:
            # Wait for messages from client
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                message_type = message.get("type")
                
                if message_type == "start_conversation":
                    # Start a new conversation
                    user_message = message.get("message", "")
                    context = message.get("context")
                    selected_agents = message.get("selected_agents")
                    
                    if not user_message:
                        await websocket_manager.send_message(session_id, {
                            "type": "error",
                            "error": "Message is required",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Start streaming conversation
                    await streaming_copilot.start_streaming_conversation(
                        session_id=session_id,
                        user_message=user_message,
                        context=context,
                        selected_agents=selected_agents
                    )
                
                elif message_type == "follow_up":
                    # Handle follow-up message
                    follow_up_message = message.get("message", "")
                    
                    if not follow_up_message:
                        await websocket_manager.send_message(session_id, {
                            "type": "error",
                            "error": "Follow-up message is required",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Start follow-up conversation
                    await streaming_copilot.start_streaming_conversation(
                        session_id=session_id,
                        user_message=follow_up_message,
                        context=None,  # Context should be maintained from previous conversation
                        selected_agents=None  # Use same agents as before
                    )
                
                elif message_type == "ping":
                    # Respond to ping with pong
                    await websocket_manager.send_message(session_id, {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                elif message_type == "get_agents":
                    # Send available agents
                    agents = autogen_copilot.get_available_agents()
                    await websocket_manager.send_message(session_id, {
                        "type": "agents_list",
                        "agents": agents,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                else:
                    await websocket_manager.send_message(session_id, {
                        "type": "error",
                        "error": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}")
                break
            except json.JSONDecodeError:
                await websocket_manager.send_message(session_id, {
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket_manager.send_message(session_id, {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    
    finally:
        # Clean up connection
        await websocket_manager.disconnect(session_id)
