import cv2
import numpy as np
import asyncio
import json
import base64
import random
import math
from datetime import datetime
from dashboard_connector import DashboardConnector
from coordinate_transformer import pixel_to_gps

class MissionScenario:
    def __init__(self, name="Default"):
        self.name = name

    def update_drone(self, drone, dt):
        pass

class ScanningScenario(MissionScenario):
    """Drone flies in a lawnmower or circular pattern."""
    def __init__(self, pattern="circular"):
        super().__init__(f"Scanning-{pattern}")
        self.pattern = pattern
        self.angle = 0
        self.radius = 150
        self.center_x = 0
        self.center_y = 0

    def update_drone(self, drone, dt):
        if self.pattern == "circular":
            self.angle += dt * 0.5
            drone["lat"] = drone["origin_lat"] + (math.cos(self.angle) * 0.001)
            drone["lon"] = drone["origin_lon"] + (math.sin(self.angle) * 0.001)
            drone["yaw"] = (math.degrees(-self.angle) + 90) % 360

class TrackingScenario(MissionScenario):
    """Drone follows a specific target."""
    def __init__(self, target_id):
        super().__init__(f"Tracking-{target_id}")
        self.target_id = target_id

    def update_drone(self, drone, dt, blocks):
        target = next((b for b in blocks if b["id"] == self.target_id), None)
        if target:
            # Simple chase logic
            # This is hard to do without mapping block pixels back to GPS
            # For now, let's just jitter the camera towards the target
            pass

class DroneSimulator:
    def __init__(self, drone_id, origin_lat=51.4545, origin_lon=-2.5879, width=640, height=480, fps=10):
        self.drone_id = drone_id
        self.width = width
        self.height = height
        self.fps = fps
        self.connector = DashboardConnector(backend_url="ws://localhost:8000/ws")
        
        self.state = {
            "lat": origin_lat,
            "lon": origin_lon,
            "origin_lat": origin_lat,
            "origin_lon": origin_lon,
            "alt": 120.0,
            "pitch": -45.0,
            "yaw": 0.0,
            "speed": 15.0 # m/s mock
        }
        
        self.scenario = ScanningScenario(pattern="circular")
        
        # Simulated "Blocks" (Targets) - Shared or local? Let's keep them local for simulation variety
        self.blocks = [
            {"id": f"{drone_id}-TGT-01", "x": random.randint(100, 500), "y": random.randint(100, 300), "vx": 2, "vy": 1, "color": (0, 0, 255), "type": "TEL"},
            {"id": f"{drone_id}-TGT-02", "x": random.randint(100, 500), "y": random.randint(100, 300), "vx": -1, "vy": 2, "color": (255, 0, 0), "type": "CP"}
        ]

    def draw_hud(self, frame):
        # Draw HUD overlays
        color = (0, 255, 0) # Tactical Green
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Corners
        length = 40
        cv2.line(frame, (20, 20), (20 + length, 20), color, 1)
        cv2.line(frame, (20, 20), (20, 20 + length), color, 1)
        cv2.line(frame, (self.width-20, 20), (self.width-20-length, 20), color, 1)
        cv2.line(frame, (self.width-20, 20), (self.width-20, 20 + length), color, 1)
        cv2.line(frame, (20, self.height-20), (20 + length, self.height-20), color, 1)
        cv2.line(frame, (20, self.height-20), (20, self.height-20-length), color, 1)
        cv2.line(frame, (self.width-20, self.height-20), (self.width-20-length, self.height-20), color, 1)
        cv2.line(frame, (self.width-20, self.height-20), (self.width-20, self.height-20-length), color, 1)

        # Telemetry
        cv2.putText(frame, f"ID: {self.drone_id}", (30, 40), font, 0.5, color, 1)
        cv2.putText(frame, f"ALT: {self.state['alt']:.1f}M", (30, 60), font, 0.5, color, 1)
        cv2.putText(frame, f"YAW: {self.state['yaw']:.1f}", (30, 80), font, 0.5, color, 1)
        
        pos_str = f"L: {self.state['lat']:.5f} N, {self.state['lon']:.5f} E"
        cv2.putText(frame, pos_str, (self.width - 250, 40), font, 0.5, color, 1)
        
        # Center Crosshair
        cx, cy = self.width // 2, self.height // 2
        cv2.line(frame, (cx - 10, cy), (cx + 10, cy), color, 1)
        cv2.line(frame, (cx, cy - 10), (cx, cy + 10), color, 1)

    def create_frame(self):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (20, 25, 20) # Tactical dark background
        
        # Subtle Grid
        for i in range(0, self.width, 100):
            cv2.line(frame, (i, 0), (i, self.height), (30, 35, 30), 1)
        for i in range(0, self.height, 100):
            cv2.line(frame, (0, i), (self.width, i), (30, 35, 30), 1)

        detections = []
        for block in self.blocks:
            # Move block
            block["x"] = (block["x"] + block["vx"]) % self.width
            block["y"] = (block["y"] + block["vy"]) % self.height
            
            # Draw block
            cv2.rectangle(frame, (int(block["x"]-12), int(block["y"]-12)), 
                          (int(block["x"]+12), int(block["y"]+12)), block["color"], 2)
            cv2.line(frame, (int(block["x"]-15), int(block["y"])), (int(block["x"]+15), int(block["y"])), block["color"], 1)
            cv2.line(frame, (int(block["x"]), int(block["y"]-15)), (int(block["x"]), int(block["y"]+15)), block["color"], 1)
            
            cv2.putText(frame, block["type"], (int(block["x"]-15), int(block["y"]-20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
            # Project to GPS
            lat, lon = pixel_to_gps(
                block["x"], block["y"], self.width, self.height,
                self.state["lat"], self.state["lon"], self.state["alt"],
                self.state["pitch"], self.state["yaw"]
            )
            
            detections.append({
                "id": block["id"],
                "type": block["type"],
                "metadata": {
                    "affiliation": "OPFOR",
                    "source": self.drone_id
                },
                "kinematics": {
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": datetime.now().isoformat()
                },
                "kill_chain_state": "TRACK",
                "confidence_score": 0.92 + (random.random() * 0.05)
            })
            
        self.draw_hud(frame)
        return frame, detections

    async def run(self):
        print(f"Starting Drone Simulator [{self.drone_id}]...")
        await self.connector.connect()
        
        dt = 1.0 / self.fps
        try:
            while True:
                start_time = asyncio.get_event_loop().time()
                
                # Update scenario
                self.scenario.update_drone(self.state, dt)
                
                # Generate frame and data
                frame, detections = self.create_frame()
                
                # Push telemetry and stream
                for det in detections:
                    await self.connector.send_telemetry(det, drone_id=self.drone_id)
                await self.connector.stream_frame(frame, drone_id=self.drone_id)
                
                elapsed = asyncio.get_event_loop().time() - start_time
                await asyncio.sleep(max(0, dt - elapsed))
                
        except Exception as e:
            print(f"[{self.drone_id}] Error: {e}")
        finally:
            await self.connector.close()

async def main():
    # Multi-drone simulation
    drones = [
        DroneSimulator("Viper-01", origin_lat=51.4545, origin_lon=-2.5879),
        DroneSimulator("Raven-02", origin_lat=51.4600, origin_lon=-2.5950)
    ]
    
    # Change scenario for the second drone
    drones[1].scenario = ScanningScenario(pattern="circular")
    drones[1].state["alt"] = 150.0
    
    await asyncio.gather(*(d.run() for d in drones))

if __name__ == "__main__":
    asyncio.run(main())
