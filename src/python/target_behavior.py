"""
target_behavior.py
==================
Target entity and behavior logic extracted from sim_engine.py.

Manages ground target movement patterns: stationary, shoot-and-scoot,
patrol, and ambush behaviors. All target state and movement logic lives here.
"""

import math
import random
import time
from collections import deque
from typing import List, Optional, Tuple

# Target states in the kill chain
TARGET_STATES = (
    "UNDETECTED",
    "DETECTED",
    "CLASSIFIED",
    "VERIFIED",
    "TRACKED",
    "IDENTIFIED",
    "NOMINATED",
    "LOCKED",
    "ENGAGED",
    "DESTROYED",
    "ESCAPED",
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

# Maximum number of position history entries per target
POSITION_HISTORY_MAXLEN = 60


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
                math.hypot(ux - self.x, uy - self.y) < CONCEALMENT_DIST_DEG for ux, uy in uav_positions
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
                    self.x = random.uniform(bounds["min_lon"], bounds["max_lon"])
                    self.y = random.uniform(bounds["min_lat"], bounds["max_lat"])
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
                        random.uniform(bounds["min_lon"], bounds["max_lon"]),
                        random.uniform(bounds["min_lat"], bounds["max_lat"]),
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

            if self.x < bounds["min_lon"] or self.x > bounds["max_lon"]:
                self.vx *= -1
                self.x = max(bounds["min_lon"], min(bounds["max_lon"], self.x))
            if self.y < bounds["min_lat"] or self.y > bounds["max_lat"]:
                self.vy *= -1
                self.y = max(bounds["min_lat"], min(bounds["max_lat"], self.y))

        elif self.behavior == "ambush":
            if self.flee_cooldown <= 0:
                for ux, uy in uav_positions:
                    if math.hypot(ux - self.x, uy - self.y) < MANPADS_FLEE_DIST_DEG:
                        flee_dx = random.uniform(-0.1, 0.1)
                        flee_dy = random.uniform(-0.1, 0.1)
                        self.x = max(bounds["min_lon"], min(bounds["max_lon"], self.x + flee_dx))
                        self.y = max(bounds["min_lat"], min(bounds["max_lat"], self.y + flee_dy))
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
