import math
import random
import time
from typing import List, Tuple, Dict, Any
from datetime import datetime

class UAV:
    def __init__(self, id: str, lon: float, lat: float, alt: float = 120.0):
        self.id = id
        self.lon = lon
        self.lat = lat
        self.alt = alt
        self.yaw = 0.0
        self.mode = "idle"  # idle, repositioning, tracking
        self.target_waypoint = None
        self.target_entity_id = None
        self.speed_deg = 0.0005 # Realistic speed for local ops
        self.last_update = time.time()

    def update(self, dt: float, targets: Dict[str, Any]):
        if self.mode == "tracking" and self.target_entity_id:
            target = targets.get(self.target_entity_id)
            if target:
                tx, ty = target.lon, target.lat
                self.target_waypoint = (tx, ty)
        
        if self.target_waypoint:
            tx, ty = self.target_waypoint
            dx = tx - self.lon
            dy = ty - self.lat
            dist = math.hypot(dx, dy)
            
            if dist < 0.0001: # Reached target/waypoint
                if self.mode != "tracking":
                    self.target_waypoint = None
                    self.mode = "idle"
            else:
                step = self.speed_deg * dt
                ratio = min(1.0, step / dist)
                self.lon += dx * ratio
                self.lat += dy * ratio
                
                # Update yaw to face movement (Corrected for North-up CCW -> CW conversion)
                math_angle = math.atan2(dy, dx)
                # In math, (dx=1, dy=0) is 0 deg. In navigation, North (dy=1, dx=0) is 0 deg.
                # To align with Cesium/Navigation:
                self.yaw = (90 - math.degrees(math_angle)) % 360
        else:
            # Loiter
            self.yaw = (self.yaw + dt * 5) % 360
            self.lon += math.sin(math.radians(self.yaw)) * 0.00005 * dt
            self.lat += math.cos(math.radians(self.yaw)) * 0.00005 * dt

    def to_dict(self):
        meta = {
            "affiliation": "FRIENDLY",
            "altitude": self.alt,
            "yaw": self.yaw,
            "mode": self.mode,
            "target_waypoint": self.target_waypoint
        }
        if self.mode == "tracking":
            meta["target_id"] = self.target_entity_id
            
        return {
            "id": self.id,
            "type": "UAV",
            "kinematics": {
                "latitude": self.lat,
                "longitude": self.lon,
                "timestamp": datetime.now().isoformat()
            },
            "metadata": meta
        }

class Target:
    def __init__(self, id: str, type: str, lon: float, lat: float, affiliation: str = "OPFOR"):
        self.id = id
        self.type = type
        self.lon = lon
        self.lat = lat
        self.affiliation = affiliation
        self.vx = (random.random() - 0.5) * 0.0005
        self.vy = (random.random() - 0.5) * 0.0005
        self.kill_chain_state = "TRACK"
        self.tracked_by = None

    def update(self, dt: float):
        self.lon += self.vx * dt
        self.lat += self.vy * dt
        
        # Jitter movement
        if random.random() < 0.05:
            self.vx += (random.random() - 0.5) * 0.0002
            self.vy += (random.random() - 0.5) * 0.0002
            
        # AO constraints roughly Kurdistan center
        if abs(self.lon - 44.3615) > 0.1: self.vx *= -1
        if abs(self.lat - 33.3128) > 0.1: self.vy *= -1

    def to_dict(self):
        return {
            "track_id": self.id,
            "type": self.type,
            "classification": self.type,
            "kinematics": {
                "latitude": self.lat,
                "longitude": self.lon,
                "timestamp": datetime.now().isoformat()
            },
            "metadata": {
                "affiliation": self.affiliation,
                "kill_chain_state": self.kill_chain_state,
                "tracked_by": self.tracked_by
            }
        }

class TacticalSimulation:
    def __init__(self, drone_count=3, target_count=5):
        self.drones: Dict[str, UAV] = {}
        self.targets: Dict[str, Target] = {}
        
        # Initialize Scaled Fleet
        for i in range(drone_count):
            did = f"Viper-0{i+1}"
            self.drones[did] = UAV(did, 44.35 + (i*0.01), 33.30 + (i*0.01))
            
        types = ["SAM", "TEL", "CP", "TRUCK"]
        for i in range(target_count):
            tid = f"TGT-{chr(65+i)}"
            ttype = random.choice(types)
            self.targets[tid] = Target(tid, ttype, 44.36 + (random.random()-0.5)*0.05, 33.31 + (random.random()-0.5)*0.05)
            
        self.scenario = "DISCOVERY" 
        self.last_tick = time.time()

    def tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now
        
        # Reset tracking associations for metadata update
        for t in self.targets.values():
            t.tracked_by = None
            
        for drone in self.drones.values():
            drone.update(dt, self.targets)
            if drone.mode == "tracking" and drone.target_entity_id:
                if drone.target_entity_id in self.targets:
                    self.targets[drone.target_entity_id].tracked_by = drone.id
            
        for target in self.targets.values():
            target.update(dt)

    def get_state(self):
        return {
            "type": "TRACK_UPDATE",
            "data": {
                "tracks": [d.to_dict() for d in self.drones.values()] + 
                          [t.to_dict() for t in self.targets.values()]
            }
        }

    def set_waypoint(self, drone_id: str, lon: float, lat: float):
        if drone_id == "ALL":
            for d in self.drones.values():
                d.target_waypoint = (lon, lat)
                d.mode = "repositioning"
        elif drone_id in self.drones:
            self.drones[drone_id].target_waypoint = (lon, lat)
            self.drones[drone_id].mode = "repositioning"
            self.drones[drone_id].target_entity_id = None

    def start_intercept(self, drone_id: str, target_id: str):
        if drone_id in self.drones and target_id in self.targets:
            self.drones[drone_id].target_entity_id = target_id
            self.drones[drone_id].mode = "tracking"

    def set_scenario(self, scenario: str):
        self.scenario = scenario
        for t in self.targets.values():
            t.kill_chain_state = "LOCK" if scenario == "PAINTING" else "TRACK"

sim = TacticalSimulation()
