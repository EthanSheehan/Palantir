"""
enemy_uav_engine.py
===================
Enemy UAV entity and behavior logic extracted from sim_engine.py.

Manages enemy UAV movement patterns: RECON loiter, ATTACK approach,
JAMMING station-keeping, and EVADING maneuvers with cooldown logic.
"""

import math
import random
from typing import Optional, Tuple

from uav_physics import MAX_TURN_RATE, _heading_from_velocity

# Enemy UAV modes
ENEMY_UAV_MODES = ("RECON", "ATTACK", "JAMMING", "EVADING", "DESTROYED")

# Enemy UAV speed (deg/sec, ~440 km/h)
ENEMY_SPEED = 0.004


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
        self.x = max(bounds["min_lon"], min(bounds["max_lon"], self.x))
        self.y = max(bounds["min_lat"], min(bounds["max_lat"], self.y))

        # Update heading
        self.heading_deg = _heading_from_velocity(self.vx, self.vy)
