"""
Crew Configuration Service
Handles reading, parsing, and updating crew_definitions.yaml file
"""

import yaml
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class CrewConfigurationService:
    """Service for managing crew configuration from YAML file"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to crew_definitions.yaml in backend directory
            self.config_path = Path(__file__).parent.parent.parent / "crew_definitions.yaml"
        else:
            self.config_path = Path(config_path)
        
        self._config_cache = None
        self._last_modified = None
        
    def _check_file_modified(self) -> bool:
        """Check if the YAML file has been modified since last read"""
        try:
            current_modified = self.config_path.stat().st_mtime
            if self._last_modified is None or current_modified > self._last_modified:
                self._last_modified = current_modified
                return True
            return False
        except FileNotFoundError:
            logger.error(f"Crew definitions file not found: {self.config_path}")
            return False
        except Exception as e:
            logger.error(f"Error checking file modification time: {e}")
            return False
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load and parse the YAML configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                logger.info(f"Successfully loaded crew configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Crew definitions file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def get_configuration(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Get the complete crew configuration
        
        Args:
            force_reload: Force reload from file even if cached
            
        Returns:
            Complete configuration dictionary
        """
        if force_reload or self._config_cache is None or self._check_file_modified():
            self._config_cache = self._load_yaml_config()
        
        return self._config_cache.copy() if self._config_cache else {}
    
    def get_agents(self) -> List[Dict[str, Any]]:
        """Get all agent definitions"""
        config = self.get_configuration()
        return config.get('agents', [])
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get all task definitions"""
        config = self.get_configuration()
        return config.get('tasks', [])
    
    def get_crews(self) -> List[Dict[str, Any]]:
        """Get all crew definitions"""
        config = self.get_configuration()
        return config.get('crews', [])
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tool definitions"""
        config = self.get_configuration()
        return config.get('available_tools', [])
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent by ID"""
        agents = self.get_agents()
        return next((agent for agent in agents if agent.get('id') == agent_id), None)
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID"""
        tasks = self.get_tasks()
        return next((task for task in tasks if task.get('id') == task_id), None)
    
    def get_crew_by_id(self, crew_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific crew by ID"""
        crews = self.get_crews()
        return next((crew for crew in crews if crew.get('id') == crew_id), None)
    
    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the complete configuration and save to YAML file
        
        Args:
            new_config: New configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate the configuration structure
            self._validate_configuration(new_config)
            
            # Create backup of current file
            self._create_backup()
            
            # Write new configuration
            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(new_config, file, default_flow_style=False, sort_keys=False, indent=2)
            
            # Update cache
            self._config_cache = new_config.copy()
            self._last_modified = self.config_path.stat().st_mtime
            
            logger.info("Successfully updated crew configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            # Restore from backup if possible
            self._restore_backup()
            return False
    
    def _validate_configuration(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure"""
        required_keys = ['agents', 'tasks', 'crews', 'available_tools']
        
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")
        
        # Validate agents
        for agent in config.get('agents', []):
            if not isinstance(agent, dict) or 'id' not in agent:
                raise ValueError("Invalid agent definition: missing 'id' field")
        
        # Validate tasks
        for task in config.get('tasks', []):
            if not isinstance(task, dict) or 'id' not in task:
                raise ValueError("Invalid task definition: missing 'id' field")
        
        # Validate crews
        for crew in config.get('crews', []):
            if not isinstance(crew, dict) or 'id' not in crew:
                raise ValueError("Invalid crew definition: missing 'id' field")
    
    def _create_backup(self) -> None:
        """Create a backup of the current configuration file"""
        try:
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix('.yaml.backup')
                import shutil
                shutil.copy2(self.config_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _restore_backup(self) -> None:
        """Restore configuration from backup"""
        try:
            backup_path = self.config_path.with_suffix('.yaml.backup')
            if backup_path.exists():
                import shutil
                shutil.copy2(backup_path, self.config_path)
                logger.info("Restored configuration from backup")
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
    
    def get_statistics(self) -> Dict[str, int]:
        """Get configuration statistics"""
        config = self.get_configuration()
        return {
            'agents_count': len(config.get('agents', [])),
            'tasks_count': len(config.get('tasks', [])),
            'crews_count': len(config.get('crews', [])),
            'tools_count': len(config.get('available_tools', []))
        }
    
    def validate_references(self) -> Dict[str, List[str]]:
        """Validate that all references between agents, tasks, and crews are valid"""
        config = self.get_configuration()
        errors = []
        warnings = []
        
        # Get all IDs
        agent_ids = {agent.get('id') for agent in config.get('agents', [])}
        task_ids = {task.get('id') for task in config.get('tasks', [])}
        tool_ids = {tool.get('id') for tool in config.get('available_tools', [])}
        
        # Validate crew references
        for crew in config.get('crews', []):
            crew_id = crew.get('id', 'unknown')
            
            # Check agent references
            for agent_id in crew.get('agents', []):
                if agent_id not in agent_ids:
                    errors.append(f"Crew '{crew_id}' references unknown agent '{agent_id}'")
            
            # Check task references
            for task_id in crew.get('tasks', []):
                if task_id not in task_ids:
                    errors.append(f"Crew '{crew_id}' references unknown task '{task_id}'")
        
        # Validate agent tool references
        for agent in config.get('agents', []):
            agent_id = agent.get('id', 'unknown')
            for tool_id in agent.get('tools', []):
                if tool_id not in tool_ids:
                    warnings.append(f"Agent '{agent_id}' references unknown tool '{tool_id}'")
        
        return {
            'errors': errors,
            'warnings': warnings
        }


# Global instance
crew_config_service = CrewConfigurationService()
