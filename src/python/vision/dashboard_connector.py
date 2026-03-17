import json
import asyncio
import websockets
import cv2
import base64
from datetime import datetime
from typing import List, Dict, Any

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
            # Disable pings/timeouts on client side to prevent '1011' errors during busy processing
            self.websocket = await websockets.connect(
                self.backend_url,
                ping_interval=None,
                ping_timeout=None,
                max_size=None, # Allow large frames if needed
            )
            # Identify as a simulator to the backend
            await self.websocket.send(json.dumps({"type": "IDENTIFY", "client_type": "SIMULATOR"}))
            print(f"Connected to C2 Backend at {self.backend_url} (Stability Mode)")

        except Exception as e:
            print(f"Failed to connect to backend: {e}")

    async def receive_command(self):
        """Listen for incoming commands from the backend."""
        if not self.websocket:
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
        await self.send_telemetry_batch([track_data], drone_id)

    async def send_telemetry_batch(self, tracks: List[Dict[str, Any]], drone_id: str = "Drone-01"):
        """
        Send a batch of tracking metadata to reduce message overhead.
        """
        if not self.websocket:
            return

        payload = {
            "type": "TRACK_UPDATE_BATCH", # New batch type
            "timestamp": datetime.now().isoformat(),
            "drone_id": drone_id,
            "data": tracks
        }
        
        try:
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=1.0)
        except Exception as e:
            print(f"Error sending telemetry: {e}")


    async def stream_frame(self, frame: Any, drone_id: str = "Drone-01"):
        """
        Compress and send a video frame as base64 encoded JPEG.
        """
        if not self.websocket:
            return

        try:
            # Drop quality to 50% for stability over bandwidth
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
            # Short timeout to prevent loop blocking
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=1.0)
        except Exception as e:
            print(f"Error streaming frame: {e}")


    async def close(self):
        if self.websocket:
            await self.websocket.close()

if __name__ == "__main__":
    # Quick mock test
    connector = DashboardConnector()
    asyncio.run(connector.connect())
