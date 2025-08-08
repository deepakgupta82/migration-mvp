from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import BaseModel
from langchain.callbacks.base import BaseCallbackHandler
from typing import Any, Dict, List, Optional
import json
import asyncio
from datetime import datetime
import os
import logging
import requests

# Disable AgentOps to avoid API key requirements
os.environ['AGENTOPS_API_KEY'] = ''
os.environ['AGENTOPS_DISABLED'] = 'true'
os.environ['AGENTOPS_ENABLED'] = 'false'

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

# Lazy import for LLM classes to improve startup time
_llm_classes = {}

def get_llm_class(provider: str):
    """Lazy load LLM classes to improve startup time"""
    if provider not in _llm_classes:
        if provider == 'openai':
            from langchain_openai import ChatOpenAI
            _llm_classes[provider] = ChatOpenAI
        elif provider == 'anthropic':
            from langchain_anthropic import ChatAnthropic
            _llm_classes[provider] = ChatAnthropic
        elif provider == 'google':
            from langchain_google_vertexai import ChatVertexAI
            _llm_classes[provider] = ChatVertexAI
        elif provider == 'ollama':
            from langchain_community.llms import Ollama
            _llm_classes[provider] = Ollama
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    return _llm_classes[provider]


def get_llm_and_model():
    """Get a default LLM instance for fallback scenarios"""
    try:
        # Try to use OpenAI with environment variable
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=openai_api_key,
                temperature=0.7
            )

        # Try to use Anthropic with environment variable
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_api_key:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-3-haiku-20240307",
                api_key=anthropic_api_key,
                temperature=0.7
            )

        # Try to use Ollama (local)
        try:
            from langchain_community.llms import Ollama
            # Test if Ollama is available
            import requests
            response = requests.get('http://localhost:11434/api/tags', timeout=2)
            if response.status_code == 200:
                return Ollama(model="llama2", base_url="http://localhost:11434")
        except:
            pass

        # If no LLM is available, raise an error
        raise Exception("No LLM provider available. Please configure OpenAI, Anthropic, or Ollama.")

    except Exception as e:
        raise Exception(f"Failed to create fallback LLM: {str(e)}")

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
from .rag_service import RAGService
from .graph_service import GraphService
# Import crew_factory locally to avoid circular imports
# from .diagramming_agent import create_diagramming_agent
from ..tools.cloud_catalog_tool import CloudServiceCatalogTool
from ..tools.compliance_tool import ComplianceFrameworkTool
from ..tools.infrastructure_analysis_tool import InfrastructureAnalysisTool
from ..tools.rag_query_tool import RAGQueryTool
from ..tools.graph_query_tool import GraphQueryTool

logger = logging.getLogger(__name__)

# LLM selection
class LLMInitializationError(Exception):
    """Custom exception for LLM initialization failures"""
    pass

def test_llm_connection(llm):
    """Test if LLM connection is working"""
    try:
        # Simple test query
        test_response = llm.invoke("Hello")
        return test_response is not None
    except Exception:
        return False

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
    """Initialize a specific LLM provider"""
    # Detailed configuration validation
    if provider == "openai":
        model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Please configure your OpenAI API key in the Settings > LLM Configuration section."
            )
        try:
            ChatOpenAI = get_llm_class('openai')
            return ChatOpenAI(model=model_name, api_key=api_key, temperature=0.1)
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAI LLM: {str(e)}. Please check your API key and model configuration.")

    elif provider == "anthropic":
        model_name = os.environ.get("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Please configure your Anthropic API key in the Settings > LLM Configuration section."
            )
        try:
            ChatAnthropic = get_llm_class('anthropic')
            return ChatAnthropic(model=model_name, api_key=api_key, temperature=0.1)
        except Exception as e:
            raise ValueError(f"Failed to initialize Anthropic LLM: {str(e)}. Please check your API key and model configuration.")

    elif provider == "google" or provider == "gemini":
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-pro")
        api_key = os.environ.get("GEMINI_API_KEY")
        project_id = os.environ.get("GEMINI_PROJECT_ID")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required. "
                "Please configure your Gemini API key in the Settings > LLM Configuration section."
            )
        if not project_id:
            raise ValueError(
                "GEMINI_PROJECT_ID environment variable is required. "
                "Please configure your Google Cloud Project ID in the Settings > LLM Configuration section."
            )
        try:
            ChatVertexAI = get_llm_class('google')
            return ChatVertexAI(model=model_name, temperature=0.1, project=project_id)
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini LLM: {str(e)}. Please check your API key, project ID, and model configuration.")

    elif provider == "ollama":
        model_name = os.environ.get("OLLAMA_MODEL_NAME", "llama2")
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            Ollama = get_llm_class('ollama')
            return Ollama(model=model_name, base_url=ollama_host, temperature=0.1)
        except Exception as e:
            raise ValueError(f"Failed to initialize Ollama LLM: {str(e)}. Please ensure Ollama is running at {ollama_host} and the model {model_name} is available.")

    elif provider == "custom":
        model_name = os.environ.get("CUSTOM_MODEL_NAME", "custom-model")
        custom_endpoint = os.environ.get("CUSTOM_ENDPOINT")
        api_key = os.environ.get("CUSTOM_API_KEY")
        if not custom_endpoint:
            raise ValueError(
                "CUSTOM_ENDPOINT environment variable is required. "
                "Please configure your custom endpoint URL in the Settings > LLM Configuration section."
            )
        try:
            # For custom endpoints, we'd typically use OpenAI-compatible interface
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name,
                api_key=api_key or "dummy",
                base_url=custom_endpoint,
                temperature=0.1
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize Custom LLM: {str(e)}. Please check your endpoint URL and configuration.")
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {provider}. "
            f"Supported providers are: openai, anthropic, gemini, ollama, custom. "
            f"Please configure a valid provider in the Settings > LLM Configuration section."
        )

def get_project_llm(project):
    """Get LLM instance from project-specific configuration"""
    try:
        # Check if project has LLM configuration
        if not hasattr(project, 'llm_provider') or not hasattr(project, 'llm_model') or not project.llm_provider or not project.llm_model:
            raise ValueError("Project does not have LLM configuration. Please configure LLM settings for this project.")

        # Note: We'll get the API key from the project's LLM configuration in the database

        # Get project-specific configuration
        provider = project.llm_provider
        model = project.llm_model
        temperature = float(project.llm_temperature or '0.1')
        max_tokens = int(project.llm_max_tokens or '4000')

        # Get API key from LLM configuration database using project's api_key_id
        api_key = None
        if project.llm_api_key_id:
            try:
                # Import here to avoid circular imports
                import requests
                from app.core.project_service import ProjectServiceClient

                project_service = ProjectServiceClient()
                response = requests.get(
                    f"{project_service.base_url}/llm-configurations/{project.llm_api_key_id}",
                    headers=project_service._get_auth_headers(),
                    timeout=5  # Reduce timeout to 5 seconds
                )

                if response.status_code == 200:
                    llm_config = response.json()
                    api_key = llm_config.get('api_key')
                else:
                    raise ValueError(f"LLM configuration '{project.llm_api_key_id}' not found in database")
            except requests.exceptions.Timeout:
                raise ValueError(f"Timeout getting LLM configuration '{project.llm_api_key_id}'. Please check the project service connection.")
            except Exception as e:
                raise ValueError(f"Failed to get LLM configuration '{project.llm_api_key_id}': {str(e)}")

        # No environment variable fallback: require explicit project LLM configuration
        if not api_key and provider != 'ollama':
            raise ValueError(
                f"API key not found for {provider} in project LLM configuration '{project.llm_api_key_id}'. "
                f"Please configure an API key in Project Settings > LLM Configuration."
            )

        if provider == 'gemini':
            # Use LangChain ChatGoogleGenerativeAI for compatibility with EntityExtractionAgent
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                # Ensure model name is in the correct format
                clean_model = model
                if model.startswith('models/'):
                    clean_model = model.replace('models/', '')
                if clean_model.startswith('gemini/'):
                    clean_model = clean_model.replace('gemini/', '')

                logger.info(f"Creating LangChain Gemini instance with model: {clean_model}")

                # Create LangChain-compatible Gemini instance
                return ChatGoogleGenerativeAI(
                    model=clean_model,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

            except ImportError as import_error:
                logger.error("Google Generative AI library not available")
                raise ValueError(f"Required library for Gemini not installed: {str(import_error)}")

            except Exception as e:
                logger.error(f"Failed to initialize Gemini LLM: {str(e)}")
                raise ValueError(f"Failed to initialize Gemini LLM: {str(e)}")
        elif provider == 'openai':
            return ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == 'anthropic':
            return ChatAnthropic(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == 'ollama':
            return Ollama(
                model=model,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    except Exception as e:
        logging.error(f"Error getting project LLM configuration: {str(e)}")
        raise

def get_project_crewai_llm(project):
    """Get CrewAI-compatible LLM instance from project-specific configuration"""
    try:
        # Check if project has LLM configuration
        if not hasattr(project, 'llm_provider') or not hasattr(project, 'llm_model') or not project.llm_provider or not project.llm_model:
            raise ValueError("Project does not have LLM configuration. Please configure LLM settings for this project.")

        # Get project-specific configuration
        provider = project.llm_provider
        model = project.llm_model
        temperature = float(project.llm_temperature or '0.1')
        max_tokens = int(project.llm_max_tokens or '4000')

        # Get API key from LLM configuration database using project's api_key_id
        api_key = None
        if project.llm_api_key_id:
            try:
                # Import here to avoid circular imports
                import requests
                from app.core.project_service import ProjectServiceClient

                project_service = ProjectServiceClient()
                response = requests.get(
                    f"{project_service.base_url}/llm-configurations/{project.llm_api_key_id}",
                    headers=project_service._get_auth_headers(),
                    timeout=5  # Reduce timeout to 5 seconds
                )

                if response.status_code == 200:
                    llm_config = response.json()
                    api_key = llm_config.get('api_key')
                else:
                    raise ValueError(f"LLM configuration '{project.llm_api_key_id}' not found in database")
            except requests.exceptions.Timeout:
                raise ValueError(f"Timeout getting LLM configuration '{project.llm_api_key_id}'. Please check the project service connection.")
            except Exception as e:
                raise ValueError(f"Failed to get LLM configuration '{project.llm_api_key_id}': {str(e)}")

        # No environment variable fallback: require explicit project LLM configuration
        if not api_key and provider != 'ollama':
            raise ValueError(
                f"API key not found for {provider} in project LLM configuration '{project.llm_api_key_id}'. "
                f"Please configure an API key in Project Settings > LLM Configuration."
            )

        if provider == 'gemini':
            # Use CrewAI LLM for document generation
            try:
                from crewai import LLM

                # Ensure model name is in the correct format for LiteLLM
                clean_model = model
                if model.startswith('models/'):
                    clean_model = model.replace('models/', '')
                if clean_model.startswith('gemini/'):
                    clean_model = clean_model.replace('gemini/', '')

                # Create LiteLLM-compatible model name
                litellm_model = f"gemini/{clean_model}"

                logger.info(f"Creating CrewAI LLM instance with model: {litellm_model}")

                # Create CrewAI LLM instance that uses LiteLLM internally
                return LLM(
                    model=litellm_model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

            except ImportError as import_error:
                logger.error("CrewAI library not available")
                raise ValueError(f"Required library for CrewAI not installed: {str(import_error)}")

            except Exception as e:
                logger.error(f"Failed to initialize CrewAI Gemini LLM: {str(e)}")
                raise ValueError(f"Failed to initialize CrewAI Gemini LLM: {str(e)}")
        elif provider == 'openai':
            # For CrewAI, we can use the same ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == 'anthropic':
            # For CrewAI, we can use the same ChatAnthropic
            return ChatAnthropic(
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == 'ollama':
            # For CrewAI, we can use the same Ollama
            return Ollama(
                model=model,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    except Exception as e:
        logging.error(f"Error getting project CrewAI LLM configuration: {str(e)}")
        raise

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
def create_assessment_crew(project_id: str, llm, websocket=None):
    """
    Creates an enhanced assessment crew with comprehensive enterprise capabilities.
    Uses the centralized crew factory for consistent crew creation.

    This implementation fully aligns with the sophisticated vision outlined in overview_and_mvp.md:
    - Senior Infrastructure Discovery Analyst (12+ years experience)
    - Principal Cloud Architect & Migration Strategist (50+ enterprise migrations)
    - Risk & Compliance Officer (10+ years regulatory expertise)
    - Lead Migration Program Manager (30+ cloud migrations)
    """
    from .crew_factory import crew_factory
    return crew_factory.create_assessment_crew(project_id, llm, websocket)



def create_document_generation_crew(project_id: str, llm, document_type: str, document_description: str, output_format: str = 'markdown', websocket=None, crew_logger=None) -> Crew:
    """
    Create a specialized crew for document generation using RAG and knowledge graph.
    Uses the centralized crew factory for consistent crew creation.
    """
    from .crew_factory import crew_factory
    return crew_factory.create_document_generation_crew(project_id, llm, document_type, document_description, output_format, websocket, crew_logger)







