"""Demo auto-pilot loop — decoupled from WebSocket globals, accepts injected dependencies."""

from __future__ import annotations

import asyncio
import collections
import json
import math
import time
from typing import TYPE_CHECKING, Callable

import structlog
from roe_engine import ROEDecision, ROEEngine

if TYPE_CHECKING:
    from agents.tactical_planner import TacticalPlannerAgent
    from hitl_manager import HITLManager
    from intel_feed import IntelFeedRouter
    from sim_engine import SimulationModel

logger = structlog.get_logger()

# Configurable delays (seconds)
DEFAULT_APPROVAL_DELAY = 5.0
DEFAULT_FOLLOW_DELAY = 4.0
DEFAULT_PAINT_DELAY = 5.0

# Circuit breaker constants
MAX_AUTO_APPROVALS_PER_MINUTE = 10
NO_DASHBOARD_TIMEOUT_S = 30.0
MAX_SESSION_ENGAGEMENTS = 50


def _get_entry_if_status(hitl: HITLManager, entry_id: str, expected_status: str) -> dict | None:
    """Re-fetch a strike board entry and return it only if it still has the expected status."""
    for e in hitl.get_strike_board():
        if e["id"] == entry_id and e["status"] == expected_status:
            return e
    return None


def _find_nearest_available_uav(sim: SimulationModel, target_id: int) -> int | None:
    """Find the nearest idle/scanning UAV to a target and return its id."""
    target = sim._find_target(target_id)
    if not target:
        return None
    available = [u for u in sim.uavs.values() if u.mode in ("IDLE", "SEARCH")]
    if not available:
        return None
    best = min(available, key=lambda u: (u.x - target.x) ** 2 + (u.y - target.y) ** 2)
    return best.id


async def demo_autopilot(
    *,
    sim: SimulationModel,
    hitl: HITLManager,
    broadcast_fn: Callable,
    clients: dict,
    intel_router: IntelFeedRouter,
    tactical_planner: TacticalPlannerAgent,
    get_effectors: Callable | None = None,
    roe_engine: ROEEngine | None = None,
    approval_delay: float = DEFAULT_APPROVAL_DELAY,
    follow_delay: float = DEFAULT_FOLLOW_DELAY,
    paint_delay: float = DEFAULT_PAINT_DELAY,
) -> None:
    """Auto-pilot loop: auto-approve nominations, dispatch UAVs to follow & paint targets."""
    logger.warning("demo_autopilot_started", note="HITL bypass active")

    await asyncio.sleep(2.0)
    await broadcast_fn(
        json.dumps(
            {
                "type": "ASSISTANT_MESSAGE",
                "text": "DEMO MODE ACTIVE — UAV intercept auto-pilot running.",
                "severity": "CRITICAL",
                "timestamp": time.strftime("%H:%M:%S"),
            }
        ),
        target_type="DASHBOARD",
    )

    in_flight: set[str] = set()
    enemy_intercept_dispatched: set[int] = set()

    # Circuit breaker state
    approval_timestamps: collections.deque = collections.deque()
    session_engagement_count: int = 0
    last_dashboard_seen: float = time.monotonic()

    while True:
        await asyncio.sleep(2.0)

        # --- Circuit breaker: update last-seen dashboard timestamp ---
        dashboard_count = sum(1 for info in clients.values() if info.get("type") == "DASHBOARD")
        if dashboard_count > 0:
            last_dashboard_seen = time.monotonic()
        elif time.monotonic() - last_dashboard_seen > NO_DASHBOARD_TIMEOUT_S:
            logger.warning("demo_autopilot_no_dashboard", timeout=NO_DASHBOARD_TIMEOUT_S)
            await intel_router.emit(
                "INTEL_FEED",
                {
                    "event": "SAFETY",
                    "summary": "Demo autopilot paused: no dashboard connected for 30s",
                },
            )
            await asyncio.sleep(5.0)
            continue

        # --- Circuit breaker: session engagement cap ---
        if session_engagement_count >= MAX_SESSION_ENGAGEMENTS:
            logger.warning("demo_autopilot_session_cap_reached", cap=MAX_SESSION_ENGAGEMENTS)
            await intel_router.emit(
                "INTEL_FEED",
                {
                    "event": "SAFETY",
                    "summary": f"Demo autopilot paused: session engagement cap ({MAX_SESSION_ENGAGEMENTS}) reached",
                },
            )
            await asyncio.sleep(10.0)
            continue

        # --- Enemy UAV auto-intercept ---
        for e in sim.enemy_uavs.values():
            if e.mode == "DESTROYED":
                enemy_intercept_dispatched.discard(e.id)
                continue
            if e.id in enemy_intercept_dispatched:
                continue
            if e.fused_confidence > 0.7:
                idle_uavs = [
                    u for u in sim.uavs.values() if u.mode in ("IDLE", "SEARCH") and u.primary_target_id is None
                ]
                if idle_uavs:
                    nearest = min(idle_uavs, key=lambda u: math.hypot(u.x - e.x, u.y - e.y))
                    sim.command_intercept_enemy(nearest.id, e.id)
                    enemy_intercept_dispatched.add(e.id)
                    await broadcast_fn(
                        json.dumps(
                            {
                                "type": "ASSISTANT_MESSAGE",
                                "text": f"AUTO-INTERCEPT: UAV-{nearest.id} dispatched against ENM-{e.id - 1000} (confidence={e.fused_confidence:.0%})",
                                "severity": "CRITICAL",
                                "timestamp": time.strftime("%H:%M:%S"),
                            }
                        ),
                        target_type="DASHBOARD",
                    )

        board = hitl.get_strike_board()
        for entry in board:
            if entry["status"] != "PENDING" or entry["id"] in in_flight:
                continue

            entry_id = entry["id"]
            target_id = entry["target_id"]
            in_flight.add(entry_id)

            # --- Gate 1: Auto-approve after delay ---
            await asyncio.sleep(approval_delay)
            entry = _get_entry_if_status(hitl, entry_id, "PENDING")
            if not entry:
                in_flight.discard(entry_id)
                continue

            # Circuit breaker: rate limit approvals per minute
            _now_cb = time.monotonic()
            while approval_timestamps and approval_timestamps[0] < _now_cb - 60.0:
                approval_timestamps.popleft()
            if len(approval_timestamps) >= MAX_AUTO_APPROVALS_PER_MINUTE:
                logger.warning("demo_autopilot_rate_limit_hit", per_minute=MAX_AUTO_APPROVALS_PER_MINUTE)
                await intel_router.emit(
                    "INTEL_FEED",
                    {
                        "event": "SAFETY",
                        "summary": f"Demo autopilot: approval rate limit ({MAX_AUTO_APPROVALS_PER_MINUTE}/min) reached",
                    },
                )
                in_flight.discard(entry_id)
                continue
            approval_timestamps.append(_now_cb)

            # --- ROE veto check ---
            if roe_engine is not None:
                roe_decision = roe_engine.evaluate(
                    target_type=entry.get("target_type", ""),
                    zone_id=entry.get("zone_id"),
                    autonomy_level=getattr(sim, "autonomy_level", "SUPERVISED"),
                )
                if roe_decision == ROEDecision.DENIED:
                    logger.warning(
                        "demo_autopilot_roe_denied",
                        entry_id=entry_id,
                        target_type=entry.get("target_type"),
                    )
                    await intel_router.emit(
                        "INTEL_FEED",
                        {
                            "event": "ROE_DENIED",
                            "summary": f"ROE DENIED engagement of {entry.get('target_type')} (id={target_id})",
                        },
                    )
                    in_flight.discard(entry_id)
                    continue
                if roe_decision == ROEDecision.ESCALATE and getattr(sim, "autonomy_level", "MANUAL") != "AUTONOMOUS":
                    logger.info(
                        "demo_autopilot_roe_escalate",
                        entry_id=entry_id,
                        target_type=entry.get("target_type"),
                    )
                    in_flight.discard(entry_id)
                    continue

            try:
                hitl.approve_nomination(entry_id, "Demo auto-approved")
            except ValueError:
                logger.exception("demo_autopilot_approve_nomination_failed", entry_id=entry_id, target_id=target_id)
                in_flight.discard(entry_id)
                continue

            from audit_log import audit_log

            audit_log.append(
                "NOMINATION_APPROVED",
                autonomy_level=getattr(sim, "autonomy_level", "SUPERVISED"),
                target_id=target_id,
                details={"entry_id": entry_id, "source": "autopilot"},
            )

            session_engagement_count += 1

            await broadcast_fn(
                json.dumps(
                    {
                        "type": "ASSISTANT_MESSAGE",
                        "text": f"AUTO-APPROVED: {entry['target_type']} (id={target_id}) — dispatching nearest UAV...",
                        "severity": "WARNING",
                        "timestamp": time.strftime("%H:%M:%S"),
                    }
                ),
                target_type="DASHBOARD",
            )
            await broadcast_fn(
                json.dumps(
                    {
                        "type": "HITL_UPDATE",
                        "action": "approved",
                        "entry": hitl.get_strike_board(),
                    }
                ),
                target_type="DASHBOARD",
            )

            # --- Dispatch UAV: follow target ---
            uav_id = _find_nearest_available_uav(sim, target_id)
            if uav_id is None:
                await broadcast_fn(
                    json.dumps(
                        {
                            "type": "ASSISTANT_MESSAGE",
                            "text": f"NO AVAILABLE UAV for {entry['target_type']} (id={target_id}) — all assets committed.",
                            "severity": "WARNING",
                            "timestamp": time.strftime("%H:%M:%S"),
                        }
                    ),
                    target_type="DASHBOARD",
                )
                in_flight.discard(entry_id)
                continue

            sim.command_follow(uav_id, target_id)
            await broadcast_fn(
                json.dumps(
                    {
                        "type": "ASSISTANT_MESSAGE",
                        "text": f"UAV-{uav_id} FOLLOWING: {entry['target_type']} (id={target_id}) — tracking in progress.",
                        "severity": "INFO",
                        "timestamp": time.strftime("%H:%M:%S"),
                    }
                ),
                target_type="DASHBOARD",
            )

            # --- After follow delay, escalate to paint (laser lock) ---
            await asyncio.sleep(follow_delay)
            target = sim._find_target(target_id)
            if target and target.tracked_by_uav_id == uav_id:
                sim.command_paint(uav_id, target_id)
                await broadcast_fn(
                    json.dumps(
                        {
                            "type": "ASSISTANT_MESSAGE",
                            "text": f"UAV-{uav_id} PAINTING: {entry['target_type']} (id={target_id}) — laser lock established.",
                            "severity": "CRITICAL",
                            "timestamp": time.strftime("%H:%M:%S"),
                        }
                    ),
                    target_type="DASHBOARD",
                )

                # Generate COAs while painting
                target_loc = entry.get("target_location", [0.0, 0.0])
                effectors = get_effectors() if get_effectors else []
                coas = tactical_planner._generate_coas_heuristic(
                    target_data={
                        "lat": target_loc[0] if len(target_loc) > 0 else 0.0,
                        "lon": target_loc[1] if len(target_loc) > 1 else 0.0,
                        "type": entry["target_type"],
                    },
                    assets=effectors,
                )
                if coas:
                    hitl.propose_coas(entry_id, coas)
                    await broadcast_fn(
                        json.dumps(
                            {
                                "type": "HITL_UPDATE",
                                "action": "coas_proposed",
                                "entry_id": entry_id,
                                "coas": hitl.get_coas_for_entry(entry_id),
                            }
                        ),
                        target_type="DASHBOARD",
                    )

                    coa_names = [f"{c.effector_name} (Pk={c.pk_estimate:.0%})" for c in coas]
                    await broadcast_fn(
                        json.dumps(
                            {
                                "type": "ASSISTANT_MESSAGE",
                                "text": f"COAs GENERATED: {' | '.join(coa_names)} — awaiting authorization.",
                                "severity": "INFO",
                                "timestamp": time.strftime("%H:%M:%S"),
                            }
                        ),
                        target_type="DASHBOARD",
                    )

                    # Auto-authorize best COA
                    await asyncio.sleep(paint_delay)
                    entry = _get_entry_if_status(hitl, entry_id, "APPROVED")
                    if entry:
                        best_coa = coas[0]
                        try:
                            hitl.authorize_coa(entry_id, best_coa.id, "Demo auto-authorized")
                        except ValueError:
                            logger.exception(
                                "demo_autopilot_authorize_coa_failed", entry_id=entry_id, target_id=target_id
                            )
                            in_flight.discard(entry_id)
                            continue
                        else:
                            audit_log.append(
                                "COA_AUTHORIZED",
                                autonomy_level=getattr(sim, "autonomy_level", "SUPERVISED"),
                                target_id=target_id,
                                drone_id=uav_id,
                                details={"entry_id": entry_id, "coa_id": best_coa.id, "source": "autopilot"},
                            )
                            await broadcast_fn(
                                json.dumps(
                                    {
                                        "type": "ASSISTANT_MESSAGE",
                                        "text": f"COA AUTHORIZED: {best_coa.effector_name} — Pk={best_coa.pk_estimate:.0%}. UAV-{uav_id} maintaining lock.",
                                        "severity": "WARNING",
                                        "timestamp": time.strftime("%H:%M:%S"),
                                    }
                                ),
                                target_type="DASHBOARD",
                            )
                            await broadcast_fn(
                                json.dumps(
                                    {
                                        "type": "HITL_UPDATE",
                                        "action": "coa_authorized",
                                        "entry_id": entry_id,
                                        "coas": hitl.get_coas_for_entry(entry_id),
                                    }
                                ),
                                target_type="DASHBOARD",
                            )

            in_flight.discard(entry_id)
