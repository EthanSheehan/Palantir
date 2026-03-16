import json
import asyncio
import websockets
import cv2
import base64
from datetime import datetime
from typing import Dict, Any

class DashboardConnector:
    """
    WebSocket client to transmit tracking data and MJPEG frames to the Palantir C2 backend.
    """
    def __init__(self, backend_url: str = "ws://localhost:8000/ws"):
        self.backend_url = backend_url
        self.websocket = None

    async def connect(self):
        """Establish WebSocket connection with robust parameters."""
        try:
            # Set ping_interval and ping_timeout to prevent keepalive timeout errors (1011)
            self.websocket = await websockets.connect(
                self.backend_url,
                ping_interval=20,
                ping_timeout=20,
                max_size=None, # Allow large frames if needed
            )
            print(f"Connected to C2 Backend at {self.backend_url} (Stability Mode)")
        except Exception as e:
            print(f"Failed to connect to backend: {e}")

    async def receive_command(self):
        """Listen for incoming commands from the backend."""
        if not self.websocket:
            await self.connect()
            return None
        try:
            # Non-blocking check for messages
            message = await asyncio.wait_for(self.websocket.recv(), timeout=0.001)
            return json.loads(message)
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            # If disconnected, try to reconnect
            print(f"Connection lost, retrying: {e}")
            self.websocket = None
            return None

    async def send_telemetry(self, track_data: Dict[str, Any], drone_id: str = "Drone-01"):
        """
        Send tracking metadata formatted as a Palantir C2 Object.
        """
        if not self.websocket:
            return

        payload = {
            "type": "TRACK_UPDATE",
            "timestamp": datetime.now().isoformat(),
            "drone_id": drone_id,
            "data": track_data
        }
        
        try:
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=2.0)
        except Exception as e:
            print(f"Error sending telemetry: {e}")

    async def stream_frame(self, frame: Any, drone_id: str = "Drone-01"):
        """
        Compress and send a video frame as base64 encoded JPEG.
        """
        if not self.websocket:
            return

        try:
            # Resize for faster streaming if necessary
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "type": "DRONE_FEED",
                "timestamp": datetime.now().isoformat(),
                "drone_id": drone_id,
                "data": {
                    "frame": jpg_as_text
                }
            }
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=2.0)
        except Exception as e:
            print(f"Error streaming frame: {e}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()

if __name__ == "__main__":
    # Quick mock test
    connector = DashboardConnector()
    asyncio.run(connector.connect())
