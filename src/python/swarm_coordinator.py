"""
swarm_coordinator.py
====================
Pure-logic swarm coordination module for Grid-Sentinel C2.

Implements optimal UAV-to-target assignment via Hungarian algorithm
(scipy.optimize.linear_sum_assignment), with idle-count guard, sensor-gap
detection, priority scoring, 120-second task expiry, auto-release on
target state transitions, drone loss promotion, and Byzantine position
anomaly detection. No I/O, no side effects.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SENSOR_TYPES = ("EO_IR", "SAR", "SIGINT")

THREAT_WEIGHTS: Dict[str, float] = {
    "SAM": 1.0,
    "TEL": 0.9,
    "MANPADS": 0.8,
    "RADAR": 0.9,
    "ARTILLERY": 0.8,
    "CP": 0.7,
    "APC": 0.6,
    "C2_NODE": 0.6,
    "TRUCK": 0.5,
    "LOGISTICS": 0.3,
}

_TASK_EXPIRY_SECONDS = 120.0
_ASSIGNABLE_MODES = frozenset({"IDLE", "SEARCH"})
_RESOLVED_STATES = frozenset({"VERIFIED", "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED"})
_BYZANTINE_THRESHOLD_KM = 50.0
_DRONE_LOSS_PRIORITY_BOOST = 1.5


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwarmTask:
    target_id: int
    assigned_uav_ids: tuple[int, ...]
    sensor_coverage: tuple[str, ...]
    formation_type: str = "SUPPORT_RING"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class TaskingOrder:
    uav_id: int
    target_id: int
    mode: str
    reason: str
    priority: int


@dataclass(frozen=True)
class SwarmRecommendation:
    uav_id: int
    target_id: int
    mode: str
    reason: str
    priority: int
    autonomy_level: str


# ---------------------------------------------------------------------------
# SwarmCoordinator
# ---------------------------------------------------------------------------


class SwarmCoordinator:
    """Greedy swarm coordinator: assigns nearest eligible UAV to cover sensor
    gaps on active targets, respecting the idle-count floor."""

    def __init__(self, min_idle_count: int = 2) -> None:
        self.min_idle_count = min_idle_count
        self._active_tasks: Dict[int, SwarmTask] = {}
        self._last_positions: Dict[int, Tuple[float, float]] = {}
        self._byzantine_flagged: set[int] = set()
        self._promoted_targets: set[int] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    _VALID_AUTONOMY_LEVELS = frozenset({"AUTONOMOUS", "SUPERVISED", "MANUAL"})

    def evaluate_and_assign(
        self,
        targets: list,
        uavs: list,
        *,
        autonomy_level: str = "AUTONOMOUS",
        force: bool = False,
    ) -> list:
        """Score targets, fill sensor gaps, return new TaskingOrders or SwarmRecommendations.

        autonomy_level controls behavior:
        - AUTONOMOUS (default): execute assignments, update _active_tasks
        - SUPERVISED / MANUAL: return SwarmRecommendation objects only (no execution)
        - force=True overrides autonomy gating — always executes

        When force=True (operator request), skip state filtering and auto-release
        so that any target state can receive swarm support.
        """
        if autonomy_level not in self._VALID_AUTONOMY_LEVELS:
            raise ValueError(
                f"autonomy_level must be one of {sorted(self._VALID_AUTONOMY_LEVELS)}, got {autonomy_level!r}"
            )
        now = time.time()

        # 1. Expiry check — remove stale tasks and release SUPPORT UAVs
        expired_ids = [tid for tid, task in self._active_tasks.items() if now - task.created_at > _TASK_EXPIRY_SECONDS]
        for tid in expired_ids:
            self._release_support_uavs(tid, uavs)
            del self._active_tasks[tid]

        if not force:
            # 2. Auto-release on resolved target state (skip when force — operator wants support)
            target_map = {t.id: t for t in targets}
            resolved_ids = [
                tid
                for tid in list(self._active_tasks)
                if tid in target_map and target_map[tid].state in _RESOLVED_STATES
            ]
            for tid in resolved_ids:
                self._release_support_uavs(tid, uavs)
                del self._active_tasks[tid]
        else:
            target_map = {t.id: t for t in targets}

        # 3. Remove tasks for targets no longer present (destroyed, etc.)
        gone_ids = [tid for tid in list(self._active_tasks) if tid not in target_map]
        for tid in gone_ids:
            del self._active_tasks[tid]

        # 4. Byzantine position anomaly detection
        self._detect_byzantine(uavs)

        # 5. Drone loss detection — promote orphaned tasks
        self._detect_drone_loss(uavs)

        # 6. Score targets that have sensor gaps
        #    force=True: all targets eligible; otherwise only DETECTED/CLASSIFIED
        scored: List[tuple[float, object]] = []
        for target in targets:
            if not force and target.state not in ("DETECTED", "CLASSIFIED"):
                continue
            gap = self._sensor_gap(target)
            if not gap:
                continue
            score = self._priority_score(target)
            if target.id in self._promoted_targets:
                score *= _DRONE_LOSS_PRIORITY_BOOST
            scored.append((score, target))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 7. Count available (IDLE/SEARCH) UAVs, excluding Byzantine-flagged
        available = [u for u in uavs if u.mode in _ASSIGNABLE_MODES and u.id not in self._byzantine_flagged]
        idle_count = len(available)

        # 8. Build task list: (target, sensor_type) pairs ordered by priority
        task_list: List[tuple[object, str]] = []
        for _score, target in scored:
            gap = self._sensor_gap(target)
            for sensor_type in gap:
                task_list.append((target, sensor_type))

        # 9. Hungarian optimal assignment
        orders = self._hungarian_assign(available, task_list, idle_count)

        # 7. If non-autonomous and not forced, return recommendations only
        if autonomy_level != "AUTONOMOUS" and not force:
            return [
                SwarmRecommendation(
                    uav_id=o.uav_id,
                    target_id=o.target_id,
                    mode=o.mode,
                    reason=o.reason,
                    priority=o.priority,
                    autonomy_level=autonomy_level,
                )
                for o in orders
            ]

        # 8. Update _active_tasks for targets that received orders
        assigned_by_target: Dict[int, List[TaskingOrder]] = {}
        for order in orders:
            assigned_by_target.setdefault(order.target_id, []).append(order)

        for target_id, target_orders in assigned_by_target.items():
            existing = self._active_tasks.get(target_id)
            new_uav_ids = tuple(o.uav_id for o in target_orders)
            new_sensor_types = tuple(o.reason for o in target_orders)

            if existing is not None:
                # Merge: preserve created_at, accumulate assigned UAVs/sensors
                merged_uavs = tuple(sorted(set(existing.assigned_uav_ids) | set(new_uav_ids)))
                merged_sensors = tuple(sorted(set(existing.sensor_coverage) | set(new_sensor_types)))
                self._active_tasks[target_id] = SwarmTask(
                    target_id=target_id,
                    assigned_uav_ids=merged_uavs,
                    sensor_coverage=merged_sensors,
                    created_at=existing.created_at,
                )
            else:
                self._active_tasks[target_id] = SwarmTask(
                    target_id=target_id,
                    assigned_uav_ids=new_uav_ids,
                    sensor_coverage=new_sensor_types,
                )

        return orders

    def get_active_tasks(self) -> Dict[int, SwarmTask]:
        return dict(self._active_tasks)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_byzantine(self, uavs: list) -> None:
        """Flag UAVs whose position jumped >50km since last tick."""
        self._byzantine_flagged.clear()
        for uav in uavs:
            if uav.id in self._last_positions:
                prev_x, prev_y = self._last_positions[uav.id]
                dx = (uav.x - prev_x) * 111.0  # rough deg→km at equator
                dy = (uav.y - prev_y) * 111.0
                dist_km = math.hypot(dx, dy)
                if dist_km > _BYZANTINE_THRESHOLD_KM:
                    self._byzantine_flagged.add(uav.id)
            self._last_positions[uav.id] = (uav.x, uav.y)

    def _detect_drone_loss(self, uavs: list) -> None:
        """Detect lost UAVs and mark their tasks for priority promotion."""
        current_uav_ids = {u.id for u in uavs}
        for tid, task in list(self._active_tasks.items()):
            lost = [uid for uid in task.assigned_uav_ids if uid not in current_uav_ids]
            if lost:
                self._promoted_targets.add(tid)
                remaining = tuple(uid for uid in task.assigned_uav_ids if uid in current_uav_ids)
                self._active_tasks[tid] = SwarmTask(
                    target_id=task.target_id,
                    assigned_uav_ids=remaining,
                    sensor_coverage=task.sensor_coverage,
                    created_at=task.created_at,
                )

    def _hungarian_assign(
        self,
        available: list,
        task_list: list,
        idle_count: int,
    ) -> List[TaskingOrder]:
        """Use Hungarian algorithm for optimal UAV-to-task assignment."""
        max_assignments = idle_count - self.min_idle_count
        if max_assignments <= 0 or not available or not task_list:
            return []

        task_list = task_list[:max_assignments]
        cost_matrix = self._build_cost_matrix(available, task_list)
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        orders: List[TaskingOrder] = []
        priority_counter = 0
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] >= 1e18:
                continue
            target, sensor_type = task_list[c]
            uav = available[r]
            priority_counter += 1
            orders.append(
                TaskingOrder(
                    uav_id=uav.id,
                    target_id=target.id,
                    mode="SUPPORT",
                    reason=sensor_type,
                    priority=priority_counter,
                )
            )
        return orders

    def _build_cost_matrix(
        self,
        uavs: list,
        task_list: list,
    ) -> np.ndarray:
        """Build cost matrix: rows=UAVs, cols=tasks. Lower = better."""
        n_uavs = len(uavs)
        n_tasks = len(task_list)
        cost = np.full((n_uavs, n_tasks), 1e18)

        for i, uav in enumerate(uavs):
            for j, (target, sensor_type) in enumerate(task_list):
                if sensor_type not in uav.sensors:
                    continue
                dist = math.hypot(uav.x - target.x, uav.y - target.y)
                score = self._priority_score(target)
                if target.id in self._promoted_targets:
                    score *= _DRONE_LOSS_PRIORITY_BOOST
                cost[i, j] = dist / max(score, 1e-9)
        return cost

    def _release_support_uavs(self, target_id: int, uavs: list) -> None:
        """Return SUPPORT UAVs tracking target_id back to SEARCH mode."""
        for uav in uavs:
            if uav.mode == "SUPPORT" and target_id in uav.tracked_target_ids:
                uav.mode = "SEARCH"
                uav.tracked_target_ids = [tid for tid in uav.tracked_target_ids if tid != target_id]

    def _sensor_gap(self, target) -> List[str]:
        """Return sensor types from SENSOR_TYPES not already contributed."""
        covered = {c.sensor_type for c in target.sensor_contributions}
        return [s for s in SENSOR_TYPES if s not in covered]

    def _priority_score(self, target) -> float:
        """Threat-weighted urgency: higher score = assign first."""
        weight = THREAT_WEIGHTS.get(target.type, 0.5)
        return weight * (1.0 - target.fused_confidence)

    def _find_nearest(
        self,
        uavs: list,
        target,
        sensor_type: str,
        exclude: Optional[set] = None,
    ):
        """Return closest assignable UAV that carries sensor_type, or None."""
        exclude = exclude or set()
        candidates = [
            u for u in uavs if u.mode in _ASSIGNABLE_MODES and sensor_type in u.sensors and u.id not in exclude
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda u: math.hypot(u.x - target.x, u.y - target.y))
