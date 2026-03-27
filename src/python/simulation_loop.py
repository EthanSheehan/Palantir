"""Simulation tick loop and sensor feed broadcast."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Callable

import structlog
from battlespace_assessment import BattlespaceAssessor
from intel_feed import IntelFeedRouter
from isr_priority import build_isr_queue
from kill_chain_tracker import KillChainTracker

if TYPE_CHECKING:
    from hitl_manager import HITLManager
    from sim_engine import SimulationModel
    from tactical_assistant import TacticalAssistant
    from target_store import TargetStore

logger = structlog.get_logger()


def _serialize_assessment(result) -> dict:
    """Convert frozen AssessmentResult to JSON-serializable dict."""
    return {
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "cluster_type": c.cluster_type,
                "member_target_ids": list(c.member_target_ids),
                "centroid_lon": round(c.centroid_lon, 4),
                "centroid_lat": round(c.centroid_lat, 4),
                "threat_score": round(c.threat_score, 3),
                "hull_points": [list(p) for p in c.hull_points],
            }
            for c in result.clusters
        ],
        "coverage_gaps": [
            {
                "zone_x": g.zone_x,
                "zone_y": g.zone_y,
                "lon": round(g.lon, 4),
                "lat": round(g.lat, 4),
                "threat_score": round(result.zone_threat_scores.get((g.zone_x, g.zone_y), 0.0), 3),
            }
            for g in result.coverage_gaps
        ],
        "zone_threat_scores": [[k[0], k[1], round(v, 3)] for k, v in result.zone_threat_scores.items()],
        "movement_corridors": [
            {"target_id": mc.target_id, "waypoints": [list(w) for w in mc.waypoints]}
            for mc in result.movement_corridors
        ],
    }


class SimulationLoopState:
    """Mutable state for the simulation loop — replaces module-level globals."""

    def __init__(self):
        self.prev_target_states: dict[int, str] = {}
        self.last_assessment_time: float = 0.0
        self.cached_assessment: dict | None = None
        self.cached_isr_queue: list | None = None
        self.kill_chain_tracker: KillChainTracker = KillChainTracker()
        self.cached_kill_chain: dict | None = None
        self.last_planned_targets_time: float = 0.0
        self.cached_planned_targets: list | None = None


async def simulation_loop(
    *,
    sim: SimulationModel,
    hitl: HITLManager,
    assistant: TacticalAssistant,
    assessor: BattlespaceAssessor,
    intel_router: IntelFeedRouter,
    broadcast_fn: Callable,
    clients: dict,
    settings,
    loop_state: SimulationLoopState | None = None,
    target_store: "TargetStore | None" = None,
) -> None:
    """Main 10Hz simulation tick loop."""
    tick_interval = 1.0 / settings.simulation_hz
    logger.info("simulation_loop_started", hz=settings.simulation_hz)

    if loop_state is None:
        loop_state = SimulationLoopState()

    while True:
        sim.tick()

        # Expire time-bounded autonomy grants
        if hasattr(sim, "autonomy_policy"):
            sim.autonomy_policy = sim.autonomy_policy.tick()

        # Cache get_state() once per tick
        state = sim.get_state()

        now = time.monotonic()
        if now - loop_state.last_assessment_time >= 5.0:
            loop_state.last_assessment_time = now
            try:
                targets_with_history = []
                for td in state["targets"]:
                    t_obj = sim.targets.get(td["id"])
                    if t_obj is None:
                        continue
                    td_copy = dict(td)
                    td_copy["position_history"] = list(t_obj.position_history)
                    targets_with_history.append(td_copy)

                # Snapshot state before thread dispatch to avoid data race
                state_snapshot = {
                    "targets": list(state["targets"]),
                    "uavs": list(state["uavs"]),
                    "zones": list(state["zones"]),
                }

                def _run_assessment_and_isr():
                    assessment = _serialize_assessment(
                        assessor.assess(
                            targets=targets_with_history,
                            uavs=state_snapshot["uavs"],
                            zones=state_snapshot["zones"],
                        )
                    )
                    isr_reqs = build_isr_queue(
                        targets=state_snapshot["targets"],
                        uavs=state_snapshot["uavs"],
                        assessment_result=assessment,
                        max_requirements=10,
                    )
                    isr_list = [
                        {
                            "target_id": r.target_id,
                            "target_type": r.target_type,
                            "urgency_score": r.urgency_score,
                            "verification_gap": r.verification_gap,
                            "missing_sensor_types": list(r.missing_sensor_types),
                            "recommended_uav_ids": list(r.recommended_uav_ids),
                        }
                        for r in isr_reqs
                    ]
                    return assessment, isr_list

                loop_state.cached_assessment, loop_state.cached_isr_queue = await asyncio.to_thread(
                    _run_assessment_and_isr
                )
                # Pass assessment to sim for threat-adaptive dispatch
                sim._last_assessment = loop_state.cached_assessment
            except Exception:
                logger.exception("battlespace_assessment_error")

        # Detect and emit INTEL_FEED events for target state transitions
        current_target_ids = set()
        for t in state.get("targets", []):
            tid = t["id"]
            current_target_ids.add(tid)
            new_state = t["state"]
            prev = loop_state.prev_target_states.get(tid)
            if prev and prev != new_state and new_state != "UNDETECTED":
                await intel_router.emit(
                    "INTEL_FEED",
                    {
                        "event": new_state,
                        "target_id": tid,
                        "target_type": t["type"],
                        "from": prev,
                        "to": new_state,
                        "summary": f"Target {tid} ({t['type']}): {prev} -> {new_state}",
                    },
                )
            loop_state.prev_target_states[tid] = new_state
        # Prune stale entries for targets no longer in the simulation
        for stale_tid in set(loop_state.prev_target_states) - current_target_ids:
            del loop_state.prev_target_states[stale_tid]

        if clients:
            strike_board_data = hitl.get_strike_board()
            state["strike_board"] = strike_board_data
            state["demo_mode"] = settings.demo_mode
            if loop_state.cached_assessment is not None:
                state["assessment"] = loop_state.cached_assessment
            if loop_state.cached_isr_queue is not None:
                state["isr_queue"] = loop_state.cached_isr_queue
            state["coverage_mode"] = sim.coverage_mode

            # Kill chain progress indicator
            kc_statuses = loop_state.kill_chain_tracker.compute(
                targets=state.get("targets", []),
                drones=state.get("uavs", []),
                strike_board=strike_board_data,
            )
            loop_state.cached_kill_chain = loop_state.kill_chain_tracker.to_dict(kc_statuses)
            state["kill_chain"] = loop_state.cached_kill_chain

            # Refresh planned targets every 5 seconds
            if target_store is not None:
                if now - loop_state.last_planned_targets_time >= 5.0:
                    loop_state.last_planned_targets_time = now
                    loop_state.cached_planned_targets = target_store.to_dict_list()
                if loop_state.cached_planned_targets is not None:
                    state["planned_targets"] = loop_state.cached_planned_targets

            state_json = json.dumps({"type": "state", "data": state})
            await broadcast_fn(state_json, target_type="DASHBOARD")

            # Update assistant
            assistant_msgs = assistant.update(state)
            for msg in assistant_msgs:
                await broadcast_fn(json.dumps(msg), target_type="DASHBOARD")

        await asyncio.sleep(tick_interval)


async def sensor_feed_loop(
    *,
    sim: SimulationModel,
    intel_router: IntelFeedRouter,
    clients: dict,
) -> None:
    """Emit per-UAV detection snapshots at 2Hz to SENSOR_FEED subscribers."""
    ACTIVE_MODES = {"SEARCH", "FOLLOW", "PAINT", "INTERCEPT"}
    while True:
        await asyncio.sleep(0.5)
        if not clients:
            continue
        state = sim.get_state()
        for uav_data in state.get("uavs", []):
            if uav_data.get("mode") not in ACTIVE_MODES:
                continue
            uav_id = uav_data["id"]
            detections = []
            for t in state.get("targets", []):
                for sc in t.get("sensor_contributions", []):
                    if sc.get("uav_id") == uav_id:
                        detections.append(
                            {
                                "target_id": t["id"],
                                "target_type": t["type"],
                                "confidence": sc["confidence"],
                                "sensor_type": sc["sensor_type"],
                            }
                        )
            if not detections:
                continue
            await intel_router.emit(
                "SENSOR_FEED",
                {
                    "uav_id": uav_id,
                    "mode": uav_data["mode"],
                    "sensors": uav_data.get("sensors", []),
                    "lat": uav_data["lat"],
                    "lon": uav_data["lon"],
                    "detections": detections,
                },
            )
