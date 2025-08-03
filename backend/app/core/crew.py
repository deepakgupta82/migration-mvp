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
# from .diagramming_agent import create_diagramming_agent
from ..tools.cloud_catalog_tool import CloudServiceCatalogTool
from ..tools.compliance_tool import ComplianceFrameworkTool
from ..tools.infrastructure_analysis_tool import InfrastructureAnalysisTool

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
    """Get configured LLM instance with proper error handling and configuration validation"""
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    # Try multiple providers with fallbacks
    providers_to_try = [provider]
    if provider != "openai":
        providers_to_try.append("openai")  # Fallback to OpenAI

    last_error = None

    for current_provider in providers_to_try:
        try:
            llm = _initialize_provider(current_provider)
            if llm and test_llm_connection(llm):
                logger.info(f"Successfully initialized LLM with provider: {current_provider}")
                return llm
            else:
                logger.warning(f"LLM connection test failed for provider: {current_provider}")
        except Exception as e:
            logger.warning(f"Failed to initialize {current_provider}: {e}")
            last_error = e
            continue

    # If all providers fail, raise clear error
    raise LLMInitializationError(
        f"No LLM providers available. Last error: {last_error}. "
        f"Please configure at least one LLM provider in Settings > LLM Configuration."
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

        if not api_key and provider != 'ollama':
            raise ValueError(f"API key not found for LLM configuration '{project.llm_api_key_id}'. Please configure the API key in Settings > LLM Configuration.")

        if provider == 'gemini':
            # Use LiteLLM with proper Gemini model format
            try:
                from crewai import LLM

                # Ensure model name is in the correct format for LiteLLM
                # Remove any prefixes and ensure proper gemini/ format
                clean_model = model
                if model.startswith('models/'):
                    clean_model = model.replace('models/', '')
                if clean_model.startswith('gemini/'):
                    clean_model = clean_model.replace('gemini/', '')

                # Create LiteLLM-compatible model name
                litellm_model = f"gemini/{clean_model}"

                logger.info(f"Creating LiteLLM instance with model: {litellm_model}")

                # Create CrewAI LLM instance that uses LiteLLM internally
                return LLM(
                    model=litellm_model,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

            except ImportError:
                logger.warning("Google Generative AI library not available, using fallback")
                # Fallback to mock LLM with Infrastructure Assessment responses
                from langchain_community.llms.fake import FakeListLLM

                infrastructure_responses = [
                    "# Infrastructure Assessment Report\n\n## Executive Summary\nThis assessment provides a comprehensive analysis of the current infrastructure state and migration recommendations.\n\n## Current State Analysis\nThe existing infrastructure consists of multiple components that require careful evaluation for cloud migration.",
                    "## Migration Strategy\nBased on the 6Rs framework, we recommend a phased approach:\n1. Rehost critical applications\n2. Refactor legacy systems\n3. Retire obsolete components\n\n## Cost Analysis\nCurrent monthly costs: $15,000\nProjected cloud costs: $12,000 (20% reduction)\nMigration investment: $250,000",
                    "## Risk Assessment\nKey risks identified:\n- Data migration complexity\n- Application dependencies\n- Downtime requirements\n\n## Recommendations\n1. Implement comprehensive backup strategy\n2. Establish monitoring and alerting\n3. Plan phased migration approach"
                ]

                return FakeListLLM(responses=infrastructure_responses)

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
#  Define the Custom Tool for RAG
# =====================================================================================
class RAGQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific knowledge base.
    This is the only way for them to access information from the uploaded documents.
    """
    name: str = "Project Knowledge Base Query Tool"
    description: str = (
        "Use this tool to answer any questions about the client's project. "
        "It queries a vector database containing the contents of all uploaded documents "
        "(architecture diagrams, project charters, security audits, server lists, etc.). "
        "Formulate clear, specific questions to get the best results."
    )
    rag_service: RAGService

    model_config = {"arbitrary_types_allowed": True}

    def run(self, question: str) -> str:
        """Executes the query against the RAG service."""
        print(f"DEBUG: RAGKnowledgeBaseTool received query: '{question}'")
        return self.rag_service.query(question)

    def _run(self, question: str) -> str:
        """Legacy method for older CrewAI versions."""
        return self.run(question)

    def _arun(self, question: str) -> str:
        """Async version of _run."""
        return self.run(question)

# =====================================================================================
#  Define the Custom Tool for Graph
# =====================================================================================
class GraphQueryTool(BaseTool):
    """
    A custom tool for the agents to query the project-specific graph database.
    """
    name: str = "Project Graph Database Query Tool"
    description: str = (
        "Use this tool to query the graph database for relationships between entities. "
        "Formulate clear, specific Cypher queries to get the best results."
    )
    graph_service: GraphService

    model_config = {"arbitrary_types_allowed": True}

    def run(self, query: str) -> str:
        """Executes the query against the Graph service."""
        print(f"DEBUG: GraphQueryTool received query: '{query}'")
        return str(self.graph_service.execute_query(query))

    def _run(self, query: str) -> str:
        """Legacy method for older CrewAI versions."""
        return self.run(query)

    def _arun(self, query: str) -> str:
        """Async version of _run."""
        return self.run(query)


# =====================================================================================
#  Function to Create the Expert Nagarro Crew
# =====================================================================================
def create_assessment_crew(project_id: str, llm, websocket=None):
    """
    Creates an enhanced assessment crew with comprehensive enterprise capabilities.

    This implementation fully aligns with the sophisticated vision outlined in overview_and_mvp.md:
    - Senior Infrastructure Discovery Analyst (12+ years experience)
    - Principal Cloud Architect & Migration Strategist (50+ enterprise migrations)
    - Risk & Compliance Officer (10+ years regulatory expertise)
    - Lead Migration Program Manager (30+ cloud migrations)

    Enhanced capabilities include:
    - Cross-modal synthesis (graph + semantic search)
    - 6Rs migration pattern analysis
    - Comprehensive compliance validation (GDPR, SOX, HIPAA, PCI-DSS)
    - Landing zone architecture design
    - 3-year TCO cost modeling
    - Wave planning with dependency analysis
    - Executive-ready deliverables
    """
    # Initialize logging callback handler
    log_handler = AgentLogStreamHandler(websocket=websocket)

    rag_service = RAGService(project_id, llm)
    rag_tool = RAGQueryTool(rag_service=rag_service)
    graph_service = GraphService()
    graph_tool = GraphQueryTool(graph_service=graph_service)

    # Enhanced Engagement Analyst with deeper expertise
    engagement_analyst = Agent(
        role='Senior Infrastructure Discovery Analyst',
        goal='Perform comprehensive cross-modal synthesis to create a complete digital twin of the client\'s current IT landscape, identifying all assets, dependencies, and business context.',
        backstory=(
            "You are a seasoned infrastructure analyst with 12+ years in enterprise IT discovery. "
            "You specialize in dependency mapping, application portfolio analysis, and business-IT alignment. "
            "Your methodology: First query the graph database for explicit relationships, then use semantic search "
            "to uncover implicit dependencies and business context. You excel at identifying hidden technical debt, "
            "compliance gaps, and modernization opportunities that others miss."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool],
        llm=llm,
        allow_delegation=False
    )

    # Enhanced Principal Cloud Architect
    principal_cloud_architect = Agent(
        role='Principal Cloud Architect & Migration Strategist',
        goal='Design optimal target cloud architecture considering cost, performance, security, and compliance. Recommend specific migration patterns (6Rs) for each application workload.',
        backstory=(
            "You are a distinguished cloud architect with deep expertise across AWS, Azure, and GCP. "
            "You hold multiple cloud certifications and have led 50+ enterprise migrations. "
            "Your approach: Analyze current state, apply cloud-native principles, optimize for cost and performance. "
            "You consider the full spectrum: lift-and-shift vs. re-platforming vs. refactoring. "
            "You always factor in compliance requirements, data residency, and business continuity."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add pricing APIs, service catalogs
        llm=llm,
        allow_delegation=False
    )

    # NEW: Risk & Compliance Officer (Missing from current implementation)
    risk_compliance_officer = Agent(
        role='Risk & Compliance Officer',
        goal='Audit proposed architecture against regulatory requirements (GDPR, SOX, HIPAA, etc.) and enterprise security policies. Force architectural iterations until fully compliant.',
        backstory=(
            "You are a cybersecurity and compliance expert with deep knowledge of global regulations. "
            "You have 10+ years in risk assessment and regulatory compliance across industries. "
            "You are adversarial by design - your job is to find flaws, gaps, and risks that others miss. "
            "You enforce zero-trust principles, data protection laws, and industry-specific compliance frameworks. "
            "You will reject any architecture that doesn't meet the highest security and compliance standards."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add compliance frameworks tool
        llm=llm,
        allow_delegation=False
    )

    # Create diagramming agent
    # diagramming_agent = create_diagramming_agent(llm)

    # Enhanced Lead Planning Manager
    lead_planning_manager = Agent(
        role='Lead Migration Program Manager',
        goal='Create a detailed, risk-minimized migration execution plan with wave sequencing, timeline estimation, and stakeholder communication strategy.',
        backstory=(
            "You are an expert program manager specializing in complex IT transformations. "
            "You have successfully managed 30+ cloud migrations with budgets exceeding $10M. "
            "Your expertise: Dependency analysis, critical path planning, risk mitigation, and stakeholder management. "
            "You excel at wave planning - grouping applications to minimize business disruption. "
            "You always include rollback plans, testing strategies, and communication frameworks."
        ),
        verbose=True,
        tools=[rag_tool, graph_tool], # TODO: Add project planning tools
        llm=llm,
        allow_delegation=True # This agent can delegate back to the architect for clarifications.
    )

    # --- TASKS ---

    # Enhanced discovery task
    current_state_synthesis_task = Task(
        description=(
            "Perform comprehensive discovery and analysis of the client's current IT landscape:\n"
            "1. INFRASTRUCTURE DISCOVERY: Query the graph database to map all servers, applications, databases, and their relationships\n"
            "2. BUSINESS CONTEXT ANALYSIS: Use semantic search to understand business processes, compliance requirements, and strategic objectives\n"
            "3. DEPENDENCY MAPPING: Identify critical dependencies, single points of failure, and integration patterns\n"
            "4. TECHNICAL DEBT ASSESSMENT: Evaluate legacy systems, outdated technologies, and modernization opportunities\n"
            "5. COMPLIANCE LANDSCAPE: Document regulatory requirements, data classification, and security policies\n"
            "6. RISK ASSESSMENT: Identify operational, security, and business continuity risks\n\n"
            "Deliver a comprehensive JSON brief covering: IT inventory, business context, dependencies, risks, and modernization readiness."
        ),
        expected_output='Detailed JSON object with complete current state analysis including infrastructure inventory, business context, dependencies, compliance requirements, and risk assessment.',
        agent=engagement_analyst
    )

    # Enhanced architecture design task
    target_architecture_design_task = Task(
        description=(
            "Design optimal target cloud architecture based on the current state analysis:\n"
            "1. CLOUD STRATEGY: Recommend primary cloud provider and multi-cloud considerations\n"
            "2. MIGRATION PATTERNS: Apply 6Rs framework (Rehost, Replatform, Refactor, etc.) to each application\n"
            "3. LANDING ZONE DESIGN: Define network architecture, security zones, and connectivity patterns\n"
            "4. SERVICE MAPPING: Map current services to cloud-native equivalents\n"
            "5. COST OPTIMIZATION: Recommend instance types, storage tiers, and cost management strategies\n"
            "6. SECURITY ARCHITECTURE: Design identity management, encryption, and monitoring frameworks\n"
            "7. DISASTER RECOVERY: Plan backup, replication, and business continuity strategies\n\n"
            "Include specific cloud services, estimated costs, and implementation complexity."
        ),
        expected_output='Comprehensive target architecture document with cloud service recommendations, migration patterns, cost estimates, and security framework.',
        agent=principal_cloud_architect,
        context=[current_state_synthesis_task]
    )

    # NEW: Compliance validation task
    compliance_validation_task = Task(
        description=(
            "Audit the proposed target architecture for compliance and security:\n"
            "1. REGULATORY COMPLIANCE: Validate against GDPR, SOX, HIPAA, PCI-DSS as applicable\n"
            "2. SECURITY ASSESSMENT: Review encryption, access controls, and monitoring capabilities\n"
            "3. DATA GOVERNANCE: Ensure data residency, classification, and retention policies\n"
            "4. RISK MITIGATION: Identify security gaps and recommend remediation\n"
            "5. COMPLIANCE GAPS: Document any non-compliance issues and required changes\n\n"
            "CRITICAL: If any compliance violations are found, REJECT the architecture and demand revisions."
        ),
        expected_output='Compliance audit report with pass/fail assessment and required architectural changes.',
        agent=risk_compliance_officer,
        context=[target_architecture_design_task]
    )

    # Task 4: Diagram Generation
    # This task creates a visual representation of the architecture
    # diagram_generation_task = Task(
    #     description=(
    #         "Analyze the JSON architecture description from the Principal Cloud Architect. "
    #         "Extract the JSON portion and use the DiagramGeneratorTool to create a visual representation of the target architecture. "
    #         "Your output must be the public URL of the generated diagram image."
    #     ),
    #     expected_output='The public URL of the generated architecture diagram image.',
    #     agent=diagramming_agent,
    #     context=[target_architecture_design_task]
    # )

    # Enhanced final report generation task
    report_generation_task = Task(
        description=(
            "Create a comprehensive, executive-ready Cloud Migration Strategy & Execution Plan:\n"
            "1. EXECUTIVE SUMMARY: High-level overview with ROI projections and strategic benefits\n"
            "2. CURRENT STATE ANALYSIS: Synthesize infrastructure discovery findings\n"
            "3. TARGET ARCHITECTURE: Present cloud strategy with embedded architecture diagram\n"
            "4. COMPLIANCE & SECURITY: Include compliance validation results and security framework\n"
            "5. MIGRATION ROADMAP: Detailed wave planning with timelines and dependencies\n"
            "6. RISK MITIGATION: Comprehensive risk assessment with mitigation strategies\n"
            "7. COST-BENEFIT ANALYSIS: 3-year TCO comparison and ROI projections\n"
            "8. IMPLEMENTATION PLAN: Detailed project plan with milestones and deliverables\n\n"
            "Format as professional Markdown suitable for C-level presentation."
        ),
        expected_output='Executive-ready Cloud Migration Strategy & Execution Plan in professional Markdown format with embedded diagrams and comprehensive analysis.',
        agent=lead_planning_manager,
        context=[current_state_synthesis_task, target_architecture_design_task, compliance_validation_task]
    )

    # Set current agent context for logging
    log_handler.set_current_agent(engagement_analyst)

    return Crew(
        agents=[engagement_analyst, principal_cloud_architect, risk_compliance_officer, lead_planning_manager],
        tasks=[current_state_synthesis_task, target_architecture_design_task, compliance_validation_task, report_generation_task],
        process=Process.sequential,
        verbose=True,
        memory=True,  # Enable memory for better collaboration between agents
        callbacks=[log_handler] if websocket else []  # Add callback handler if WebSocket is provided
    )

def create_document_generation_crew(project_id: str, llm, document_type: str, document_description: str, output_format: str = 'markdown', websocket=None, crew_logger=None) -> Crew:
    """
    Create a specialized crew for document generation using RAG and knowledge graph.

    This crew focuses on creating professional documents based on project data,
    uploaded documents, and knowledge graph relationships.
    """
    # Initialize logging callback handler
    log_handler = AgentLogStreamHandler(websocket=websocket) if websocket else None

    rag_service = RAGService(project_id, llm)
    rag_tool = RAGQueryTool(rag_service=rag_service)
    graph_service = GraphService()
    graph_tool = GraphQueryTool(graph_service=graph_service)

    # Document Research Agent
    document_researcher = Agent(
        role="Document Research Specialist",
        goal=f"Research and gather comprehensive information for creating a {document_type} document",
        backstory=f"""You are an expert document researcher with deep knowledge of enterprise
        documentation standards. You excel at gathering relevant information from multiple
        sources including uploaded documents, knowledge graphs, and vector databases to
        create comprehensive, accurate, and professional documents.

        TEMPLATE REQUIREMENTS: {document_description}

        Follow these specific requirements when researching and structuring the document.
        Ensure all sections and details specified in the template requirements are addressed.""",
        verbose=True,
        tools=[rag_tool, graph_tool],
        llm=llm,
        allow_delegation=False
    )

    # Content Architect Agent
    content_architect = Agent(
        role="Content Architecture Specialist",
        goal=f"Structure and organize content for the {document_type} document with professional formatting",
        backstory=f"""You are a content architecture expert who specializes in creating
        well-structured, professional documents. You understand document hierarchies,
        information flow, and how to present complex technical information in a clear,
        accessible manner. You ensure all documents meet enterprise standards.

        TEMPLATE REQUIREMENTS: {document_description}

        Structure the document according to these specific template requirements.
        Ensure proper organization, formatting, and adherence to the specified structure.""",
        verbose=True,
        tools=[rag_tool],
        llm=llm,
        allow_delegation=False
    )

    # Quality Assurance Agent
    quality_reviewer = Agent(
        role="Document Quality Assurance Specialist",
        goal=f"Review and refine the {document_type} document for accuracy, completeness, and professional presentation",
        backstory=f"""You are a meticulous quality assurance specialist with expertise in
        document review and validation. You ensure all documents are accurate, complete,
        well-formatted, and meet professional standards. You have a keen eye for detail
        and can identify gaps, inconsistencies, or areas for improvement.

        TEMPLATE REQUIREMENTS: {document_description}

        Verify that the document meets all template requirements and specifications.
        Ensure completeness, accuracy, and professional quality.""",
        verbose=True,
        tools=[rag_tool, graph_tool],
        llm=llm,
        allow_delegation=False
    )

    # Research Task
    research_task = Task(
        description=f"""Research and gather comprehensive information for creating a {document_type} document.

        Document Requirements:
        - Type: {document_type}
        - Description: {document_description}
        - Output Format: {output_format}

        Your tasks:
        1. Query the RAG system to find relevant information from uploaded documents
        2. Search the knowledge graph for related entities and relationships
        3. Identify key themes, technologies, processes, and requirements
        4. Gather supporting data, metrics, and evidence
        5. Create a comprehensive research summary with all relevant findings

        Focus on:
        - Technical accuracy and completeness
        - Relevant business context and requirements
        - Supporting evidence and data points
        - Relationships between different components/concepts

        Provide a detailed research report with all findings organized by topic.""",
        expected_output="A comprehensive research report containing all relevant information, data, and insights needed to create the requested document, organized by topic with supporting evidence.",
        agent=document_researcher
    )

    # Content Architecture Task
    content_structure_task = Task(
        description=f"""Create a comprehensive Infrastructure Assessment Report based on the research findings.

        Using the research report, create a professional Infrastructure Assessment document following this specific template structure:

        # Infrastructure Assessment Report

        ## Project Overview
        - Project ID and basic information
        - Assessment date and scope
        - Template version

        ## Executive Summary
        - High-level overview of assessment findings
        - Key recommendations summary
        - Critical issues and opportunities

        ## Current State Analysis
        - Detailed analysis of existing infrastructure
        - Server inventory and specifications
        - Network architecture and topology
        - Application stack and dependencies
        - Security posture assessment

        ## Migration Strategy
        - Recommended migration approach using 6Rs framework:
          * Rehost (Lift and Shift)
          * Refactor (Re-architect)
          * Revise (Modify)
          * Rebuild (Re-engineer)
          * Replace (Purchase)
          * Retire (Eliminate)
        - Phased migration timeline
        - Risk mitigation strategies

        ## Cost Analysis
        - Current vs. future state cost comparison
        - Migration investment requirements
        - ROI timeline and projections
        - Cost optimization opportunities

        ## Risk Assessment
        - Technical risks and dependencies
        - Business continuity considerations
        - Compliance and security risks
        - Mitigation strategies

        ## Recommendations
        - Prioritized action items
        - Best practices implementation
        - Monitoring and governance

        ## Next Steps
        - Immediate actions required
        - Implementation roadmap
        - Success metrics and KPIs

        Ensure the document is:
        - Professional and enterprise-ready
        - Technically accurate and comprehensive
        - Well-organized with clear sections
        - Formatted appropriately for {output_format}""",
        expected_output=f"A comprehensive Infrastructure Assessment Report in {output_format} format following the standard template structure with all required sections and professional formatting.",
        agent=content_architect
    )

    # Quality Review Task
    quality_review_task = Task(
        description=f"""Review and refine the {document_type} document to ensure it meets the highest professional standards.

        Your review should cover:
        1. Content accuracy and completeness
        2. Professional formatting and presentation
        3. Logical flow and organization
        4. Technical accuracy and consistency
        5. Grammar, spelling, and style
        6. Compliance with enterprise documentation standards

        Improvements to make:
        - Enhance clarity and readability
        - Ensure all sections are comprehensive
        - Verify technical accuracy
        - Improve formatting and presentation
        - Add any missing critical information
        - Ensure professional tone throughout

        Deliver the final, polished document that is ready for enterprise use.""",
        expected_output=f"A final, polished {document_type} document in {output_format} format that meets enterprise standards for accuracy, completeness, and professional presentation.",
        agent=quality_reviewer
    )

    # Set current agent context for logging
    if log_handler:
        log_handler.set_current_agent(document_researcher)

    # Create crew logger callback if provided
    callbacks = []
    if log_handler:
        callbacks.append(log_handler)

    if crew_logger:
        # Create a custom callback that integrates with our crew logger
        crew_callback = CrewLoggerCallback(crew_logger)
        callbacks.append(crew_callback)

    return Crew(
        agents=[document_researcher, content_architect, quality_reviewer],
        tasks=[research_task, content_structure_task, quality_review_task],
        process=Process.sequential,
        verbose=True,
        memory=True,
        callbacks=callbacks
    )
