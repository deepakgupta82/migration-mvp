"""
Deprecated: Agent definitions now live in services/ai-agent-service/app/agents.
This backend stub remains to avoid import errors; do not use in new code.
"""

class AgentDefinitions:  # pragma: no cover
    def __getattr__(self, name):
        raise RuntimeError("AgentDefinitions is deprecated in backend. Use ai-agent-service.")
