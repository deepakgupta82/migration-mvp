"""
Crew Factory Service - Centralized crew creation and management
Extracted from backend/app/core/crew.py for better organization
"""

import logging

logger = logging.getLogger(__name__)
logger.warning("backend.app.core.crew_factory is deprecated; use ai-agent-service for CrewAI orchestration.")

class CrewFactory:  # pragma: no cover
    def __getattr__(self, name):
        raise RuntimeError("CrewFactory is deprecated in backend. Use ai-agent-service.")

crew_factory = CrewFactory()
