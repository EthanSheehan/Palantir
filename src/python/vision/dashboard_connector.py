import json
import asyncio
import websockets
import cv2
import base64
from datetime import datetime
from typing import Dict, Any

class DashboardConnector:
    """
    WebSocket client to transmit tracking data and MJPEG frames to the Antigravity C2 backend.
    """
    def __init__(self, backend_url: str = "ws://localhost:8000/ws"):
        self.backend_url = backend_url
        self.websocket = None

    async def connect(self):
        """Establish WebSocket connection."""
        try:
            self.websocket = await websockets.connect(self.backend_url)
            print(f"Connected to C2 Backend at {self.backend_url}")
        except Exception as e:
            print(f"Failed to connect to backend: {e}")

    async def send_telemetry(self, track_data: Dict[str, Any], drone_id: str = "Drone-01"):
        """
        Send tracking metadata formatted as a Project Antigravity Object.
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
            await self.websocket.send(json.dumps(payload))
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
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "type": "DRONE_FEED",
                "timestamp": datetime.now().isoformat(),
                "drone_id": drone_id,
                "data": {
                    "frame": jpg_as_text
                }
            }
            await self.websocket.send(json.dumps(payload))
        except Exception as e:
            print(f"Error streaming frame: {e}")

    async def close(self):
        if self.websocket:
            await self.websocket.close()

if __name__ == "__main__":
    # Quick mock test
    connector = DashboardConnector()
    asyncio.run(connector.connect())
