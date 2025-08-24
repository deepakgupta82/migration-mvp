from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import os
import json

@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key_env: Optional[str] = None
    extras: Dict[str, Any] | None = None

class ConfigurationParser:
    """
    Lightweight local ConfigurationParser used by ai-agent-service to avoid backend import.
    Reads minimal settings from environment variables or a simple JSON file if provided.
    """
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path
        self._data: Dict[str, Any] = {}
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)

    def get(self, path: list[str], default: Any = None) -> Any:
        # Try data first
        cur: Any = self._data
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                cur = None
                break
        if cur is not None:
            return cur
        # Then env using UPPER_SNAKE joined with '__'
        env_key = '__'.join([str(p).upper() for p in path])
        return os.getenv(env_key, default)

    def get_llm_config(self) -> LLMConfig:
        provider = self.get(["llm", "provider"], os.getenv("LLM_PROVIDER", "openai"))
        model = self.get(["llm", "model"], os.getenv("LLM_MODEL", "gpt-4o-mini"))
        api_key_env = self.get(["llm", "api_key_env"], os.getenv("LLM_API_KEY_ENV", None))
        extras = self.get(["llm", "extras"], None)
        return LLMConfig(provider=provider, model=model, api_key_env=api_key_env, extras=extras)
