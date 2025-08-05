"""
Dynamic Crew Loader - Loads crew definitions from YAML configuration
"""

import yaml
import os
import json
from typing import Dict, List, Any
from crewai import Agent, Task, Crew, Process
from .rag_service import RAGService
from .graph_service import GraphService
# from ..tools.hybrid_search_tool import HybridSearchTool
# from ..tools.live_data_fetch_tool import LiveDataFetchTool
# from ..tools.lessons_learned_tool import LessonsLearnedTool
# from ..tools.context_tool import ContextTool
from .crew import RAGQueryTool, GraphQueryTool
from .crew import AgentLogStreamHandler
import logging

logger = logging.getLogger(__name__)

class CrewDefinitionLoader:
    """Loads and manages crew definitions from YAML configuration"""

    def __init__(self, config_path: str = None, client_profile_path: str = None):
        if config_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(backend_dir, "crew_definitions.yaml")
        
        if client_profile_path is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            client_profile_path = os.path.join(backend_dir, "..", "config", "client_profile.json")

        self.config_path = config_path
        self.client_profile_path = client_profile_path
        self.config = None
        self.client_profile = None
        self.load_config()
        self.load_client_profile()

    def load_config(self) -> Dict[str, Any]:
        """Load crew definitions from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            logger.info(f"Loaded crew definitions from {self.config_path}")
            return self.config
        except FileNotFoundError:
            logger.error(f"Crew definitions file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise

    def load_client_profile(self) -> Dict[str, Any]:
        """Load client profile from JSON file"""
        try:
            with open(self.client_profile_path, 'r', encoding='utf-8') as file:
                self.client_profile = json.load(file)
            logger.info(f"Loaded client profile from {self.client_profile_path}")
            return self.client_profile
        except FileNotFoundError:
            logger.warning(f"Client profile not found: {self.client_profile_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON file: {e}")
            raise

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save crew definitions to YAML file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)
            self.config = config
            logger.info(f"Saved crew definitions to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving YAML file: {e}")
            raise

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        if self.config is None:
            self.load_config()
        return self.config

    def get_available_tools(self) -> Dict[str, Any]:
        """Get available tools mapping"""
        config = self.get_config()
        return {tool['id']: tool for tool in config.get('available_tools', [])}

    def create_tool_instances(self, tool_ids: List[str], project_id: str, llm) -> List[Any]:
        """Create tool instances based on tool IDs"""
        tools = []

        # Initialize services
        rag_service = RAGService(project_id, llm)
        graph_service = GraphService()

        for tool_id in tool_ids:
            # if tool_id == 'hybrid_search_tool':
            #     tools.append(HybridSearchTool())
            # if tool_id == 'live_data_fetch_tool':
            #     tools.append(LiveDataFetchTool())
            # if tool_id == 'lessons_learned_tool':
            #     tools.append(LessonsLearnedTool())
            # if tool_id == 'context_tool':
            #     tools.append(ContextTool())
            if tool_id == 'rag_tool':
                tools.append(RAGQueryTool(rag_service=rag_service))
            elif tool_id == 'graph_tool':
                tools.append(GraphQueryTool(graph_service=graph_service))
            # TODO: Add other tools as they are implemented
            # elif tool_id == 'cloud_catalog_tool':
            #     tools.append(CloudCatalogTool())
            # elif tool_id == 'compliance_framework_tool':
            #     tools.append(ComplianceFrameworkTool())
            # elif tool_id == 'project_planning_tool':
            #     tools.append(ProjectPlanningTool())
            else:
                logger.warning(f"Unknown tool ID: {tool_id}")

        return tools

    def create_agent(self, agent_config: Dict[str, Any], project_id: str, llm) -> Agent:
        """Create an Agent instance from configuration"""
        tools = self.create_tool_instances(agent_config.get('tools', []), project_id, llm)

        # Format goal and backstory with client profile
        goal = agent_config['goal'].format(**self.client_profile)
        backstory = agent_config['backstory'].format(**self.client_profile)

        return Agent(
            role=agent_config['role'],
            goal=goal,
            backstory=backstory,
            tools=tools,
            llm=llm,
            allow_delegation=agent_config.get('allow_delegation', False),
            verbose=agent_config.get('verbose', True)
        )

    def create_task(self, task_config: Dict[str, Any], agents_dict: Dict[str, Agent]) -> Task:
        """Create a Task instance from configuration"""
        agent_id = task_config['agent']
        if agent_id not in agents_dict:
            raise ValueError(f"Agent '{agent_id}' not found for task '{task_config['id']}'")

        # Format description and expected_output with client profile
        description = task_config['description'].format(**self.client_profile)
        expected_output = task_config['expected_output'].format(**self.client_profile)

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agents_dict[agent_id]
        )

    def create_crew(self, crew_id: str, project_id: str, llm, websocket=None) -> Crew:
        """Create a Crew instance from configuration"""
        config = self.get_config()

        # Find crew configuration
        crew_config = None
        for crew in config.get('crews', []):
            if crew['id'] == crew_id:
                crew_config = crew
                break

        if crew_config is None:
            raise ValueError(f"Crew '{crew_id}' not found in configuration")

        # Create agents
        agents_dict = {}
        agents_list = []

        agent_configs = {agent['id']: agent for agent in config.get('agents', [])}

        for agent_id in crew_config['agents']:
            if agent_id not in agent_configs:
                raise ValueError(f"Agent '{agent_id}' not found in configuration")

            agent = self.create_agent(agent_configs[agent_id], project_id, llm)
            agents_dict[agent_id] = agent
            agents_list.append(agent)

        # Create tasks
        tasks_list = []
        task_configs = {task['id']: task for task in config.get('tasks', [])}

        for task_id in crew_config['tasks']:
            if task_id not in task_configs:
                raise ValueError(f"Task '{task_id}' not found in configuration")

            task = self.create_task(task_configs[task_id], agents_dict)
            tasks_list.append(task)

        # Create callback handler for logging
        callbacks = []
        if websocket:
            log_handler = AgentLogStreamHandler(websocket=websocket)
            callbacks.append(log_handler)

        # Determine process type
        process_type = Process.sequential
        if crew_config.get('process') == 'hierarchical':
            process_type = Process.hierarchical

        return Crew(
            agents=agents_list,
            tasks=tasks_list,
            process=process_type,
            verbose=bool(crew_config.get('verbose', True)),
            memory=crew_config.get('memory', True),
            callbacks=callbacks
        )

# Global instance
crew_loader = CrewDefinitionLoader()

def create_assessment_crew_from_config(project_id: str, llm, websocket=None) -> Crew:
    """Create assessment crew from YAML configuration"""
    return crew_loader.create_crew('assessment_crew', project_id, llm, websocket)

def create_document_generation_crew_from_config(project_id: str, llm, websocket=None) -> Crew:
    """Create document generation crew from YAML configuration"""
    return crew_loader.create_crew('document_generation_crew', project_id, llm, websocket)

def get_crew_definitions() -> Dict[str, Any]:
    """Get current crew definitions"""
    return crew_loader.get_config()

def update_crew_definitions(config: Dict[str, Any]) -> None:
    """Update crew definitions"""
    crew_loader.save_config(config)
