"""
AutoGen Co-pilot Integration  
Full implementation of Microsoft AutoGen for conversational AI assistance
Using the new autogen-agentchat structure
"""

import asyncio
import json
import logging
import os
import sys
import time
import hashlib
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger("autogen-copilot")

# Import usage tracking for conversation logging
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
    from usage_client import get_usage_client
    USAGE_TRACKING_AVAILABLE = True
    logger.info("Usage tracking available for conversation logging")
except ImportError as e:
    logger.warning(f"Usage tracking not available: {e}")
    USAGE_TRACKING_AVAILABLE = False
    def get_usage_client():
        return None

# Import WebSocket manager for streaming support
try:
    from ..websockets.autogen_ws import websocket_manager
    WEBSOCKET_AVAILABLE = True
    logger.info("WebSocket manager available for streaming")
except ImportError as e:
    logger.warning(f"WebSocket manager not available: {e}")
    WEBSOCKET_AVAILABLE = False

# Import the new AutoGen structure with error handling
try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent  
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.messages import TextMessage
    from autogen_agentchat.conditions import MaxMessageTermination
    AUTOGEN_AVAILABLE = True
    logger.info("AutoGen successfully imported")
except ImportError as e:
    logger.warning(f"AutoGen not available: {e}. Using fallback implementation.")
    # Create dummy classes for type hints when AutoGen is not available
    class AssistantAgent: pass
    class UserProxyAgent: pass
    class RoundRobinGroupChat: pass
    class TextMessage: pass
    class MaxMessageTermination: pass
    AUTOGEN_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
    # Changed from INFO to DEBUG: This only checks if openai library is installed (import check)
    # Does NOT indicate fallback usage - actual provider/model determined by llm_config
    logger.debug("OpenAI library detected (import check only, not indicating usage)")
except ImportError:
    logger.debug("OpenAI library not installed")
    OPENAI_AVAILABLE = False

# AutoGen agents are now created directly in the AutoGenCopilot class using AssistantAgent

class AutoGenCopilot:
    """
    Advanced Multi-Agent Copilot for Cloud Migration Assistance
    Uses AutoGen framework for multi-agent conversations
    """

    def __init__(self, llm_config: Dict[str, Any], conversation_repository=None):
        self.llm_config = llm_config
        self.agents: Dict[str, AssistantAgent] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_session_id: Optional[str] = None
        self.conversation_repository = conversation_repository

        # Log repository status
        if self.conversation_repository:
            logger.info("AutoGenCopilot initialized with persistent storage")
        else:
            logger.warning("AutoGenCopilot initialized without persistent storage (in-memory only)")

        # Defer agent initialization until a project-scoped api_key is applied
        if self.llm_config.get("api_key"):
            self._initialize_agents()

    def apply_project_llm_config(self, project_id: str, llm_config: Dict[str, Any]):
        """Apply a project-specific LLM configuration (must include api_key & model)."""
        api_key = llm_config.get("api_key")
        model = llm_config.get("model")
        if not api_key or not model:
            raise ValueError(f"Incomplete LLM config for project {project_id} (api_key/model missing)")
        # Replace and rebuild agents
        self.llm_config = {**llm_config, "project_id": project_id, "project_scoped": True}
        self.agents.clear()
        self._initialize_agents()

    def has_websocket_connection(self, session_id: str) -> bool:
        """Check if there's an active WebSocket connection for the given session"""
        if not WEBSOCKET_AVAILABLE:
            return False
        try:
            return websocket_manager.has_session(session_id)
        except Exception:
            return session_id in websocket_manager.connections

    async def stream_message_to_websocket(self, session_id: str, message_type: str, data: Dict[str, Any]):
        """Stream a message to WebSocket if connection exists"""
        if not WEBSOCKET_AVAILABLE or not self.has_websocket_connection(session_id):
            return

        try:
            message = {
                "type": message_type,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                **data
            }
            await websocket_manager.send_message(session_id, message)
        except Exception as e:
            logger.warning(f"Failed to stream message to WebSocket for session {session_id}: {e}")
    
    def _create_model_client(self):
        """Create model client for AutoGen agents"""
        if AUTOGEN_AVAILABLE:
            # AutoGen expects an object with a model_info attribute in some code paths
            class _ModelClientWrapper:
                def __init__(self, base: Dict[str, Any], project_id: str = None):
                    self._base = base
                    self._project_id = project_id  # Store project_id for LLM service calls
                    # Provide model_info with at least vision flag to satisfy AssistantAgent._get_compatible_context
                    self.model_info = {
                        "vision": False,
                        "model": base.get("model"),
                    }
                    logger.info(f"ModelClientWrapper initialized with model: {base.get('model')}, project_id: {project_id}")

                # Fallback attribute access to underlying dict
                def __getattr__(self, item):
                    try:
                        return self._base[item]
                    except KeyError:
                        raise AttributeError(item)

                # Allow dict-style usage if any internal code assumes mapping
                def get(self, key, default=None):
                    return self._base.get(key, default)

                def to_dict(self):
                    return dict(self._base)

                async def create(self, messages: List[Dict[str, str]], **kwargs):
                    """OpenAI-compatible create() returning a response object that AutoGen can process.

                    Returns a response object that contains choices with message content,
                    which AssistantAgent can extract from properly. We cannot return TextMessage
                    directly as that causes "No model result was produced" assertion failure.
                    """
                    import hashlib, random
                    provider = self._base.get("provider") or self._base.get("api_type") or "openai"
                    model = self._base.get("model")
                    if not model:
                        raise ValueError("Model not configured - project LLM config must include 'model'")
                    api_key = self._base.get("api_key")
                    temperature = kwargs.get("temperature", 0.3)

                    logger.info(f"ModelClientWrapper.create called with provider={provider}, model={model}, has_api_key={bool(api_key)}")

                    # Normalize incoming messages
                    normalized: List[Dict[str, str]] = []
                    prompt_accum: List[str] = []

                    def _extract(m) -> Dict[str, str]:
                        if isinstance(m, dict):
                            return {"role": m.get("role") or m.get("source") or "user", "content": m.get("content") or ""}
                        role = getattr(m, "role", None) or getattr(m, "source", None) or "user"
                        content = getattr(m, "content", None)
                        if content is None:
                            content = str(m)
                        return {"role": role, "content": content}

                    for m in messages:
                        try:
                            nm = _extract(m)
                            normalized.append(nm)
                            if nm["role"] in ("system", "user") and nm["content"]:
                                prompt_accum.append(nm["content"])
                        except Exception as ex:
                            logger.debug(f"Message normalization failed: {ex}")
                    prompt_excerpt = (" ".join(prompt_accum))[:400]

                    # Use LLM service for all providers (including OpenAI)
                    try:
                        from services.shared.service_client import get_service_client

                        # Call the LLM service with the normalized messages
                        client = await get_service_client()
                        llm_payload = {
                            "messages": normalized,
                            "model": model,
                            "temperature": temperature,
                            "max_tokens": kwargs.get("max_tokens", 128000),  # Increased from 512 to 128000 for comprehensive responses
                            "provider": provider,
                            "project_id": self._project_id  # Use stored project_id instead of self.llm_config
                        }

                        logger.info(f"Calling LLM service with payload: {llm_payload}")

                        # Call LLM service
                        llm_response = await client.post("llm", "/api/llm/chat/completions", json=llm_payload)

                        if isinstance(llm_response, dict) and "choices" in llm_response:
                            # Return the raw dict response - AutoGen can handle dict responses better than custom objects
                            # This avoids the message type registration issues with custom classes
                            logger.info("Returning raw dict response from LLM service")
                            return llm_response
                        else:
                            logger.warning(f"Invalid LLM service response: {llm_response}")
                            raise Exception(f"Invalid LLM service response: {llm_response}")

                    except Exception as e:
                        logger.error(f"LLM service call failed: {e}")
                        # Re-raise the exception instead of using fallback
                        # This ensures proper error handling up the call stack
                        raise Exception(f"LLM service unavailable: {e}")

            model_client = _ModelClientWrapper({
                "model": self.llm_config.get("model"),
                "api_key": self.llm_config.get("api_key"),
                "api_type": self.llm_config.get("provider", "openai"),
                "provider": self.llm_config.get("provider", "openai"),
            }, project_id=self.llm_config.get("project_id"))  # Pass project_id to wrapper
            logger.info(f"Created model client: {type(model_client)}")
            return model_client
        else:
            # Fallback configuration for OpenAI direct usage
            logger.warning("AutoGen not available, using fallback configuration")
            return {
                "api_key": self.llm_config.get("api_key"),
                "model": self.llm_config.get("model"),
                "temperature": self.llm_config.get("temperature", 0.7),
                "max_tokens": self.llm_config.get("max_tokens", 1000)
            }
        
    def _initialize_agents(self):
        """Initialize specialized cloud migration agents using AutoGen"""
        
        model_client = self._create_model_client()
        
        agent_definitions = {
            "migration_architect": {
                "role": "Senior Cloud Migration Architect",
                "system_message": """You are a Senior Cloud Migration Architect with deep expertise in:
                - AWS, Azure, and GCP migration strategies
                - Application modernization and containerization  
                - Infrastructure as Code (Terraform, CloudFormation)
                - Database migration and data lake architecture
                - Security and compliance during migration
                
                Your role is to provide strategic guidance on cloud migration projects.
                Always consider cost optimization, security, scalability, and business continuity.
                Provide detailed architectural recommendations with clear rationale.
                Keep responses focused, practical, and actionable."""
            },
            
            "devops_expert": {
                "role": "DevOps Automation Specialist",
                "system_message": """You are a DevOps automation specialist focusing on:
                - CI/CD pipeline design and implementation
                - Kubernetes and container orchestration
                - Infrastructure automation and monitoring
                - Site reliability engineering (SRE) practices
                - Cloud-native application deployment
                
                Provide practical implementation guidance, code snippets, and automation scripts.
                Focus on best practices for deployment, scaling, and operational excellence.
                Always consider automation, monitoring, and reliability."""
            },
            
            "security_expert": {
                "role": "Cloud Security & Compliance Expert",
                "system_message": """You are a Cloud Security and Compliance expert specializing in:
                - Cloud security frameworks (AWS Well-Architected, Azure Security Center)
                - Identity and Access Management (IAM) design
                - Data encryption and key management
                - Compliance standards (SOC 2, GDPR, HIPAA, ISO 27001)
                - Security monitoring and incident response
                
                Ensure all recommendations meet security best practices and compliance requirements.
                Identify potential security risks and provide concrete mitigation strategies.
                Focus on zero-trust principles and defense in depth."""
            },
            
            "cost_optimizer": {
                "role": "Cloud Cost Optimization Specialist",
                "system_message": """You are a Cloud Cost Optimization specialist focused on:
                - Cloud resource rightsizing and cost analysis
                - Reserved instances and savings plans optimization
                - Multi-cloud cost comparison and strategy
                - FinOps practices and cost governance
                - Resource lifecycle management
                
                Analyze costs throughout migration planning and provide optimization recommendations.
                Consider both immediate migration costs and long-term operational expenses.
                Provide specific cost-saving strategies with quantifiable benefits."""
            },
            
            "data_expert": {
                "role": "Data Migration & Analytics Expert", 
                "system_message": """You are a Data Migration and Analytics expert specializing in:
                - Database migration strategies (rehost, replatform, refactor)
                - Data lake and warehouse architecture
                - ETL/ELT pipeline design and optimization
                - Big data technologies (Spark, Hadoop, streaming)
                - Data governance and quality assurance
                
                Focus on data architecture, migration patterns, and analytics platform design.
                Ensure data integrity, performance, and accessibility throughout migration.
                Consider data lineage, quality, and governance requirements."""
            },
            
            "app_modernization": {
                "role": "Application Modernization Expert",
                "system_message": """You are an Application Modernization specialist focusing on:
                - Legacy application assessment and refactoring strategies
                - Microservices architecture and API design
                - Serverless and event-driven architectures
                - Application performance optimization
                - Technology stack modernization (containerization, PaaS adoption)
                
                Provide guidance on application transformation, technology choices, and implementation approaches.
                Consider maintainability, scalability, and developer productivity.
                Focus on practical modernization patterns and best practices."""
            }
        }
        
        # Create agent instances using AutoGen AssistantAgent or fallback
        for agent_name, config in agent_definitions.items():
            if AUTOGEN_AVAILABLE:
                self.agents[agent_name] = AssistantAgent(
                    name=agent_name,
                    system_message=config["system_message"],
                    model_client=model_client
                )
                logger.info(f"Initialized AutoGen agent: {agent_name}")
            else:
                # Create a fallback agent structure
                self.agents[agent_name] = {
                    "name": agent_name,
                    "role": config["role"], 
                    "system_message": config["system_message"],
                    "model_client": model_client
                }
                logger.info(f"Initialized fallback agent: {agent_name}")
    
    async def start_conversation(
        self, 
        user_message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Start a new AutoGen conversation with specified agents
        
        Args:
            user_message: Initial user question/request
            session_id: Unique session identifier
            context: Additional context about the project
            selected_agents: Specific agents to include (if None, uses all)
            
        Returns:
            Conversation results with messages and recommendations
        """
        
        self.current_session_id = session_id
        conversation_start_time = datetime.now()  # Use server local time for timestamp consistency

        # Check if WebSocket streaming is available
        websocket_streaming = self.has_websocket_connection(session_id)

        try:
            # Stream conversation start if WebSocket connected
            if websocket_streaming:
                await self.stream_message_to_websocket(session_id, "conversation_starting", {
                    "user_message": user_message,
                    "selected_agents": selected_agents or []
                })

            # Determine which agents to include
            if selected_agents:
                agent_names = [name for name in selected_agents if name in self.agents]
            else:
                # Default set of agents for most migration conversations
                agent_names = ["migration_architect", "devops_expert", "security_expert", "cost_optimizer"]
            
            # Load previous conversation history for ChatGPT-like memory
            conversation_history_str = ""
            if self.conversation_repository:
                try:
                    previous_messages = self.conversation_repository.get_session_history(session_id)
                    if previous_messages:
                        # Format previous conversation as context
                        history_parts = []
                        for msg in previous_messages[-20:]:  # Last 20 messages to avoid overwhelming context
                            role = msg.get("agent_name") or msg.get("source", "unknown")
                            content = msg.get("content", "")
                            if content:
                                history_parts.append(f"{role}: {content}")
                        if history_parts:
                            conversation_history_str = "=== Previous Conversation ===\n" + "\n\n".join(history_parts) + "\n\n=== Current Request ===\n"
                            logger.info(f"Loaded {len(previous_messages)} previous messages for session {session_id}")
                except Exception as history_error:
                    logger.warning(f"Failed to load conversation history: {history_error}")

            # Add context to the conversation if provided
            initial_message = user_message
            formatted_context_str: Optional[str] = None
            if context:
                try:
                    formatted_context_str = self._format_context(context)
                except Exception as fc_e:
                    logger.warning(f"Context formatting failed: {fc_e}")
                
            # Combine conversation history, context, and user message
            message_parts = []
            if conversation_history_str:
                message_parts.append(conversation_history_str)
            if formatted_context_str:
                message_parts.append(formatted_context_str)
            message_parts.append(f"User Question: {user_message}")
            
            if len(message_parts) > 1:
                initial_message = "\n\n".join(message_parts)
            else:
                initial_message = user_message
            
            logger.info(f"Starting conversation for session {session_id} with AutoGen: {AUTOGEN_AVAILABLE}")
            try:
                logger.info(
                    "llm_active provider=%s model=%s project_scoped=%s",
                    self.llm_config.get("provider"),
                    self.llm_config.get("model"),
                    self.llm_config.get("project_scoped"),
                )
            except Exception:
                pass

            logger.info(f"About to check AutoGen availability: {AUTOGEN_AVAILABLE}")

            # Check if agents are properly initialized
            if AUTOGEN_AVAILABLE and self.agents:
                agent_status = []
                for name, agent in self.agents.items():
                    # Check if agent is AssistantAgent instance or has model_client
                    has_client = isinstance(agent, AssistantAgent) or hasattr(agent, 'model_client')
                    agent_status.append(f"{name}: {'✓' if has_client else '✗'}")
                logger.info(f"Agent status: {', '.join(agent_status)}")
                
                # Use AutoGen if all agents are properly initialized
                all_agents_ready = all(isinstance(agent, AssistantAgent) or hasattr(agent, 'model_client') for agent in self.agents.values())
                
                if all_agents_ready:
                    logger.info("All agents ready, using AutoGen conversation method")
                    # Try AutoGen conversation first
                    try:
                        conversation_result = await self._run_autogen_conversation(
                            agent_names,
                            initial_message
                        )
                    except Exception as autogen_error:
                        logger.warning(f"AutoGen conversation failed: {autogen_error}, falling back")
                        conversation_result = await self._run_fallback_conversation(
                            agent_names,
                            initial_message
                        )
                else:
                    logger.warning("Some agents not ready, using fallback conversation method")
                    conversation_result = await self._run_fallback_conversation(
                        agent_names,
                        initial_message
                    )
            else:
                logger.warning("AutoGen not available or agents not initialized, using fallback")
                conversation_result = await self._run_fallback_conversation(
                    agent_names,
                    initial_message
                )
            
            logger.info(f"Conversation execution completed, processing results. Status: {conversation_result.get('status', 'unknown')}, Messages: {len(conversation_result.get('messages', []))}")

            # Process and structure the results
            structured_result = await self._process_conversation_result(
                conversation_result,
                conversation_start_time,
                agent_names
            )

            logger.info(f"Result processing completed. Final status: {structured_result.get('status', 'unknown')}")
            
            # Store conversation history in both memory and repository
            conversation_data = {
                "session_id": session_id,
                "timestamp": conversation_start_time.isoformat(),
                "user_message": user_message,
                # Preserve original structured context PLUS flattened string
                "context": {
                    "raw": context,
                    "formatted": formatted_context_str
                },
                "result": structured_result
            }

            # Store in memory for immediate access
            self.conversation_history.append(conversation_data)

            # Store in repository for persistence
            if self.conversation_repository:
                try:
                    self.conversation_repository.save_conversation_result(
                        session_id=session_id,
                        user_message=user_message,
                        context=context,
                        structured_result=structured_result
                    )
                    logger.info(f"Conversation {session_id} saved to repository")
                except Exception as repo_e:
                    logger.error(f"Failed to save conversation to repository: {repo_e}")

            # DO NOT send conversation_completed - let conversation stay open for follow-up questions
            # User should be able to continue the conversation without auto-closing
            # if websocket_streaming:
            #     await self.stream_message_to_websocket(session_id, "conversation_completed", {
            #         "result": structured_result
            #     })

            # Log conversation usage for tracking and analytics (Issue #3 fix)
            if USAGE_TRACKING_AVAILABLE:
                try:
                    usage_client = get_usage_client()
                    if usage_client:
                        # Calculate conversation duration
                        duration_ms = int((datetime.now() - conversation_start_time).total_seconds() * 1000)
                        
                        # Extract token usage if available from structured_result
                        usage_data = structured_result.get("usage", {}) or {}
                        input_tokens = usage_data.get("prompt_tokens", 0)
                        output_tokens = usage_data.get("completion_tokens", 0)
                        total_tokens = usage_data.get("total_tokens", 0) or (input_tokens + output_tokens)
                        
                        # Build full conversation messages for logging
                        normalized_messages = structured_result.get("normalized_messages", [])
                        
                        # Prepare prompt and response texts for usage logging
                        prompt_text = f"User: {user_message}\n\nContext: {formatted_context_str[:500]}..."  # Truncate context
                        response_text = structured_result.get("final_response", "")
                        if not response_text and normalized_messages:
                            # Fallback: use last agent message as response
                            response_text = normalized_messages[-1].get("content", "") if normalized_messages else ""
                        
                        # Log the conversation - using correct parameter names (prompt, response)
                        await usage_client.log_llm_call(
                            project_id=self.llm_config.get("project_id"),
                            correlation_id=session_id,
                            provider=self.llm_config.get("provider", "autogen"),
                            model=self.llm_config.get("model", "unknown"),
                            prompt=prompt_text,
                            response=response_text,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            duration_ms=duration_ms,
                            status="success" if structured_result.get("status") == "success" else "error",
                            metadata={
                                "session_id": session_id,
                                "agent_count": len(agent_names),
                                "message_count": len(normalized_messages),
                                "mode": structured_result.get("mode", "unknown"),
                                "process_type": "autogen_discussion"
                            }
                        )
                        logger.info(f"Logged conversation usage for session {session_id}: {total_tokens} tokens, {duration_ms}ms")
                except Exception as usage_e:
                    # Best-effort logging - don't fail the conversation if logging fails
                    logger.warning(f"Failed to log conversation usage: {usage_e}")

            return structured_result
            
        except Exception as e:
            logger.error(f"Error in AutoGen conversation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()  # Use server local time for consistency
            }
    
    async def _run_autogen_conversation(
        self,
        agent_names: List[str],
        initial_message: str
    ) -> Dict[str, Any]:
        """Run conversation using AutoGen framework"""

        logger.info(f"Starting AutoGen conversation with {len(agent_names)} agents: {agent_names}")

        try:
            # Basic validation
            if not isinstance(initial_message, str):
                initial_message = str(initial_message)
            # Get the actual AutoGen agents
            active_agents = [self.agents[name] for name in agent_names]
            logger.info(f"Retrieved {len(active_agents)} active agents")

            # Validate agents have proper model clients
            for i, agent in enumerate(active_agents):
                agent_name = agent_names[i]
                if hasattr(agent, 'model_client'):
                    logger.info(f"Agent {agent_name} has model_client: {type(agent.model_client)}")
                else:
                    logger.warning(f"Agent {agent_name} missing model_client")

            # Create group chat using AutoGen RoundRobinGroupChat
            group_chat = RoundRobinGroupChat(
                participants=active_agents,
                termination_condition=MaxMessageTermination(max_messages=20)
            )
            logger.info("Created RoundRobinGroupChat")

            # Create initial message (guarantee proper TextMessage)
            try:
                user_message = TextMessage(content=initial_message, source="user")
                logger.info("Created TextMessage successfully")
            except Exception as tm_e:
                # Last-resort string cast
                logger.warning(f"Failed to build TextMessage: {tm_e}; using fallback plain string")
                user_message = TextMessage(content=str(initial_message), source="user")
            
            # Run the conversation without stream parameter
            messages = []
            try:
                logger.info("Running group chat...")
                # Try with the correct run method (without stream parameter)
                result = await group_chat.run(task=user_message)
                logger.info(f"Group chat completed, result type: {type(result)}")

                # Check if result has expected attributes
                if hasattr(result, 'messages'):
                    logger.info(f"Result has {len(result.messages)} messages")
                else:
                    logger.warning("Result does not have messages attribute")

                if hasattr(result, 'stop_reason'):
                    logger.info(f"Stop reason: {result.stop_reason}")
                else:
                    logger.info("No stop_reason attribute found")

                # Defensive: some AutoGen internals may have produced raw dict messages
                raw_msgs = getattr(result, 'messages', []) if result else []
                sanitized = []
                for m in raw_msgs:
                    if isinstance(m, dict):
                        # Wrap dict into a synthetic TextMessage-like structure for downstream uniformity
                        wrapped = {
                            "timestamp": datetime.now().isoformat(),
                            "source": m.get("source") or m.get("role") or "agent",
                            "content": m.get("content") or json.dumps({k: v for k, v in m.items() if k not in ("source","role","content")})[:400],
                            "message_type": "RawDictWrapped"
                        }
                        sanitized.append(wrapped)
                    else:
                        sanitized.append(m)
                # Replace messages attribute if we altered anything (best-effort)
                if sanitized and len(sanitized) != len(raw_msgs) or any(isinstance(x, dict) for x in raw_msgs):
                    try:
                        result.messages = [x for x in sanitized if not isinstance(x, dict)]  # keep original objects
                        # Append converted dicts as TextMessage style dicts to messages list we will return later
                        # We'll merge them in normalization below
                    except Exception:
                        pass

                def _normalize_autogen_message(msg_obj, timestamp_offset_ms=0):
                    """Normalize AutoGen message with unique timestamp using server local time"""
                    base_time = datetime.now()  # Use server local time for consistency
                    if timestamp_offset_ms > 0:
                        from datetime import timedelta
                        base_time = base_time + timedelta(milliseconds=timestamp_offset_ms)
                    
                    return {
                        "timestamp": base_time.isoformat(),
                        "source": getattr(msg_obj, 'source', 'unknown'),
                        "content": getattr(msg_obj, 'content', str(msg_obj)),
                        "message_type": type(msg_obj).__name__
                    }

                if hasattr(result, 'messages'):
                    for idx, m in enumerate(result.messages):
                        try:
                            # Skip any stray dicts (already wrapped above)
                            if isinstance(m, dict):
                                continue
                            # Add small offset to ensure unique timestamps (idx * 100ms)
                            messages.append(_normalize_autogen_message(m, timestamp_offset_ms=idx * 100))
                        except Exception as norm_e:
                            logger.warning(f"Failed to normalize AutoGen message: {norm_e}")
                # Include any wrapped raw dict messages we created earlier
                for m in sanitized:
                    if isinstance(m, dict) and m.get("message_type") == "RawDictWrapped":
                        messages.append(m)
                else:
                    # Fallback simulated multi-agent exchange
                    base_resp = f"I understand you need help with: {initial_message}. As a cloud migration architect, I can provide guidance on strategy, risk assessment, and best practices."
                    messages.append({
                        "timestamp": datetime.now().isoformat(),
                        "source": "migration_architect",
                        "content": base_resp,
                        "message_type": "TextMessage"
                    })
                    if len(agent_names) > 1:
                        devops_resp = "From a DevOps perspective, I can assist with infrastructure automation, CI/CD pipelines, and deployment strategies."
                        messages.append({
                            "timestamp": datetime.now().isoformat(),
                            "source": agent_names[1],
                            "content": devops_resp,
                            "message_type": "TextMessage"
                        })
                
            except Exception as inner_e:
                logger.error(f"AutoGen conversation failed with error: {inner_e}")
                logger.error(f"Error type: {type(inner_e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")

                # Check if this is a message type registration error
                if "Message type" in str(inner_e) and "not registered" in str(inner_e):
                    logger.warning("Detected message type registration error, using enhanced fallback")
                    # Use the fallback conversation method instead
                    fallback_result = await self._run_fallback_conversation(agent_names, initial_message)
                    return fallback_result

                # Create fallback responses for other errors
                messages = [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "source": "migration_architect",
                        "content": f"Thank you for your question: '{initial_message}'. I'm here to help with your cloud migration strategy and planning.",
                        "message_type": "TextMessage"
                    }
                ]

                for agent_name in agent_names[1:3]:  # Add 1-2 more responses
                    agent_response = self._get_agent_fallback_response(agent_name, initial_message)
                    messages.append({
                        "timestamp": datetime.now().isoformat(),
                        "source": agent_name,
                        "content": agent_response,
                        "message_type": "TextMessage"
                    })
            # Provide minimal derived structures for downstream processing even in fallback
            recs = [
                {
                    "agent": m.get("source"),
                    "recommendation": m.get("content")
                } for m in messages[:2]
            ]
            actions = [
                {
                    "agent": messages[0].get("source"),
                    "action": "Review above high-level guidance and supply more specific project constraints for deeper analysis."
                }
            ] if messages else []
            return {
                "status": "success",
                "messages": messages,
                "total_messages": len(messages),
                "mode": "autogen",
                "recommendations": recs,
                "action_items": actions,
                "fallback_used": True
            }
            
        except Exception as e:
            logger.error(f"Error running AutoGen conversation: {e}")
            return {
                "status": "error", 
                "error": str(e),
                "messages": [],
                "mode": "autogen"
            }
    
    def _get_agent_fallback_response(self, agent_name: str, user_message: str) -> str:
        """Generate fallback responses for different agent types"""
        responses = {
            "migration_architect": f"As a cloud migration architect, I can help you plan and execute your migration strategy for: {user_message[:100]}...",
            "devops_expert": "From a DevOps perspective, I can assist with infrastructure automation, CI/CD pipelines, and deployment strategies.",
            "security_expert": "I'll help ensure your migration maintains security best practices, compliance requirements, and data protection standards.",
            "cost_optimizer": "I can analyze cost implications and help optimize your cloud spending throughout the migration process.",
            "data_expert": "I'll provide guidance on data migration strategies, database optimization, and data architecture considerations.",
            "app_modernization": "I can help modernize your applications for cloud-native architectures and recommend containerization strategies."
        }
        return responses.get(agent_name, f"I'm the {agent_name} and I'm here to help with your cloud migration needs.")

    async def _run_fallback_conversation(
        self,
        agent_names: List[str],
        initial_message: str
    ) -> Dict[str, Any]:
        """Run conversation using LLM service as fallback"""

        try:
            messages = []

            # Check if WebSocket streaming is available for this session
            websocket_streaming = self.has_websocket_connection(self.current_session_id)

            # Get responses from each agent using LLM service
            for agent_name in agent_names:
                try:
                    # Get agent system message from the agent definitions
                    agent_definitions = {
                        "migration_architect": {
                            "role": "Senior Cloud Migration Architect",
                            "system_message": """You are a Senior Cloud Migration Architect with deep expertise in:
                            - AWS, Azure, and GCP migration strategies
                            - Application modernization and containerization
                            - Infrastructure as Code (Terraform, CloudFormation)
                            - Database migration and data lake architecture
                            - Security and compliance during migration

                            Your role is to provide strategic guidance on cloud migration projects.
                            Always consider cost optimization, security, scalability, and business continuity.
                            Provide detailed architectural recommendations with clear rationale.
                            Keep responses focused, practical, and actionable."""
                        },
                        "devops_expert": {
                            "role": "DevOps Automation Specialist",
                            "system_message": """You are a DevOps automation specialist focusing on:
                            - CI/CD pipeline design and implementation
                            - Kubernetes and container orchestration
                            - Infrastructure automation and monitoring
                            - Site reliability engineering (SRE) practices
                            - Cloud-native application deployment

                            Provide practical implementation guidance, code snippets, and automation scripts.
                            Focus on best practices for deployment, scaling, and operational excellence.
                            Always consider automation, monitoring, and reliability."""
                        },
                        "security_expert": {
                            "role": "Cloud Security & Compliance Expert",
                            "system_message": """You are a Cloud Security and Compliance expert specializing in:
                            - Cloud security frameworks (AWS Well-Architected, Azure Security Center)
                            - Identity and Access Management (IAM) design
                            - Data encryption and key management
                            - Compliance standards (SOC 2, GDPR, HIPAA, ISO 27001)
                            - Security monitoring and incident response

                            Ensure all recommendations meet security best practices and compliance requirements.
                            Identify potential security risks and provide concrete mitigation strategies.
                            Focus on zero-trust principles and defense in depth."""
                        },
                        "cost_optimizer": {
                            "role": "Cloud Cost Optimization Specialist",
                            "system_message": """You are a Cloud Cost Optimization specialist focused on:
                            - Cloud resource rightsizing and cost analysis
                            - Reserved instances and savings plans optimization
                            - Multi-cloud cost comparison and strategy
                            - FinOps practices and cost governance
                            - Resource lifecycle management

                            Analyze costs throughout migration planning and provide optimization recommendations.
                            Consider both immediate migration costs and long-term operational expenses.
                            Provide specific cost-saving strategies with quantifiable benefits."""
                        },
                        "data_expert": {
                            "role": "Data Migration & Analytics Expert",
                            "system_message": """You are a Data Migration and Analytics expert specializing in:
                            - Database migration strategies (rehost, replatform, refactor)
                            - Data lake and warehouse architecture
                            - ETL/ELT pipeline design and optimization
                            - Big data technologies (Spark, Hadoop, streaming)
                            - Data governance and quality assurance

                            Focus on data architecture, migration patterns, and analytics platform design.
                            Ensure data integrity, performance, and accessibility throughout migration.
                            Consider data lineage, quality, and governance requirements."""
                        },
                        "app_modernization": {
                            "role": "Application Modernization Expert",
                            "system_message": """You are an Application Modernization specialist focusing on:
                            - Legacy application assessment and refactoring strategies
                            - Microservices architecture and API design
                            - Serverless and event-driven architectures
                            - Application performance optimization
                            - Technology stack modernization (containerization, PaaS adoption)

                            Provide guidance on application transformation, technology choices, and implementation approaches.
                            Consider maintainability, scalability, and developer productivity.
                            Focus on practical modernization patterns and best practices."""
                        }
                    }

                    system_message = agent_definitions.get(agent_name, {}).get("system_message", f"You are a {agent_name} expert.")

                    # Call LLM service
                    from services.shared.service_client import get_service_client
                    client = await get_service_client()

                    llm_payload = {
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": initial_message}
                        ],
                        "model": self.llm_config.get("model"),
                        "temperature": 0.7,
                        "max_tokens": 1000,
                        "provider": self.llm_config.get("provider"),
                        "project_id": self.llm_config.get("project_id"),  # Required for ENFORCE_PROJECT_LLM policy
                        "process_type": "conversation"  # Use conversation process type
                    }

                    llm_response = await client.post("llm", "/api/llm/chat/completions", json=llm_payload)

                    if isinstance(llm_response, dict) and "choices" in llm_response and llm_response["choices"]:
                        agent_response = llm_response["choices"][0].get("message", {}).get("content", "")
                    else:
                        agent_response = f"As a {agent_name}, I can help you with your cloud migration needs."

                    messages.append({
                        "timestamp": datetime.now().isoformat(),
                        "source": agent_name,
                        "content": agent_response,
                        "message_type": "LLMServiceResponse"
                    })

                    # Stream agent response if WebSocket connected
                    if websocket_streaming:
                        await self.stream_message_to_websocket(self.current_session_id, "agent_response", {
                            "agent_name": agent_name,
                            "content": agent_response,
                            "message_type": "LLMServiceResponse"
                        })

                except Exception as e:
                    logger.error(f"Error getting response from {agent_name}: {e}")
                    # Add a fallback response for this agent
                    fallback_response = self._get_agent_fallback_response(agent_name, initial_message)
                    messages.append({
                        "timestamp": datetime.now().isoformat(),
                        "source": agent_name,
                        "content": fallback_response,
                        "message_type": "FallbackResponse",
                        "error": str(e)
                    })

            # Ensure we always have at least one message
            if not messages:
                logger.warning("No messages generated, creating default response")
                messages.append({
                    "timestamp": datetime.now().isoformat(),
                    "source": "migration_architect",
                    "content": f"Thank you for your question: '{initial_message}'. I'm here to help with your cloud migration strategy and planning.",
                    "message_type": "DefaultResponse"
                })

            return {
                "status": "success",
                "messages": messages,
                "total_messages": len(messages),
                "mode": "llm_service_fallback"
            }

        except Exception as e:
            logger.error(f"Error running fallback conversation: {e}")
            # Return mock conversation as final fallback
            return self._generate_mock_conversation(agent_names, initial_message)
    
    def _generate_mock_conversation(self, agent_names: List[str], initial_message: str) -> Dict[str, Any]:
        """Generate mock conversation when neither AutoGen nor OpenAI is available"""

        logger.info(f"Generating mock conversation for {len(agent_names)} agents")

        mock_responses = {
            "migration_architect": f"As a Migration Architect, I recommend analyzing your current infrastructure for '{initial_message[:50]}...'. Consider cloud-native patterns and scalability requirements.",
            "devops_expert": f"From a DevOps perspective on '{initial_message[:50]}...', implement CI/CD pipelines early and use Infrastructure as Code.",
            "security_expert": f"Regarding security for '{initial_message[:50]}...', ensure compliance frameworks and zero-trust architecture are in place.",
            "cost_optimizer": f"For cost optimization regarding '{initial_message[:50]}...', consider reserved instances and right-sizing resources.",
            "data_expert": f"From a data migration standpoint on '{initial_message[:50]}...', plan for data validation and ETL pipelines.",
            "app_modernization": f"For application modernization regarding '{initial_message[:50]}...', consider microservices and containerization strategies."
        }

        messages = []
        for agent_name in agent_names:
            response = mock_responses.get(agent_name, f"As {agent_name}, I would provide specialized guidance for your question.")
            messages.append({
                "timestamp": datetime.now().isoformat(),
                "source": agent_name,
                "content": response,
                "message_type": "MockResponse",
                "is_mock": True
            })

        # Ensure we always have at least one message
        if not messages:
            messages.append({
                "timestamp": datetime.now().isoformat(),
                "source": "migration_architect",
                "content": f"Thank you for your question: '{initial_message}'. I'm here to help with your cloud migration strategy and planning.",
                "message_type": "DefaultMockResponse",
                "is_mock": True
            })

        logger.info(f"Generated {len(messages)} mock messages")

        return {
            "status": "success",
            "messages": messages,
            "total_messages": len(messages),
            "mode": "mock"
        }
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format project + gathered context for the conversation.

        Accepts a context dict that may include gathered keys:
          - vector_snippets: List[ {text, score, metadata} ]
          - graph_facts: List[ {text, category, confidence} ]
          - document_insights: List[ {title, summary, category} ]
          - provided_context: original project context
        
        IMPORTANT: This context is for the LLM's internal use only.
        The LLM should analyze this data and provide a polished answer to the user,
        NOT echo the raw context back.
        """
        try:
            project_ctx = context.get("provided_context") if isinstance(context, dict) else None
        except Exception:
            project_ctx = None

        lines: List[str] = [
            "=== CONTEXT FOR INTERNAL ANALYSIS (DO NOT SHOW TO USER) ===",
            "",
            "INSTRUCTIONS:",
            "- Analyze the context below to answer the user's question",
            "- Provide a polished, professional response in natural language",
            "- DO NOT include raw context snippets, vector scores, or metadata in your response",
            "- DO NOT repeat this context section back to the user",
            "- If information is missing, say so concisely without listing what data you have",
            "",
            "PROJECT CONTEXT:"
        ]
        
        if project_ctx:
            if project_ctx.get("project_name"):
                lines.append(f"- Project: {project_ctx['project_name']}")
            for key in ["current_infrastructure", "target_cloud", "timeline", "budget"]:
                if project_ctx.get(key):
                    lines.append(f"- {key.replace('_',' ').title()}: {project_ctx[key]}")
            if project_ctx.get("migration_goals"):
                lines.append("- Migration Goals: " + ", ".join(project_ctx["migration_goals"]))
            if project_ctx.get("constraints"):
                lines.append("- Constraints: " + ", ".join(project_ctx["constraints"]))
        else:
            lines.append("(No explicit project context provided)")

        # Vector snippets section
        snippets = context.get("vector_snippets") if isinstance(context, dict) else None
        if snippets:
            lines.append("")
            lines.append("RELEVANT KNOWLEDGE (from documents):")
            for i, sn in enumerate(snippets[:5]):
                txt = (sn.get("text") or "").strip().replace('\n', ' ')
                if len(txt) > 280:
                    txt = txt[:277] + "..."
                lines.append(f"- {txt}")

        # Graph facts
        facts = context.get("graph_facts") if isinstance(context, dict) else None
        if facts:
            lines.append("")
            lines.append("KEY FACTS (from knowledge graph):")
            for i, f in enumerate(facts[:8]):
                txt = (f.get("text") or "").strip().replace('\n', ' ')
                if len(txt) > 200:
                    txt = txt[:197] + "..."
                cat = f.get("category") or "general"
                lines.append(f"- [{cat}] {txt}")

        # Document insights
        insights = context.get("document_insights") if isinstance(context, dict) else None
        if insights:
            lines.append("")
            lines.append("DOCUMENT INSIGHTS:")
            for i, ins in enumerate(insights[:5]):
                title = ins.get("title") or ins.get("category") or f"Insight {i+1}"
                summary = (ins.get("summary") or "").strip().replace('\n', ' ')
                if len(summary) > 240:
                    summary = summary[:237] + "..."
                lines.append(f"- {title}: {summary}")

        # Conversation history
        conversation_history = context.get("conversation_history") if isinstance(context, dict) else None
        if conversation_history:
            lines.append("")
            lines.append("PREVIOUS CONVERSATION:")
            lines.append(conversation_history)

        # If no contextual signals at all, add guidance note
        if not snippets and not facts and not insights and not conversation_history:
            lines.append("")
            lines.append("NOTE: No contextual data available. Answer based on general knowledge and explicitly state assumptions.")

        lines.append("")
        lines.append("=== END OF CONTEXT ===")
        lines.append("")

        return "\n".join(lines)
    
    async def _process_conversation_result(
        self,
        conversation_result: Dict[str, Any],
        start_time: datetime,
        agent_names: List[str]
    ) -> Dict[str, Any]:
        """Process and structure the conversation results"""

        if conversation_result["status"] == "error":
            return conversation_result

        messages = conversation_result.get("messages", [])

        # Check if WebSocket streaming is available
        websocket_streaming = self.has_websocket_connection(self.current_session_id)

        # Extract key insights from each agent
        agent_contributions = {}
        recommendations = []
        action_items = []

        for message in messages:
            agent_name = message.get("source", "unknown")
            content = message.get("content", "")

            if agent_name not in agent_contributions:
                agent_contributions[agent_name] = []

            agent_contributions[agent_name].append({
                "timestamp": message.get("timestamp", datetime.now().isoformat()),
                "content": content
            })

            # Extract recommendations and action items
            if "recommend" in content.lower() or "suggest" in content.lower():
                recommendations.append({
                    "agent": agent_name,
                    "recommendation": content
                })

            if "action" in content.lower() or "next step" in content.lower():
                action_items.append({
                    "agent": agent_name,
                    "action": content
                })
        
        # Generate summary
        summary = self._generate_conversation_summary(messages, agent_contributions)

        # Stream recommendations and action items if WebSocket connected
        if websocket_streaming:
            # Stream recommendations
            if recommendations:
                await self.stream_message_to_websocket(self.current_session_id, "recommendations_ready", {
                    "recommendations": recommendations,
                    "count": len(recommendations)
                })

            # Stream action items
            if action_items:
                await self.stream_message_to_websocket(self.current_session_id, "action_items_ready", {
                    "action_items": action_items,
                    "count": len(action_items)
                })

        return {
            "status": "success",
            "session_id": self.current_session_id,
            "timestamp": start_time.isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "participating_agents": agent_names,
            "message_count": len(messages),
            "agent_contributions": agent_contributions,
            "recommendations": recommendations,
            "action_items": action_items,
            "summary": summary,
            "full_conversation": messages,
            "conversation_mode": conversation_result.get("mode", "unknown"),
            "autogen_enabled": AUTOGEN_AVAILABLE
        }
    
    def _generate_conversation_summary(
        self,
        messages: List[Dict[str, Any]], 
        agent_contributions: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate a structured summary of the conversation"""
        
        return {
            "total_messages": len(messages),
            "agents_participated": list(agent_contributions.keys()),
            "key_topics_discussed": self._extract_topics(messages),
            "main_recommendations": self._extract_main_recommendations(messages),
            "implementation_complexity": self._assess_complexity(messages),
            "estimated_timeline": self._extract_timeline_estimates(messages)
        }
    
    def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract main topics discussed in the conversation"""
        # Simple keyword-based topic extraction
        topics = set()
        
        topic_keywords = {
            "Security": ["security", "compliance", "encryption", "iam", "access"],
            "Cost Optimization": ["cost", "pricing", "budget", "savings", "optimization"],
            "Architecture": ["architecture", "design", "infrastructure", "components"],
            "Migration Strategy": ["migration", "strategy", "approach", "methodology"],
            "DevOps": ["ci/cd", "automation", "deployment", "pipeline", "devops"],
            "Data Migration": ["database", "data", "etl", "warehouse", "analytics"],
            "Application Modernization": ["application", "modernization", "microservices", "containers"]
        }
        
        for message in messages:
            content = message.get("content", "").lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in content for keyword in keywords):
                    topics.add(topic)
        
        return list(topics)
    
    def _extract_main_recommendations(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract main recommendations from the conversation"""
        recommendations = []
        
        for message in messages:
            content = message.get("content", "")
            lines = content.split('\n')
            
            for line in lines:
                if any(word in line.lower() for word in ["recommend", "suggest", "should", "must"]):
                    recommendations.append(line.strip())
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _assess_complexity(self, messages: List[Dict[str, Any]]) -> str:
        """Assess implementation complexity based on conversation content"""
        complexity_indicators = {
            "high": ["complex", "challenging", "difficult", "multi-phase", "enterprise"],
            "medium": ["moderate", "standard", "typical", "straightforward"],
            "low": ["simple", "easy", "basic", "minimal"]
        }
        
        content = " ".join([msg.get("content", "") for msg in messages]).lower()
        
        for level, keywords in complexity_indicators.items():
            if any(keyword in content for keyword in keywords):
                return level
        
        return "medium"  # Default
    
    def _extract_timeline_estimates(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract timeline estimates from the conversation"""
        import re
        
        content = " ".join([msg.get("content", "") for msg in messages])
        
        # Look for time patterns
        time_patterns = [
            r"(\d+)\s*(weeks?|months?|days?)",
            r"(Q[1-4]|quarter)",
            r"(\d+)\s*to\s*(\d+)\s*(weeks?|months?)"
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return str(matches[0])
        
        return None
    
    def get_conversation_history(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get conversation history for a session or all sessions"""
        if session_id:
            # Try repository first, then fall back to memory
            if self.conversation_repository:
                try:
                    repo_history = self.conversation_repository.get_session_history(session_id)
                    if repo_history:
                        logger.info(f"Retrieved {len(repo_history)} messages from repository for session {session_id}")
                        return repo_history
                except Exception as e:
                    logger.error(f"Error retrieving from repository: {e}")

            # Fall back to in-memory storage
            memory_history = [conv for conv in self.conversation_history if conv["session_id"] == session_id]
            if memory_history:
                logger.info(f"Retrieved {len(memory_history)} messages from memory for session {session_id}")
                return memory_history

            return []
        return self.conversation_history
    
    def get_available_agents(self) -> Dict[str, str]:
        """Get list of available agents and their descriptions"""
        return {
            "migration_architect": "Senior Cloud Migration Architect - Strategic guidance and architecture",
            "devops_expert": "DevOps Automation Specialist - CI/CD, containers, infrastructure automation",
            "security_expert": "Cloud Security & Compliance Expert - Security frameworks and compliance",
            "cost_optimizer": "Cloud Cost Optimization Specialist - Cost analysis and optimization",
            "data_expert": "Data Migration & Analytics Expert - Database and data platform migration",
            "app_modernization": "Application Modernization Expert - Legacy app transformation",
            "web_researcher": "Research Specialist - Current information and best practices"
        }

    async def test_agent_response(self, agent_name: str, test_message: str = "Hello, can you help me with cloud migration?") -> Dict[str, Any]:
        """Test a specific agent's response to verify AutoGen is working"""
        logger.info(f"Testing agent {agent_name} with message: {test_message}")

        if agent_name not in self.agents:
            return {"status": "error", "error": f"Agent {agent_name} not found"}

        try:
            # Create a simple test conversation
            test_session_id = f"test-{agent_name}-{int(time.time())}"
            result = await self.start_conversation(
                test_message,
                test_session_id,
                selected_agents=[agent_name]
            )

            # Check if we got any messages
            messages = result.get("full_conversation", [])
            if messages:
                logger.info(f"Test successful: Agent {agent_name} responded with {len(messages)} messages")
                return {"status": "success", "messages": messages, "agent": agent_name}
            else:
                logger.warning(f"Test failed: Agent {agent_name} produced no messages")
                return {"status": "error", "error": "No messages generated", "agent": agent_name}

        except Exception as e:
            logger.error(f"Test failed for agent {agent_name}: {e}")
            return {"status": "error", "error": str(e), "agent": agent_name}
    
    async def continue_conversation(
        self,
        session_id: str,
        follow_up_message: str
    ) -> Dict[str, Any]:
        """Continue an existing conversation with a follow-up message"""

        logger.info(f"Continuing conversation for session {session_id}")

        # Try to load conversation from repository first, then fall back to in-memory
        existing_conv = None
        original_context = {}
        original_result = {}
        participating_agents = ["migration_architect"]

        # Try to load from repository
        if self.conversation_repository:
            try:
                session_data = self.conversation_repository.get_session(session_id)
                if session_data:
                    logger.info(f"Found conversation in repository for session {session_id}")
                    # Reconstruct conversation structure from repository data
                    existing_conv = {
                        "session_id": session_id,
                        "context": session_data.get("context"),
                        "result": {
                            "participating_agents": session_data.get("participating_agents", ["migration_architect"]),
                            "full_conversation": self.conversation_repository.get_session_history(session_id)
                        }
                    }
                    original_context = session_data.get("context", {})
                    participating_agents = session_data.get("participating_agents", ["migration_architect"])
                    original_result = existing_conv["result"]
                else:
                    logger.warning(f"No conversation found in repository for session {session_id}")
            except Exception as e:
                logger.error(f"Error loading conversation from repository: {e}")

        # Fall back to in-memory storage if repository didn't work
        if not existing_conv:
            existing_conv = next(
                (conv for conv in self.conversation_history if conv["session_id"] == session_id),
                None
            )
            if existing_conv:
                logger.info(f"Found conversation in memory for session {session_id}")
                original_context = existing_conv.get("context", {})
                original_result = existing_conv.get("result", {})
                participating_agents = original_result.get("participating_agents", ["migration_architect"])

        if not existing_conv:
            logger.warning(f"No conversation found for session {session_id}")
            return {
                "status": "error",
                "error": f"No conversation found for session {session_id}"
            }

        logger.info(f"Found existing conversation with {len(participating_agents)} agents: {participating_agents}")

        # For AutoGen continuation, we need to build conversation history
        conversation_start_time = datetime.now()

        try:
            # Build conversation context with previous messages
            previous_messages = original_result.get("full_conversation", [])
            logger.info(f"Found {len(previous_messages)} previous messages in conversation")

            # Format the follow-up message with conversation history
            conversation_history = ""
            if previous_messages:
                conversation_history = "\n\n## Previous Conversation:\n"
                for msg in previous_messages[-5:]:  # Include last 5 messages for context
                    source = msg.get("source", "unknown")
                    content = msg.get("content", "")[:200]  # Truncate for brevity
                    conversation_history += f"**{source}**: {content}...\n"

            enhanced_message = f"{conversation_history}\n\n## New Question:\n{follow_up_message}"

            # Add the enhanced context to the original context
            enhanced_context = original_context.copy() if original_context else {}
            enhanced_context["conversation_history"] = conversation_history

            logger.info("Enhanced message with conversation history for continuation")

            # Use the same conversation flow but with enhanced context
            return await self.start_conversation(
                enhanced_message,
                session_id,
                context=enhanced_context,
                selected_agents=participating_agents
            )

        except Exception as e:
            logger.error(f"Error continuing conversation: {e}")
            # Fallback to simple continuation
            return await self.start_conversation(
                follow_up_message,
                session_id,
                context=original_context,
                selected_agents=participating_agents
            )
    
    async def chat_query(
        self,
        user_message: str,
        session_id: str,
        project_id: str,
        context: Dict[str, Any],
        process_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lightweight chat query with single agent and conversation memory
        
        Args:
            user_message: User's question
            session_id: Session ID for conversation persistence
            project_id: Project identifier
            context: Gathered context (vector + graph + docs)
            process_type: Optional process type for LLM config
            
        Returns:
            Structured response with answer, sources, entities
        """
        try:
            logger.info(f"Processing chat query for session {session_id}, project {project_id}")
            
            # Load conversation history (last 10 messages for context)
            history = await self._load_conversation_history(session_id, limit=10)
            logger.info(f"Loaded {len(history)} messages from conversation history")
            
            # Format context for chat agent
            formatted_context = self._format_context_for_chat(context, history)
            
            # Stream status if WebSocket available
            if self.has_websocket_connection(session_id):
                await self.stream_message_to_websocket(
                    session_id, "agent_thinking", 
                    {"message": "Analyzing your question..."}
                )
            
            # Use a lightweight approach: single agent with formatted context
            # Call LLM service with project context
            try:
                from .service_client import get_service_client
                
                # Build messages for the LLM
                messages = [
                    {"role": "system", "content": formatted_context},
                    {"role": "user", "content": user_message}
                ]
                
                # Call LLM service with project_id
                client = await get_service_client()
                llm_request = {
                    "messages": messages,
                    "project_id": project_id,
                    "temperature": 0.3,
                    "max_tokens": 1024
                }
                
                logger.info(f"Calling LLM service for project {project_id}")
                llm_response = await client.post("llm", "/chat/completions", json=llm_request)
                
                # Extract answer from LLM response
                if isinstance(llm_response, dict):
                    if "choices" in llm_response and len(llm_response["choices"]) > 0:
                        answer = llm_response["choices"][0]["message"]["content"]
                    elif "content" in llm_response:
                        answer = llm_response["content"]
                    elif "answer" in llm_response:
                        answer = llm_response["answer"]
                    else:
                        answer = str(llm_response)
                else:
                    answer = str(llm_response)
                
                logger.info(f"LLM service returned answer of length {len(answer)}")
                
            except Exception as e:
                logger.error(f"LLM service call failed: {e}", exc_info=True)
                # Fallback to simple response
                answer = await self._simple_chat_response(user_message, context, history)
            
            # Build structured response
            result = {
                "status": "success",
                "session_id": session_id,
                "answer": answer,
                "sources": self._extract_sources(context),
                "graph_entities": self._extract_entities(context),
                "timestamp": datetime.now().isoformat(),
                "conversation_context": {
                    "message_count": len(history) + 1,
                    "project_id": project_id
                }
            }
            
            # Persist to database
            if self.conversation_repository:
                await self._save_chat_message(session_id, user_message, result, project_id)
            
            # Stream completion
            if self.has_websocket_connection(session_id):
                await self.stream_message_to_websocket(
                    session_id, "chat_completed", {"result": result}
                )
            
            logger.info(f"Chat query completed for session {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Chat query failed for session {session_id}: {e}")
            return {
                "status": "error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _format_context_for_chat(
        self, 
        context: Dict[str, Any], 
        history: List[Dict[str, Any]]
    ) -> str:
        """Format gathered context and conversation history for agent"""
        parts = []
        
        # Conversation history
        if history:
            parts.append("## Conversation History:")
            for msg in history[-5:]:  # Last 5 exchanges
                source = msg.get('source', 'unknown')
                content = msg.get('content', '')[:200]  # Truncate long messages
                parts.append(f"{source}: {content}")
            parts.append("")
        
        # Vector search results
        if context.get('vector_snippets'):
            parts.append("## Relevant Document Excerpts:")
            for snippet in context['vector_snippets'][:5]:  # Top 5
                text = snippet.get('text', '')
                metadata = snippet.get('metadata', {})
                filename = metadata.get('filename', 'unknown')
                parts.append(f"From {filename}: {text[:300]}")
            parts.append("")
        
        # Graph facts
        if context.get('graph_facts'):
            parts.append("## Knowledge Graph Facts:")
            for fact in context['graph_facts'][:8]:  # Top 8
                parts.append(f"- {fact.get('text', '')} (category: {fact.get('category', 'general')})")
            parts.append("")
        
        # Document insights
        if context.get('document_insights'):
            parts.append("## Document Insights:")
            for insight in context['document_insights'][:5]:  # Top 5
                title = insight.get('title', 'Insight')
                summary = insight.get('summary', '')
                parts.append(f"- {title}: {summary[:200]}")
            parts.append("")
        
        parts.append("## Instructions:")
        parts.append("You are a helpful project assistant. Based on the above context, provide a clear and concise answer.")
        parts.append("If the answer is not in the context, say so clearly.")
        parts.append("Cite sources when possible using filename references.")
        parts.append("Be conversational but professional.")
        
        return "\n".join(parts)
    
    async def _simple_chat_response(
        self,
        user_message: str,
        context: Dict[str, Any],
        history: List[Dict[str, Any]]
    ) -> str:
        """Fallback simple response when AutoGen is not available"""
        # Extract relevant information from context
        vector_snippets = context.get('vector_snippets', [])
        graph_facts = context.get('graph_facts', [])
        
        if not vector_snippets and not graph_facts:
            return "I don't have enough context to answer this question. Please make sure your project has processed documents and a knowledge graph."
        
        # Build a simple response from context
        response_parts = ["Based on the available information:\n"]
        
        if vector_snippets:
            response_parts.append(f"From project documents: {vector_snippets[0].get('text', '')[:200]}...")
        
        if graph_facts:
            response_parts.append(f"\nKnowledge graph fact: {graph_facts[0].get('text', '')}")
        
        response_parts.append("\n\nFor more detailed analysis, please ensure the LLM service is properly configured.")
        
        return "\n".join(response_parts)
    
    def _extract_sources(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract source citations from context"""
        sources = []
        
        # Extract from vector snippets
        for snippet in context.get('vector_snippets', [])[:5]:
            metadata = snippet.get('metadata', {})
            sources.append({
                "filename": metadata.get('filename', 'unknown'),
                "content": snippet.get('text', '')[:300],
                "score": snippet.get('score', 0.0),
                "type": "document"
            })
        
        return sources
    
    def _extract_entities(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract related entities from context"""
        entities = []
        
        # Extract from graph facts
        for fact in context.get('graph_facts', [])[:8]:
            # Try to extract entity information from fact text
            entities.append({
                "name": fact.get('category', 'Unknown'),
                "type": fact.get('category', 'fact'),
                "properties": {
                    "text": fact.get('text', ''),
                    "confidence": fact.get('confidence', 0.0)
                }
            })
        
        return entities
    
    async def _load_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Load conversation history from repository"""
        if not self.conversation_repository:
            return []
        
        try:
            messages = self.conversation_repository.get_session_history(session_id)
            # Return last N messages
            return messages[-limit:] if len(messages) > limit else messages
        except Exception as e:
            logger.warning(f"Failed to load conversation history for session {session_id}: {e}")
            return []
    
    async def _save_chat_message(
        self,
        session_id: str,
        user_message: str,
        result: Dict[str, Any],
        project_id: str
    ):
        """Save chat message to repository"""
        if not self.conversation_repository:
            return
        
        try:
            # Create a minimal structured result for persistence
            structured_result = {
                "status": "success",
                "answer": result.get("answer", ""),
                "sources_count": len(result.get("sources", [])),
                "entities_count": len(result.get("graph_entities", []))
            }
            
            self.conversation_repository.save_conversation_result(
                session_id=session_id,
                user_message=user_message,
                context={"project_id": project_id},
                structured_result=structured_result
            )
            logger.info(f"Saved chat message for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to save chat message for session {session_id}: {e}")
