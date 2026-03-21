"""TacticalAssistant — tracks new detections, triggers ISR -> Strategy -> HITL pipeline."""

from __future__ import annotations

import json
import time

import structlog
from agents.isr_observer import ISRObserverAgent
from agents.strategy_analyst import StrategyAnalystAgent
from hitl_manager import HITLManager
from schemas.ontology import EngagementDecision

logger = structlog.get_logger()


class TacticalAssistant:
    """Tracks new detections, triggers ISR->Strategy->HITL pipeline per event."""

    def __init__(self):
        self.message_history = []
        self.last_detected = {}  # target_id -> bool
        self._last_verified: dict = {}  # target_id -> bool
        # track_id -> True for targets already nominated to avoid duplicates
        self._nominated: set = set()

    def update(
        self,
        sim_state,
        *,
        hitl: HITLManager | None = None,
        isr_observer: ISRObserverAgent | None = None,
        strategy_analyst: StrategyAnalystAgent | None = None,
    ):
        new_messages = []
        targets_list = sim_state.get("targets", [])
        # Prune stale entries for targets no longer in the simulation
        active_track_keys = {f"TRK-{t['id']}" for t in targets_list}
        self._nominated = self._nominated & active_track_keys
        active_ids = {t["id"] for t in targets_list}
        self._last_verified = {k: v for k, v in self._last_verified.items() if k in active_ids}
        self.last_detected = {k: v for k, v in self.last_detected.items() if k in active_ids}
        for target in targets_list:
            tid = target["id"]
            current_state = target.get("state", "UNDETECTED")
            is_any_detected = current_state != "UNDETECTED"
            is_verified = current_state == "VERIFIED"
            t_type = target["type"]

            # UI visibility: fire "NEW CONTACT" on first detection (any non-UNDETECTED state)
            if is_any_detected and not self.last_detected.get(tid, False):
                msg = {
                    "type": "ASSISTANT_MESSAGE",
                    "text": f"NEW CONTACT: {t_type} localized at {target['lon']:.4f}, {target['lat']:.4f}",
                    "severity": "INFO",
                    "timestamp": time.strftime("%H:%M:%S"),
                }
                new_messages.append(msg)

            # ISR pipeline gate: only fire on VERIFIED (was not verified last tick)
            was_verified = self._last_verified.get(tid, False)
            if is_verified and not was_verified:
                hitl_msg = process_new_detection(
                    target,
                    self._nominated,
                    hitl=hitl,
                    isr_observer=isr_observer,
                    strategy_analyst=strategy_analyst,
                )
                if hitl_msg:
                    new_messages.append(hitl_msg)

            self.last_detected[tid] = is_any_detected
            self._last_verified[tid] = is_verified

        return new_messages


def process_new_detection(
    target: dict,
    nominated: set,
    *,
    hitl: HITLManager | None = None,
    isr_observer: ISRObserverAgent | None = None,
    strategy_analyst: StrategyAnalystAgent | None = None,
) -> dict | None:
    """Run ISR Observer -> Strategy Analyst -> HITL nomination for a newly detected target.

    Returns an ASSISTANT_MESSAGE dict if the target was nominated, otherwise None.
    This is intentionally synchronous (heuristic path only).
    """
    track_key = f"TRK-{target['id']}"
    if track_key in nominated:
        return None

    raw_json = json.dumps(
        {
            "id": target["id"],
            "type": target["type"],
            "source": "UAV",
            "lat": target.get("lat", 0.0),
            "lon": target.get("lon", 0.0),
            "confidence": target.get("confidence", 0.75),
            "classification": target["type"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )

    if isr_observer is None or strategy_analyst is None or hitl is None:
        return None

    try:
        isr_output = isr_observer.process_sensor_data(raw_json)
        analyst_output = strategy_analyst.evaluate_tracks(isr_output)
    except Exception:
        logger.exception("isr_strategy_pipeline_failed")
        return None

    for nomination in analyst_output.nominations:
        if nomination.decision != EngagementDecision.NOMINATE:
            continue

        # Find the matching track for location data
        track = next(
            (t for t in isr_output.tracks if t.track_id == nomination.track_id),
            None,
        )
        lat = track.lat if track else target.get("lat", 0.0)
        lon = track.lon if track else target.get("lon", 0.0)

        hitl.nominate_target(
            target_data={
                "target_id": target["id"],
                "target_type": target["type"],
                "target_location": (lat, lon),
                "detection_confidence": target.get("confidence", 0.75),
            },
            evaluation={
                "priority_score": 8.0,
                "roe_evaluation": nomination.collateral_risk,
                "reasoning_trace": nomination.reasoning,
            },
        )
        nominated.add(track_key)
        logger.info(
            "target_nominated_to_strike_board",
            target_id=target["id"],
            target_type=target["type"],
            track_id=nomination.track_id,
        )
        return {
            "type": "ASSISTANT_MESSAGE",
            "text": (f"NOMINATED: {target['type']} (id={target['id']}) forwarded to strike board for HITL review."),
            "severity": "WARNING",
            "timestamp": time.strftime("%H:%M:%S"),
        }

    return None
