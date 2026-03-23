import math
import random
import time
from typing import List, Tuple
from romania_grid import RomaniaMacroGrid

class UAV:
    MAX_CLIMB_DEG = 15.0  # Max climb angle for this asset class (also used as launch angle)

    def __init__(self, id: int, x: float, y: float, zone_id: Tuple[int, int], alt_m: float = 2000.0):
        self.id = id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.alt_m = alt_m
        self.target_alt_m = 2000.0  # Operating altitude
        self.launch_phase = alt_m < self.target_alt_m  # True if ascending from launch
        self.pitch_deg = 0.0   # Nose up/down angle (positive = nose up)
        self.roll_deg = 0.0    # Bank angle (positive = right bank)
        self._prev_heading = 0.0  # For roll calculation
        self.mode = "idle"  # idle, serving, repositioning, launching
        self.zone_id = zone_id  # (col, row)
        self.target = None
        self.commanded_target = None
        self.service_timer = 0.0

    def update(self, dt_sec: float, speed: float):
        # Altitude transition during launch/climb/descend phase
        if self.launch_phase:
            alt_diff = self.target_alt_m - self.alt_m
            if abs(alt_diff) < 1.0:
                # Reached target altitude
                self.alt_m = self.target_alt_m
                self.launch_phase = False
                self.pitch_deg = 0.0
                if self.mode == "launching":
                    self.mode = "idle"
            else:
                # Compute climb rate proportional to remaining distance
                # so pitch matches the actual geometry (alt_diff / horiz_dist)
                horiz_speed_mps = math.hypot(self.vx, self.vy) * 111000
                climbing = alt_diff > 0
                if self.commanded_target and horiz_speed_mps > 0.1:
                    horiz_dist_m = math.hypot(
                        (self.commanded_target[0] - self.x) * 111000 * math.cos(math.radians(self.y)),
                        (self.commanded_target[1] - self.y) * 111000
                    )
                    if horiz_dist_m > 1:
                        # Pitch from geometry: atan2(alt_remaining, horiz_remaining)
                        target_pitch = math.degrees(math.atan2(alt_diff, horiz_dist_m))
                        if climbing:
                            # Cap climb at MAX_CLIMB_DEG — drone climbs at max rate
                            target_pitch = min(self.MAX_CLIMB_DEG, target_pitch)
                        else:
                            # Descent uncapped (but sanity limit at -60°)
                            target_pitch = max(-60.0, target_pitch)
                        climb_rate = horiz_speed_mps * math.tan(math.radians(target_pitch))
                    else:
                        # Very close horizontally — climb/descend at class limit
                        climb_rate = 11.0 * (1.0 if climbing else -1.0)
                        target_pitch = self.MAX_CLIMB_DEG * (1.0 if climbing else -1.0)
                else:
                    # No horizontal target — fixed climb rate at class limit
                    climb_rate = 11.0 * (1.0 if climbing else -1.0)
                    target_pitch = self.MAX_CLIMB_DEG * (1.0 if climbing else -1.0)

                self.alt_m += climb_rate * dt_sec
                # Clamp altitude to not overshoot
                if alt_diff > 0:
                    self.alt_m = min(self.target_alt_m, self.alt_m)
                else:
                    self.alt_m = max(self.target_alt_m, self.alt_m)
                self.pitch_deg = target_pitch
        else:
            # Gradually return pitch to 0 when not climbing
            self.pitch_deg *= 0.9

        if self.commanded_target:
            tx, ty = self.commanded_target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self.commanded_target = None
                self.mode = "idle"
                self.vx = 0
                self.vy = 0
            else:
                self.mode = "repositioning"
                self.vx = (dx / dist) * speed
                self.vy = (dy / dist) * speed
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec
            self._update_roll()
            return

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

        self._update_roll()

    def _update_roll(self):
        """Compute roll (bank angle) from difference between actual and smoothed heading."""
        current_heading = 0.0
        if abs(self.vx) > 1e-8 or abs(self.vy) > 1e-8:
            current_heading = math.degrees(math.atan2(self.vx, self.vy)) % 360

        # Smoothed heading tracks slowly — difference = how much we're turning
        heading_diff = current_heading - self._prev_heading
        if heading_diff > 180: heading_diff -= 360
        if heading_diff < -180: heading_diff += 360

        # Update smoothed heading (slow follow)
        self._prev_heading = self._prev_heading + heading_diff * 0.15

        # Roll proportional to the remaining heading error, capped at ±30°
        target_roll = max(-30.0, min(30.0, heading_diff * 8.0))
        self.roll_deg = self.roll_deg + (target_roll - self.roll_deg) * 0.2


class Launcher:
    """Ground-based launcher vehicle — stationary at a fixed location."""
    def __init__(self, id: int, x: float, y: float, heading: float = 0.0):
        self.id = id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.heading = heading
        self.mode = "idle"


class SimulationModel:
    def __init__(self):
        self.NUM_UAVS = 20
        self.grid = RomaniaMacroGrid()
        self.uavs: List[UAV] = []
        self.launchers: List[Launcher] = [
            Launcher(0, 26.0850, 44.5711, heading=45.0),   # Otopeni / Henri Coandă Airport
            Launcher(1, 28.4883, 44.3622, heading=120.0),   # Mihail Kogălniceanu Airport
        ]
        
        self.SPEED_DEG_PER_SEC = 0.000375  # ~150 km/h at mid-latitudes
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
                    "target": target_coord,
                    "source_id": d["source_id"],
                    "target_id": d["target_id"],
                    "count": d["count"],
                })

        # 6. Update Kinematics
        for u in self.uavs:
            u.update(dt_sec, self.SPEED_DEG_PER_SEC)

    def trigger_demand_spike(self, lon: float, lat: float):
        z = self.grid.get_zone_at(lon, lat)
        if z:
            z.queue += 120

    def command_move(self, uav_id: int, lon: float, lat: float, alt_m: float = None):
        for u in self.uavs:
            if u.id == uav_id:
                u.commanded_target = (lon, lat)
                u.mode = "repositioning"
                if alt_m is not None and abs(alt_m - u.alt_m) > 1:
                    u.target_alt_m = alt_m
                    u.launch_phase = True  # Reuse climb/descend logic
                break

    def launch_drone(self, launcher_id: int):
        """Launch a new drone from a launcher. Returns the new UAV or None."""
        launcher = None
        for l in self.launchers:
            if l.id == launcher_id:
                launcher = l
                break
        if not launcher:
            return None

        new_id = max((u.id for u in self.uavs), default=-1) + 1
        # Spawn at launcher position, ground level
        zone = self.grid.get_zone_at(launcher.x, launcher.y)
        zone_id = zone.id if zone else (0, 0)
        uav = UAV(new_id, launcher.x, launcher.y, zone_id, alt_m=130.0)
        uav.mode = "launching"
        uav.launch_phase = True

        # Set target ~2km ahead in launcher heading direction
        heading_rad = math.radians(launcher.heading)
        offset_deg = 0.02  # ~2km in degrees
        target_lon = launcher.x + offset_deg * math.sin(heading_rad)
        target_lat = launcher.y + offset_deg * math.cos(heading_rad)
        uav.commanded_target = (target_lon, target_lat)

        self.uavs.append(uav)
        return uav

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
                    "alt_m": u.alt_m,
                    "heading_deg": (math.degrees(math.atan2(u.vx, u.vy)) % 360) if (abs(u.vx) > 1e-8 or abs(u.vy) > 1e-8) else 0.0,
                    "pitch_deg": u.pitch_deg,
                    "roll_deg": u.roll_deg,
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
            "flows": self.active_flows,
            "launchers": [
                {
                    "id": l.id,
                    "lon": l.x,
                    "lat": l.y,
                    "heading": l.heading,
                    "mode": l.mode
                } for l in self.launchers
            ]
        }
