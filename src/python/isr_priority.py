"""
isr_priority.py
===============
Pure-function ISR priority queue builder for Grid-Sentinel C2.

Converts battlespace assessment output and sim state into a ranked list of
ISRRequirement objects. No instance state, no side effects.

Usage:
    from isr_priority import build_isr_queue, ISRRequirement, THREAT_WEIGHTS
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_SENSOR_TYPES: frozenset[str] = frozenset({"EO_IR", "SAR", "SIGINT"})

_EXCLUDED_STATES: frozenset[str] = frozenset({"DESTROYED", "ESCAPED", "UNDETECTED"})

THREAT_WEIGHTS: dict[str, float] = {
    "SAM": 1.0,
    "TEL": 0.9,
    "MANPADS": 0.8,
    "RADAR": 0.7,
    "CP": 0.6,
    "C2_NODE": 0.6,
    "ARTILLERY": 0.5,
    "APC": 0.4,
    "TRUCK": 0.4,
    "LOGISTICS": 0.3,
}

# Max UAVs to recommend per target
_MAX_RECOMMENDED_UAVS = 3


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ISRRequirement:
    target_id: int
    target_type: str
    urgency_score: float  # 0.0-1.0, higher = more urgent
    verification_gap: float  # 1.0 - fused_confidence
    missing_sensor_types: tuple  # sensor types not yet contributing
    recommended_uav_ids: tuple  # nearest IDLE UAVs with matching sensors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _score_target(target: dict) -> float:
    """
    urgency = threat_weight * (1 - fused_confidence) * (0.5 + 0.5 * time_factor)

    time_factor ramps from 0.0 to 1.0 as time_in_state_sec goes from 0 to 60s.
    """
    threat_w = THREAT_WEIGHTS.get(target.get("type", ""), 0.5)
    verification_gap = 1.0 - target.get("fused_confidence", 0.0)
    time_in_state = target.get("time_in_state_sec", 0.0)
    time_factor = min(1.0, time_in_state / 60.0)
    return threat_w * verification_gap * (0.5 + 0.5 * time_factor)


def _missing_sensors(target: dict) -> tuple:
    """Return sensor types in ALL_SENSOR_TYPES not yet contributing (confidence > 0.05)."""
    contributing = {
        c.get("sensor_type", "") for c in target.get("sensor_contributions", []) if c.get("confidence", 0.0) > 0.05
    }
    return tuple(sorted(ALL_SENSOR_TYPES - contributing))


def _recommend_uavs(target: dict, missing: tuple, uavs: list[dict]) -> tuple:
    """
    Return IDs of IDLE UAVs that carry at least one of the missing sensor types,
    sorted by Euclidean distance to the target (closest first).
    """
    t_lon = target.get("lon", 0.0)
    t_lat = target.get("lat", 0.0)
    missing_set = set(missing)
    candidates = []
    for u in uavs:
        if u.get("mode") != "IDLE":
            continue
        u_sensors = set(u.get("sensors", []))
        if not u_sensors.intersection(missing_set):
            continue
        dist = math.hypot(u.get("lon", 0.0) - t_lon, u.get("lat", 0.0) - t_lat)
        candidates.append((dist, u["id"]))
    candidates.sort()
    return tuple(uid for _, uid in candidates[:_MAX_RECOMMENDED_UAVS])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_isr_queue(
    targets: list[dict],
    uavs: list[dict],
    assessment_result: dict | None = None,
    max_requirements: int = 10,
) -> List[ISRRequirement]:
    """
    Build a ranked list of ISR requirements from sim state.

    Args:
        targets: List of target dicts from sim_engine.get_state()
        uavs: List of UAV dicts from sim_engine.get_state()
        assessment_result: Optional battlespace assessment dict (reserved for future use)
        max_requirements: Maximum entries to return

    Returns:
        List of ISRRequirement sorted by urgency_score descending, capped at max_requirements
    """
    requirements: list[ISRRequirement] = []

    for t in targets:
        state = t.get("state", "UNDETECTED")
        if state in _EXCLUDED_STATES:
            continue

        score = _score_target(t)
        gap = 1.0 - t.get("fused_confidence", 0.0)
        missing = _missing_sensors(t)
        recommended = _recommend_uavs(t, missing, uavs)

        requirements.append(
            ISRRequirement(
                target_id=t["id"],
                target_type=t.get("type", "UNKNOWN"),
                urgency_score=round(score, 4),
                verification_gap=round(gap, 4),
                missing_sensor_types=missing,
                recommended_uav_ids=recommended,
            )
        )

    requirements.sort(key=lambda r: -r.urgency_score)
    return requirements[:max_requirements]
