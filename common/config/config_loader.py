"""
Configuration Loader for AgentiMigrate Platform

Implements hierarchical configuration loading with environment variable substitution.
Supports base configuration with environment-specific overrides.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache

from ..exceptions import ConfigurationError


class ConfigLoader:
    """
    Hierarchical configuration loader with environment variable substitution.
    
    Loads configuration in the following order:
    1. config.base.json (base configuration)
    2. config.{environment}.json (environment-specific overrides)
    3. Environment variable substitution
    """
    
    def __init__(self, config_dir: Optional[Path] = None, environment: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (e.g., 'local', 'dev-aws', 'prod-azure')
        """
        self.config_dir = config_dir or Path(__file__).parent.parent.parent / "config"
        self.environment = environment or os.getenv("CONFIG_ENV", "local")
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        Load and merge configuration from base and environment-specific files.
        
        Returns:
            Merged configuration dictionary
            
        Raises:
            ConfigurationError: If configuration files are missing or invalid
        """
        if self._config is not None:
            return self._config
        
        # Load base configuration
        base_config = self._load_config_file("config.base.json")
        
        # Load environment-specific configuration
        env_config_file = f"config.{self.environment}.json"
        env_config = self._load_config_file(env_config_file)
        
        # Merge configurations (environment overrides base)
        merged_config = self._deep_merge(base_config, env_config)
        
        # Substitute environment variables
        self._config = self._substitute_env_vars(merged_config)
        
        return self._config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value (e.g., 'database.host')
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        config = self.load()
        keys = key_path.split('.')
        
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def _load_config_file(self, filename: str) -> Dict[str, Any]:
        """Load configuration from a JSON file."""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {filename}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading {filename}: {e}")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, with override values taking precedence.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """
        Recursively substitute environment variables in configuration values.
        
        Environment variables are specified as ${VAR_NAME} or ${VAR_NAME:default_value}
        
        Args:
            config: Configuration value (can be dict, list, string, etc.)
            
        Returns:
            Configuration with environment variables substituted
        """
        if isinstance(config, dict):
            return {key: self._substitute_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            return self._substitute_string_env_vars(config)
        else:
            return config
    
    def _substitute_string_env_vars(self, value: str) -> str:
        """
        Substitute environment variables in a string value.
        
        Supports:
        - ${VAR_NAME} - Required environment variable
        - ${VAR_NAME:default} - Optional environment variable with default
        
        Args:
            value: String value potentially containing environment variables
            
        Returns:
            String with environment variables substituted
            
        Raises:
            ConfigurationError: If required environment variable is missing
        """
        def replace_env_var(match):
            var_expr = match.group(1)
            
            if ':' in var_expr:
                var_name, default_value = var_expr.split(':', 1)
                return os.getenv(var_name, default_value)
            else:
                var_name = var_expr
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ConfigurationError(
                        f"Required environment variable '{var_name}' is not set"
                    )
                return env_value
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_env_var, value)


# Global configuration instance
_config_loader: Optional[ConfigLoader] = None


@lru_cache(maxsize=1)
def get_config() -> Dict[str, Any]:
    """
    Get the global configuration instance.
    
    Returns:
        Configuration dictionary
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader()
    
    return _config_loader.load()


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Get a specific configuration value using dot notation.
    
    Args:
        key_path: Dot-separated path to configuration value
        default: Default value if key is not found
        
    Returns:
        Configuration value or default
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader()
    
    return _config_loader.get(key_path, default)


def reload_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Reload configuration, optionally changing the environment.
    
    Args:
        environment: New environment name
        
    Returns:
        Reloaded configuration dictionary
    """
    global _config_loader
    
    _config_loader = ConfigLoader(environment=environment)
    get_config.cache_clear()  # Clear the cache
    
    return _config_loader.load()
