import math
import random
import time
from typing import List, Optional, Tuple
from romania_grid import RomaniaMacroGrid
from sensor_model import evaluate_detection, EnvironmentConditions
from theater_loader import load_theater, TheaterConfig, list_theaters

import structlog

logger = structlog.get_logger()

# Target states in the kill chain
TARGET_STATES = (
    "UNDETECTED", "DETECTED", "TRACKED", "IDENTIFIED",
    "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED",
)

# UAV modes
UAV_MODES = (
    "IDLE", "SCANNING", "VIEWING", "FOLLOWING",
    "PAINTING", "REPOSITIONING", "RTB",
)

# Types that emit radar signals
EMITTING_TYPES = frozenset({"SAM", "RADAR"})

# Probability per tick that an emitting type toggles is_emitting
EMIT_TOGGLE_PROB = 0.005

# Behavior mapping per unit type
UNIT_BEHAVIOR = {
    "SAM": "stationary",
    "TEL": "shoot_and_scoot",
    "TRUCK": "patrol",
    "CP": "stationary",
    "MANPADS": "ambush",
    "RADAR": "stationary",
    "C2_NODE": "stationary",
    "LOGISTICS": "patrol",
}

# Distance threshold for MANPADS flee trigger (~5km in degrees)
MANPADS_FLEE_DIST_DEG = 0.045

# Distance threshold for concealment trigger (~3km)
CONCEALMENT_DIST_DEG = 0.03

# Logistics patrol speed multiplier (slower than TRUCK)
LOGISTICS_SPEED_MULT = 0.5

# Orbit radius for VIEWING mode (degrees, ~2km at Romanian latitudes)
VIEWING_ORBIT_RADIUS_DEG = 0.018

# Follow offset distance (degrees)
FOLLOW_OFFSET_DEG = 0.01


def _heading_from_velocity(vx: float, vy: float) -> float:
    if abs(vx) < 1e-9 and abs(vy) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(vx, vy)) % 360.0


class Target:
    def __init__(self, id: int, x: float, y: float):
        self.id = id
        self.x = x
        self.y = y
        angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.0005, 0.0015)
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed
        self.type = random.choice(["SAM", "TEL", "TRUCK", "CP"])
        self.detected_time = 0

        # New fields (replacing boolean detected)
        self.state = "UNDETECTED"
        self.detection_confidence = 0.0
        self.detected_by_sensor: Optional[str] = None
        self.heading_deg = _heading_from_velocity(self.vx, self.vy)
        self.is_emitting = self.type in EMITTING_TYPES
        self.tracked_by_uav_id: Optional[int] = None

        # Behavior fields
        self.behavior = UNIT_BEHAVIOR.get(self.type, "stationary")
        self.relocate_timer = random.uniform(30.0, 60.0)
        self.concealed = False
        self.flee_cooldown = 0.0
        # Waypoints for patrol behavior: list of (x, y) tuples
        self._patrol_waypoints: List[Tuple[float, float]] = []
        self._patrol_index = 0

    @property
    def detected(self) -> bool:
        return self.state != "UNDETECTED"

    def update(self, dt_sec: float, bounds: dict, uav_positions: Optional[List[Tuple[float, float]]] = None):
        uav_positions = uav_positions or []

        if self.flee_cooldown > 0:
            self.flee_cooldown = max(0.0, self.flee_cooldown - dt_sec)

        if self.type in ("TEL", "MANPADS"):
            self.concealed = any(
                math.hypot(ux - self.x, uy - self.y) < CONCEALMENT_DIST_DEG
                for ux, uy in uav_positions
            )
        else:
            self.concealed = False

        if self.behavior == "stationary":
            self.vx = 0.0
            self.vy = 0.0

        elif self.behavior == "shoot_and_scoot":
            if self.concealed:
                self.vx = 0.0
                self.vy = 0.0
            else:
                self.relocate_timer -= dt_sec
                if self.relocate_timer <= 0:
                    self.x = random.uniform(bounds['min_lon'], bounds['max_lon'])
                    self.y = random.uniform(bounds['min_lat'], bounds['max_lat'])
                    self.vx = 0.0
                    self.vy = 0.0
                    self.relocate_timer = random.uniform(30.0, 60.0)

        elif self.behavior == "patrol":
            speed_mult = LOGISTICS_SPEED_MULT if self.type == "LOGISTICS" else 1.0
            effective_speed = self.speed * speed_mult

            if not self._patrol_waypoints:
                num_wp = random.randint(3, 5)
                self._patrol_waypoints = [
                    (
                        random.uniform(bounds['min_lon'], bounds['max_lon']),
                        random.uniform(bounds['min_lat'], bounds['max_lat']),
                    )
                    for _ in range(num_wp)
                ]
                self._patrol_index = 0

            wp_x, wp_y = self._patrol_waypoints[self._patrol_index]
            dx = wp_x - self.x
            dy = wp_y - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self._patrol_index = (self._patrol_index + 1) % len(self._patrol_waypoints)
            else:
                self.vx = (dx / dist) * effective_speed
                self.vy = (dy / dist) * effective_speed

            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec

            if self.x < bounds['min_lon'] or self.x > bounds['max_lon']:
                self.vx *= -1
                self.x = max(bounds['min_lon'], min(bounds['max_lon'], self.x))
            if self.y < bounds['min_lat'] or self.y > bounds['max_lat']:
                self.vy *= -1
                self.y = max(bounds['min_lat'], min(bounds['max_lat'], self.y))

        elif self.behavior == "ambush":
            if self.flee_cooldown <= 0:
                for ux, uy in uav_positions:
                    if math.hypot(ux - self.x, uy - self.y) < MANPADS_FLEE_DIST_DEG:
                        flee_dx = random.uniform(-0.1, 0.1)
                        flee_dy = random.uniform(-0.1, 0.1)
                        self.x = max(bounds['min_lon'], min(bounds['max_lon'], self.x + flee_dx))
                        self.y = max(bounds['min_lat'], min(bounds['max_lat'], self.y + flee_dy))
                        self.vx = 0.0
                        self.vy = 0.0
                        self.flee_cooldown = 15.0
                        break
            else:
                self.vx = 0.0
                self.vy = 0.0

        self.heading_deg = _heading_from_velocity(self.vx, self.vy)

        if self.type in EMITTING_TYPES and random.random() < EMIT_TOGGLE_PROB:
            self.is_emitting = not self.is_emitting


class UAV:
    def __init__(self, id: int, x: float, y: float, zone_id: Tuple[int, int]):
        self.id = id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.mode = "IDLE"
        self.zone_id = zone_id
        self.target = None
        self.commanded_target = None
        self.service_timer = 0.0

        # New fields
        self.altitude_m = 3000.0
        self.sensor_type = "EO_IR"
        self.heading_deg = 0.0
        self.tracked_target_id: Optional[int] = None
        self.fuel_hours: float = 24.0
        self.fuel_rate: float = 1.0

    def update(self, dt_sec: float, speed: float):
        if self.commanded_target:
            tx, ty = self.commanded_target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self.commanded_target = None
                self.mode = "IDLE"
                self.vx = 0
                self.vy = 0
            else:
                self.mode = "REPOSITIONING"
                self.vx = (dx / dist) * speed
                self.vy = (dy / dist) * speed
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec
            self.heading_deg = _heading_from_velocity(self.vx, self.vy)
            return

        if self.mode == "REPOSITIONING" and self.target:
            tx, ty = self.target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self.mode = "IDLE"
                self.vx = 0
                self.vy = 0
                self.target = None
            else:
                self.vx = (dx / dist) * speed
                self.vy = (dy / dist) * speed
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec

        elif self.mode in ("IDLE", "SCANNING"):
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

        elif self.mode == "RTB":
            # Placeholder — drift slowly for now
            self.vx *= 0.98
            self.vy *= 0.98
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec

        # VIEWING, FOLLOWING, PAINTING are handled in SimulationModel.tick()

        self.fuel_hours -= (dt_sec / 3600.0) * self.fuel_rate
        self.fuel_hours = max(0.0, self.fuel_hours)
        if self.fuel_hours < 1.0 and self.mode != "RTB":
            self.mode = "RTB"

        self.heading_deg = _heading_from_velocity(self.vx, self.vy)


class SimulationModel:
    def __init__(self, theater_name: str = "romania"):
        self.theater_name = theater_name
        self.theater: Optional[TheaterConfig] = None

        try:
            self.theater = load_theater(theater_name)
            logger.info("theater_loaded_for_sim", theater=theater_name)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("theater_load_failed_using_defaults", error=str(exc))

        self.grid = RomaniaMacroGrid()
        self.uavs: List[UAV] = []

        if self.theater:
            self.NUM_UAVS = self.theater.blue_force.uavs.count
            self.bounds = {
                'min_lon': self.theater.bounds.min_lon,
                'max_lon': self.theater.bounds.max_lon,
                'min_lat': self.theater.bounds.min_lat,
                'max_lat': self.theater.bounds.max_lat,
            }
            self.environment = EnvironmentConditions()
        else:
            self.NUM_UAVS = 20
            self.bounds = {
                'min_lon': self.grid.MIN_LON,
                'max_lon': self.grid.MAX_LON,
                'min_lat': self.grid.MIN_LAT,
                'max_lat': self.grid.MAX_LAT,
            }
            self.environment = EnvironmentConditions()

        self.SPEED_DEG_PER_SEC = 0.005
        self.SERVICE_TIME_SEC = 2.0

        self.last_update_time = time.time()
        self.active_flows = []
        self.targets: List[Target] = []
        self.NUM_TARGETS = sum(c for _, c in self._build_target_pool())

        self.initialize()

    def _build_target_pool(self) -> list:
        """Build weighted target type list from theater config."""
        if not self.theater:
            return [("SAM", 3), ("TEL", 4), ("TRUCK", 8), ("CP", 2)]
        return [(u.type, u.count) for u in self.theater.red_force.units]

    def initialize(self):
        zone_keys = list(self.grid.zones.keys())

        # Spawn UAVs
        for i in range(self.NUM_UAVS):
            if not zone_keys:
                break
            zx, zy = random.choice(zone_keys)
            z = self.grid.zones[(zx, zy)]
            ux = z.lon + random.uniform(-z.width_deg / 3, z.width_deg / 3)
            uy = z.lat + random.uniform(-z.height_deg / 3, z.height_deg / 3)
            uav = UAV(i, ux, uy, (zx, zy))
            if self.theater:
                uav.altitude_m = float(self.theater.blue_force.uavs.default_altitude_m)
                uav.sensor_type = self.theater.blue_force.uavs.sensor_type
                uav.fuel_hours = float(self.theater.blue_force.uavs.endurance_hours)
            self.uavs.append(uav)

        # Spawn targets from theater config
        target_pool = self._build_target_pool()
        target_id = 0
        for unit_type, count in target_pool:
            for _ in range(count):
                if not zone_keys:
                    break
                zx, zy = random.choice(zone_keys)
                z = self.grid.zones[(zx, zy)]
                tx = z.lon + random.uniform(-z.width_deg / 2, z.width_deg / 2)
                ty = z.lat + random.uniform(-z.height_deg / 2, z.height_deg / 2)
                t = Target(target_id, tx, ty)
                t.type = unit_type
                t.is_emitting = unit_type in EMITTING_TYPES
                t.behavior = UNIT_BEHAVIOR.get(unit_type, "stationary")
                target_id += 1
                self.targets.append(t)

    def _find_uav(self, uav_id: int) -> Optional[UAV]:
        for u in self.uavs:
            if u.id == uav_id:
                return u
        return None

    def _find_target(self, target_id: int) -> Optional[Target]:
        for t in self.targets:
            if t.id == target_id:
                return t
        return None

    def command_view(self, uav_id: int, target_id: int):
        uav = self._find_uav(uav_id)
        target = self._find_target(target_id)
        if not uav or not target:
            logger.warning("command_view_failed", uav_id=uav_id, target_id=target_id)
            return
        uav.mode = "VIEWING"
        uav.tracked_target_id = target_id
        uav.commanded_target = None
        target.tracked_by_uav_id = uav_id
        if target.state == "DETECTED":
            target.state = "TRACKED"
        logger.info("command_view", uav_id=uav_id, target_id=target_id)

    def command_follow(self, uav_id: int, target_id: int):
        uav = self._find_uav(uav_id)
        target = self._find_target(target_id)
        if not uav or not target:
            logger.warning("command_follow_failed", uav_id=uav_id, target_id=target_id)
            return
        uav.mode = "FOLLOWING"
        uav.tracked_target_id = target_id
        uav.commanded_target = None
        target.tracked_by_uav_id = uav_id
        if target.state in ("DETECTED", "TRACKED"):
            target.state = "TRACKED"
        logger.info("command_follow", uav_id=uav_id, target_id=target_id)

    def command_paint(self, uav_id: int, target_id: int):
        uav = self._find_uav(uav_id)
        target = self._find_target(target_id)
        if not uav or not target:
            logger.warning("command_paint_failed", uav_id=uav_id, target_id=target_id)
            return
        uav.mode = "PAINTING"
        uav.tracked_target_id = target_id
        uav.commanded_target = None
        target.tracked_by_uav_id = uav_id
        target.state = "LOCKED"
        logger.info("command_paint", uav_id=uav_id, target_id=target_id)

    def cancel_track(self, uav_id: int):
        uav = self._find_uav(uav_id)
        if not uav:
            logger.warning("cancel_track_failed", uav_id=uav_id)
            return
        old_target_id = uav.tracked_target_id
        uav.mode = "SCANNING"
        uav.tracked_target_id = None
        if old_target_id is not None:
            target = self._find_target(old_target_id)
            if target and target.tracked_by_uav_id == uav_id:
                target.tracked_by_uav_id = None
                if target.state in ("TRACKED", "LOCKED"):
                    target.state = "DETECTED"
        logger.info("cancel_track", uav_id=uav_id, old_target_id=old_target_id)

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
                u.x = self.grid.MIN_LON + (self.grid.MAX_LON - self.grid.MIN_LON) / 2
                u.y = self.grid.MIN_LAT + (self.grid.MAX_LAT - self.grid.MIN_LAT) / 2

        # 2. Demand Generation
        for z in self.grid.zones.values():
            prob = z.demand_rate * dt_sec
            arrivals = 0
            while prob > 0:
                if random.random() < min(1.0, prob):
                    arrivals += 1
                prob -= 1.0
            z.queue += arrivals

        # 3. Assign Missions — idle UAVs in zones with demand become SCANNING
        for z_id, z in self.grid.zones.items():
            if z.queue > 0:
                idle_in_zone = [u for u in self.uavs if u.zone_id == z_id and u.mode == "IDLE"]
                assign_count = min(z.queue, len(idle_in_zone))
                for i in range(assign_count):
                    idle_in_zone[i].mode = "SCANNING"
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

            idle_in_r = [u for u in self.uavs if u.zone_id == source_id and u.mode == "IDLE"]
            dispatched_count = min(count, len(idle_in_r))

            for i in range(dispatched_count):
                u = idle_in_r[i]
                u.mode = "REPOSITIONING"
                u.target = target_coord
                self.active_flows.append({
                    "source": d["source_coord"],
                    "target": target_coord
                })

        # 6. Handle target-tracking modes (VIEWING, FOLLOWING, PAINTING)
        self._update_tracking_modes(dt_sec)

        # 7. Update Kinematics (handles IDLE, SCANNING, REPOSITIONING, RTB)
        for u in self.uavs:
            if u.mode not in ("VIEWING", "FOLLOWING", "PAINTING"):
                u.update(dt_sec, self.SPEED_DEG_PER_SEC)

        # 8. Decrement service timers for SCANNING UAVs
        for u in self.uavs:
            if u.mode == "SCANNING":
                u.service_timer -= dt_sec
                if u.service_timer <= 0:
                    u.mode = "IDLE"

        # 9. Update Targets & Probabilistic Detection
        uav_positions = [(u.x, u.y) for u in self.uavs]
        for t in self.targets:
            t.update(dt_sec, self.bounds, uav_positions)

            if t.state in ("DESTROYED", "ENGAGED"):
                continue

            best_detection = None
            for u in self.uavs:
                if u.mode in ("RTB", "REPOSITIONING"):
                    continue

                # Compute aspect angle: bearing from UAV to target vs target heading
                dlat = t.y - u.y
                dlon = (t.x - u.x) * math.cos(math.radians((u.y + t.y) / 2.0))
                bearing_rad = math.atan2(dlon, dlat)
                bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
                aspect_deg = (bearing_deg - t.heading_deg + 360.0) % 360.0

                result = evaluate_detection(
                    uav_lat=u.y,
                    uav_lon=u.x,
                    target_lat=t.y,
                    target_lon=t.x,
                    target_type=t.type,
                    sensor_type=u.sensor_type,
                    env=self.environment,
                    aspect_deg=aspect_deg,
                    emitting=t.is_emitting,
                )
                if result.detected:
                    if best_detection is None or result.confidence > best_detection.confidence:
                        best_detection = result

            if best_detection is not None:
                if t.state == "UNDETECTED":
                    t.state = "DETECTED"
                t.detection_confidence = best_detection.confidence
                t.detected_by_sensor = best_detection.sensor_type
            else:
                # If no drone detects it, it may fade back to undetected
                # (only if not being actively tracked)
                if t.state == "DETECTED" and t.tracked_by_uav_id is None:
                    t.detection_confidence *= 0.95
                    if t.detection_confidence < 0.1:
                        t.state = "UNDETECTED"
                        t.detection_confidence = 0.0
                        t.detected_by_sensor = None

    def _update_tracking_modes(self, dt_sec: float):
        speed = self.SPEED_DEG_PER_SEC
        for u in self.uavs:
            if u.mode not in ("VIEWING", "FOLLOWING", "PAINTING"):
                continue

            target = self._find_target(u.tracked_target_id) if u.tracked_target_id is not None else None
            if not target:
                u.mode = "SCANNING"
                u.tracked_target_id = None
                u.vx = 0
                u.vy = 0
                continue

            dx = target.x - u.x
            dy = target.y - u.y
            dist = math.hypot(dx, dy)

            if u.mode == "VIEWING":
                # Orbit target at ~2km radius
                if dist < 0.001:
                    # Too close, push out
                    u.x -= VIEWING_ORBIT_RADIUS_DEG
                    dist = VIEWING_ORBIT_RADIUS_DEG

                # Tangential velocity for circular orbit
                nx, ny = dx / dist, dy / dist
                # Tangent perpendicular to radial direction
                tx, ty = -ny, nx

                if dist < VIEWING_ORBIT_RADIUS_DEG * 0.8:
                    # Move outward + tangential
                    u.vx = (-nx * 0.3 + tx * 0.7) * speed
                    u.vy = (-ny * 0.3 + ty * 0.7) * speed
                elif dist > VIEWING_ORBIT_RADIUS_DEG * 1.2:
                    # Move inward + tangential
                    u.vx = (nx * 0.3 + tx * 0.7) * speed
                    u.vy = (ny * 0.3 + ty * 0.7) * speed
                else:
                    # Pure tangential orbit
                    u.vx = tx * speed
                    u.vy = ty * speed

                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "FOLLOWING":
                # Follow target, maintaining offset behind
                desired_x = target.x - target.vx * (FOLLOW_OFFSET_DEG / max(target.speed, 0.0001))
                desired_y = target.y - target.vy * (FOLLOW_OFFSET_DEG / max(target.speed, 0.0001))
                fdx = desired_x - u.x
                fdy = desired_y - u.y
                fdist = math.hypot(fdx, fdy)
                if fdist > 0.001:
                    follow_speed = min(speed * 1.2, speed * (fdist / FOLLOW_OFFSET_DEG))
                    u.vx = (fdx / fdist) * follow_speed
                    u.vy = (fdy / fdist) * follow_speed
                else:
                    # Match target velocity
                    u.vx = target.vx
                    u.vy = target.vy
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "PAINTING":
                # Hold steady, pointed at target — minimal drift
                u.vx *= 0.9
                u.vy *= 0.9
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            u.heading_deg = _heading_from_velocity(u.vx, u.vy)

            # Keep detection confidence high while actively tracking
            target.detection_confidence = min(1.0, target.detection_confidence + 0.1 * dt_sec)
            target.detected_by_sensor = u.sensor_type

    def set_environment(self, time_of_day: float = 12.0, cloud_cover: float = 0.0, precipitation: float = 0.0):
        self.environment = EnvironmentConditions(
            time_of_day=time_of_day,
            cloud_cover=cloud_cover,
            precipitation=precipitation,
        )
        logger.info(
            "environment_updated",
            time_of_day=time_of_day,
            cloud_cover=cloud_cover,
            precipitation=precipitation,
        )

    def trigger_demand_spike(self, lon: float, lat: float):
        z = self.grid.get_zone_at(lon, lat)
        if z:
            z.queue += 120

    def command_move(self, uav_id: int, lon: float, lat: float):
        uav = self._find_uav(uav_id)
        if uav:
            uav.commanded_target = (lon, lat)
            uav.mode = "REPOSITIONING"
            # Clear any tracking
            if uav.tracked_target_id is not None:
                old_target = self._find_target(uav.tracked_target_id)
                if old_target and old_target.tracked_by_uav_id == uav_id:
                    old_target.tracked_by_uav_id = None
                uav.tracked_target_id = None

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
                    "mode": u.mode,
                    "altitude_m": u.altitude_m,
                    "sensor_type": u.sensor_type,
                    "heading_deg": round(u.heading_deg, 1),
                    "tracked_target_id": u.tracked_target_id,
                    "fuel_hours": round(u.fuel_hours, 2),
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
            "targets": [
                {
                    "id": t.id,
                    "lon": t.x,
                    "lat": t.y,
                    "type": t.type,
                    "detected": t.detected,
                    "state": t.state,
                    "detection_confidence": round(t.detection_confidence, 3),
                    "detected_by_sensor": t.detected_by_sensor,
                    "is_emitting": t.is_emitting,
                    "heading_deg": round(t.heading_deg, 1),
                    "tracked_by_uav_id": t.tracked_by_uav_id,
                } for t in self.targets
            ],
            "environment": {
                "time_of_day": self.environment.time_of_day,
                "cloud_cover": self.environment.cloud_cover,
                "precipitation": self.environment.precipitation,
            },
        }
