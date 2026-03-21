"""
kill_chain_tracker.py
=====================
F2T2EA Kill Chain Progress Tracker.

Pure-function module that classifies targets into their current kill chain
phase based on target state, drone tracking status, and strike board entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KillChainPhase(Enum):
    FIND = "FIND"
    FIX = "FIX"
    TRACK = "TRACK"
    TARGET = "TARGET"
    ENGAGE = "ENGAGE"
    ASSESS = "ASSESS"


@dataclass(frozen=True)
class KillChainStatus:
    phase: KillChainPhase
    target_count: int
    target_ids: list[int]


# States that map to ASSESS phase
_ASSESS_STATES = frozenset({"DESTROYED", "ESCAPED"})

# States that map to ENGAGE phase
_ENGAGE_STATES = frozenset({"ENGAGED"})

# States that map to TARGET phase
_TARGET_STATES = frozenset({"VERIFIED", "NOMINATED", "LOCKED"})

# Strike board statuses that indicate engagement
_ENGAGE_STRIKE_STATUSES = frozenset({"APPROVED", "IN_FLIGHT"})

# Strike board statuses that indicate assessment
_ASSESS_STRIKE_STATUSES = frozenset({"HIT", "MISS"})

# Drone modes that indicate active tracking
_TRACKING_MODES = frozenset({"FOLLOW", "PAINT", "INTERCEPT"})


class KillChainTracker:
    def compute(
        self,
        targets: list[dict],
        drones: list[dict],
        strike_board: list[dict],
    ) -> list[KillChainStatus]:
        """Classify each target into its F2T2EA kill chain phase.

        Returns a list of six KillChainStatus entries, one per phase.
        """
        # Build lookup: target_id -> set of strike statuses
        strike_by_target: dict[int, set[str]] = {}
        for entry in strike_board:
            tid = entry.get("target_id")
            status = entry.get("status", "")
            if tid is not None:
                strike_by_target.setdefault(tid, set()).add(status)

        # Build lookup: target_id -> True if actively tracked by a drone
        actively_tracked: set[int] = set()
        for drone in drones:
            if drone.get("mode") in _TRACKING_MODES:
                tracked_tid = drone.get("tracked_target_id")
                if tracked_tid is not None:
                    actively_tracked.add(tracked_tid)

        # Classify each target
        phase_bins: dict[KillChainPhase, list[int]] = {p: [] for p in KillChainPhase}

        for target in targets:
            tid = target["id"]
            state = target.get("state", "UNDETECTED")

            if state == "UNDETECTED":
                continue

            strike_statuses = strike_by_target.get(tid, set())

            phase = _classify_target(state, tid, strike_statuses, actively_tracked)
            phase_bins[phase].append(tid)

        return [
            KillChainStatus(
                phase=phase,
                target_count=len(ids),
                target_ids=ids,
            )
            for phase, ids in phase_bins.items()
        ]

    def to_dict(self, statuses: list[KillChainStatus]) -> dict:
        """Convert list of KillChainStatus to a JSON-serializable dict."""
        phases = [
            {
                "phase": s.phase.value,
                "target_count": s.target_count,
                "target_ids": list(s.target_ids),
            }
            for s in statuses
        ]
        total = sum(s.target_count for s in statuses)
        return {"phases": phases, "total_tracked": total}


def _classify_target(
    state: str,
    target_id: int,
    strike_statuses: set[str],
    actively_tracked: set[int],
) -> KillChainPhase:
    """Determine the kill chain phase for a single target."""
    # Check assessment outcomes first (highest priority)
    if state in _ASSESS_STATES or strike_statuses & _ASSESS_STRIKE_STATUSES:
        return KillChainPhase.ASSESS

    # Engagement phase
    if state in _ENGAGE_STATES or strike_statuses & _ENGAGE_STRIKE_STATUSES:
        return KillChainPhase.ENGAGE

    # Targeting phase (verified/nominated/locked, or pending strike)
    if state in _TARGET_STATES:
        return KillChainPhase.TARGET

    # Track phase: actively tracked by a drone in FOLLOW/PAINT/INTERCEPT
    if target_id in actively_tracked:
        return KillChainPhase.TRACK

    # Fix phase: classified (sensor fusion active)
    if state == "CLASSIFIED":
        return KillChainPhase.FIX

    # Default: FIND (DETECTED or any other active state)
    return KillChainPhase.FIND
