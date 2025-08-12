import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger("platform.crew_config_ws")

class CrewConfigWSManager:
    def __init__(self):
        self.connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in list(self.connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

# Singleton accessor
_manager: CrewConfigWSManager | None = None

def get_crew_config_ws_manager() -> CrewConfigWSManager:
    global _manager
    if _manager is None:
        _manager = CrewConfigWSManager()
    return _manager
