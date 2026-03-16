import math
import random
import time
from typing import List, Tuple
from romania_grid import RomaniaMacroGrid

class UAV:
    def __init__(self, id: int, x: float, y: float, zone_id: Tuple[int, int]):
        self.id = id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mode = "idle"  # idle, serving, repositioning
        self.zone_id = zone_id  # (col, row)
        self.target = None
        self.service_timer = 0.0

    def update(self, dt_sec: float, speed: float):
        if self.mode == "repositioning" and self.target:
            tx, ty = self.target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self.mode = "idle"
                self.vx = 0
                self.vy = 0
                self.target = None
            else:
                self.vx = (dx / dist) * speed
                self.vy = (dy / dist) * speed
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec
        elif self.mode == "idle":
            rx = random.uniform(-1, 1) * speed * 0.2
            ry = random.uniform(-1, 1) * speed * 0.2
            self.vx += rx * dt_sec
            self.vy += ry * dt_sec
            self.vx *= 0.95
            self.vy *= 0.95
            
            curr_speed = math.hypot(self.vx, self.vy)
            max_loiter_speed = speed * 0.3
            if curr_speed > max_loiter_speed:
                self.vx = (self.vx / curr_speed) * max_loiter_speed
                self.vy = (self.vy / curr_speed) * max_loiter_speed
                
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec
            
        elif self.mode == "serving":
            self.service_timer -= dt_sec
            if self.service_timer <= 0:
                self.mode = "idle"

class SimulationModel:
    def __init__(self):
        self.NUM_UAVS = 20
        self.grid = RomaniaMacroGrid()
        self.uavs: List[UAV] = []
        
        self.SPEED_DEG_PER_SEC = 0.005
        self.SERVICE_TIME_SEC = 2.0
        
        self.last_update_time = time.time()
        self.active_flows = []
        
        self.initialize()

    def initialize(self):
        zone_keys = list(self.grid.zones.keys())
        for i in range(self.NUM_UAVS):
            if not zone_keys:
                break
            zx, zy = random.choice(zone_keys)
            z = self.grid.zones[(zx, zy)]
            ux = z.lon + random.uniform(-z.width_deg/3, z.width_deg/3)
            uy = z.lat + random.uniform(-z.height_deg/3, z.height_deg/3)
            self.uavs.append(UAV(i, ux, uy, (zx, zy)))

    def tick(self):
        now = time.time()
        dt_sec = now - self.last_update_time
        self.last_update_time = now
        
        if dt_sec > 0.1:
            dt_sec = 0.1
            
        # 1. Update UAV zone associations
        for z in self.grid.zones.values():
            z.uav_count = 0
            
        for u in self.uavs:
            z = self.grid.get_zone_at(u.x, u.y)
            if z:
                u.zone_id = z.id
                z.uav_count += 1
            else:
                # Out of bounds, pull back to center
                u.x = self.grid.MIN_LON + (self.grid.MAX_LON - self.grid.MIN_LON)/2
                u.y = self.grid.MIN_LAT + (self.grid.MAX_LAT - self.grid.MIN_LAT)/2

        # 2. Demand Generation
        for z in self.grid.zones.values():
            prob = z.demand_rate * dt_sec
            arrivals = 0
            while prob > 0:
                if random.random() < min(1.0, prob):
                    arrivals += 1
                prob -= 1.0
            z.queue += arrivals

        # 3. Assign Missions
        for z_id, z in self.grid.zones.items():
            if z.queue > 0:
                idle_in_zone = [u for u in self.uavs if u.zone_id == z_id and u.mode == "idle"]
                assign_count = min(z.queue, len(idle_in_zone))
                for i in range(assign_count):
                    idle_in_zone[i].mode = "serving"
                    idle_in_zone[i].service_timer = self.SERVICE_TIME_SEC
                    z.queue -= 1

        # 4. Calculate imbalances and dispatches via the grid logic
        dispatches = self.grid.calculate_macro_flow(dt_sec)
        
        # 5. Execute Dispatches
        self.active_flows = []
        for d in dispatches:
            source_id = d["source_id"]
            count = d["count"]
            target_coord = d["target_coord"]
            
            idle_in_r = [u for u in self.uavs if u.zone_id == source_id and u.mode == "idle"]
            dispatched_count = min(count, len(idle_in_r))
            
            for i in range(dispatched_count):
                u = idle_in_r[i]
                u.mode = "repositioning"
                u.target = target_coord
                self.active_flows.append({
                    "source": d["source_coord"],
                    "target": target_coord
                })

        # 6. Update Kinematics
        for u in self.uavs:
            u.update(dt_sec, self.SPEED_DEG_PER_SEC)

    def trigger_demand_spike(self, lon: float, lat: float):
        z = self.grid.get_zone_at(lon, lat)
        if z:
            z.queue += 120

    def reset_queues(self):
        for z in self.grid.zones.values():
            z.queue = 0
            z.demand_rate = z.base_lambda

    def get_state(self):
        return {
            "uavs": [
                {
                    "id": u.id,
                    "lon": u.x,
                    "lat": u.y,
                    "mode": u.mode
                } for u in self.uavs
            ],
            "zones": [
                {
                    "x_idx": z.id[0],
                    "y_idx": z.id[1],
                    "lon": z.lon,
                    "lat": z.lat,
                    "width": z.width_deg,
                    "height": z.height_deg,
                    "queue": z.queue,
                    "uav_count": z.uav_count,
                    "imbalance": z.imbalance
                } for z in self.grid.zones.values()
            ],
            "flows": self.active_flows
        }
