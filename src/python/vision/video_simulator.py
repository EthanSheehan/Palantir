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
            pass
class PaintingScenario(MissionScenario):
    """Drone orbits and 'paints' (locks onto) a specific target."""
    def __init__(self, target_id):
        super().__init__(f"Painting-{target_id}")
        self.target_id = target_id
        self.angle = 0

    def update_drone(self, drone, dt):
        self.angle += dt * 0.3
        # Orbit around a fixed point representing the target
        drone["lat"] = drone["origin_lat"] + (math.cos(self.angle) * 0.0005)
        drone["lon"] = drone["origin_lon"] + (math.sin(self.angle) * 0.0005)
        # Always face the center (the target)
        drone["yaw"] = (math.degrees(-self.angle)) % 360

class DroneSimulator:
    def __init__(self, drone_id, origin_lat=51.4545, origin_lon=-2.5879, width=800, height=600, fps=12):
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
        
        # Simulated "Blocks" (Targets)
        self.blocks = [
            {"id": f"CP-1", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": 2, "vy": 1, "color": (0, 0, 255), "type": "TEL"},
            {"id": f"CP-2", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": -1, "vy": 2, "color": (255, 0, 0), "type": "CP"}
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
        
        is_painting = isinstance(self.scenario, PaintingScenario)
        if is_painting:
            color = (0, 0, 255) # Red for Lock
            cv2.putText(frame, "TARGET LOCKED - PAINTING", (cx - 100, cy - 40), font, 0.6, color, 2)
            # Reticle
            cv2.drawMarker(frame, (cx, cy), color, cv2.MARKER_TILTED_CROSS, 20, 2)
        else:
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
            
            # Draw AI Bounding Box
            bx, by = int(block["x"]), int(block["y"])
            bw, bh = 40, 40
            cv2.rectangle(frame, (bx - bw//2, by - bh//2), (bx + bw//2, by + bh//2), block["color"], 1)
            
            # Corner markers for the box
            cl = 10
            cv2.line(frame, (bx-bw//2, by-bh//2), (bx-bw//2+cl, by-bh//2), block["color"], 2)
            cv2.line(frame, (bx-bw//2, by-bh//2), (bx-bw//2, by-bh//2+cl), block["color"], 2)
            
            cv2.line(frame, (bx+bw//2, by-bh//2), (bx+bw//2-cl, by-bh//2), block["color"], 2)
            cv2.line(frame, (bx+bw//2, by-bh//2), (bx+bw//2, by-bh//2+cl), block["color"], 2)
            
            cv2.line(frame, (bx-bw//2, by+bh//2), (bx-bw//2+cl, by+bh//2), block["color"], 2)
            cv2.line(frame, (bx-bw//2, by+bh//2), (bx-bw//2, by+bh//2-cl), block["color"], 2)
            
            cv2.line(frame, (bx+bw//2, by+bh//2), (bx+bw//2-cl, by+bh//2), block["color"], 2)
            cv2.line(frame, (bx+bw//2, by+bh//2), (bx+bw//2, by+bh//2-cl), block["color"], 2)

            # Label & Confidence
            conf = 0.92 + (random.random() * 0.05)
            label = f"{block['type']} [{conf:.2f}]"
            cv2.putText(frame, label, (bx - bw//2, by - bh//2 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, block["color"], 1)
            
            # Crosshair in box
            cv2.line(frame, (bx-5, by), (bx+5, by), block["color"], 1)
            cv2.line(frame, (bx, by-5), (bx, by+5), block["color"], 1)
            
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
                "kill_chain_state": "LOCK" if isinstance(self.scenario, PaintingScenario) else "TRACK",
                "confidence_score": 0.98 if isinstance(self.scenario, PaintingScenario) else 0.92 + (random.random() * 0.05)
            })
            
        self.draw_hud(frame)
        return frame, detections

    async def run(self):
        print(f"Starting Drone Simulator [{self.drone_id}]...")
        await self.connector.connect()
        
        dt = 1.0 / self.fps
        tick_count = 0
        try:
            while True:
                tick_count += 1
                start_time = asyncio.get_event_loop().time()
                
                # Check for incoming commands
                cmd = await self.connector.receive_command()
                if cmd and cmd.get("type") == "CMD_SET_SCENARIO":
                    scenario_name = cmd.get("scenario")
                    drone_target = cmd.get("drone_id")
                    
                    if drone_target == self.drone_id or drone_target == "ALL":
                        print(f"[{self.drone_id}] Received Command: SET_SCENARIO -> {scenario_name}")
                        if scenario_name == "PAINTING":
                            target_id = f"{self.drone_id}-TGT-PAINTED"
                            self.blocks = [{"id": target_id, "x": 320, "y": 240, "vx": 0, "vy": 0, "color": (0, 0, 255), "type": "TGT"}]
                            self.scenario = PaintingScenario(target_id)
                        elif scenario_name == "DISCOVERY":
                            self.scenario = ScanningScenario(pattern="circular")
                        self.blocks = [
                                {"id": "CP-1", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": 2, "vy": 1, "color": (255, 100, 0), "type": "TEL"},
                                {"id": "CP-2", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": -1, "vy": 2, "color": (0, 150, 255), "type": "CP"},
                                {"id": "TGT-ALPHA", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": 1, "vy": -1, "color": (0, 0, 255), "type": "SAM"},
                                {"id": "TGT-BRAVO", "x": random.randint(100, 700), "y": random.randint(100, 500), "vx": -2, "vy": 0.5, "color": (0, 255, 255), "type": "TRUCK"}
                            ]
                
                # Update scenario
                self.scenario.update_drone(self.state, dt)
                
                # Generate frame and data
                frame, detections = self.create_frame()
                
                # Push drone's own telemetry as a UAV track
                drone_track = {
                    "id": self.drone_id,
                    "type": "UAV",
                    "kinematics": {
                        "latitude": self.state["lat"],
                        "longitude": self.state["lon"],
                        "timestamp": datetime.now().isoformat()
                    },
                    "metadata": {
                        "affiliation": "FRIENDLY",
                        "altitude": self.state["alt"],
                        "yaw": self.state["yaw"]
                    }
                }
                try:
                    # Collect all tracks for this tick (Drone itself + Detections)
                    all_tracks = [drone_track] + detections
                    
                    # Push all tracks in a single batch to minimize overhead
                    await self.connector.send_telemetry_batch(all_tracks, drone_id=self.drone_id)
                    
                    # Stream frames less frequently to avoid network congestion
                    if tick_count % 3 == 0:  # ~3.3 FPS
                        await self.connector.stream_frame(frame, drone_id=self.drone_id)
                    
                    elapsed = asyncio.get_event_loop().time() - start_time
                    await asyncio.sleep(max(0, dt - elapsed))
                except Exception as e:
                    # Log but don't crash the simulation on individual send errors
                    error_str = str(e).lower()
                    if "1011" in error_str or "timeout" in error_str or "keepalive" in error_str:
                        # Transient network/busy error, just skip this tick
                        print(f"[{self.drone_id}] Transient WS error (dropping data): {e}")
                        pass
                    else:
                        print(f"[{self.drone_id}] Connection lost, retrying: {e}")
                        await asyncio.sleep(5)
                        break # Exit the inner while to trigger the outer reconnect


        except Exception as e:
            print(f"[{self.drone_id}] Global Error: {e}")
            await self.connector.close()
            await asyncio.sleep(5)
            await self.connector.connect()
            print(f"[{self.drone_id}] Reconnected.")
        finally:
            await self.connector.close()

async def main():
    # Multi-drone simulation with reduced load in Romania
    drones = [
        DroneSimulator("0", origin_lat=45.9432, origin_lon=24.9668, fps=8),
        DroneSimulator("1", origin_lat=46.1000, origin_lon=25.2000, fps=8)
    ]

    
    # Change scenario for the second drone
    drones[1].scenario = ScanningScenario(pattern="circular")
    drones[1].state["alt"] = 150.0
    
    await asyncio.gather(*(d.run() for d in drones))

if __name__ == "__main__":
    asyncio.run(main())
