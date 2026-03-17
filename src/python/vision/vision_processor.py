import cv2
import asyncio
import numpy as np
from ultralytics import YOLO
from datetime import datetime
import uuid

import structlog

# Internal modules
try:
    from vision.coordinate_transformer import pixel_to_gps
    from vision.dashboard_connector import DashboardConnector
except ImportError:
    from coordinate_transformer import pixel_to_gps
    from dashboard_connector import DashboardConnector

logger = structlog.get_logger()


class VisionProcessor:
    def __init__(self, model_path: str = "yolov8n.pt", source: str = "0"):
        self.model = YOLO(model_path)
        self.source = source
        self.connector = DashboardConnector()

        # Mock drone state (would ideally come from MAVLink/Telemetry)
        self.drone_state = {
            "lat": 51.4545,
            "lon": -2.5879,
            "alt": 100.0,
            "pitch": -90.0,
            "yaw": 0.0
        }

    async def run(self):
        """Main inference loop."""
        await self.connector.connect()

        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            logger.error("video_source_open_failed", source=self.source)
            return

        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # 1. Run inference with tracking (ByteTrack)
            results = self.model.track(frame, persist=True, verbose=False)

            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                track_ids = results[0].boxes.id.cpu().numpy().astype(int)
                cls = results[0].boxes.cls.cpu().numpy()
                conf = results[0].boxes.conf.cpu().numpy()

                h, w, _ = frame.shape

                for box, track_id, c, score in zip(boxes, track_ids, cls, conf):
                    # Only process vehicles (YOLO class 2: car, 3: motorcycle, 5: bus, 7: truck)
                    if int(c) not in [2, 3, 5, 7]:
                        continue

                    x1, y1, x2, y2 = box
                    center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    # 2. Project to GPS
                    lat, lon = pixel_to_gps(
                        center_x, center_y, w, h,
                        self.drone_state["lat"], self.drone_state["lon"], self.drone_state["alt"],
                        self.drone_state["pitch"], self.drone_state["yaw"]
                    )

                    # 3. Format telemetry payload (Antigravity Ontology)
                    track_payload = {
                        "id": f"DRONE-TRK-{track_id}",
                        "type": "TANK" if int(c) == 7 else "TEL", # Simplified mapping
                        "metadata": {
                            "affiliation": "UNKNOWN",
                            "source": "Drone-01"
                        },
                        "kinematics": {
                            "latitude": lat,
                            "longitude": lon,
                            "timestamp": datetime.now().isoformat()
                        },
                        "kill_chain_state": "TRACK",
                        "confidence_score": float(score)
                    }

                    # 4. Push to Dashboard (5Hz throttling simple implementation)
                    if frame_count % 6 == 0: # Assuming ~30fps, 5Hz = every 6th frame
                        await self.connector.send_telemetry(track_payload)

            # Stream frame at reduced frequency
            if frame_count % 3 == 0:
                await self.connector.stream_frame(frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        await self.connector.close()

if __name__ == "__main__":
    processor = VisionProcessor(source="test_path.mp4") # Or 0 for webcam
    asyncio.run(processor.run())
