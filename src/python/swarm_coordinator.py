"""
swarm_coordinator.py
====================
Pure-logic swarm coordination module for Palantir C2.

Implements greedy UAV-to-target assignment with idle-count guard, sensor-gap
detection, priority scoring, 120-second task expiry, and auto-release on
target state transitions. No I/O, no side effects.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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


# ---------------------------------------------------------------------------
# SwarmCoordinator
# ---------------------------------------------------------------------------

class SwarmCoordinator:
    """Greedy swarm coordinator: assigns nearest eligible UAV to cover sensor
    gaps on active targets, respecting the idle-count floor."""

    def __init__(self, min_idle_count: int = 2) -> None:
        self.min_idle_count = min_idle_count
        self._active_tasks: Dict[int, SwarmTask] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_and_assign(self, targets: list, uavs: list, *, force: bool = False) -> List[TaskingOrder]:
        """Score targets, fill sensor gaps, return new TaskingOrders.

        When force=True (operator request), skip state filtering and auto-release
        so that any target state can receive swarm support.
        """
        now = time.time()

        # 1. Expiry check — remove stale tasks and release SUPPORT UAVs
        expired_ids = [
            tid for tid, task in self._active_tasks.items()
            if now - task.created_at > _TASK_EXPIRY_SECONDS
        ]
        for tid in expired_ids:
            self._release_support_uavs(tid, uavs)
            del self._active_tasks[tid]

        if not force:
            # 2. Auto-release on resolved target state (skip when force — operator wants support)
            target_map = {t.id: t for t in targets}
            resolved_ids = [
                tid for tid in list(self._active_tasks)
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

        # 4. Score targets that have sensor gaps
        #    force=True: all targets eligible; otherwise only DETECTED/CLASSIFIED
        scored: List[tuple[float, object]] = []
        for target in targets:
            if not force and target.state not in ("DETECTED", "CLASSIFIED"):
                continue
            gap = self._sensor_gap(target)
            if not gap:
                continue
            score = self._priority_score(target)
            scored.append((score, target))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 5. Count available (IDLE/SEARCH) UAVs
        idle_count = sum(1 for u in uavs if u.mode in _ASSIGNABLE_MODES)

        # 6. Greedy assignment pass
        orders: List[TaskingOrder] = []
        already_assigned: set[int] = set()
        priority_counter = 0

        for _score, target in scored:
            gap = self._sensor_gap(target)
            for sensor_type in gap:
                if idle_count <= self.min_idle_count:
                    break
                uav = self._find_nearest(uavs, target, sensor_type, already_assigned)
                if uav is None:
                    continue
                priority_counter += 1
                orders.append(TaskingOrder(
                    uav_id=uav.id,
                    target_id=target.id,
                    mode="SUPPORT",
                    reason=sensor_type,
                    priority=priority_counter,
                ))
                idle_count -= 1
                already_assigned.add(uav.id)

        # 7. Update _active_tasks for targets that received orders
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

    def _release_support_uavs(self, target_id: int, uavs: list) -> None:
        """Return SUPPORT UAVs tracking target_id back to SEARCH mode."""
        for uav in uavs:
            if uav.mode == "SUPPORT" and target_id in uav.tracked_target_ids:
                uav.mode = "SEARCH"
                uav.tracked_target_ids = [
                    tid for tid in uav.tracked_target_ids if tid != target_id
                ]

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
            u for u in uavs
            if u.mode in _ASSIGNABLE_MODES
            and sensor_type in u.sensors
            and u.id not in exclude
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda u: math.hypot(u.x - target.x, u.y - target.y))
