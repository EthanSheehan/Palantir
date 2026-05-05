import asyncio
import base64
import json
from datetime import datetime
from typing import Any, Dict, List

import cv2
import structlog
import websockets

logger = structlog.get_logger()


class DashboardConnector:
    """
    WebSocket client to transmit tracking data and MJPEG frames to the Grid-Sentinel C2 backend.
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
                max_size=None,  # Allow large frames if needed
            )
            # Identify as a simulator to the backend
            await self.websocket.send(json.dumps({"type": "IDENTIFY", "client_type": "SIMULATOR"}))
            logger.info("backend_connected", url=self.backend_url, mode="stability")

        except (ConnectionRefusedError, OSError, websockets.exceptions.WebSocketException) as exc:
            logger.error("backend_connect_failed", url=self.backend_url, error=str(exc))

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
        except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError) as exc:
            logger.warning("connection_lost_retrying", error=str(exc))
            self.websocket = None
            return None

    async def send_telemetry(self, track_data: Dict[str, Any], drone_id: str = "Drone-01"):
        """
        Send tracking metadata formatted as a Grid-Sentinel C2 Object.
        """
        await self.send_telemetry_batch([track_data], drone_id)

    async def send_telemetry_batch(self, tracks: List[Dict[str, Any]], drone_id: str = "Drone-01"):
        """
        Send a batch of tracking metadata to reduce message overhead.
        """
        if not self.websocket:
            return

        payload = {
            "type": "TRACK_UPDATE_BATCH",  # New batch type
            "timestamp": datetime.now().isoformat(),
            "drone_id": drone_id,
            "data": tracks,
        }

        try:
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=1.0)
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, ConnectionError, OSError) as exc:
            logger.error("telemetry_send_failed", drone_id=drone_id, error=str(exc))

    async def stream_frame(self, frame: Any, drone_id: str = "Drone-01"):
        """
        Compress and send a video frame as base64 encoded JPEG.
        """
        if not self.websocket:
            return

        try:
            # Drop quality to 50% for stability over bandwidth
            _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            jpg_as_text = base64.b64encode(buffer).decode("utf-8")

            payload = {
                "type": "DRONE_FEED",
                "timestamp": datetime.now().isoformat(),
                "drone_id": drone_id,
                "data": {"frame": jpg_as_text},
            }
            # Short timeout to prevent loop blocking
            await asyncio.wait_for(self.websocket.send(json.dumps(payload)), timeout=1.0)
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, ConnectionError, OSError) as exc:
            logger.error("frame_stream_failed", drone_id=drone_id, error=str(exc))

    async def close(self):
        if self.websocket:
            await self.websocket.close()


if __name__ == "__main__":
    # Quick mock test
    connector = DashboardConnector()
    asyncio.run(connector.connect())
