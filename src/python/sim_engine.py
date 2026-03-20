import math
import random
import time
from collections import deque
from typing import Dict, List, Optional, Tuple
from romania_grid import RomaniaMacroGrid
from sensor_model import evaluate_detection, EnvironmentConditions
from theater_loader import load_theater, TheaterConfig, list_theaters
from sensor_fusion import SensorContribution, fuse_detections
from verification_engine import evaluate_target_state, VERIFICATION_THRESHOLDS, _DEFAULT_THRESHOLD
from swarm_coordinator import SwarmCoordinator, TaskingOrder

import structlog

logger = structlog.get_logger()

# Target states in the kill chain
TARGET_STATES = (
    "UNDETECTED", "DETECTED", "CLASSIFIED", "VERIFIED",
    "TRACKED", "IDENTIFIED", "NOMINATED", "LOCKED",
    "ENGAGED", "DESTROYED", "ESCAPED",
)

# UAV modes
UAV_MODES = (
    "IDLE", "SEARCH", "FOLLOW",
    "PAINT", "INTERCEPT", "REPOSITIONING", "RTB",
    "SUPPORT", "VERIFY", "OVERWATCH", "BDA",
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

# Autonomous transition table: (current_mode, trigger) -> new_mode
AUTONOMOUS_TRANSITIONS = {
    ("IDLE", "target_detected_in_zone"): "SEARCH",
    ("SEARCH", "high_confidence_detection"): "FOLLOW",
    ("FOLLOW", "verification_gap"): "VERIFY",
    ("FOLLOW", "target_verified_nominated"): "PAINT",
    ("PAINT", "engagement_complete"): "BDA",
    ("BDA", "assessment_complete"): "SEARCH",
    ("IDLE", "swarm_support_requested"): "SUPPORT",
    ("IDLE", "coverage_gap_detected"): "OVERWATCH",
}

# Minimum idle UAV count to maintain before threat-adaptive dispatch
MIN_IDLE_COUNT = 3

# Distance threshold for MANPADS flee trigger (~5km in degrees)
MANPADS_FLEE_DIST_DEG = 0.045

# Distance threshold for concealment trigger (~3km)
CONCEALMENT_DIST_DEG = 0.03

# Logistics patrol speed multiplier (slower than TRUCK)
LOGISTICS_SPEED_MULT = 0.5

# Maximum number of position history entries per target
POSITION_HISTORY_MAXLEN = 60

# Follow orbit radius (degrees, ~2km — loose orbit)
FOLLOW_ORBIT_RADIUS_DEG = 0.018

# Paint orbit radius (degrees, ~1km — tight lock orbit)
PAINT_ORBIT_RADIUS_DEG = 0.009

# Intercept approach distance (degrees, ~300m — danger close)
INTERCEPT_CLOSE_DEG = 0.003

# Follow offset distance (degrees)
FOLLOW_OFFSET_DEG = 0.01

# Fixed-wing loiter circle radius (degrees, ~3km)
LOITER_RADIUS_DEG = 0.027

# New mode orbit/pattern radii (Phase 3)
SUPPORT_ORBIT_RADIUS_DEG = 0.027       # ~3km wide orbit for secondary coverage
VERIFY_CROSS_DISTANCE_DEG = 0.009      # ~1km perpendicular offset for sensor passes
OVERWATCH_RACETRACK_LENGTH_DEG = 0.045 # ~5km racetrack legs for area coverage
BDA_ORBIT_RADIUS_DEG = 0.009           # ~1km tight orbit for damage assessment
BDA_DURATION_SEC = 30.0                # Auto-transition to SEARCH after 30s
SUPERVISED_TIMEOUT_SEC = 10.0          # Supervised pending transition auto-approve timeout

# Max turn rate for fixed-wing (radians/sec, ~3 deg/sec standard rate turn)
MAX_TURN_RATE = math.radians(3.0)

# Degrees per km (approximate)
DEG_PER_KM = 1.0 / 111.0

# Enemy UAV modes
ENEMY_UAV_MODES = ("RECON", "ATTACK", "JAMMING", "EVADING", "DESTROYED")

# Enemy UAV speed (deg/sec, ~440 km/h)
ENEMY_SPEED = 0.004

# Sensor distribution weights: (sensors, weight)
_SENSOR_DISTRIBUTION = [
    (["EO_IR"],          50),
    (["SAR"],            20),
    (["SIGINT"],         10),
    (["EO_IR", "SAR"],   10),
    (["EO_IR", "SIGINT"], 10),
]


def _pick_sensors() -> List[str]:
    population = [s for s, w in _SENSOR_DISTRIBUTION for _ in range(w)]
    return list(random.choice(population))


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
        self.tracked_by_uav_ids: list = []
        self.sensor_contributions: list = []
        self.fused_confidence: float = 0.0
        self.sensor_count: int = 0

        # Behavior fields
        self.behavior = UNIT_BEHAVIOR.get(self.type, "stationary")
        self.relocate_timer = random.uniform(30.0, 60.0)
        self.concealed = False
        self.flee_cooldown = 0.0
        # Waypoints for patrol behavior: list of (x, y) tuples
        self._patrol_waypoints: List[Tuple[float, float]] = []
        self._patrol_index = 0

        # Theater-wired fields (set externally)
        self.threat_range_km: Optional[float] = None
        self.detection_range_km: Optional[float] = None

        # Verification timer fields
        self.time_in_state_sec: float = 0.0
        self.last_sensor_contact_time: float = time.time()

        # Position history for movement corridor detection (not serialized in get_state)
        self.position_history: deque = deque(maxlen=POSITION_HISTORY_MAXLEN)

    @property
    def detected(self) -> bool:
        return self.state != "UNDETECTED"

    @property
    def tracked_by_uav_id(self) -> Optional[int]:
        return self.tracked_by_uav_ids[0] if self.tracked_by_uav_ids else None

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

        self.position_history.append((self.x, self.y))


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
        self.sensors: List[str] = _pick_sensors()
        self.heading_deg = 0.0
        self.tracked_target_ids: list = []
        self.primary_target_id: Optional[int] = None
        self.fuel_hours: float = 24.0
        self.fuel_rate: float = 1.0

        # Phase 3: autonomy and new mode fields
        self.autonomy_override: Optional[str] = None
        self.mode_source: str = "HUMAN"
        self.tasking_source: str = "ZONE_BALANCE"
        self.bda_timer: float = 0.0
        self.overwatch_waypoints: list = []
        self.overwatch_wp_idx: int = 0

    @property
    def tracked_target_id(self) -> Optional[int]:
        return self.primary_target_id

    @tracked_target_id.setter
    def tracked_target_id(self, value: Optional[int]):
        self.primary_target_id = value
        if value is not None and value not in self.tracked_target_ids:
            self.tracked_target_ids.append(value)
        elif value is None:
            self.tracked_target_ids.clear()
            self.primary_target_id = None

    def _turn_toward(self, target_vx: float, target_vy: float, speed: float, dt_sec: float):
        """Gradually turn toward desired direction (fixed-wing turn rate limit)."""
        curr_heading = math.atan2(self.vx, self.vy) if math.hypot(self.vx, self.vy) > 1e-9 else 0.0
        desired_heading = math.atan2(target_vx, target_vy)
        diff = desired_heading - curr_heading
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        max_delta = MAX_TURN_RATE * dt_sec * 3  # 3x for repositioning urgency
        if abs(diff) > max_delta:
            diff = math.copysign(max_delta, diff)
        new_heading = curr_heading + diff
        self.vx = math.sin(new_heading) * speed
        self.vy = math.cos(new_heading) * speed

    def update(self, dt_sec: float, speed: float):
        if self.commanded_target:
            tx, ty = self.commanded_target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist < 0.005:
                self.commanded_target = None
                self.mode = "IDLE"
            else:
                self.mode = "REPOSITIONING"
                self._turn_toward((dx / dist) * speed, (dy / dist) * speed, speed, dt_sec)
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
                self._turn_toward((dx / dist) * speed, (dy / dist) * speed, speed, dt_sec)
            self.x += self.vx * dt_sec
            self.y += self.vy * dt_sec

        elif self.mode in ("IDLE", "SEARCH"):
            # Fixed-wing loiter: fly in a circle around a loiter point
            loiter_speed = speed * 0.5
            curr_speed = math.hypot(self.vx, self.vy)

            if curr_speed < loiter_speed * 0.3:
                # Kick-start with initial heading
                angle = math.radians(self.heading_deg) if self.heading_deg else random.uniform(0, 2 * math.pi)
                self.vx = math.sin(angle) * loiter_speed
                self.vy = math.cos(angle) * loiter_speed

            # Apply gentle constant turn (fixed-wing circle)
            heading_rad = math.atan2(self.vx, self.vy)
            turn = MAX_TURN_RATE * dt_sec
            heading_rad += turn
            self.vx = math.sin(heading_rad) * loiter_speed
            self.vy = math.cos(heading_rad) * loiter_speed

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


class EnemyUAV:
    def __init__(self, id: int, x: float, y: float, mode: str = "RECON", behavior: str = "recon"):
        self.id = id
        self.x = x
        self.y = y
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.heading_deg: float = 0.0
        self.mode: str = mode
        self.behavior: str = behavior
        self.detected: bool = False
        self.fused_confidence: float = 0.0
        self.sensor_count: int = 0
        self.sensor_contributions: list = []
        self.is_jamming: bool = mode == "JAMMING"
        self.speed: float = ENEMY_SPEED
        self.evasion_cooldown: float = 0.0
        self.attack_waypoint: Optional[Tuple[float, float]] = None
        self._original_mode: str = mode

    def _turn_toward(self, target_vx: float, target_vy: float, speed: float, dt_sec: float):
        """Gradually turn toward desired direction (fixed-wing turn rate limit, no 3x multiplier)."""
        curr_heading = math.atan2(self.vx, self.vy) if math.hypot(self.vx, self.vy) > 1e-9 else 0.0
        desired_heading = math.atan2(target_vx, target_vy)
        diff = desired_heading - curr_heading
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        max_delta = MAX_TURN_RATE * dt_sec
        if abs(diff) > max_delta:
            diff = math.copysign(max_delta, diff)
        new_heading = curr_heading + diff
        self.vx = math.sin(new_heading) * speed
        self.vy = math.cos(new_heading) * speed

    def update(self, dt_sec: float, bounds: dict):
        if self.mode == "DESTROYED":
            return

        if self.mode == "RECON":
            # Circular loiter: constant heading turn
            if math.hypot(self.vx, self.vy) < self.speed * 0.3:
                # Kick-start with initial velocity
                angle = math.radians(self.heading_deg) if self.heading_deg else random.uniform(0, 2 * math.pi)
                self.vx = math.sin(angle) * self.speed
                self.vy = math.cos(angle) * self.speed
            heading_rad = math.atan2(self.vx, self.vy)
            heading_rad += MAX_TURN_RATE * dt_sec
            self.vx = math.sin(heading_rad) * self.speed
            self.vy = math.cos(heading_rad) * self.speed

        elif self.mode == "ATTACK":
            if self.attack_waypoint is not None:
                wp_x, wp_y = self.attack_waypoint
                dx = wp_x - self.x
                dy = wp_y - self.y
                dist = math.hypot(dx, dy)
                if dist > 0.001:
                    target_vx = (dx / dist) * self.speed
                    target_vy = (dy / dist) * self.speed
                    self._turn_toward(target_vx, target_vy, self.speed, dt_sec)
                # If no velocity yet, initialize toward waypoint
                if math.hypot(self.vx, self.vy) < self.speed * 0.3 and dist > 0.001:
                    self.vx = (dx / dist) * self.speed
                    self.vy = (dy / dist) * self.speed

        elif self.mode == "JAMMING":
            # Station keeping — no movement
            self.vx = 0.0
            self.vy = 0.0
            self.is_jamming = True

        elif self.mode == "EVADING":
            evasion_speed = self.speed * 1.5
            # Evasive random heading change
            if math.hypot(self.vx, self.vy) < evasion_speed * 0.3:
                angle = random.uniform(0, 2 * math.pi)
                self.vx = math.sin(angle) * evasion_speed
                self.vy = math.cos(angle) * evasion_speed
            # Turn toward random direction with urgency
            target_angle = math.atan2(self.vx, self.vy) + random.uniform(-math.pi / 2, math.pi / 2)
            target_vx = math.sin(target_angle) * evasion_speed
            target_vy = math.cos(target_angle) * evasion_speed
            self._turn_toward(target_vx, target_vy, evasion_speed, dt_sec)
            # Decrement cooldown
            self.evasion_cooldown = max(0.0, self.evasion_cooldown - dt_sec)
            # Exit EVADING when cooldown expired and confidence is low
            if self.evasion_cooldown <= 0.0 and self.fused_confidence < 0.3:
                self.mode = self._original_mode

        # Check evasion trigger (not already EVADING or DESTROYED)
        if self.mode not in ("EVADING", "DESTROYED") and self.fused_confidence > 0.5:
            self._original_mode = self.mode
            self.mode = "EVADING"
            self.evasion_cooldown = 15.0

        # Move
        self.x += self.vx * dt_sec
        self.y += self.vy * dt_sec

        # Clamp to bounds
        self.x = max(bounds['min_lon'], min(bounds['max_lon'], self.x))
        self.y = max(bounds['min_lat'], min(bounds['max_lat'], self.y))

        # Update heading
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

        # Phase 3: autonomy system fields
        self.autonomy_level: str = "MANUAL"
        self.pending_transitions: dict = {}
        self.supervised_timeout_sec: float = SUPERVISED_TIMEOUT_SEC

        self.SPEED_DEG_PER_SEC = 0.005
        self.SERVICE_TIME_SEC = 2.0

        # Build per-type config maps from theater
        self._unit_speed_map: Dict[str, float] = {}
        self._unit_threat_range_map: Dict[str, Optional[float]] = {}
        self._unit_detection_range_map: Dict[str, Optional[float]] = {}
        if self.theater:
            for unit in self.theater.red_force.units:
                if unit.speed_kmh is not None:
                    # Convert km/h to deg/sec: speed_kmh * 1000m/km / 3600s/hr * DEG_PER_KM
                    self._unit_speed_map[unit.type] = unit.speed_kmh * DEG_PER_KM / 3600.0
                if unit.threat_range_km is not None:
                    self._unit_threat_range_map[unit.type] = float(unit.threat_range_km)
                if unit.detection_range_km is not None:
                    self._unit_detection_range_map[unit.type] = float(unit.detection_range_km)

        self.last_update_time = time.time()
        self.active_flows = []

        # Phase 8: adaptive ISR coverage mode
        self.coverage_mode: str = "balanced"
        self._last_assessment: Optional[dict] = None
        self.targets: List[Target] = []
        self.enemy_uavs: List[EnemyUAV] = []
        self.NUM_TARGETS = sum(c for _, c in self._build_target_pool())
        self.demo_fast: bool = False

        # Phase 5: swarm coordination
        self.swarm_coordinator = SwarmCoordinator(min_idle_count=2)  # 2 per locked decision
        self._swarm_tick_counter = 0

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
                # Wire theater fields
                if unit_type in self._unit_speed_map:
                    t.speed = self._unit_speed_map[unit_type]
                t.threat_range_km = self._unit_threat_range_map.get(unit_type)
                t.detection_range_km = self._unit_detection_range_map.get(unit_type)
                target_id += 1
                self.targets.append(t)

        self._spawn_enemy_uavs()

    def _spawn_enemy_uavs(self):
        """Spawn enemy UAVs from theater config (or defaults). IDs start at 1001."""
        self.enemy_uavs = []
        eid = 1001

        if self.theater and self.theater.enemy_uavs:
            for unit_cfg in self.theater.enemy_uavs.units:
                mode = unit_cfg.behavior.upper()
                if mode not in ENEMY_UAV_MODES:
                    mode = "RECON"
                speed_deg_sec = unit_cfg.speed_kmh * DEG_PER_KM / 3600.0
                for _ in range(unit_cfg.count):
                    ex = random.uniform(self.bounds['min_lon'], self.bounds['max_lon'])
                    ey = random.uniform(self.bounds['min_lat'], self.bounds['max_lat'])
                    e = EnemyUAV(id=eid, x=ex, y=ey, mode=mode, behavior=unit_cfg.behavior.lower())
                    if speed_deg_sec > 0:
                        e.speed = speed_deg_sec
                    if mode == "JAMMING":
                        e.is_jamming = True
                    self.enemy_uavs.append(e)
                    eid += 1
        else:
            # Fallback: 3 RECON drones
            for _ in range(3):
                ex = random.uniform(self.bounds['min_lon'], self.bounds['max_lon'])
                ey = random.uniform(self.bounds['min_lat'], self.bounds['max_lat'])
                e = EnemyUAV(id=eid, x=ex, y=ey, mode="RECON", behavior="recon")
                self.enemy_uavs.append(e)
                eid += 1

    def _find_enemy_uav(self, enemy_uav_id: int) -> Optional[EnemyUAV]:
        for e in self.enemy_uavs:
            if e.id == enemy_uav_id:
                return e
        return None

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

    def _assign_target(self, uav_id: int, target_id: int, mode: str, target_state: str):
        uav = self._find_uav(uav_id)
        target = self._find_target(target_id)
        if not uav or not target:
            logger.warning("command_failed", mode=mode, uav_id=uav_id, target_id=target_id)
            return
        uav.mode = mode
        uav.tracked_target_id = target_id
        uav.commanded_target = None
        if uav_id not in target.tracked_by_uav_ids:
            target.tracked_by_uav_ids.append(uav_id)
        if target_state == "LOCKED" or target.state in ("DETECTED", "CLASSIFIED", "VERIFIED", "UNDETECTED"):
            target.state = target_state
        logger.info("command_assign", mode=mode, uav_id=uav_id, target_id=target_id)

    def command_follow(self, uav_id: int, target_id: int):
        self._assign_target(uav_id, target_id, "FOLLOW", "TRACKED")

    def command_paint(self, uav_id: int, target_id: int):
        self._assign_target(uav_id, target_id, "PAINT", "LOCKED")

    def command_intercept(self, uav_id: int, target_id: int):
        self._assign_target(uav_id, target_id, "INTERCEPT", "LOCKED")

    def command_intercept_enemy(self, uav_id: int, enemy_uav_id: int):
        uav = self._find_uav(uav_id)
        enemy = self._find_enemy_uav(enemy_uav_id)
        if not uav or not enemy:
            logger.warning("command_intercept_enemy_failed", uav_id=uav_id, enemy_uav_id=enemy_uav_id)
            return
        uav.mode = "INTERCEPT"
        uav.primary_target_id = enemy_uav_id
        uav.commanded_target = None
        uav._intercept_dwell = 0.0
        logger.info("command_intercept_enemy", uav_id=uav_id, enemy_uav_id=enemy_uav_id)

    def cancel_track(self, uav_id: int):
        uav = self._find_uav(uav_id)
        if not uav:
            logger.warning("cancel_track_failed", uav_id=uav_id)
            return
        old_target_id = uav.primary_target_id
        uav.mode = "SEARCH"
        uav.tracked_target_ids = [tid for tid in uav.tracked_target_ids if tid != old_target_id]
        uav.primary_target_id = None
        if old_target_id is not None:
            target = self._find_target(old_target_id)
            if target:
                target.tracked_by_uav_ids = [uid for uid in target.tracked_by_uav_ids if uid != uav_id]
                if not target.tracked_by_uav_ids and target.state in ("TRACKED", "LOCKED"):
                    target.state = "DETECTED"
        logger.info("cancel_track", uav_id=uav_id, old_target_id=old_target_id)

    def request_swarm(self, target_id: int):
        """Force-assign UAVs to fill sensor gaps for target (operator request).
        Runs unconditionally regardless of autonomy tier — operator request always executes.
        """
        target = self._find_target(target_id)
        if not target:
            return
        orders = self.swarm_coordinator.evaluate_and_assign([target], self.uavs, force=True)
        for order in orders:
            uav = self._find_uav(order.uav_id)
            if uav and not (uav.mode == "SUPPORT" and order.target_id in uav.tracked_target_ids):
                self._assign_target(order.uav_id, order.target_id, "SUPPORT", "DETECTED")

    def release_swarm(self, target_id: int):
        """Release all SUPPORT UAVs from target, set them to SEARCH."""
        for u in self.uavs:
            if u.mode == "SUPPORT" and target_id in u.tracked_target_ids:
                self.cancel_track(u.id)

    def set_coverage_mode(self, mode: str):
        """Switch between 'balanced' (zone-grid dispatch) and 'threat_adaptive' (ISR-driven dispatch)."""
        if mode in ("balanced", "threat_adaptive"):
            self.coverage_mode = mode

    def _threat_adaptive_dispatches(self) -> list:
        """Generate dispatch orders toward coverage gaps ranked by threat score.

        Respects MIN_IDLE_COUNT — never dispatches if idle UAVs <= MIN_IDLE_COUNT.
        Returns a list of dispatch dicts compatible with the standard dispatch loop.
        """
        if self._last_assessment is None:
            return []
        idle_uavs = [u for u in self.uavs if u.mode == "IDLE"]
        if len(idle_uavs) <= MIN_IDLE_COUNT:
            return []
        gaps = sorted(
            self._last_assessment.get("coverage_gaps", []),
            key=lambda g: -g.get("threat_score", 0.0),
        )
        dispatches = []
        available = list(idle_uavs)
        for gap in gaps:
            if len(available) <= MIN_IDLE_COUNT:
                break
            nearest = min(available, key=lambda u: (u.x - gap["lon"]) ** 2 + (u.y - gap["lat"]) ** 2)
            dispatches.append({
                "source_id": nearest.zone_id,
                "count": 1,
                "source_coord": (nearest.x, nearest.y),
                "target_coord": (gap["lon"], gap["lat"]),
            })
            nearest.tasking_source = "ISR_PRIORITY"
            nearest.mode_source = "AUTO"
            available.remove(nearest)
        return dispatches

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
                    idle_in_zone[i].mode = "SEARCH"
                    idle_in_zone[i].service_timer = self.SERVICE_TIME_SEC
                    z.queue -= 1

        # 4. Calculate imbalances and dispatches via the grid logic
        if self.coverage_mode == "threat_adaptive" and self._last_assessment is not None:
            dispatches = self._threat_adaptive_dispatches()
        else:
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
                if self.coverage_mode == "balanced":
                    u.tasking_source = "ZONE_BALANCE"
                self.active_flows.append({
                    "source": d["source_coord"],
                    "target": target_coord
                })

        # 6. Handle target-tracking modes (VIEWING, FOLLOWING, PAINTING, and new modes)
        self._update_tracking_modes(dt_sec)

        # 6b. Evaluate autonomy transitions
        self._evaluate_autonomy(dt_sec)

        # 7. Update Kinematics (handles IDLE, SCANNING, REPOSITIONING, RTB)
        for u in self.uavs:
            if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT", "SUPPORT", "VERIFY", "OVERWATCH", "BDA"):
                u.update(dt_sec, self.SPEED_DEG_PER_SEC)

        # 8. Decrement service timers for SCANNING UAVs
        for u in self.uavs:
            if u.mode == "SEARCH":
                u.service_timer -= dt_sec
                if u.service_timer <= 0:
                    u.mode = "IDLE"

        # 9. Update Targets & Probabilistic Detection
        uav_positions = [(u.x, u.y) for u in self.uavs]
        for t in self.targets:
            t.update(dt_sec, self.bounds, uav_positions)

            if t.state in ("DESTROYED", "ENGAGED"):
                continue

            contributions: list = []

            for u in self.uavs:
                if u.mode in ("RTB", "REPOSITIONING"):
                    continue

                # Use target's detection_range_km to gate detection if available
                if t.detection_range_km is not None:
                    dist_deg = math.hypot(u.x - t.x, u.y - t.y)
                    dist_km = dist_deg / DEG_PER_KM
                    if dist_km > t.detection_range_km:
                        continue

                # Compute aspect angle: bearing from UAV to target vs target heading
                dlat = t.y - u.y
                dlon = (t.x - u.x) * math.cos(math.radians((u.y + t.y) / 2.0))
                bearing_rad = math.atan2(dlon, dlat)
                bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
                aspect_deg = (bearing_deg - t.heading_deg + 360.0) % 360.0

                # Evaluate each sensor on this UAV
                for sensor_type in u.sensors:
                    result = evaluate_detection(
                        uav_lat=u.y,
                        uav_lon=u.x,
                        target_lat=t.y,
                        target_lon=t.x,
                        target_type=t.type,
                        sensor_type=sensor_type,
                        env=self.environment,
                        aspect_deg=aspect_deg,
                        emitting=t.is_emitting,
                    )
                    if result.detected:
                        contributions.append(SensorContribution(
                            uav_id=u.id,
                            sensor_type=sensor_type,
                            confidence=result.confidence,
                            range_m=result.range_m,
                            bearing_deg=result.bearing_deg,
                            timestamp=time.time(),
                        ))

            if contributions:
                # Fuse all contributions and update state
                fused = fuse_detections(contributions)
                t.sensor_contributions = list(fused.contributions)
                t.fused_confidence = fused.fused_confidence
                t.sensor_count = fused.sensor_count
                # tracked_by_uav_ids is managed by the command system (_assign_target / cancel_track)
                if t.state == "UNDETECTED":
                    t.state = "DETECTED"
                t.detection_confidence = fused.fused_confidence
                best = max(contributions, key=lambda c: c.confidence)
                t.detected_by_sensor = best.sensor_type
            else:
                # Fade logic for targets that lost sensor contact
                if t.state in ("DETECTED", "CLASSIFIED", "VERIFIED") and not t.tracked_by_uav_ids:
                    t.detection_confidence *= 0.95
                    t.fused_confidence *= 0.95
                    if t.detection_confidence < 0.1:
                        t.state = "UNDETECTED"
                        t.detection_confidence = 0.0
                        t.fused_confidence = 0.0
                        t.sensor_contributions = []
                        t.sensor_count = 0
                        t.detected_by_sensor = None

        # --- Verification step (Phase 2) ---
        _now = time.time()
        for t in self.targets:
            if t.state in ("UNDETECTED", "DESTROYED", "ENGAGED", "ESCAPED"):
                continue
            sensor_type_count = len(set(
                c.sensor_type for c in t.sensor_contributions
            )) if t.sensor_contributions else (1 if t.detection_confidence > 0 else 0)
            new_state = evaluate_target_state(
                current_state=t.state,
                target_type=t.type,
                fused_confidence=t.fused_confidence,
                sensor_type_count=sensor_type_count,
                time_in_current_state_sec=t.time_in_state_sec,
                seconds_since_last_sensor=_now - t.last_sensor_contact_time,
                demo_fast=self.demo_fast,
            )
            if new_state != t.state:
                old_state = t.state
                t.state = new_state
                t.time_in_state_sec = 0.0
                logger.info("target_state_transition", target_id=t.id, target_type=t.type,
                            from_state=old_state, to_state=new_state,
                            fused_confidence=t.fused_confidence)
            else:
                t.time_in_state_sec += dt_sec
            if t.detection_confidence > 0.05:
                t.last_sensor_contact_time = _now

        # 9b. Update Enemy UAVs (movement)
        for e in self.enemy_uavs:
            if e.mode != "DESTROYED":
                e.update(dt_sec, self.bounds)

        # 10. Enemy UAV Detection
        for e in self.enemy_uavs:
            if e.mode == "DESTROYED":
                continue
            contributions = []
            for u in self.uavs:
                if u.mode in ("RTB", "REPOSITIONING"):
                    continue
                dlat = e.y - u.y
                dlon = (e.x - u.x) * math.cos(math.radians((u.y + e.y) / 2.0))
                bearing_deg = (math.degrees(math.atan2(dlon, dlat)) + 360.0) % 360.0
                aspect_deg = (bearing_deg - e.heading_deg + 360.0) % 360.0
                for sensor_type in u.sensors:
                    result = evaluate_detection(
                        uav_lat=u.y,
                        uav_lon=u.x,
                        target_lat=e.y,
                        target_lon=e.x,
                        target_type="ENEMY_UAV",
                        sensor_type=sensor_type,
                        env=self.environment,
                        aspect_deg=aspect_deg,
                        emitting=e.is_jamming,
                    )
                    if result.detected:
                        contributions.append(SensorContribution(
                            uav_id=u.id,
                            sensor_type=sensor_type,
                            confidence=result.confidence,
                            range_m=result.range_m,
                            bearing_deg=result.bearing_deg,
                            timestamp=time.time(),
                        ))
            if contributions:
                fused = fuse_detections(contributions)
                e.fused_confidence = fused.fused_confidence
                e.sensor_count = fused.sensor_count
                e.sensor_contributions = list(fused.contributions)
                e.detected = True
            else:
                e.fused_confidence = max(0.0, e.fused_confidence * 0.95)
                e.detected = e.fused_confidence > 0.1

        # 11. Swarm coordination — auto-dispatch complementary sensors (throttled: every 50 ticks = 5s)
        # Note: autonomy tier integration deferred — full AUTONOMOUS/SUPERVISED/MANUAL gating
        # will be added when the autonomy tier selector phase is implemented. Operator
        # request_swarm/release_swarm WS actions always available regardless of tier.
        self._swarm_tick_counter += 1
        if self._swarm_tick_counter % 50 == 0:
            swarm_orders = self.swarm_coordinator.evaluate_and_assign(self.targets, self.uavs)
            for order in swarm_orders:
                uav = self._find_uav(order.uav_id)
                # Guard: skip if UAV already in SUPPORT for this target
                if uav and not (uav.mode == "SUPPORT" and order.target_id in uav.tracked_target_ids):
                    self._assign_target(order.uav_id, order.target_id, "SUPPORT", "DETECTED")

    def _update_enemy_intercept(self, u: UAV, dt_sec: float):
        """Handle UAV intercept of an enemy UAV (primary_target_id >= 1000)."""
        speed = self.SPEED_DEG_PER_SEC
        enemy = self._find_enemy_uav(u.primary_target_id)
        if not enemy or enemy.mode == "DESTROYED":
            u.mode = "SEARCH"
            u.primary_target_id = None
            u.vx = 0
            u.vy = 0
            return

        if not hasattr(u, '_intercept_dwell'):
            u._intercept_dwell = 0.0

        dx = enemy.x - u.x
        dy = enemy.y - u.y
        dist = math.hypot(dx, dy)

        if dist > INTERCEPT_CLOSE_DEG:
            # Approach: fly directly at enemy at 1.5x speed
            intercept_speed = speed * 1.5
            u._turn_toward((dx / dist) * intercept_speed, (dy / dist) * intercept_speed, intercept_speed, dt_sec)
            u.x += u.vx * dt_sec
            u.y += u.vy * dt_sec
        else:
            # Within kill range — accumulate dwell time, hold position
            u._intercept_dwell += dt_sec
            # Keep velocity zero while in dwell zone (hold over target)
            u.vx = 0.0
            u.vy = 0.0
            if u._intercept_dwell >= 3.0:
                # Kill!
                enemy.mode = "DESTROYED"
                enemy.vx = 0.0
                enemy.vy = 0.0
                u.mode = "SEARCH"
                u.primary_target_id = None
                u._intercept_dwell = 0.0
                logger.info("enemy_uav_destroyed", uav_id=u.id, enemy_id=enemy.id)
                return

        u.heading_deg = _heading_from_velocity(u.vx, u.vy)

    def _update_tracking_modes(self, dt_sec: float):
        speed = self.SPEED_DEG_PER_SEC
        for u in self.uavs:
            if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT", "SUPPORT", "VERIFY", "OVERWATCH", "BDA"):
                continue

            # OVERWATCH does not require a target — handle it first before target lookup
            if u.mode == "OVERWATCH":
                if not u.overwatch_waypoints:
                    cx, cy = u.x, u.y
                    half = OVERWATCH_RACETRACK_LENGTH_DEG / 2
                    u.overwatch_waypoints = [
                        (
                            max(self.bounds['min_lon'], min(self.bounds['max_lon'], cx - half)),
                            max(self.bounds['min_lat'], min(self.bounds['max_lat'], cy)),
                        ),
                        (
                            max(self.bounds['min_lon'], min(self.bounds['max_lon'], cx + half)),
                            max(self.bounds['min_lat'], min(self.bounds['max_lat'], cy)),
                        ),
                    ]
                    u.overwatch_wp_idx = 0
                wp = u.overwatch_waypoints[u.overwatch_wp_idx]
                dx, dy = wp[0] - u.x, wp[1] - u.y
                dist = math.hypot(dx, dy)
                if dist < 0.005:
                    u.overwatch_wp_idx = (u.overwatch_wp_idx + 1) % len(u.overwatch_waypoints)
                else:
                    u._turn_toward((dx / dist) * speed, (dy / dist) * speed, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec
                u.heading_deg = _heading_from_velocity(u.vx, u.vy)
                continue

            # Check if this is an enemy UAV intercept (IDs >= 1000)
            if u.primary_target_id is not None and u.primary_target_id >= 1000:
                self._update_enemy_intercept(u, dt_sec)
                continue

            target = self._find_target(u.tracked_target_id) if u.tracked_target_id is not None else None
            if not target:
                u.mode = "SEARCH"
                u.tracked_target_id = None
                u.vx = 0
                u.vy = 0
                continue

            dx = target.x - u.x
            dy = target.y - u.y
            dist = math.hypot(dx, dy)

            if u.mode == "FOLLOW":
                # Loose orbit at ~2km
                orbit_r = FOLLOW_ORBIT_RADIUS_DEG
                if dist < 0.001:
                    u.x -= orbit_r
                    dist = orbit_r
                    dx, dy = target.x - u.x, target.y - u.y
                nx, ny = dx / dist, dy / dist
                tx, ty = -ny, nx
                if dist < orbit_r * 0.8:
                    dvx = (-nx * 0.3 + tx * 0.7) * speed
                    dvy = (-ny * 0.3 + ty * 0.7) * speed
                elif dist > orbit_r * 1.2:
                    dvx = (nx * 0.3 + tx * 0.7) * speed
                    dvy = (ny * 0.3 + ty * 0.7) * speed
                else:
                    dvx, dvy = tx * speed, ty * speed
                u._turn_toward(dvx, dvy, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "PAINT":
                # Tight orbit at ~1km (laser lock)
                orbit_r = PAINT_ORBIT_RADIUS_DEG
                if dist < 0.001:
                    u.x -= orbit_r
                    dist = orbit_r
                    dx, dy = target.x - u.x, target.y - u.y
                nx, ny = dx / dist, dy / dist
                tx, ty = -ny, nx
                if dist < orbit_r * 0.8:
                    dvx = (-nx * 0.4 + tx * 0.6) * speed
                    dvy = (-ny * 0.4 + ty * 0.6) * speed
                elif dist > orbit_r * 1.2:
                    dvx = (nx * 0.4 + tx * 0.6) * speed
                    dvy = (ny * 0.4 + ty * 0.6) * speed
                else:
                    dvx, dvy = tx * speed, ty * speed
                u._turn_toward(dvx, dvy, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "INTERCEPT":
                # Fly directly at target, danger close (~300m)
                if dist > INTERCEPT_CLOSE_DEG:
                    intercept_speed = speed * 1.5
                    u._turn_toward((dx / dist) * intercept_speed, (dy / dist) * intercept_speed, intercept_speed, dt_sec)
                else:
                    # Arrived — tight orbit
                    nx, ny = dx / max(dist, 0.0001), dy / max(dist, 0.0001)
                    tx, ty = -ny, nx
                    u._turn_toward(tx * speed, ty * speed, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "SUPPORT":
                # Wide orbit at ~3km — secondary sensor coverage
                orbit_r = SUPPORT_ORBIT_RADIUS_DEG
                if dist < 0.001:
                    u.x -= orbit_r
                    dist = orbit_r
                    dx, dy = target.x - u.x, target.y - u.y
                nx, ny = dx / dist, dy / dist
                tx, ty = -ny, nx
                if dist < orbit_r * 0.8:
                    dvx = (-nx * 0.2 + tx * 0.8) * speed
                    dvy = (-ny * 0.2 + ty * 0.8) * speed
                elif dist > orbit_r * 1.2:
                    dvx = (nx * 0.2 + tx * 0.8) * speed
                    dvy = (ny * 0.2 + ty * 0.8) * speed
                else:
                    dvx, dvy = tx * speed, ty * speed
                u._turn_toward(dvx, dvy, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "VERIFY":
                # Sensor-specific pass pattern over target
                primary_sensor = u.sensors[0] if u.sensors else "EO_IR"
                orbit_r = VERIFY_CROSS_DISTANCE_DEG

                if primary_sensor == "EO_IR":
                    # Perpendicular cross pattern: alternate tangent directions
                    if dist < 0.001:
                        u.x -= orbit_r
                        dist = orbit_r
                        dx, dy = target.x - u.x, target.y - u.y
                    nx, ny = dx / dist, dy / dist
                    tx, ty = -ny, nx
                    if dist < orbit_r * 0.8:
                        dvx = (-nx * 0.3 + tx * 0.7) * speed
                        dvy = (-ny * 0.3 + ty * 0.7) * speed
                    elif dist > orbit_r * 1.5:
                        dvx = (nx * 0.5 + tx * 0.5) * speed
                        dvy = (ny * 0.5 + ty * 0.5) * speed
                    else:
                        dvx, dvy = tx * speed, ty * speed
                    u._turn_toward(dvx, dvy, speed, dt_sec)

                elif primary_sensor == "SAR":
                    # Parallel track: fly along heading axis of target
                    track_heading = math.radians(target.heading_deg) if hasattr(target, 'heading_deg') else 0.0
                    track_vx = math.sin(track_heading) * speed
                    track_vy = math.cos(track_heading) * speed
                    if dist > orbit_r * 2.0:
                        # Approach target
                        approach_vx = (dx / dist) * speed
                        approach_vy = (dy / dist) * speed
                        u._turn_toward(approach_vx, approach_vy, speed, dt_sec)
                    else:
                        u._turn_toward(track_vx, track_vy, speed, dt_sec)

                else:  # SIGINT — loiter circle over target
                    if dist < 0.001:
                        u.x -= orbit_r
                        dist = orbit_r
                        dx, dy = target.x - u.x, target.y - u.y
                    nx, ny = dx / dist, dy / dist
                    tx, ty = -ny, nx
                    if dist < orbit_r * 0.8:
                        dvx = (-nx * 0.3 + tx * 0.7) * speed
                        dvy = (-ny * 0.3 + ty * 0.7) * speed
                    elif dist > orbit_r * 1.2:
                        dvx = (nx * 0.3 + tx * 0.7) * speed
                        dvy = (ny * 0.3 + ty * 0.7) * speed
                    else:
                        dvx, dvy = tx * speed, ty * speed
                    u._turn_toward(dvx, dvy, speed, dt_sec)

                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "BDA":
                # Tight orbit for damage assessment — same radius as PAINT
                orbit_r = BDA_ORBIT_RADIUS_DEG
                u.bda_timer -= dt_sec
                if u.bda_timer <= 0:
                    u.mode = "SEARCH"
                    u.tracked_target_id = None
                    u.vx = 0
                    u.vy = 0
                    continue

                if dist < 0.001:
                    u.x -= orbit_r
                    dist = orbit_r
                    dx, dy = target.x - u.x, target.y - u.y
                nx, ny = dx / dist, dy / dist
                tx, ty = -ny, nx
                if dist < orbit_r * 0.8:
                    dvx = (-nx * 0.4 + tx * 0.6) * speed
                    dvy = (-ny * 0.4 + ty * 0.6) * speed
                elif dist > orbit_r * 1.2:
                    dvx = (nx * 0.4 + tx * 0.6) * speed
                    dvy = (ny * 0.4 + ty * 0.6) * speed
                else:
                    dvx, dvy = tx * speed, ty * speed
                u._turn_toward(dvx, dvy, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            u.heading_deg = _heading_from_velocity(u.vx, u.vy)

            # Keep detection confidence high while actively tracking
            target.detection_confidence = min(1.0, target.detection_confidence + 0.1 * dt_sec)
            target.fused_confidence = min(1.0, target.fused_confidence + 0.1 * dt_sec)
            target.detected_by_sensor = u.sensor_type

    def _effective_autonomy(self, uav: UAV) -> str:
        """Return the effective autonomy level for a UAV (override takes precedence)."""
        return uav.autonomy_override or self.autonomy_level

    def _detect_trigger(self, uav: UAV) -> Optional[str]:
        """Detect autonomy trigger conditions for a UAV. Returns trigger name or None."""
        if uav.mode == "IDLE":
            # Check if any target in same zone is DETECTED
            for t in self.targets:
                if t.state in ("DETECTED", "CLASSIFIED", "VERIFIED", "NOMINATED"):
                    z = self.grid.get_zone_at(t.x, t.y)
                    if z and z.id == uav.zone_id:
                        return "target_detected_in_zone"

        elif uav.mode == "SEARCH" and uav.tracked_target_id is not None:
            # Check if tracked target has high confidence
            target = self._find_target(uav.tracked_target_id)
            if target and target.detection_confidence >= 0.7:
                return "high_confidence_detection"

        return None

    def _evaluate_autonomy(self, dt_sec: float):
        """Evaluate autonomous transitions for all UAVs."""
        import time as _time
        now = _time.monotonic()

        # Expire timed-out pending transitions (auto-approve in SUPERVISED)
        for uav_id, pending in list(self.pending_transitions.items()):
            if now >= pending["expires_at"]:
                uav = self._find_uav(uav_id)
                if uav:
                    uav.mode = pending["mode"]
                    uav.mode_source = "AUTO"
                del self.pending_transitions[uav_id]

        for u in self.uavs:
            effective = self._effective_autonomy(u)
            if effective == "MANUAL":
                continue
            if u.id in self.pending_transitions:
                continue  # already has a pending transition

            trigger = self._detect_trigger(u)
            if trigger is None:
                continue
            key = (u.mode, trigger)
            new_mode = AUTONOMOUS_TRANSITIONS.get(key)
            if new_mode is None:
                continue

            if effective == "AUTONOMOUS":
                u.mode = new_mode
                u.mode_source = "AUTO"
            elif effective == "SUPERVISED":
                self.pending_transitions[u.id] = {
                    "mode": new_mode,
                    "reason": trigger,
                    "expires_at": now + self.supervised_timeout_sec,
                }

    def approve_transition(self, uav_id: int):
        """Apply a pending transition immediately."""
        pending = self.pending_transitions.pop(uav_id, None)
        if pending:
            uav = self._find_uav(uav_id)
            if uav:
                uav.mode = pending["mode"]
                uav.mode_source = "AUTO"

    def reject_transition(self, uav_id: int):
        """Remove a pending transition without changing mode."""
        self.pending_transitions.pop(uav_id, None)

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
            uav.tasking_source = "OPERATOR"
            # Clear any tracking
            if uav.tracked_target_id is not None:
                old_target = self._find_target(uav.tracked_target_id)
                if old_target:
                    old_target.tracked_by_uav_ids = [uid for uid in old_target.tracked_by_uav_ids if uid != uav_id]
                uav.tracked_target_id = None

    def _set_target_state(self, target_id: int, new_state: str):
        """Set a target's state directly (used by demo auto-pilot)."""
        target = self._find_target(target_id)
        if target and new_state in TARGET_STATES:
            target.state = new_state
            if new_state == "DESTROYED":
                target.vx = 0.0
                target.vy = 0.0
            logger.info("target_state_set", target_id=target_id, new_state=new_state)

    def reset_queues(self):
        for z in self.grid.zones.values():
            z.queue = 0
            z.demand_rate = z.base_lambda

    def _get_next_threshold(self, target) -> Optional[float]:
        thresh = VERIFICATION_THRESHOLDS.get(target.type, _DEFAULT_THRESHOLD)
        if target.state == "DETECTED":
            return thresh.classify_confidence
        if target.state == "CLASSIFIED":
            return thresh.verify_confidence
        return None

    def _compute_fov_targets(self, uav) -> list:
        """Return list of target IDs that are detected and within detection range of this UAV."""
        result = []
        for t in self.targets:
            if t.state == "UNDETECTED":
                continue
            dist_deg = math.hypot(uav.x - t.x, uav.y - t.y)
            range_km = t.detection_range_km if t.detection_range_km is not None else 15.0
            if dist_deg / DEG_PER_KM <= range_km:
                result.append(t.id)
        return result

    _SENSOR_QUALITY_MAP = {
        "PAINT": 1.0,
        "FOLLOW": 0.8,
        "INTERCEPT": 0.8,
        "SEARCH": 0.6,
        "SUPPORT": 0.7,
        "VERIFY": 0.9,
        "OVERWATCH": 0.5,
    }

    def get_state(self):
        return {
            "autonomy_level": self.autonomy_level,
            "uavs": [
                {
                    "id": u.id,
                    "lon": u.x,
                    "lat": u.y,
                    "mode": u.mode,
                    "altitude_m": u.altitude_m,
                    "sensor_type": u.sensor_type,
                    "sensors": u.sensors,
                    "heading_deg": round(u.heading_deg, 1),
                    "tracked_target_id": u.tracked_target_id,
                    "tracked_target_ids": list(u.tracked_target_ids),
                    "primary_target_id": u.primary_target_id,
                    "fuel_hours": round(u.fuel_hours, 2),
                    "autonomy_override": u.autonomy_override,
                    "mode_source": u.mode_source,
                    "tasking_source": u.tasking_source,
                    "pending_transition": self.pending_transitions.get(u.id),
                    "fov_targets": self._compute_fov_targets(u),
                    "sensor_quality": self._SENSOR_QUALITY_MAP.get(u.mode, 0.6),
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
                    "tracked_by_uav_ids": list(t.tracked_by_uav_ids),
                    "fused_confidence": round(t.fused_confidence, 3),
                    "sensor_count": t.sensor_count,
                    "sensor_contributions": [
                        {"uav_id": c.uav_id, "sensor_type": c.sensor_type, "confidence": round(c.confidence, 3)}
                        for c in sorted(t.sensor_contributions, key=lambda c: c.confidence, reverse=True)[:10]
                        if c.confidence > 0.05
                    ],
                    "threat_range_km": t.threat_range_km,
                    "detection_range_km": t.detection_range_km,
                    "time_in_state_sec": round(t.time_in_state_sec, 1),
                    "next_threshold": self._get_next_threshold(t),
                    "concealed": getattr(t, 'concealed', False),
                } for t in self.targets
            ],
            "enemy_uavs": [
                {
                    "id": e.id,
                    "lon": e.x,
                    "lat": e.y,
                    "mode": e.mode,
                    "behavior": e.behavior,
                    "heading_deg": round(e.heading_deg, 1),
                    "detected": e.detected,
                    "fused_confidence": round(e.fused_confidence, 3),
                    "sensor_count": e.sensor_count,
                    "is_jamming": e.is_jamming,
                } for e in self.enemy_uavs
            ],
            "environment": {
                "time_of_day": self.environment.time_of_day,
                "cloud_cover": self.environment.cloud_cover,
                "precipitation": self.environment.precipitation,
            },
            "theater": {
                "name": self.theater_name,
                "bounds": self.bounds,
            },
            "swarm_tasks": [
                {
                    "target_id": task.target_id,
                    "assigned_uav_ids": list(task.assigned_uav_ids),
                    "sensor_coverage": list(task.sensor_coverage),
                    "formation_type": task.formation_type,
                }
                for task in self.swarm_coordinator.get_active_tasks().values()
            ],
        }
