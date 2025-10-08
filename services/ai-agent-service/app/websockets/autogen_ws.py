from __future__ import annotations

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
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    # Only for type hints; avoid runtime import to prevent circular dependency
    from ..core.autogen_copilot import AutoGenCopilot
from ..repository.conversations import get_conversation_repository

logger = logging.getLogger("autogen-websocket")

class AutoGenWebSocketManager:
    """Manage WebSocket connections for real-time AutoGen conversations"""
    
    def __init__(self):
        # Active WebSocket connections: session_id -> websocket
        self.connections = {}
        # Conversation states: session_id -> conversation_state
        self.conversation_states = {}
        # Alias map to route messages when REST session_id differs from WS session_id
        # Maps alias_session_id -> actual_session_id
        self.session_aliases = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect a WebSocket client for a conversation session"""
        # Diagnostic: log intended origin BEFORE accept to trace 403 issues occurring upstream
        try:
            origin = websocket.headers.get("origin") or websocket.headers.get("Origin")
            logger.info("WebSocket handshake attempt session=%s origin=%s client=%s", session_id, origin, websocket.client)
        except Exception:
            pass
        # For now accept unconditionally; upstream 403 indicates middleware / proxy rejection prior to this point
        await websocket.accept()
        async with self._lock:
            self.connections[session_id] = websocket
            self.conversation_states[session_id] = {
                "status": "connected",
                "start_time": datetime.now().isoformat(),
                "message_count": 0,
                # Track origin to help REST endpoints infer session when not explicitly provided
                "origin": origin if 'origin' in locals() else None,
            }
        
        # Log limited handshake info safely
        try:
            hdrs = {k: v for k, v in websocket.headers.items() if k.lower() in ("origin", "host", "sec-websocket-version")}
            logger.info("WebSocket connected session=%s client=%s headers=%s", session_id, websocket.client, hdrs)
        except Exception:
            logger.info(f"WebSocket connected for session {session_id}")
        
        # Send connection confirmation
        await self.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def disconnect(self, session_id: str):
        """Disconnect a WebSocket client"""
        async with self._lock:
            websocket = self.connections.get(session_id)
            if websocket:
                # Try to close the websocket gracefully
                try:
                    await websocket.close()
                except Exception as e:
                    logger.debug(f"Error closing websocket for session {session_id}: {e}")
            
            if session_id in self.connections:
                del self.connections[session_id]
            if session_id in self.conversation_states:
                del self.conversation_states[session_id]
            # Remove any aliases targeting this session
            try:
                to_delete = [alias for alias, target in self.session_aliases.items() if target == session_id or alias == session_id]
                for a in to_delete:
                    del self.session_aliases[a]
            except Exception:
                pass
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_message(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific WebSocket connection"""
        # Resolve via alias first
        target_session_id = self.resolve_session(session_id)
        if target_session_id not in self.connections:
            # Silently skip if no connection - don't spam logs
            # This is normal when conversations run without WebSocket streaming
            return False  # Return False to indicate message was not sent
        
        try:
            websocket = self.connections[target_session_id]
            await websocket.send_text(json.dumps(message))
            
            # Update message count
            if target_session_id in self.conversation_states:
                self.conversation_states[target_session_id]["message_count"] += 1
            # Persist selected streaming message types best-effort
            try:
                mtype = message.get("type")
                if mtype in {"agent_responding", "recommendation_received", "action_item_received"}:
                    repo = get_conversation_repository()
                    content = (
                        message.get("message")
                        or (message.get("recommendation") or {}).get("recommendation")
                        or (message.get("action_item") or {}).get("action")
                        or ""
                    )
                    repo.add_messages(session_id, [
                        {
                            "timestamp": message.get("timestamp"),
                            "source": message.get("agent_name")
                                      or (message.get("recommendation") or {}).get("agent")
                                      or (message.get("action_item") or {}).get("agent")
                                      or "system",
                            "message_type": mtype,
                            "content": content,
                        }
                    ])
            except Exception:
                # Do not disrupt streaming on persistence errors
                pass
            
            return True  # Return True to indicate message was sent successfully
                
        except Exception as e:
            logger.error(f"Failed to send message to session {session_id}: {e}")
            # Remove disconnected websocket
            await self.disconnect(target_session_id)
            return False  # Return False to indicate message failed
    
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

    # --------- Alias and resolution helpers ---------
    def register_alias(self, alias_session_id: str, target_session_id: str):
        """Register an alias so that messages for alias_session_id are routed to target_session_id."""
        if not alias_session_id or not target_session_id:
            return
        if target_session_id not in self.connections:
            # don't create alias if target isn't connected
            return
        self.session_aliases[alias_session_id] = target_session_id
        logger.info("Registered session alias alias=%s -> target=%s", alias_session_id, target_session_id)

    def resolve_session(self, session_id: str) -> str:
        """Resolve a session_id through alias map to the actual connected session id."""
        try:
            return self.session_aliases.get(session_id, session_id)
        except Exception:
            return session_id

    def has_session(self, session_id: str) -> bool:
        """Return True if session_id or its alias maps to an active connection."""
        return self.resolve_session(session_id) in self.connections

    def find_latest_session_by_origin(self, origin: Optional[str]) -> Optional[str]:
        """Find the most recent connected session, preferring ones matching the given Origin."""
        if not self.conversation_states:
            return None
        try:
            if origin:
                matching = [
                    (sid, st) for sid, st in self.conversation_states.items()
                    if st.get("origin") == origin
                ]
                if matching:
                    return max(matching, key=lambda kv: kv[1].get("start_time", ""))[0]
            # fallback to latest overall
            return max(self.conversation_states.items(), key=lambda kv: kv[1].get("start_time", ""))[0]
        except Exception:
            return None

# Global WebSocket manager
websocket_manager = AutoGenWebSocketManager()

class StreamingAutoGenCopilot:
    """
    Streaming version of AutoGen Copilot for real-time WebSocket communication
    """
    
    def __init__(self, autogen_copilot):
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
                "timestamp": datetime.now().isoformat()
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
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in streaming conversation: {e}")
            
            # Send error notification
            await websocket_manager.send_message(session_id, {
                "type": "conversation_error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
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
            "start_time": datetime.now(),
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
                "timestamp": datetime.now().isoformat()
            })
        
        await asyncio.sleep(1)  # Give time for agent initialization messages
        
        # Send agents ready notification
        await websocket_manager.send_message(session_id, {
            "type": "agents_ready",
            "session_id": session_id,
            "active_agents": active_agents,
            "timestamp": datetime.now().isoformat()
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
        """Run AutoGen conversation with enhanced message interception for real-time streaming"""

        # Send initial thinking message
        await websocket_manager.send_message(session_id, {
            "type": "agents_thinking",
            "session_id": session_id,
            "message": "🤔 Agents are analyzing your question and preparing responses...",
            "timestamp": datetime.now().isoformat()
        })

        # Get agent details for better messaging
        available_agents = self.copilot.get_available_agents()
        agents = selected_agents or ["migration_architect", "devops_expert", "security_expert", "cost_optimizer"]

        # Send agent-by-agent initialization with roles
        for agent_name in agents:
            agent_description = available_agents.get(agent_name, f"{agent_name} expert")
            await websocket_manager.send_message(session_id, {
                "type": "agent_initializing",
                "session_id": session_id,
                "agent_name": agent_name,
                "agent_description": agent_description,
                "message": f"🔄 Initializing {agent_name}...",
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(0.5)  # Brief pause for visual effect

        # Send agents ready notification
        await websocket_manager.send_message(session_id, {
            "type": "agents_ready",
            "session_id": session_id,
            "active_agents": agents,
            "message": f"✅ All {len(agents)} agents are ready to discuss your question",
            "timestamp": datetime.now().isoformat()
        })

        # Send context gathering message
        await websocket_manager.send_message(session_id, {
            "type": "context_gathering",
            "session_id": session_id,
            "message": "🔍 Gathering relevant context from knowledge base...",
            "timestamp": datetime.now().isoformat()
        })

        # Simulate agent thinking and discussion phases
        discussion_phases = [
            ("migration_architect", "Analyzing migration strategy and architectural considerations..."),
            ("devops_expert", "Evaluating infrastructure automation and deployment approaches..."),
            ("security_expert", "Assessing security implications and compliance requirements..."),
            ("cost_optimizer", "Calculating cost implications and optimization opportunities...")
        ]

        # Send agent-by-agent thinking updates
        for agent_name, thinking_message in discussion_phases[:len(agents)]:
            if agent_name in agents:
                await websocket_manager.send_message(session_id, {
                    "type": "agent_thinking",
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "message": f"💭 {agent_name}: {thinking_message}",
                    "timestamp": datetime.now().isoformat()
                })
                await asyncio.sleep(1.5)  # Simulate thinking time

        # Send collaborative discussion message
        await websocket_manager.send_message(session_id, {
            "type": "agents_discussing",
            "session_id": session_id,
            "message": "🗣️ Agents are now discussing and collaborating on the best solution...",
            "timestamp": datetime.now().isoformat()
        })

        # Run the actual AutoGen conversation
        await websocket_manager.send_message(session_id, {
            "type": "conversation_processing",
            "session_id": session_id,
            "message": "⚡ Running comprehensive multi-agent analysis...",
            "timestamp": datetime.now().isoformat()
        })

        # Execute the real conversation
        result = await self.copilot.start_conversation(
            user_message=user_message,
            session_id=session_id,
            context=context,
            selected_agents=selected_agents
        )

        # Enhanced streaming of results with better formatting
        if result.get("status") == "success":
            # Get the full conversation messages for streaming
            full_conversation = result.get("full_conversation", [])

            # Stream agent responses one by one
            for message in full_conversation:
                agent_name = message.get("source", "unknown")
                content = message.get("content", "")
                message_type = message.get("message_type", "response")

                # Skip system messages and user messages
                if agent_name in ["user", "system"] or not content:
                    continue

                await websocket_manager.send_message(session_id, {
                    "type": "agent_response",
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "content": content,
                    "message_type": message_type,
                    "timestamp": message.get("timestamp", datetime.now().isoformat())
                })
                await asyncio.sleep(0.8)  # Brief pause between agent responses

            # Send recommendations with enhanced formatting
            recommendations = result.get("recommendations", [])
            if recommendations:
                await websocket_manager.send_message(session_id, {
                    "type": "recommendations_start",
                    "session_id": session_id,
                    "count": len(recommendations),
                    "message": f"📋 Found {len(recommendations)} key recommendations",
                    "timestamp": datetime.now().isoformat()
                })

                for i, rec in enumerate(recommendations):
                    await asyncio.sleep(0.5)
                    await websocket_manager.send_message(session_id, {
                        "type": "recommendation_received",
                        "session_id": session_id,
                        "recommendation": rec,
                        "index": i + 1,
                        "total": len(recommendations),
                        "timestamp": datetime.now().isoformat()
                    })

            # Send action items with enhanced formatting
            action_items = result.get("action_items", [])
            if action_items:
                await websocket_manager.send_message(session_id, {
                    "type": "action_items_start",
                    "session_id": session_id,
                    "count": len(action_items),
                    "message": f"🎯 Identified {len(action_items)} actionable next steps",
                    "timestamp": datetime.now().isoformat()
                })

                for i, action in enumerate(action_items):
                    await asyncio.sleep(0.3)
                    await websocket_manager.send_message(session_id, {
                        "type": "action_item_received",
                        "session_id": session_id,
                        "action_item": action,
                        "index": i + 1,
                        "total": len(action_items),
                        "timestamp": datetime.now().isoformat()
                    })

            # Send summary with enhanced formatting
            summary = result.get("summary", {})
            if summary:
                await websocket_manager.send_message(session_id, {
                    "type": "summary_ready",
                    "session_id": session_id,
                    "summary": summary,
                    "message": "📊 Analysis complete! Here's the comprehensive summary:",
                    "timestamp": datetime.now().isoformat()
                })

        return result

# WebSocket endpoint handler
async def handle_autogen_websocket(
    websocket: WebSocket,
    session_id: str,
    autogen_copilot: "AutoGenCopilot"
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
                            "timestamp": datetime.now().isoformat()
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
                            "timestamp": datetime.now().isoformat()
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
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif message_type == "get_agents":
                    # Send available agents
                    agents = autogen_copilot.get_available_agents()
                    await websocket_manager.send_message(session_id, {
                        "type": "agents_list",
                        "agents": agents,
                        "timestamp": datetime.now().isoformat()
                    })
                
                else:
                    await websocket_manager.send_message(session_id, {
                        "type": "error",
                        "error": f"Unknown message type: {message_type}",
                        "timestamp": datetime.now().isoformat()
                    })
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}")
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from session {session_id}")
                try:
                    await websocket_manager.send_message(session_id, {
                        "type": "error",
                        "error": "Invalid JSON format",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception:
                    # If we can't send error message, connection is likely dead
                    logger.error(f"Failed to send error message to session {session_id} - breaking connection")
                    break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                # Try to send error, but if it fails, break the loop
                try:
                    sent = await websocket_manager.send_message(session_id, {
                        "type": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    # If send_message returns False, the connection is dead
                    if not sent:
                        logger.error(f"WebSocket connection lost for session {session_id} - breaking loop")
                        break
                except Exception as send_error:
                    # If we can't send the error message, the connection is definitely dead
                    logger.error(f"Failed to send error message to session {session_id}: {send_error} - breaking loop")
                    break
    
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    
    finally:
        # Clean up connection
        await websocket_manager.disconnect(session_id)
