"""
sim_engine.py
=============
Simulation orchestrator for the Palantir C2 system.

This module owns only the tick() loop and coordination logic.
Entity classes and physics live in dedicated sub-modules:
  - target_behavior.py  — Target class, ground unit behaviors
  - uav_physics.py      — UAV class, fixed-wing flight model
  - enemy_uav_engine.py — EnemyUAV class, adversary behaviors
"""

import math
import random
import time
from typing import Dict, Optional

import structlog
from enemy_uav_engine import ENEMY_UAV_MODES, EnemyUAV
from romania_grid import RomaniaMacroGrid
from sensor_fusion import SensorContribution, fuse_detections
from sensor_model import EnvironmentConditions, evaluate_detection
from ops_alerts import OpsAlertManager
from swarm_coordinator import SwarmCoordinator, TaskingOrder
from target_behavior import (
    EMITTING_TYPES,
    TARGET_STATES,
    UNIT_BEHAVIOR,
    Target,
)
from theater_loader import TheaterConfig, load_theater
from uav_physics import (
    DEG_PER_KM,
    UAV,
    _heading_from_velocity,
)
from verification_engine import _DEFAULT_THRESHOLD, VERIFICATION_THRESHOLDS, evaluate_target_state

logger = structlog.get_logger()

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

# Confidence fade constants for untracked targets
CONFIDENCE_FADE_FACTOR = 0.95
CONFIDENCE_FADE_THRESHOLD = 0.1

# Minimum idle UAV count to maintain before threat-adaptive dispatch
MIN_IDLE_COUNT = 3

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
SUPPORT_ORBIT_RADIUS_DEG = 0.027  # ~3km wide orbit for secondary coverage
VERIFY_CROSS_DISTANCE_DEG = 0.009  # ~1km perpendicular offset for sensor passes
OVERWATCH_RACETRACK_LENGTH_DEG = 0.045  # ~5km racetrack legs for area coverage
BDA_ORBIT_RADIUS_DEG = 0.009  # ~1km tight orbit for damage assessment
BDA_DURATION_SEC = 30.0  # Auto-transition to SEARCH after 30s
SUPERVISED_TIMEOUT_SEC = 10.0  # Supervised pending transition auto-approve timeout


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
        self.uavs: Dict[int, UAV] = {}

        if self.theater:
            self.NUM_UAVS = self.theater.blue_force.uavs.count
            self.bounds = {
                "min_lon": self.theater.bounds.min_lon,
                "max_lon": self.theater.bounds.max_lon,
                "min_lat": self.theater.bounds.min_lat,
                "max_lat": self.theater.bounds.max_lat,
            }
            self.environment = EnvironmentConditions()
        else:
            self.NUM_UAVS = 20
            self.bounds = {
                "min_lon": self.grid.MIN_LON,
                "max_lon": self.grid.MAX_LON,
                "min_lat": self.grid.MIN_LAT,
                "max_lat": self.grid.MAX_LAT,
            }
            self.environment = EnvironmentConditions()

        # Phase 3: autonomy system fields
        self.autonomy_level: str = "MANUAL"
        from autonomy_policy import AutonomyPolicy

        self.autonomy_policy: AutonomyPolicy = AutonomyPolicy(default_level="MANUAL")
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
        self.targets: Dict[int, Target] = {}
        self.enemy_uavs: Dict[int, EnemyUAV] = {}
        self.NUM_TARGETS = sum(c for _, c in self._build_target_pool())
        self.demo_fast: bool = False

        # Ops alert management
        self.ops_alert_manager = OpsAlertManager()

        # Phase 5: swarm coordination
        self.swarm_coordinator = SwarmCoordinator(min_idle_count=2)
        self._swarm_tick_counter = 0

        self.initialize()

    def _build_target_pool(self) -> list:
        if not self.theater:
            return [("SAM", 3), ("TEL", 4), ("TRUCK", 8), ("CP", 2)]
        return [(u.type, u.count) for u in self.theater.red_force.units]

    def initialize(self):
        zone_keys = list(self.grid.zones.keys())

        for i in range(self.NUM_UAVS):
            if not zone_keys:
                break
            zx, zy = random.choice(zone_keys)
            z = self.grid.zones[(zx, zy)]
            ux = z.lon + random.uniform(-z.width_deg / 3, z.width_deg / 3)
            uy = z.lat + random.uniform(-z.height_deg / 3, z.height_deg / 3)
            uav = UAV(i, ux, uy, (zx, zy))
            if self.theater:
                uav.target_altitude_m = float(self.theater.blue_force.uavs.default_altitude_m)
                uav.sensor_type = self.theater.blue_force.uavs.sensor_type
                uav.fuel_hours = float(self.theater.blue_force.uavs.endurance_hours)
                uav.home_position = (
                    self.theater.blue_force.uavs.base_lon,
                    self.theater.blue_force.uavs.base_lat,
                )
            uav.altitude_m = uav.launch_start_alt
            self.uavs[uav.id] = uav

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
                if unit_type in self._unit_speed_map:
                    t.speed = self._unit_speed_map[unit_type]
                t.threat_range_km = self._unit_threat_range_map.get(unit_type)
                t.detection_range_km = self._unit_detection_range_map.get(unit_type)
                target_id += 1
                self.targets[t.id] = t

        self._spawn_enemy_uavs()

    def _spawn_enemy_uavs(self):
        self.enemy_uavs = {}
        eid = 1001

        if self.theater and self.theater.enemy_uavs:
            for unit_cfg in self.theater.enemy_uavs.units:
                mode = unit_cfg.behavior.upper()
                if mode not in ENEMY_UAV_MODES:
                    mode = "RECON"
                speed_deg_sec = unit_cfg.speed_kmh * DEG_PER_KM / 3600.0
                for _ in range(unit_cfg.count):
                    ex = random.uniform(self.bounds["min_lon"], self.bounds["max_lon"])
                    ey = random.uniform(self.bounds["min_lat"], self.bounds["max_lat"])
                    e = EnemyUAV(id=eid, x=ex, y=ey, mode=mode, behavior=unit_cfg.behavior.lower())
                    if speed_deg_sec > 0:
                        e.speed = speed_deg_sec
                    if mode == "JAMMING":
                        e.is_jamming = True
                    self.enemy_uavs[e.id] = e
                    eid += 1
        else:
            for _ in range(3):
                ex = random.uniform(self.bounds["min_lon"], self.bounds["max_lon"])
                ey = random.uniform(self.bounds["min_lat"], self.bounds["max_lat"])
                e = EnemyUAV(id=eid, x=ex, y=ey, mode="RECON", behavior="recon")
                self.enemy_uavs[e.id] = e
                eid += 1

    def _find_enemy_uav(self, enemy_uav_id: int) -> Optional[EnemyUAV]:
        return self.enemy_uavs.get(enemy_uav_id)

    def _find_uav(self, uav_id: int) -> Optional[UAV]:
        return self.uavs.get(uav_id)

    def _find_target(self, target_id: int) -> Optional[Target]:
        return self.targets.get(target_id)

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
        target = self._find_target(target_id)
        if not target:
            return
        orders = self.swarm_coordinator.evaluate_and_assign([target], list(self.uavs.values()), force=True)
        for order in orders:
            uav = self._find_uav(order.uav_id)
            if uav and not (uav.mode == "SUPPORT" and order.target_id in uav.tracked_target_ids):
                self._assign_target(order.uav_id, order.target_id, "SUPPORT", "DETECTED")

    def release_swarm(self, target_id: int):
        for u in self.uavs.values():
            if u.mode == "SUPPORT" and target_id in u.tracked_target_ids:
                self.cancel_track(u.id)

    def set_coverage_mode(self, mode: str):
        if mode in ("balanced", "threat_adaptive"):
            self.coverage_mode = mode

    def _threat_adaptive_dispatches(self) -> list:
        if self._last_assessment is None:
            return []
        idle_uavs = [u for u in self.uavs.values() if u.mode == "IDLE"]
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
            dispatches.append(
                {
                    "source_id": nearest.zone_id,
                    "count": 1,
                    "source_coord": (nearest.x, nearest.y),
                    "target_coord": (gap["lon"], gap["lat"]),
                }
            )
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

        for u in self.uavs.values():
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

        # 3. Assign Missions
        for z_id, z in self.grid.zones.items():
            if z.queue > 0:
                idle_in_zone = [u for u in self.uavs.values() if u.zone_id == z_id and u.mode == "IDLE"]
                assign_count = min(z.queue, len(idle_in_zone))
                for i in range(assign_count):
                    idle_in_zone[i].mode = "SEARCH"
                    idle_in_zone[i].service_timer = self.SERVICE_TIME_SEC
                    z.queue -= 1

        # 4. Calculate imbalances and dispatches
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

            idle_in_r = [u for u in self.uavs.values() if u.zone_id == source_id and u.mode == "IDLE"]
            dispatched_count = min(count, len(idle_in_r))

            for i in range(dispatched_count):
                u = idle_in_r[i]
                u.mode = "REPOSITIONING"
                u.target = target_coord
                if self.coverage_mode == "balanced":
                    u.tasking_source = "ZONE_BALANCE"
                self.active_flows.append({"source": d["source_coord"], "target": target_coord})

        # 6. Handle target-tracking modes (FOLLOW, PAINT, INTERCEPT, and new modes)
        self._update_tracking_modes(dt_sec)

        # 6b. Evaluate autonomy transitions
        self._evaluate_autonomy(dt_sec)

        # 6c. Launch phase: climb to operating altitude
        for u in self.uavs.values():
            if u.launch_phase:
                u.altitude_m += u.launch_climb_rate * dt_sec
                if u.altitude_m >= u.target_altitude_m:
                    u.altitude_m = u.target_altitude_m
                    u.launch_phase = False

        # 7. Update Kinematics (handles IDLE, SEARCH, REPOSITIONING, RTB)
        for u in self.uavs.values():
            if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT", "SUPPORT", "VERIFY", "OVERWATCH", "BDA"):
                u.update(dt_sec, self.SPEED_DEG_PER_SEC)

        # 8. Decrement service timers
        for u in self.uavs.values():
            if u.mode == "SEARCH":
                u.service_timer -= dt_sec
                if u.service_timer <= 0:
                    u.mode = "IDLE"

        # 9. Update Targets & Probabilistic Detection
        uav_positions = [(u.x, u.y) for u in self.uavs.values()]
        for t in self.targets.values():
            t.update(dt_sec, self.bounds, uav_positions)

            if t.state in ("DESTROYED", "ENGAGED"):
                continue

            contributions: list = []

            for u in self.uavs.values():
                if u.mode in ("RTB", "REPOSITIONING"):
                    continue

                if t.detection_range_km is not None:
                    dist_deg = math.hypot(u.x - t.x, u.y - t.y)
                    dist_km = dist_deg / DEG_PER_KM
                    if dist_km > t.detection_range_km:
                        continue

                dlat = t.y - u.y
                dlon = (t.x - u.x) * math.cos(math.radians((u.y + t.y) / 2.0))
                bearing_rad = math.atan2(dlon, dlat)
                bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
                aspect_deg = (bearing_deg - t.heading_deg + 360.0) % 360.0

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
                        altitude_m=u.altitude_m,
                    )
                    if result.detected:
                        contributions.append(
                            SensorContribution(
                                uav_id=u.id,
                                sensor_type=sensor_type,
                                confidence=result.confidence,
                                range_m=result.range_m,
                                bearing_deg=result.bearing_deg,
                                timestamp=time.time(),
                            )
                        )

            if contributions:
                fused = fuse_detections(contributions)
                t.sensor_contributions = list(fused.contributions)
                t.fused_confidence = fused.fused_confidence
                t.sensor_count = fused.sensor_count
                if t.state == "UNDETECTED":
                    t.state = "DETECTED"
                t.detection_confidence = fused.fused_confidence
                best = max(contributions, key=lambda c: c.confidence)
                t.detected_by_sensor = best.sensor_type
            else:
                if t.state in ("DETECTED", "CLASSIFIED", "VERIFIED") and not t.tracked_by_uav_ids:
                    t.detection_confidence *= CONFIDENCE_FADE_FACTOR
                    t.fused_confidence *= CONFIDENCE_FADE_FACTOR
                    if t.detection_confidence < CONFIDENCE_FADE_THRESHOLD:
                        t.state = "UNDETECTED"
                        t.detection_confidence = 0.0
                        t.fused_confidence = 0.0
                        t.sensor_contributions = []
                        t.sensor_count = 0
                        t.detected_by_sensor = None

        # --- Verification step (Phase 2) ---
        _now = time.time()
        for t in self.targets.values():
            if t.state in ("UNDETECTED", "DESTROYED", "ENGAGED", "ESCAPED"):
                continue
            sensor_type_count = (
                len(set(c.sensor_type for c in t.sensor_contributions))
                if t.sensor_contributions
                else (1 if t.detection_confidence > 0 else 0)
            )
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
                logger.info(
                    "target_state_transition",
                    target_id=t.id,
                    target_type=t.type,
                    from_state=old_state,
                    to_state=new_state,
                    fused_confidence=t.fused_confidence,
                )
            else:
                t.time_in_state_sec += dt_sec
            if t.detection_confidence > 0.05:
                t.last_sensor_contact_time = _now

        # 9b. Update Enemy UAVs (movement)
        for e in self.enemy_uavs.values():
            if e.mode != "DESTROYED":
                e.update(dt_sec, self.bounds)

        # 10. Enemy UAV Detection
        for e in self.enemy_uavs.values():
            if e.mode == "DESTROYED":
                continue
            contributions = []
            for u in self.uavs.values():
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
                        altitude_m=u.altitude_m,
                    )
                    if result.detected:
                        contributions.append(
                            SensorContribution(
                                uav_id=u.id,
                                sensor_type=sensor_type,
                                confidence=result.confidence,
                                range_m=result.range_m,
                                bearing_deg=result.bearing_deg,
                                timestamp=time.time(),
                            )
                        )
            if contributions:
                fused = fuse_detections(contributions)
                e.fused_confidence = fused.fused_confidence
                e.sensor_count = fused.sensor_count
                e.sensor_contributions = list(fused.contributions)
                e.detected = True
            else:
                e.fused_confidence = max(0.0, e.fused_confidence * CONFIDENCE_FADE_FACTOR)
                e.detected = e.fused_confidence > CONFIDENCE_FADE_THRESHOLD

        # 11. Swarm coordination
        self._swarm_tick_counter += 1
        if self._swarm_tick_counter % 50 == 0:
            swarm_orders = self.swarm_coordinator.evaluate_and_assign(
                list(self.targets.values()),
                list(self.uavs.values()),
                autonomy_level=self.autonomy_level,
            )
            for order in swarm_orders:
                if not isinstance(order, TaskingOrder):
                    continue
                uav = self._find_uav(order.uav_id)
                if uav and not (uav.mode == "SUPPORT" and order.target_id in uav.tracked_target_ids):
                    self._assign_target(order.uav_id, order.target_id, "SUPPORT", "DETECTED")

        # 12. Ops alert evaluation
        for u in self.uavs.values():
            self.ops_alert_manager.evaluate_drone(u.id, u.fuel_hours, u.mode)

    def _update_enemy_intercept(self, u: UAV, dt_sec: float):
        speed = self.SPEED_DEG_PER_SEC
        enemy = self._find_enemy_uav(u.primary_target_id)
        if not enemy or enemy.mode == "DESTROYED":
            u.mode = "SEARCH"
            u.primary_target_id = None
            u.vx = 0
            u.vy = 0
            return

        dx = enemy.x - u.x
        dy = enemy.y - u.y
        dist = math.hypot(dx, dy)

        if dist > INTERCEPT_CLOSE_DEG:
            intercept_speed = speed * 1.5
            u._turn_toward((dx / dist) * intercept_speed, (dy / dist) * intercept_speed, intercept_speed, dt_sec)
            u.x += u.vx * dt_sec
            u.y += u.vy * dt_sec
        else:
            u._intercept_dwell += dt_sec
            u.vx = 0.0
            u.vy = 0.0
            if u._intercept_dwell >= 3.0:
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
        for u in self.uavs.values():
            if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT", "SUPPORT", "VERIFY", "OVERWATCH", "BDA"):
                continue

            if u.mode == "OVERWATCH":
                if not u.overwatch_waypoints:
                    cx, cy = u.x, u.y
                    half = OVERWATCH_RACETRACK_LENGTH_DEG / 2
                    u.overwatch_waypoints = [
                        (
                            max(self.bounds["min_lon"], min(self.bounds["max_lon"], cx - half)),
                            max(self.bounds["min_lat"], min(self.bounds["max_lat"], cy)),
                        ),
                        (
                            max(self.bounds["min_lon"], min(self.bounds["max_lon"], cx + half)),
                            max(self.bounds["min_lat"], min(self.bounds["max_lat"], cy)),
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
                if dist > INTERCEPT_CLOSE_DEG:
                    intercept_speed = speed * 1.5
                    u._turn_toward(
                        (dx / dist) * intercept_speed, (dy / dist) * intercept_speed, intercept_speed, dt_sec
                    )
                else:
                    nx, ny = dx / max(dist, 0.0001), dy / max(dist, 0.0001)
                    tx, ty = -ny, nx
                    u._turn_toward(tx * speed, ty * speed, speed, dt_sec)
                u.x += u.vx * dt_sec
                u.y += u.vy * dt_sec

            elif u.mode == "SUPPORT":
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
                primary_sensor = u.sensors[0] if u.sensors else "EO_IR"
                orbit_r = VERIFY_CROSS_DISTANCE_DEG

                if primary_sensor == "EO_IR":
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
                    track_heading = math.radians(target.heading_deg) if hasattr(target, "heading_deg") else 0.0
                    track_vx = math.sin(track_heading) * speed
                    track_vy = math.cos(track_heading) * speed
                    if dist > orbit_r * 2.0:
                        approach_vx = (dx / dist) * speed
                        approach_vy = (dy / dist) * speed
                        u._turn_toward(approach_vx, approach_vy, speed, dt_sec)
                    else:
                        u._turn_toward(track_vx, track_vy, speed, dt_sec)

                else:
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

            target.detection_confidence = min(1.0, target.detection_confidence + 0.1 * dt_sec)
            target.fused_confidence = min(1.0, target.fused_confidence + 0.1 * dt_sec)
            target.detected_by_sensor = u.sensor_type

    def _effective_autonomy(self, uav: UAV) -> str:
        return uav.autonomy_override or self.autonomy_level

    def _detect_trigger(self, uav: UAV) -> Optional[str]:
        if uav.mode == "IDLE":
            for t in self.targets.values():
                if t.state in ("DETECTED", "CLASSIFIED", "VERIFIED", "NOMINATED"):
                    z = self.grid.get_zone_at(t.x, t.y)
                    if z and z.id == uav.zone_id:
                        return "target_detected_in_zone"

        elif uav.mode == "SEARCH" and uav.tracked_target_id is not None:
            target = self._find_target(uav.tracked_target_id)
            if target and target.detection_confidence >= 0.7:
                return "high_confidence_detection"

        return None

    def _evaluate_autonomy(self, dt_sec: float):
        now = time.monotonic()

        for uav_id, pending in list(self.pending_transitions.items()):
            if now >= pending["expires_at"]:
                uav = self._find_uav(uav_id)
                if uav:
                    uav.mode = pending["mode"]
                    uav.mode_source = "AUTO"
                del self.pending_transitions[uav_id]

        for u in self.uavs.values():
            effective = self._effective_autonomy(u)
            if effective == "MANUAL":
                continue
            if u.id in self.pending_transitions:
                continue

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
        pending = self.pending_transitions.pop(uav_id, None)
        if pending:
            uav = self._find_uav(uav_id)
            if uav:
                uav.mode = pending["mode"]
                uav.mode_source = "AUTO"

    def reject_transition(self, uav_id: int):
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
            if uav.tracked_target_id is not None:
                old_target = self._find_target(uav.tracked_target_id)
                if old_target:
                    old_target.tracked_by_uav_ids = [uid for uid in old_target.tracked_by_uav_ids if uid != uav_id]
                uav.tracked_target_id = None

    def _set_target_state(self, target_id: int, new_state: str):
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
        result = []
        for t in self.targets.values():
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
                    "launch_phase": u.launch_phase,
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
                }
                for u in self.uavs.values()
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
                    "imbalance": z.imbalance,
                }
                for z in self.grid.zones.values()
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
                    "concealed": getattr(t, "concealed", False),
                }
                for t in self.targets.values()
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
                }
                for e in self.enemy_uavs.values()
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
            "ops_alerts": self.ops_alert_manager.get_active_alerts(),
        }
