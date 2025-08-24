"""Configuration parser bridge for ai-agent-service.

Always prefer the local implementation to avoid backend coupling.
"""

# Use absolute import to avoid incorrect package base during reloads
from app.utils._local_config_parsers import ConfigurationParser  # type: ignore F401

__all__ = ["ConfigurationParser"]
