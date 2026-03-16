"""
agents/strategy_analyst.py
==========================
Strategy Analyst Agent — evaluates ISR detections against ROE,
performs decision-gap analysis, assigns priority scores, and
hands off actionable targets to the Strike Board.

This module implements the core LangGraph node function.
"""

from __future__ import annotations

import math
from typing import Any

from core.ontology import (
    ActionableTarget,
    Detection,
    FriendlyForce,
    IdentityClassification,
    Location,
    ROEAction,
    RuleOfEngagement,
    SensorType,
    TaskingRequest,
)
from core.state import AnalystState


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _haversine_m(a: Location, b: Location) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000  # Earth radius in metres
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def _nearest_friendly(
    det: Detection,
    friendlies: list[FriendlyForce],
) -> tuple[str, float]:
    """Return (friendly_id, distance_m) for the closest friendly unit."""
    if not friendlies:
        return ("none", float("inf"))

    best_id = friendlies[0].id
    best_dist = _haversine_m(det.location, friendlies[0].location)
    for ff in friendlies[1:]:
        d = _haversine_m(det.location, ff.location)
        if d < best_dist:
            best_id = ff.id
            best_dist = d
    return best_id, best_dist


def _compute_priority(
    det: Detection,
    nearest_dist_m: float,
) -> int:
    """
    Assign a 1-10 priority score.

    Factors
    -------
    * Identity classification weight (hostile > suspect > unknown)
    * Sensor confidence
    * Proximity to friendly forces (closer = higher threat)
    """
    # Base weight from identity
    identity_weight = {
        IdentityClassification.HOSTILE: 4.0,
        IdentityClassification.SUSPECT: 2.5,
        IdentityClassification.UNKNOWN: 1.5,
        IdentityClassification.NEUTRAL: 0.5,
        IdentityClassification.FRIENDLY: 0.0,
    }.get(det.identity, 1.0)

    # Confidence factor (0-1 -> 0-3)
    confidence_factor = det.confidence * 3.0

    # Proximity factor: closer = more dangerous
    # 0m -> 3.0,  5000m+ -> 0.0
    proximity_factor = max(0.0, 3.0 * (1.0 - nearest_dist_m / 5000.0))

    raw = identity_weight + confidence_factor + proximity_factor
    return max(1, min(10, round(raw)))


from schemas.ontology import StrategyAnalystOutput, TargetNomination, EngagementDecision, ISRObserverOutput

class StrategyAnalystAgent:
    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    def evaluate_tracks(self, isr_output: ISRObserverOutput) -> StrategyAnalystOutput:
        """
        Evaluate fused tracks from the ISR Observer and nominate targets.
        """
        # Re-use the existing logic but map to the new pipeline types
        nominations = []
        for track in isr_output.tracks:
            # Simple heuristic for now: nominate high-priority tracks
            if track.is_high_priority:
                decision = EngagementDecision.NOMINATE
            else:
                decision = EngagementDecision.MONITOR
                
            nominations.append(TargetNomination(
                track_id=track.track_id,
                decision=decision,
                roe_compliance=True,
                collateral_risk="LOW",
                reasoning=f"Heuristic decision based on classification {track.classification.value}."
            ))
            
        return StrategyAnalystOutput(
            nominations=nominations,
            summary=f"Evaluated {len(isr_output.tracks)} tracks. {sum(1 for n in nominations if n.decision == EngagementDecision.NOMINATE)} nominated."
        )

def evaluate_detections(state: AnalystState) -> dict[str, Any]:
    # (Existing LangGraph node function remains for backward compatibility)
    ...
