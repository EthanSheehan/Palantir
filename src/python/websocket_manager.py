import asyncio
import json
from typing import List, Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections with frame-dropping and non-blocking safety."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Track which drones each connection is interested in for video
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        # Track if we are currently sending to a socket to avoid pilling up
        self.busy_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()

    async def disconnect(self, websocket: WebSocket):
        """Cleanly remove a connection and its subscriptions."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        if websocket in self.busy_connections:
            self.busy_connections.discard(websocket)
        
        try:
            await websocket.close()
        except:
            pass

    async def subscribe(self, websocket: WebSocket, drone_id: str):
        """Register interest in a specific drone's video feed."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(drone_id)

    async def unsubscribe(self, websocket: WebSocket, drone_id: str):
        """Unregister interest in a specific drone's video feed."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].discard(drone_id)

    async def broadcast(self, message: dict, exclude: WebSocket = None):
        """Send a message to all connected clients except the excluded one."""
        if not self.active_connections:
            return

        msg_type = message.get("type")
        drone_id = message.get("drone_id")

        async def send_to_conn(conn: WebSocket):
            if conn in self.busy_connections:
                # SKIP if already sending (prevents task accumulation and 1011 errors)
                return

            try:
                # If it's a video feed, only send if subscribed
                if msg_type == "DRONE_FEED" and drone_id:
                    subs = self.subscriptions.get(conn, set())
                    if drone_id not in subs:
                        return

                self.busy_connections.add(conn)
                # Use a tighter timeout to keep the loop moving
                await asyncio.wait_for(conn.send_json(message), timeout=0.5)
            except Exception:
                # If a send fails/times out, we just drop it and proceed
                pass
            finally:
                self.busy_connections.discard(conn)

        for connection in self.active_connections[:]:
            if connection != exclude:
                # Fire and forget send task
                asyncio.create_task(send_to_conn(connection))


manager = ConnectionManager()
