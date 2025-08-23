"""
Deprecated: Monolithic CrewAI orchestration moved to services/ai-agent-service.
This module remains as a stub to avoid import errors during transition.
"""

from langchain.callbacks.base import BaseCallbackHandler
from typing import Any, Dict
from datetime import datetime
import os
import asyncio
import json
import logging

class CrewLoggerCallback(BaseCallbackHandler):
    """Custom callback handler that integrates with CrewInteractionLogger"""

    def __init__(self, crew_logger):
        super().__init__()
        self.crew_logger = crew_logger
        self.current_agent = None
        self.current_task = None

    def on_agent_start(self, agent, **kwargs):
        """Called when an agent starts"""
        self.current_agent = agent.role
        asyncio.create_task(self.crew_logger.log_agent_start(
            agent_name=agent.role,
            role=agent.role,
            goal=agent.goal,
            backstory=getattr(agent, 'backstory', '')
        ))

    def on_agent_finish(self, agent, **kwargs):
        """Called when an agent finishes"""
        asyncio.create_task(self.crew_logger.log_agent_complete(
            agent_name=agent.role,
            success=True
        ))

    def on_tool_start(self, tool, input_str, **kwargs):
        """Called when a tool starts"""
        if self.current_agent:
            asyncio.create_task(self.crew_logger.log_tool_call(
                agent_name=self.current_agent,
                tool_name=tool.__class__.__name__,
                function_name='execute',
                params={'input': input_str}
            ))

    def on_tool_end(self, output, **kwargs):
        """Called when a tool ends"""
        # Tool response logging is handled in the tool call completion
        pass

    def on_text(self, text, **kwargs):
        """Called when there's text output"""
        # Log reasoning steps if they contain thought patterns
        if self.current_agent and ('thought:' in text.lower() or 'action:' in text.lower()):
            asyncio.create_task(self.crew_logger.log_agent_reasoning(
                agent_name=self.current_agent,
                thought=text,
                action='processing'
            ))

def get_llm_class(provider: str):
    from .llm_utils import get_llm_class as _g
    return _g(provider)


def get_llm_and_model():
    from .llm_utils import LLMInitializationError
    raise LLMInitializationError("Deprecated path: use app.core.llm_factory or ai-agent-service.")

# BaseTool is now properly imported from crewai.tools

# =====================================================================================
# Agent Log Stream Handler for Real-time Monitoring
# =====================================================================================

class AgentLogStreamHandler(BaseCallbackHandler):
    """Custom callback handler to stream agent interactions via WebSocket"""

    def __init__(self, websocket=None):
        super().__init__()
        self.websocket = websocket
        self.current_agent = None
        self.current_task = None

    async def send_log(self, log_data: Dict[str, Any]):
        """Send log data via WebSocket if available"""
        if self.websocket:
            try:
                await self.websocket.send_text(json.dumps(log_data))
            except Exception as e:
                logging.error(f"Failed to send WebSocket log: {e}")

    async def send_detailed_log(self, agent_name, action, details):
        """Send detailed human-readable log message"""
        if self.websocket:
            try:
                message = f"{agent_name}: {action}"
                if details:
                    message += f" - {details}"
                await self.websocket.send_text(message)
            except Exception as e:
                logging.error(f"Failed to send detailed WebSocket log: {e}")

    def on_agent_action(self, action, **kwargs: Any) -> Any:
        """Called when an agent takes an action"""
        agent_name = getattr(self.current_agent, 'role', 'Unknown Agent')

        log_data = {
            "type": "agent_action",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "tool": action.tool,
            "tool_input": str(action.tool_input),
            "log": action.log if hasattr(action, 'log') else "",
            "action_description": f"{agent_name} is using {action.tool}"
        }

        # Send detailed WebSocket message
        if self.websocket:
            asyncio.create_task(self.send_detailed_log(f"🤖 {agent_name}", f"Using tool: {action.tool}", str(action.tool_input)[:200]))
            asyncio.create_task(self.send_log(log_data))

        logging.info(f"Agent Action: {log_data}")

    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """Called when a tool finishes execution"""
        agent_name = getattr(self.current_agent, 'role', 'Unknown Agent')
        output_preview = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)

        log_data = {
            "type": "tool_result",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "output": str(output)[:500] + "..." if len(str(output)) > 500 else str(output),
            "status": "success"
        }

        if self.websocket:
            asyncio.create_task(self.send_detailed_log(f"✅ {agent_name}", "Tool completed", output_preview))
            asyncio.create_task(self.send_log(log_data))

        logging.info(f"Tool Result: {log_data}")

    def on_tool_error(self, error: Exception, **kwargs: Any) -> Any:
        """Called when a tool encounters an error"""
        log_data = {
            "type": "tool_error",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": getattr(self.current_agent, 'role', 'Unknown Agent'),
            "error": str(error),
            "status": "error"
        }

        if self.websocket:
            asyncio.create_task(self.send_log(log_data))

        logging.error(f"Tool Error: {log_data}")

    def on_agent_finish(self, finish, **kwargs: Any) -> Any:
        """Called when an agent finishes its task"""
        agent_name = getattr(self.current_agent, 'role', 'Unknown Agent')

        log_data = {
            "type": "agent_finish",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "output": str(finish.return_values) if hasattr(finish, 'return_values') else str(finish),
            "status": "completed"
        }

        if self.websocket:
            asyncio.create_task(self.send_detailed_log(f"🎉 {agent_name}", "Task completed", "Moving to next agent"))
            asyncio.create_task(self.send_log(log_data))

        logging.info(f"Agent Finished: {log_data}")

    def on_agent_start(self, agent, **kwargs: Any) -> Any:
        """Called when an agent starts working"""
        agent_name = getattr(agent, 'role', 'Unknown Agent')
        self.current_agent = agent

        log_data = {
            "type": "agent_start",
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "goal": getattr(agent, 'goal', 'No goal specified'),
            "status": "started"
        }

        if self.websocket:
            asyncio.create_task(self.send_detailed_log(f"🚀 {agent_name}", "Starting task", getattr(agent, 'goal', '')[:100]))
            asyncio.create_task(self.send_log(log_data))

        logging.info(f"Agent Started: {log_data}")

    def set_current_agent(self, agent):
        """Set the current agent for context"""
        self.current_agent = agent

    def set_current_task(self, task):
        """Set the current task for context"""
        self.current_task = task

# Import other services and tools
logger = logging.getLogger(__name__)

# LLM selection
from .llm_utils import LLMInitializationError, test_llm_connection

def get_llm_and_model():
    """Get configured LLM instance with proper error handling - NO FALLBACKS"""
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    try:
        llm = _initialize_provider(provider)
        if llm and test_llm_connection(llm):
            logger.info(f"Successfully initialized LLM with provider: {provider}")
            return llm
        else:
            raise Exception(f"LLM connection test failed for provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to initialize {provider}: {e}")
        raise LLMInitializationError(
            f"Failed to initialize LLM provider '{provider}': {str(e)}. "
            f"Please check your configuration and API key in Settings > LLM Configuration."
        )

def _initialize_provider(provider: str):
    from .llm_factory import _instantiate_llm
    import os
    provider_norm = provider.lower()
    # Map env to minimal config then delegate to llm_factory for uniform behavior
    if provider_norm == 'openai':
        return _instantiate_llm('openai', os.getenv('OPENAI_MODEL_NAME', 'gpt-4o'), os.getenv('OPENAI_API_KEY'), 0.1, 4000)
    if provider_norm == 'anthropic':
        return _instantiate_llm('anthropic', os.getenv('ANTHROPIC_MODEL_NAME', 'claude-3-sonnet-20240229'), os.getenv('ANTHROPIC_API_KEY'), 0.1, 4000)
    if provider_norm in ('google', 'gemini'):
        return _instantiate_llm('gemini', os.getenv('GEMINI_MODEL_NAME', 'gemini-1.5-pro'), os.getenv('GEMINI_API_KEY'), 0.1, 4000)
    if provider_norm == 'ollama':
        return _instantiate_llm('ollama', os.getenv('OLLAMA_MODEL_NAME', 'llama3.1:8b'), None, 0.1, 4000)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

def get_project_llm(project):
    from .llm_factory import LLMProcessFactory
    lf = LLMProcessFactory()
    return lf._get_project_default_llm(project)

def get_project_crewai_llm(project):
    raise LLMInitializationError("Deprecated: CrewAI moved to ai-agent-service.")

# Agent logging setup
os.makedirs("logs", exist_ok=True)
agent_logger = logging.getLogger("agents")
agent_handler = logging.FileHandler("logs/agents.log")
agent_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not agent_logger.hasHandlers():
    agent_logger.addHandler(agent_handler)
agent_logger.setLevel(logging.INFO)

# Token usage logging
token_logger = logging.getLogger("tokens")
token_handler = logging.FileHandler("logs/tokens.log")
token_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
if not token_logger.hasHandlers():
    token_logger.addHandler(token_handler)
token_logger.setLevel(logging.INFO)

def log_token_usage(model_name: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, operation: str = "unknown"):
    """Log token usage for monitoring and cost tracking"""
    token_logger.info(
        f"Model: {model_name} | Operation: {operation} | "
        f"Prompt: {prompt_tokens} tokens | Completion: {completion_tokens} tokens | "
        f"Total: {total_tokens} tokens"
    )

# =====================================================================================
#  Tool definitions moved to backend/app/tools/ for better organization
# =====================================================================================
# RAGQueryTool -> backend/app/tools/rag_query_tool.py
# GraphQueryTool -> backend/app/tools/graph_query_tool.py


# =====================================================================================
#  Function to Create the Expert Nagarro Crew
# =====================================================================================
def create_assessment_crew(*args, **kwargs):
    raise RuntimeError("Use ai-agent-service for crews. This path is deprecated.")



def create_document_generation_crew(*args, **kwargs):
    raise RuntimeError("Use ai-agent-service for crews. This path is deprecated.")







