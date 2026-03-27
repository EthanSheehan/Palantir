"""WebSocket command dispatch table — replaces the if/elif chain in handle_payload()."""

from __future__ import annotations

import json
import math
import pathlib
import re
import time
from typing import TYPE_CHECKING, Callable

import rbac
import structlog
import yaml
from event_logger import log_event
from fastapi import WebSocket, WebSocketDisconnect
from rbac import check_permission
from roe_engine import ROEEngine
from schemas.ontology import (
    Detection,
    SensorSource,
    TargetClassification,
)
from verification_engine import _DEFAULT_THRESHOLD, VERIFICATION_THRESHOLDS, evaluate_target_state

if TYPE_CHECKING:
    from hitl_manager import HITLManager
    from sim_engine import SimulationModel

logger = structlog.get_logger()

# Input validation allowlists
VALID_COVERAGE_MODES = frozenset({"balanced", "threat_adaptive"})
VALID_FEED_TYPES = frozenset({"INTEL_FEED", "COMMAND_FEED", "SENSOR_FEED"})
MAX_SITREP_QUERY_LENGTH = 500
_OPERATOR_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


async def _send_error(websocket: WebSocket, message: str, action: str | None = None) -> None:
    """Send a consistent error response to the client."""
    error_payload = {"type": "ERROR", "message": message}
    if action:
        error_payload["action"] = action
    try:
        await websocket.send_text(json.dumps(error_payload))
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


# ---------------------------------------------------------------------------
# Action -> required fields schema
# ---------------------------------------------------------------------------
_ACTION_SCHEMAS: dict[str, dict[str, str]] = {
    "spike": {"lon": "float", "lat": "float"},
    "move_drone": {"drone_id": "int", "target_lon": "float", "target_lat": "float"},
    "intercept_target": {"drone_id": "int", "target_id": "int"},
    "follow_target": {"drone_id": "int", "target_id": "int"},
    "paint_target": {"drone_id": "int", "target_id": "int"},
    "cancel_track": {"drone_id": "int"},
    "approve_nomination": {"entry_id": "str"},
    "reject_nomination": {"entry_id": "str"},
    "retask_nomination": {"entry_id": "str"},
    "authorize_coa": {"entry_id": "str", "coa_id": "str"},
    "reject_coa": {"entry_id": "str"},
    "verify_target": {"target_id": "int"},
    "scan_area": {"drone_id": "int"},
    "set_autonomy_level": {"level": "str"},
    "set_action_autonomy": {"action": "str", "level": "str"},
    "set_drone_autonomy": {"drone_id": "int"},
    "approve_transition": {"drone_id": "int"},
    "reject_transition": {"drone_id": "int"},
    "intercept_enemy": {"uav_id": "int", "enemy_uav_id": "int"},
    "request_swarm": {"target_id": "int"},
    "release_swarm": {"target_id": "int"},
    "set_coverage_mode": {"mode": "str"},
    "save_checkpoint": {"mission_id": "int"},
    "load_mission": {"mission_id": "int"},
}

# Field type validators
_TYPE_VALIDATORS = {
    "int": lambda v: isinstance(v, int) or (isinstance(v, float) and v == int(v)),
    "float": lambda v: isinstance(v, (int, float)),
    "str": lambda v: isinstance(v, str),
}


def _validate_payload(payload: dict, schema: dict[str, str]) -> str | None:
    """Validate that payload contains required fields with correct types."""
    for field, type_name in schema.items():
        if field not in payload or payload[field] is None:
            return f"Missing required field: '{field}'"
        validator = _TYPE_VALIDATORS.get(type_name)
        if validator and not validator(payload[field]):
            return f"Field '{field}' must be {type_name}, got {type(payload[field]).__name__}"
    return None


def _build_sitrep_payload(sim: SimulationModel, hitl: HITLManager, query_text: str = "") -> dict:
    """Build a SITREP payload dict from current sim state."""
    state = sim.get_state()
    targets = state.get("targets", [])
    strike_board = hitl.get_strike_board()
    detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
    pending_hitl = [e for e in strike_board if e.get("status") == "PENDING"]

    if detected:
        threat_lines = [f"{t['type']} at ({t.get('lat', 0):.4f}, {t.get('lon', 0):.4f})" for t in detected[:5]]
        narrative = (
            f"SITREP: {len(detected)} active contact(s) detected. "
            f"Threats: {'; '.join(threat_lines)}. "
            f"{len(pending_hitl)} target(s) awaiting HITL review."
        )
        key_threats = [f"{t['type']} (id={t['id']})" for t in detected[:5]]
    else:
        narrative = "SITREP: No active contacts. Battlespace clear."
        key_threats = []

    recommended_actions: list[str] = []
    if pending_hitl:
        recommended_actions.append(f"Review {len(pending_hitl)} pending strike board nomination(s).")
    if not detected:
        recommended_actions.append("Continue ISR coverage.")

    payload = {
        "sitrep_narrative": narrative,
        "key_threats": key_threats,
        "recommended_actions": recommended_actions,
        "data_sources_consulted": ["sim_engine", "hitl_strike_board"],
        "confidence": 0.7 if detected else 0.9,
    }
    if query_text:
        payload["query"] = query_text
    return payload


# ---------------------------------------------------------------------------
# Individual action handlers — each receives (payload, websocket, ctx)
# ctx is a dict with keys: sim, hitl, intel_router, broadcast, clients,
#                           ai_tasking_manager, raw_data
# ---------------------------------------------------------------------------


class HandlerContext:
    """Holds shared dependencies injected from api_main."""

    __slots__ = (
        "sim",
        "hitl",
        "intel_router",
        "broadcast",
        "clients",
        "ai_tasking_manager",
        "raw_data",
        "roe_engine",
        "override_tracker",
    )

    def __init__(
        self,
        *,
        sim,
        hitl,
        intel_router,
        broadcast,
        clients,
        ai_tasking_manager,
        raw_data: str,
        roe_engine: ROEEngine | None = None,
        override_tracker=None,
    ):
        self.sim = sim
        self.hitl = hitl
        self.intel_router = intel_router
        self.broadcast = broadcast
        self.clients = clients
        self.ai_tasking_manager = ai_tasking_manager
        self.raw_data = raw_data
        self.roe_engine = roe_engine
        self.override_tracker = override_tracker


async def _handle_spike(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.trigger_demand_spike(payload["lon"], payload["lat"])


async def _handle_move_drone(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    tlon, tlat = payload["target_lon"], payload["target_lat"]
    if not math.isfinite(tlon) or not math.isfinite(tlat):
        await _send_error(websocket, "target_lon/target_lat must be finite numbers (not NaN or Inf)", "move_drone")
        return
    if not (-180.0 <= tlon <= 180.0) or not (-90.0 <= tlat <= 90.0):
        await _send_error(websocket, "target_lon must be in [-180,180] and target_lat in [-90,90]", "move_drone")
        return
    ctx.sim.command_move(payload["drone_id"], tlon, tlat)


async def _handle_set_scenario(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    from theater_loader import list_theaters as _list_theaters

    scenario = payload.get("scenario") or payload.get("theater")
    if scenario and scenario not in _list_theaters():
        await _send_error(websocket, f"Unknown theater '{scenario}'. Valid: {_list_theaters()}", "SET_SCENARIO")
        return
    await ctx.broadcast(ctx.raw_data, target_type="SIMULATOR", sender=websocket)


async def _handle_forward_to_dashboard(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    await ctx.broadcast(ctx.raw_data, target_type="DASHBOARD", sender=websocket)


async def _handle_follow_target(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.command_follow(payload["drone_id"], payload["target_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "follow_target",
            "drone_id": payload["drone_id"],
            "target_id": payload["target_id"],
            "source": "operator",
        },
    )


async def _handle_paint_target(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.command_paint(payload["drone_id"], payload["target_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "paint_target",
            "drone_id": payload["drone_id"],
            "target_id": payload["target_id"],
            "source": "operator",
        },
    )


async def _handle_intercept_target(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.command_intercept(payload["drone_id"], payload["target_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "intercept_target",
            "drone_id": payload["drone_id"],
            "target_id": payload["target_id"],
            "source": "operator",
        },
    )


async def _handle_intercept_enemy(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.command_intercept_enemy(payload["uav_id"], payload["enemy_uav_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "intercept_enemy",
            "uav_id": payload["uav_id"],
            "enemy_uav_id": payload["enemy_uav_id"],
            "source": "operator",
        },
    )


async def _handle_cancel_or_scan(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    action = payload.get("action")
    ctx.sim.cancel_track(payload["drone_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": action, "drone_id": payload["drone_id"], "source": "operator"}
    )


async def _handle_approve_nomination(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    rationale = payload.get("rationale", "")
    operator_id = payload.get("operator_id")
    if operator_id is not None:
        if not isinstance(operator_id, str) or not _OPERATOR_ID_RE.match(operator_id):
            await _send_error(websocket, "Field 'operator_id' must match [a-zA-Z0-9_-]{1,64}", "approve_nomination")
            return
    try:
        ctx.hitl.approve_nomination(payload["entry_id"], rationale, operator_id=operator_id)
        await ctx.intel_router.emit(
            "COMMAND_FEED", {"action": "approved", "entry_id": payload["entry_id"], "source": "operator"}
        )
        response = json.dumps({"type": "HITL_UPDATE", "action": "approved", "entry": ctx.hitl.get_strike_board()})
        await ctx.broadcast(response, target_type="DASHBOARD")
    except ValueError as exc:
        logger.warning("approve_nomination_failed", error=str(exc))


async def _handle_reject_nomination(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    rationale = payload.get("rationale", "")
    reason = payload.get("reason")
    reason_text = payload.get("reason_text")
    operator_id = payload.get("operator_id")
    if operator_id is not None:
        if not isinstance(operator_id, str) or not _OPERATOR_ID_RE.match(operator_id):
            await _send_error(websocket, "Field 'operator_id' must match [a-zA-Z0-9_-]{1,64}", "reject_nomination")
            return
    try:
        ctx.hitl.reject_nomination(payload["entry_id"], rationale, operator_id=operator_id)
        from audit_log import audit_log

        details: dict = {"entry_id": payload["entry_id"], "action": "reject_nomination", "rationale": rationale}
        if reason:
            details["reason"] = reason
        if reason_text:
            details["reason_text"] = reason_text
        audit_log.append(
            "OPERATOR_OVERRIDE",
            autonomy_level=getattr(ctx.sim, "autonomy_level", "MANUAL"),
            details=details,
        )
        if ctx.override_tracker and reason:
            from override_tracker import OverrideReason

            try:
                reason_enum = OverrideReason(reason)
            except ValueError:
                reason_enum = OverrideReason.OTHER
            ctx.override_tracker.record(
                action_type="REJECT_NOMINATION",
                target_id=payload.get("target_id"),
                reason=reason_enum,
                free_text=reason_text,
                ai_recommendation=rationale or "AI nomination",
            )
        response = json.dumps({"type": "HITL_UPDATE", "action": "rejected", "entry": ctx.hitl.get_strike_board()})
        await ctx.broadcast(response, target_type="DASHBOARD")
    except ValueError as exc:
        logger.warning("reject_nomination_failed", error=str(exc))


async def _handle_retask_nomination(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    rationale = payload.get("rationale", "")
    operator_id = payload.get("operator_id")
    if operator_id is not None:
        if not isinstance(operator_id, str) or not _OPERATOR_ID_RE.match(operator_id):
            await _send_error(websocket, "Field 'operator_id' must match [a-zA-Z0-9_-]{1,64}", "retask_nomination")
            return
    try:
        ctx.hitl.retask_nomination(payload["entry_id"], rationale, operator_id=operator_id)
        response = json.dumps({"type": "HITL_UPDATE", "action": "retasked", "entry": ctx.hitl.get_strike_board()})
        await ctx.broadcast(response, target_type="DASHBOARD")
    except ValueError as exc:
        logger.warning("retask_nomination_failed", error=str(exc))


async def _handle_authorize_coa(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    rationale = payload.get("rationale", "")
    try:
        ctx.hitl.authorize_coa(payload["entry_id"], payload["coa_id"], rationale)
        await ctx.intel_router.emit(
            "COMMAND_FEED",
            {
                "action": "coa_authorized",
                "entry_id": payload["entry_id"],
                "coa_id": payload["coa_id"],
                "source": "operator",
            },
        )
        response = json.dumps(
            {
                "type": "HITL_UPDATE",
                "action": "coa_authorized",
                "entry_id": payload["entry_id"],
                "coas": ctx.hitl.get_coas_for_entry(payload["entry_id"]),
            }
        )
        await ctx.broadcast(response, target_type="DASHBOARD")
    except ValueError as exc:
        logger.warning("authorize_coa_failed", error=str(exc))


async def _handle_reject_coa(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    rationale = payload.get("rationale", "")
    reason = payload.get("reason")
    reason_text = payload.get("reason_text")
    try:
        ctx.hitl.reject_coa(payload["entry_id"], rationale)
        from audit_log import audit_log

        details: dict = {"entry_id": payload["entry_id"], "action": "reject_coa", "rationale": rationale}
        if reason:
            details["reason"] = reason
        if reason_text:
            details["reason_text"] = reason_text
        audit_log.append(
            "OPERATOR_OVERRIDE",
            autonomy_level=getattr(ctx.sim, "autonomy_level", "MANUAL"),
            details=details,
        )
        if ctx.override_tracker and reason:
            from override_tracker import OverrideReason

            try:
                reason_enum = OverrideReason(reason)
            except ValueError:
                reason_enum = OverrideReason.OTHER
            ctx.override_tracker.record(
                action_type="REJECT_COA",
                target_id=payload.get("target_id"),
                reason=reason_enum,
                free_text=reason_text,
                ai_recommendation=rationale or "AI COA",
            )
        response = json.dumps(
            {
                "type": "HITL_UPDATE",
                "action": "coas_rejected",
                "entry_id": payload["entry_id"],
                "coas": ctx.hitl.get_coas_for_entry(payload["entry_id"]),
            }
        )
        await ctx.broadcast(response, target_type="DASHBOARD")
    except ValueError as exc:
        logger.warning("reject_coa_failed", error=str(exc))


async def _handle_verify_target(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    target_id = payload["target_id"]
    target = ctx.sim._find_target(target_id)
    if target and target.state == "CLASSIFIED":
        sensor_type_count = (
            len({s.sensor_type for s in target.sensor_contributions}) if target.sensor_contributions else 1
        )
        seconds_since_last_sensor = (
            (time.time() - target.last_sensor_contact_time)
            if hasattr(target, "last_sensor_contact_time") and target.last_sensor_contact_time
            else 0.0
        )
        new_state = evaluate_target_state(
            current_state=target.state,
            target_type=target.type,
            fused_confidence=target.fused_confidence,
            sensor_type_count=sensor_type_count,
            time_in_current_state_sec=target.time_in_state_sec,
            seconds_since_last_sensor=seconds_since_last_sensor,
        )
        if new_state == target.state:
            thresholds = VERIFICATION_THRESHOLDS.get(target.type, _DEFAULT_THRESHOLD)
            await _send_error(
                websocket,
                f"Cannot verify: confidence {target.fused_confidence:.2f} below threshold {thresholds.verify_confidence:.2f}",
                "verify_target",
            )
        else:
            old_state = target.state
            target.state = new_state
            target.time_in_state_sec = 0.0
            log_event(
                "OPERATOR_OVERRIDE",
                {
                    "action": "verify_target",
                    "target_id": target_id,
                    "target_type": target.type,
                    "from_state": old_state,
                    "to_state": new_state,
                    "operator_override": True,
                },
            )
            await ctx.intel_router.emit(
                "INTEL_FEED",
                {
                    "event": "state_transition",
                    "target_id": target_id,
                    "target_type": target.type,
                    "from": old_state,
                    "to": new_state,
                    "source": "manual_operator",
                    "summary": f"Target {target_id} ({target.type}) manually verified",
                },
            )
            logger.info("manual_verify", target_id=target_id)


async def _handle_sitrep_query(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    query_text = payload.get("query", "Provide current situation report.")
    action = payload.get("action") or "sitrep_query"
    if not isinstance(query_text, str):
        await _send_error(websocket, "Field 'query' must be str", action)
        return
    if len(query_text) > MAX_SITREP_QUERY_LENGTH:
        await _send_error(websocket, f"Query exceeds {MAX_SITREP_QUERY_LENGTH} character limit", action)
        return
    response_payload = {"type": "SITREP_RESPONSE", **_build_sitrep_payload(ctx.sim, ctx.hitl, query_text)}
    try:
        await websocket.send_text(json.dumps(response_payload))
    except (WebSocketDisconnect, ConnectionError, OSError) as exc:
        logger.warning("sitrep_reply_failed", error=str(exc))


async def _handle_retask_sensors(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    try:
        detection = Detection(
            source=SensorSource.UAV,
            lat=float(payload.get("lat", 0.0)),
            lon=float(payload.get("lon", 0.0)),
            confidence=float(payload.get("confidence", 0.5)),
            classification=TargetClassification(
                payload.get("target_type", "Unknown")
                if payload.get("target_type") in TargetClassification.__members__
                else "Unknown"
            ),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = ctx.ai_tasking_manager.evaluate_and_retask(detection, available_assets=[])
        response = {
            "type": "RETASK_RESPONSE",
            "tasking_orders": [o.model_dump(mode="json") for o in result.tasking_orders],
            "confidence_gap": result.confidence_gap,
            "reasoning": result.reasoning,
        }
    except Exception as exc:
        logger.error("retask_sensors_failed", error=str(exc))
        response = {"type": "RETASK_RESPONSE", "error": "Sensor retasking failed"}

    try:
        await websocket.send_text(json.dumps(response))
    except (WebSocketDisconnect, ConnectionError, OSError) as exc:
        logger.warning("retask_reply_failed", error=str(exc))


async def _handle_reset(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.reset_queues()
    logger.info("grid_state_reset")


async def _handle_set_autonomy_level(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    level = payload.get("level")
    if level not in ("MANUAL", "SUPERVISED", "AUTONOMOUS"):
        await _send_error(
            websocket, "Invalid autonomy level. Must be MANUAL, SUPERVISED, or AUTONOMOUS.", "set_autonomy_level"
        )
        return
    ctx.sim.autonomy_level = level
    # Keep autonomy_policy default in sync (backward compat)
    if hasattr(ctx.sim, "autonomy_policy"):
        ctx.sim.autonomy_policy = ctx.sim.autonomy_policy.set_default_level(level)
    await ctx.intel_router.emit("COMMAND_FEED", {"action": "set_autonomy_level", "level": level, "source": "operator"})
    logger.info("autonomy_level_set", level=level)


async def _handle_set_action_autonomy(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    from autonomy_policy import VALID_ACTIONS, VALID_LEVELS

    action = payload.get("action", "")
    level = payload.get("level", "")
    duration = payload.get("duration_seconds")
    if action not in VALID_ACTIONS:
        await _send_error(websocket, f"Invalid action. Must be one of: {sorted(VALID_ACTIONS)}", "set_action_autonomy")
        return
    if level not in VALID_LEVELS:
        await _send_error(websocket, f"Invalid level. Must be one of: {sorted(VALID_LEVELS)}", "set_action_autonomy")
        return
    if not hasattr(ctx.sim, "autonomy_policy"):
        await _send_error(websocket, "Autonomy policy not initialized", "set_action_autonomy")
        return
    ctx.sim.autonomy_policy = ctx.sim.autonomy_policy.set_action_level(action, level, duration_seconds=duration)
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "set_action_autonomy",
            "target_action": action,
            "level": level,
            "duration": duration,
            "source": "operator",
        },
    )
    logger.info("action_autonomy_set", target_action=action, level=level, duration=duration)


async def _handle_force_manual(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.autonomy_level = "MANUAL"
    if hasattr(ctx.sim, "autonomy_policy"):
        ctx.sim.autonomy_policy = ctx.sim.autonomy_policy.force_manual()
    await ctx.intel_router.emit("COMMAND_FEED", {"action": "force_manual", "source": "operator"})
    logger.info("force_manual_activated")


async def _handle_set_drone_autonomy(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    uav = ctx.sim._find_uav(payload["drone_id"])
    if not uav:
        await _send_error(websocket, f"UAV {payload['drone_id']} not found", "set_drone_autonomy")
        return
    override_level = payload.get("level")  # None clears override
    if override_level is not None and override_level not in ("MANUAL", "SUPERVISED", "AUTONOMOUS"):
        await _send_error(websocket, "Invalid autonomy level for drone override.", "set_drone_autonomy")
        return
    uav.autonomy_override = override_level
    await ctx.intel_router.emit(
        "COMMAND_FEED",
        {
            "action": "set_drone_autonomy",
            "drone_id": payload["drone_id"],
            "level": override_level,
            "source": "operator",
        },
    )
    logger.info("drone_autonomy_set", drone_id=payload["drone_id"], level=override_level)


async def _handle_approve_transition(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.approve_transition(payload["drone_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": "approve_transition", "drone_id": payload["drone_id"], "source": "operator"}
    )
    logger.info("transition_approved", drone_id=payload["drone_id"])


async def _handle_reject_transition(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.reject_transition(payload["drone_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": "reject_transition", "drone_id": payload["drone_id"], "source": "operator"}
    )
    logger.info("transition_rejected", drone_id=payload["drone_id"])


async def _handle_request_swarm(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.request_swarm(payload["target_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": "request_swarm", "target_id": payload["target_id"], "source": "operator"}
    )


async def _handle_release_swarm(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    ctx.sim.release_swarm(payload["target_id"])
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": "release_swarm", "target_id": payload["target_id"], "source": "operator"}
    )


async def _handle_set_coverage_mode(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    mode = payload["mode"]
    if mode not in VALID_COVERAGE_MODES:
        await _send_error(
            websocket,
            f"Invalid coverage mode '{mode}'. Must be one of: {', '.join(sorted(VALID_COVERAGE_MODES))}",
            "set_coverage_mode",
        )
        return
    ctx.sim.set_coverage_mode(mode)
    await ctx.intel_router.emit("COMMAND_FEED", {"action": "set_coverage_mode", "mode": mode, "source": "operator"})


async def _handle_subscribe(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    feeds = payload.get("feeds", [])
    if not isinstance(feeds, list):
        await _send_error(websocket, "Field 'feeds' must be a list", "subscribe")
        return
    invalid_feeds = [f for f in feeds if f not in VALID_FEED_TYPES]
    if invalid_feeds:
        await _send_error(
            websocket, f"Unknown feed type(s): {invalid_feeds}. Valid: {sorted(VALID_FEED_TYPES)}", "subscribe"
        )
        return
    client_info = ctx.clients.get(websocket, {})
    client_info["subscriptions"] = set(feeds)
    if "INTEL_FEED" in feeds:
        history = ctx.intel_router.get_history("INTEL_FEED")
        if history:
            await websocket.send_text(json.dumps({"type": "FEED_HISTORY", "feed": "INTEL_FEED", "events": history}))
    if "COMMAND_FEED" in feeds:
        history = ctx.intel_router.get_history("COMMAND_FEED")
        if history:
            await websocket.send_text(json.dumps({"type": "FEED_HISTORY", "feed": "COMMAND_FEED", "events": history}))


_MAX_SENSOR_FEED_UAV_IDS = 50


async def _handle_subscribe_sensor_feed(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    uav_ids = payload.get("uav_ids", [])
    if not isinstance(uav_ids, list):
        await _send_error(websocket, "Field 'uav_ids' must be a list", "subscribe_sensor_feed")
        return
    if len(uav_ids) > _MAX_SENSOR_FEED_UAV_IDS:
        await _send_error(
            websocket,
            f"Field 'uav_ids' exceeds maximum of {_MAX_SENSOR_FEED_UAV_IDS} items",
            "subscribe_sensor_feed",
        )
        return
    non_ints = [uid for uid in uav_ids if not isinstance(uid, int)]
    if non_ints:
        await _send_error(websocket, "All items in 'uav_ids' must be integers", "subscribe_sensor_feed")
        return
    valid_ids = set(uav_ids)
    client_info = ctx.clients.get(websocket, {})
    client_info.setdefault("subscriptions", set()).add("SENSOR_FEED")
    client_info["sensor_feed_uav_ids"] = valid_ids


async def _handle_save_checkpoint(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    import api_main

    mission_id = payload.get("mission_id")
    if not isinstance(mission_id, int):
        await _send_error(websocket, "Field 'mission_id' must be int", "save_checkpoint")
        return
    state_json = json.dumps(ctx.sim.get_state())
    api_main.mission_store.save_checkpoint(mission_id, state_json)
    try:
        await websocket.send_text(json.dumps({"type": "CHECKPOINT_SAVED", "mission_id": mission_id}))
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


async def _handle_load_mission(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    import api_main

    mission_id = payload.get("mission_id")
    if not isinstance(mission_id, int):
        await _send_error(websocket, "Field 'mission_id' must be int", "load_mission")
        return
    checkpoint = api_main.mission_store.load_checkpoint(mission_id)
    if checkpoint is None:
        await _send_error(websocket, f"No checkpoint for mission {mission_id}", "load_mission")
        return
    try:
        await websocket.send_text(
            json.dumps({"type": "MISSION_LOADED", "mission_id": mission_id, "state": json.loads(checkpoint)})
        )
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


async def _handle_get_roe(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    if ctx.roe_engine is None:
        await _send_error(websocket, "No ROE engine loaded", "get_roe")
        return
    rules_data = [
        {
            "name": r.name,
            "target_type": r.target_type,
            "zone_id": r.zone_id,
            "min_autonomy_level": r.min_autonomy_level,
            "max_collateral_radius_m": r.max_collateral_radius_m,
            "decision": r.decision.value,
        }
        for r in ctx.roe_engine.rules
    ]
    try:
        await websocket.send_text(json.dumps({"type": "ROE_RULES", "rules": rules_data}))
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


_ROE_BASE = (pathlib.Path(__file__).parent.parent.parent / "roe").resolve()


async def _handle_launch_drone(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    launcher_name = payload.get("launcher_name")
    if not launcher_name or not isinstance(launcher_name, str):
        await _send_error(websocket, "Field 'launcher_name' is required and must be a string", "launch_drone")
        return
    if len(launcher_name) > 128:
        await _send_error(websocket, "Launcher name too long", "launch_drone")
        return
    launcher = next((l for l in ctx.sim.launchers if l["name"] == launcher_name), None)
    if launcher is None:
        await _send_error(websocket, f"Launcher '{launcher_name}' not found", "launch_drone")
        return
    if launcher["available"] <= 0:
        await _send_error(websocket, f"Launcher '{launcher_name}' has no available capacity", "launch_drone")
        return
    launcher["available"] = max(0, launcher["available"] - 1)
    new_id = ctx.sim.add_uav_at(launcher["lon"], launcher["lat"])
    if new_id is None:
        launcher["available"] += 1
        await _send_error(websocket, "UAV limit reached", "launch_drone")
        return
    try:
        await websocket.send_text(
            json.dumps({"type": "DRONE_LAUNCHED", "uav_id": new_id, "launcher_name": launcher_name})
        )
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


async def _handle_set_roe(payload: dict, websocket: WebSocket, ctx: HandlerContext) -> None:
    path = payload.get("path")
    if not path or not isinstance(path, str):
        await _send_error(websocket, "Field 'path' is required and must be a string", "set_roe")
        return
    resolved = pathlib.Path(path).resolve()
    if not str(resolved).startswith(str(_ROE_BASE)):
        await _send_error(websocket, "Invalid ROE path: must be within the roe/ directory", "set_roe")
        return
    try:
        new_engine = ROEEngine.load_from_yaml(path)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        await _send_error(websocket, f"Failed to load ROE: {exc}", "set_roe")
        return
    ctx.roe_engine = new_engine
    await ctx.intel_router.emit(
        "COMMAND_FEED", {"action": "set_roe", "path": path, "rule_count": len(new_engine.rules), "source": "operator"}
    )
    logger.info("roe_rules_loaded_via_ws", path=path, rule_count=len(new_engine.rules))
    try:
        await websocket.send_text(
            json.dumps({"type": "ROE_UPDATED", "rule_count": len(new_engine.rules), "path": path})
        )
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


# ---------------------------------------------------------------------------
# Command dispatch table — dict mapping action strings to handler functions
# ---------------------------------------------------------------------------
_DISPATCH_TABLE: dict[str, Callable] = {
    "spike": _handle_spike,
    "move_drone": _handle_move_drone,
    "SET_SCENARIO": _handle_set_scenario,
    "follow_target": _handle_follow_target,
    "paint_target": _handle_paint_target,
    "intercept_target": _handle_intercept_target,
    "intercept_enemy": _handle_intercept_enemy,
    "cancel_track": _handle_cancel_or_scan,
    "scan_area": _handle_cancel_or_scan,
    "approve_nomination": _handle_approve_nomination,
    "reject_nomination": _handle_reject_nomination,
    "retask_nomination": _handle_retask_nomination,
    "authorize_coa": _handle_authorize_coa,
    "reject_coa": _handle_reject_coa,
    "verify_target": _handle_verify_target,
    "sitrep_query": _handle_sitrep_query,
    "generate_sitrep": _handle_sitrep_query,
    "retask_sensors": _handle_retask_sensors,
    "reset": _handle_reset,
    "set_autonomy_level": _handle_set_autonomy_level,
    "set_action_autonomy": _handle_set_action_autonomy,
    "force_manual": _handle_force_manual,
    "set_drone_autonomy": _handle_set_drone_autonomy,
    "approve_transition": _handle_approve_transition,
    "reject_transition": _handle_reject_transition,
    "request_swarm": _handle_request_swarm,
    "release_swarm": _handle_release_swarm,
    "set_coverage_mode": _handle_set_coverage_mode,
    "subscribe": _handle_subscribe,
    "subscribe_sensor_feed": _handle_subscribe_sensor_feed,
    "get_roe": _handle_get_roe,
    "set_roe": _handle_set_roe,
    "save_checkpoint": _handle_save_checkpoint,
    "load_mission": _handle_load_mission,
    "launch_drone": _handle_launch_drone,
}

# Type-based dispatch for forwarding messages
_TYPE_FORWARD = frozenset({"DRONE_FEED", "TRACK_UPDATE", "TRACK_UPDATE_BATCH"})


async def handle_payload(payload: dict, websocket: WebSocket, raw_data: str, ctx: HandlerContext) -> None:
    """Dispatch incoming WebSocket payloads to the correct handler."""
    action = payload.get("action")
    p_type = payload.get("type")

    # RBAC permission check — skip when AUTH_DISABLED
    if not rbac.AUTH_DISABLED:
        # Resolve the action key for the permission matrix (type-based forwards use p_type)
        _rbac_key = action or p_type
        session = ctx.clients.get(websocket, {}).get("session")
        role = session.role if session else rbac.Role.OBSERVER
        if _rbac_key and not check_permission(role, _rbac_key):
            await _send_error(websocket, f"Permission denied for action '{_rbac_key}'", action)
            return

    # Validate payload against schema if action has one
    if action in _ACTION_SCHEMAS:
        error = _validate_payload(payload, _ACTION_SCHEMAS[action])
        if error:
            logger.warning("ws_payload_validation_failed", action=action, error=error)
            await _send_error(websocket, error, action)
            return

    # Action-based dispatch
    handler = _DISPATCH_TABLE.get(action)
    if handler:
        await handler(payload, websocket, ctx)
        return

    # Type-based forwarding
    if p_type in _TYPE_FORWARD:
        await _handle_forward_to_dashboard(payload, websocket, ctx)
        return

    # SITREP_QUERY by type (not action)
    if p_type == "SITREP_QUERY":
        await _handle_sitrep_query(payload, websocket, ctx)
        return
