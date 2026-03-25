"""
uav_physics.py
==============
UAV entity and fixed-wing flight physics extracted from sim_engine.py.

Manages UAV movement: loiter circles, repositioning, RTB navigation,
fuel consumption, and turn-rate-limited heading changes.
"""

import math
import random
from typing import List, Optional, Tuple

# UAV modes
UAV_MODES = (
    "IDLE",
    "SEARCH",
    "FOLLOW",
    "PAINT",
    "INTERCEPT",
    "REPOSITIONING",
    "RTB",
    "SUPPORT",
    "VERIFY",
    "OVERWATCH",
    "BDA",
)

# RTB arrival threshold: switch to IDLE when within this distance of home (km)
ARRIVAL_THRESHOLD_KM = 0.5

# Max turn rate for fixed-wing (radians/sec, ~3 deg/sec standard rate turn)
MAX_TURN_RATE = math.radians(3.0)

# Degrees per km (approximate)
DEG_PER_KM = 1.0 / 111.0

# Sensor distribution weights: (sensors, weight)
_SENSOR_DISTRIBUTION = [
    (["EO_IR"], 50),
    (["SAR"], 20),
    (["SIGINT"], 10),
    (["EO_IR", "SAR"], 10),
    (["EO_IR", "SIGINT"], 10),
]


def _pick_sensors() -> List[str]:
    population = [s for s, w in _SENSOR_DISTRIBUTION for _ in range(w)]
    return list(random.choice(population))


def _heading_from_velocity(vx: float, vy: float) -> float:
    if abs(vx) < 1e-9 and abs(vy) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(vx, vy)) % 360.0


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
        self.home_position: Tuple[float, float] = (x, y)

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
        self._intercept_dwell: float = 0.0

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
            home_x, home_y = self.home_position
            dx = home_x - self.x
            dy = home_y - self.y
            dist_deg = math.hypot(dx, dy)
            if dist_deg < ARRIVAL_THRESHOLD_KM * DEG_PER_KM:
                self.mode = "IDLE"
                self.vx = 0.0
                self.vy = 0.0
            else:
                self._turn_toward((dx / dist_deg) * speed, (dy / dist_deg) * speed, speed, dt_sec)
                self.x += self.vx * dt_sec
                self.y += self.vy * dt_sec
                # Re-check arrival after moving (handles overshoot at speed)
                if math.hypot(home_x - self.x, home_y - self.y) < ARRIVAL_THRESHOLD_KM * DEG_PER_KM:
                    self.mode = "IDLE"
                    self.vx = 0.0
                    self.vy = 0.0

        # FOLLOW, PAINT, INTERCEPT etc. are handled in SimulationModel._update_tracking_modes()

        self.fuel_hours -= (dt_sec / 3600.0) * self.fuel_rate
        self.fuel_hours = max(0.0, self.fuel_hours)
        if self.fuel_hours < 1.0 and self.mode != "RTB":
            self.mode = "RTB"

        self.heading_deg = _heading_from_velocity(self.vx, self.vy)
