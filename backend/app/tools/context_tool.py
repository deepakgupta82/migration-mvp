from crewai_tools import BaseTool
from common.project_context import ProjectContext
import json

class ContextTool(BaseTool):
    name: str = "Project Context Tool"
    description: str = "Read from or write to the shared Project Context workspace to collaborate with other agents. Always read the entire context before writing to avoid overwriting data."
    _context: ProjectContext = ProjectContext()

    def _run(self, operation: str, key: str = None, value: dict = None) -> str:
        if operation == 'read':
            if key:
                return getattr(self._context, key, 'Key not found')
            return self._context.model_dump_json(indent=2)
        elif operation == 'write':
            if not key or not value:
                return "Error: Both key and value must be provided for a write operation."
            
            current_value = getattr(self._context, key, None)
            if isinstance(current_value, list):
                current_value.append(value)
                setattr(self._context, key, current_value)
            else:
                setattr(self._context, key, value)
            return f"Successfully wrote to {key}."
        else:
            return "Error: Invalid operation. Use 'read' or 'write'."
