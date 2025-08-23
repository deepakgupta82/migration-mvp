"""
Deprecated: Dynamic Crew Loader moved to ai-agent-service. This backend module is retained only to avoid import errors.
"""
import logging

logger = logging.getLogger(__name__)
logger.warning("backend.app.core.crew_loader is deprecated; use ai-agent-service for crews.")

class CrewDefinitionLoader:  # pragma: no cover
    def __init__(self, *args, **kwargs):
        raise RuntimeError("crew_loader is deprecated in backend. Use ai-agent-service.")

# Backwards-compat names
crew_loader = None

def create_assessment_crew_from_config(*args, **kwargs):
    raise RuntimeError("Deprecated: use ai-agent-service crew endpoints.")

def create_document_generation_crew_from_config(*args, **kwargs):
    raise RuntimeError("Deprecated: use ai-agent-service crew endpoints.")

def get_crew_definitions(*args, **kwargs):
    raise RuntimeError("Deprecated: crew definitions are owned by ai-agent-service.")

def update_crew_definitions(*args, **kwargs):
    raise RuntimeError("Deprecated: crew definitions are owned by ai-agent-service.")
