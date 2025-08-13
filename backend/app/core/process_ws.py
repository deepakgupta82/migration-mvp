import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("backend")

class ProcessWSManager:
    """Simple WS manager to stream processing updates per project."""
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(project_id, set()).add(websocket)
        logger.info(f"WS(process-documents): client connected for project {project_id}. total={len(self._connections.get(project_id, []))}")

    def disconnect(self, project_id: str, websocket: WebSocket):
        try:
            conns = self._connections.get(project_id)
            if conns and websocket in conns:
                conns.remove(websocket)
                if not conns:
                    self._connections.pop(project_id, None)
        except Exception:
            pass

    async def broadcast(self, project_id: str, message: str):
        dead = []
        for ws in list(self._connections.get(project_id, set())):
            try:
                # Skip if websocket looks closed
                if hasattr(ws, "application_state") and getattr(ws, "application_state", None) and getattr(ws.application_state, "name", "") == "DISCONNECTED":
                    dead.append(ws)
                    continue
                await ws.send_text(message)
            except Exception as e:
                # Common benign disconnects on Windows asyncio / browsers: treat as dead and continue
                if isinstance(e, (ConnectionResetError,)) or "ConnectionResetError" in str(e) or "cannot write to closing transport" in str(e):
                    pass
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


_manager: ProcessWSManager | None = None

def get_process_ws_manager() -> ProcessWSManager:
    global _manager
    if _manager is None:
        _manager = ProcessWSManager()
    return _manager
