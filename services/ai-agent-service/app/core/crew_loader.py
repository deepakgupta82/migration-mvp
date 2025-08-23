"""
Dynamic Crew Loader for ai-agent-service - Loads crew definitions from YAML configuration
Ported from backend with adaptations to local tools and services.
"""

import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional

from crewai import Agent, Task, Crew, Process

from app.tools.rag_query_tool import RAGQueryTool
from app.tools.graph_query_tool import GraphQueryTool
from app.core.agent_logs import AgentLogStreamHandler

logger = logging.getLogger(__name__)


class CrewDefinitionLoader:
    """Loads and manages crew definitions from YAML configuration"""

    def __init__(self, config_path: Optional[str] = None, client_profile_path: Optional[str] = None):
        # Default to shared backend YAML so UI continues to edit a single source of truth
        if config_path is None:
            # .../services/ai-agent-service/app/core -> repo root
            here = os.path.dirname(__file__)
            repo_root = os.path.abspath(os.path.join(here, '..', '..', '..'))
            config_path = os.path.join(repo_root, 'backend', 'crew_definitions.yaml')

        if client_profile_path is None:
            here = os.path.dirname(__file__)
            repo_root = os.path.abspath(os.path.join(here, '..', '..', '..'))
            client_profile_path = os.path.join(repo_root, 'backend', 'config', 'client_profile.json')

        self.config_path = config_path
        self.client_profile_path = client_profile_path
        self.config: Optional[Dict[str, Any]] = None
        self.client_profile: Dict[str, Any] = {}
        self.load_config()
        self.load_client_profile()

    def load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded crew definitions from {self.config_path}")
            return self.config
        except FileNotFoundError:
            logger.error(f"Crew definitions file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise

    def load_client_profile(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.client_profile_path):
                with open(self.client_profile_path, 'r', encoding='utf-8') as f:
                    self.client_profile = json.load(f) or {}
                logger.info(f"Loaded client profile from {self.client_profile_path}")
            else:
                logger.warning(f"Client profile not found: {self.client_profile_path}")
            return self.client_profile
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing client profile JSON: {e}")
            raise

    def save_config(self, config: Dict[str, Any]) -> None:
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            self.config = config
            logger.info(f"Saved crew definitions to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving YAML file: {e}")
            raise

    def get_config(self) -> Dict[str, Any]:
        if self.config is None:
            self.load_config()
        return self.config or {}

    def get_available_tools(self) -> Dict[str, Any]:
        cfg = self.get_config()
        return {tool['id']: tool for tool in cfg.get('available_tools', [])}

    def create_tool_instances(self, tool_ids: List[str], project_id: str, llm) -> List[Any]:
        tools: List[Any] = []

        for tool_id in tool_ids:
            if tool_id == 'rag_tool':
                # Use gateway-backed RAG tool; RAGService will be used internally if injected elsewhere
                tools.append(RAGQueryTool())
            elif tool_id == 'graph_tool':
                tools.append(GraphQueryTool(project_id=project_id))
            else:
                # Other specialized tools are created in CrewFactory based on process needs
                logger.debug(f"Tool '{tool_id}' will be provided by CrewFactory or is not yet supported here")

        return tools

    def create_agent(self, agent_config: Dict[str, Any], project_id: str, llm) -> Agent:
        tools = self.create_tool_instances(agent_config.get('tools', []), project_id, llm)

        # Format goal and backstory with client profile fields
        goal = (agent_config.get('goal') or '').format(**self.client_profile)
        backstory = (agent_config.get('backstory') or '').format(**self.client_profile)

        return Agent(
            role=agent_config['role'],
            goal=goal,
            backstory=backstory,
            tools=tools,
            llm=llm,
            allow_delegation=bool(agent_config.get('allow_delegation', False)),
            verbose=bool(agent_config.get('verbose', True))
        )

    def create_task(self, task_config: Dict[str, Any], agents_dict: Dict[str, Agent]) -> Task:
        agent_id = task_config['agent']
        if agent_id not in agents_dict:
            raise ValueError(f"Agent '{agent_id}' not found for task '{task_config['id']}'")

        description = (task_config.get('description') or '').format(**self.client_profile)
        expected_output = (task_config.get('expected_output') or '').format(**self.client_profile)

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agents_dict[agent_id]
        )

    def create_crew(self, crew_id: str, project_id: str, llm, websocket=None) -> Crew:
        cfg = self.get_config()

        crew_config = next((c for c in cfg.get('crews', []) if c.get('id') == crew_id), None)
        if not crew_config:
            raise ValueError(f"Crew '{crew_id}' not found in configuration")

        # Create agents
        agents_dict: Dict[str, Agent] = {}
        agents_list: List[Agent] = []

        agent_configs = {a['id']: a for a in cfg.get('agents', [])}
        for agent_id in crew_config.get('agents', []):
            if agent_id not in agent_configs:
                raise ValueError(f"Agent '{agent_id}' not defined in configuration")
            agent = self.create_agent(agent_configs[agent_id], project_id, llm)
            agents_dict[agent_id] = agent
            agents_list.append(agent)

        # Create tasks
        tasks_list: List[Task] = []
        task_configs = {t['id']: t for t in cfg.get('tasks', [])}
        for task_id in crew_config.get('tasks', []):
            if task_id not in task_configs:
                raise ValueError(f"Task '{task_id}' not defined in configuration")
            task = self.create_task(task_configs[task_id], agents_dict)
            tasks_list.append(task)

        # Callbacks for logging
        callbacks = []
        if websocket:
            callbacks.append(AgentLogStreamHandler(websocket=websocket))

        process_type = Process.sequential
        if str(crew_config.get('process', 'sequential')).lower() == 'hierarchical':
            process_type = Process.hierarchical

        return Crew(
            agents=agents_list,
            tasks=tasks_list,
            process=process_type,
            verbose=bool(crew_config.get('verbose', True)),
            memory=bool(crew_config.get('memory', True)),
            callbacks=callbacks
        )


# Global instance for reuse
crew_loader = CrewDefinitionLoader()

def get_crew_definitions() -> Dict[str, Any]:
    return crew_loader.get_config()

def update_crew_definitions(config: Dict[str, Any]) -> None:
    crew_loader.save_config(config)
