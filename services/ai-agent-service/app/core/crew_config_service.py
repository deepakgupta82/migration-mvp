"""
Crew Configuration Service for AI Agent microservice
Reads and updates the shared crew_definitions.yaml used by the Agent Editor UI
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import logging

logger = logging.getLogger("ai-agent-service.crew-config")


class CrewConfigurationService:
    def __init__(self, config_path: Optional[str] = None):
        # Default path points to the repository's existing YAML to avoid duplicating state
        # In future, move to a service-local config directory if desired.
        if config_path:
            self.config_path = Path(config_path)
        else:
            # ../../.. to repo root, then backend/crew_definitions.yaml
            self.config_path = (Path(__file__).resolve().parents[3] / "backend" / "crew_definitions.yaml")

        self._cache: Optional[Dict[str, Any]] = None
        self._last_mtime: Optional[float] = None

    def _maybe_reload(self, force: bool = False):
        try:
            mtime = self.config_path.stat().st_mtime
        except FileNotFoundError:
            logger.error(f"Crew config file not found: {self.config_path}")
            raise
        if force or self._cache is None or self._last_mtime is None or mtime > self._last_mtime:
            with self.config_path.open("r", encoding="utf-8") as fh:
                self._cache = yaml.safe_load(fh) or {}
            self._last_mtime = mtime
            logger.info(f"Loaded crew configuration from {self.config_path}")

    def get_configuration(self, force_reload: bool = False) -> Dict[str, Any]:
        self._maybe_reload(force_reload)
        return dict(self._cache or {})

    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        # Minimal schema validation
        for key in ["agents", "tasks", "crews", "available_tools"]:
            if key not in new_config:
                raise ValueError(f"Missing required key: {key}")
        # Backup existing
        try:
            if self.config_path.exists():
                backup = self.config_path.with_suffix(self.config_path.suffix + ".backup")
                backup.write_text(self.config_path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
        # Write new
        with self.config_path.open("w", encoding="utf-8") as fh:
            yaml.dump(new_config, fh, default_flow_style=False, sort_keys=False, indent=2)
        # Refresh cache
        self._maybe_reload(True)
        return True

    def get_statistics(self) -> Dict[str, int]:
        cfg = self.get_configuration()
        return {
            "agents_count": len(cfg.get("agents", [])),
            "tasks_count": len(cfg.get("tasks", [])),
            "crews_count": len(cfg.get("crews", [])),
            "tools_count": len(cfg.get("available_tools", [])),
        }

    def validate_references(self) -> Dict[str, List[str]]:
        cfg = self.get_configuration()
        errors: List[str] = []
        warnings: List[str] = []
        agent_ids = {a.get("id") for a in cfg.get("agents", [])}
        task_ids = {t.get("id") for t in cfg.get("tasks", [])}
        tool_ids = {t.get("id") for t in cfg.get("available_tools", [])}
        for crew in cfg.get("crews", []):
            cid = crew.get("id", "unknown")
            for aid in crew.get("agents", []):
                if aid not in agent_ids:
                    errors.append(f"Crew '{cid}' references unknown agent '{aid}'")
            for tid in crew.get("tasks", []):
                if tid not in task_ids:
                    errors.append(f"Crew '{cid}' references unknown task '{tid}'")
        for agent in cfg.get("agents", []):
            aid = agent.get("id", "unknown")
            for tool in agent.get("tools", []) or []:
                if tool not in tool_ids:
                    warnings.append(f"Agent '{aid}' references unknown tool '{tool}'")
        return {"errors": errors, "warnings": warnings}


# Singleton
crew_config_service = CrewConfigurationService()
