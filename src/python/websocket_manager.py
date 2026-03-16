from typing import List
from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections for real-time telemetry streaming."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict, exclude: WebSocket = None):
        """Send a message to all connected clients except the excluded one."""
        for connection in self.active_connections[:]:
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                # Handle disconnected clients gracefully
                if connection in self.active_connections:
                    self.active_connections.remove(connection)


manager = ConnectionManager()
