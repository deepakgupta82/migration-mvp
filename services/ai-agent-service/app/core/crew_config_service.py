"""
Crew Configuration Service for AI Agent microservice
Reads and updates the shared crew_definitions.yaml used by the Agent Editor UI
"""

from pathlib import Path
import os
from typing import Dict, Any, List, Optional
import yaml
import logging

logger = logging.getLogger("ai-agent-service.crew-config")


class CrewConfigurationService:
    def __init__(self, config_path: Optional[str] = None):
        """
        Resolve the crew_definitions.yaml path with the following precedence:
        1) Explicit config_path argument
        2) Environment variable AI_AGENT_CREW_CONFIG_PATH
        3) Auto-discover by searching upwards for a backend/crew_definitions.yaml
        4) Fallback to a service-local crew_definitions.yaml under this service
        """
        resolved: Optional[Path] = None

        try:
            if config_path:
                resolved = Path(config_path)
            else:
                env_path = os.getenv("AI_AGENT_CREW_CONFIG_PATH")
                if env_path:
                    resolved = Path(env_path)
        except Exception:
            resolved = None

        if not resolved:
            # Try to locate repo root containing 'backend/crew_definitions.yaml'
            try:
                here = Path(__file__).resolve()
                for parent in [here.parents[i] for i in range(0, min(5, len(here.parents)))]:
                    candidate = parent / "backend" / "crew_definitions.yaml"
                    if candidate.exists():
                        resolved = candidate
                        break
            except Exception:
                pass

        if not resolved:
            # Fallback to a service-local file so the service can still start
            local_fallback = Path(__file__).resolve().parents[1] / "crew_definitions.yaml"
            resolved = local_fallback
            if not local_fallback.exists():
                try:
                    # Create a minimal valid structure
                    minimal = {"agents": [], "tasks": [], "crews": [], "available_tools": []}
                    local_fallback.write_text(yaml.dump(minimal, sort_keys=False), encoding="utf-8")
                    logger.warning(f"Created local fallback crew config at {local_fallback}")
                except Exception as e:
                    logger.error(f"Failed to create local fallback crew config: {e}")

        self.config_path = resolved

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
