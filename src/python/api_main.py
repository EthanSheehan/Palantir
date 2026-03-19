from __future__ import annotations

import asyncio
import collections
import json
import time

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

from logging_config import configure_logging
from config import load_settings
from event_logger import log_event, start_logger as start_event_logger, stop_logger as stop_event_logger

from sim_engine import SimulationModel
from hitl_manager import HITLManager
from agents.isr_observer import ISRObserverAgent
from agents.strategy_analyst import StrategyAnalystAgent
from agents.tactical_planner import TacticalPlannerAgent
from agents.ai_tasking_manager import AITaskingManagerAgent
from agents.battlespace_manager import BattlespaceManagerAgent
from agents.synthesis_query_agent import SynthesisQueryAgent
from llm_adapter import LLMAdapter
from pipeline import F2T2EAPipeline
from schemas.ontology import (
    Detection,
    EngagementDecision,
    SensorSource,
    TargetClassification,
)

configure_logging()
logger = structlog.get_logger()

settings = load_settings()

# ---------------------------------------------------------------------------
# WebSocket hardening constants
# ---------------------------------------------------------------------------
MAX_WS_CONNECTIONS = 20
RATE_LIMIT_MAX_MESSAGES = 30  # per second
RATE_LIMIT_WINDOW = 1.0  # seconds

# Field type validators
_TYPE_VALIDATORS = {
    "int": lambda v: isinstance(v, int) or (isinstance(v, float) and v == int(v)),
    "float": lambda v: isinstance(v, (int, float)),
    "str": lambda v: isinstance(v, str),
}


def _validate_payload(payload: dict, schema: dict[str, str]) -> str | None:
    """Validate that payload contains required fields with correct types.

    schema maps field_name -> type_name ("int", "float", "str").
    Returns an error message string on failure, None on success.
    """
    for field, type_name in schema.items():
        if field not in payload or payload[field] is None:
            return f"Missing required field: '{field}'"
        validator = _TYPE_VALIDATORS.get(type_name)
        if validator and not validator(payload[field]):
            return f"Field '{field}' must be {type_name}, got {type(payload[field]).__name__}"
    return None


async def _send_error(websocket: WebSocket, message: str, action: str | None = None) -> None:
    """Send a consistent error response to the client."""
    error_payload = {"type": "ERROR", "message": message}
    if action:
        error_payload["action"] = action
    try:
        await websocket.send_text(json.dumps(error_payload))
    except (WebSocketDisconnect, ConnectionError, OSError):
        pass


def _check_rate_limit(client_info: dict) -> bool:
    """Return True if the client is within rate limits, False if exceeded."""
    now = time.monotonic()
    timestamps = client_info.setdefault("msg_timestamps", collections.deque())
    # Purge old timestamps outside the window
    while timestamps and timestamps[0] < now - RATE_LIMIT_WINDOW:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_MAX_MESSAGES:
        return False
    timestamps.append(now)
    return True


# Action -> required fields schema
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
}

# ---------------------------------------------------------------------------
# Agent instantiation (heuristic mode — LLMAdapter handles fallback automatically)
# ---------------------------------------------------------------------------

llm_adapter = LLMAdapter()
pipeline = F2T2EAPipeline(llm_client=None, available_effectors=None)
isr_observer = ISRObserverAgent()
strategy_analyst = StrategyAnalystAgent()
tactical_planner = TacticalPlannerAgent()
ai_tasking_manager = AITaskingManagerAgent(llm_client=None)
battlespace_manager = BattlespaceManagerAgent(llm_client=None)
synthesis_query = SynthesisQueryAgent(llm_client=None)


class TacticalAssistant:
    """Tracks new detections, triggers ISR→Strategy→HITL pipeline per event."""

    def __init__(self):
        self.message_history = []
        self.last_detected = {}  # target_id -> bool
        # track_id -> True for targets already nominated to avoid duplicates
        self._nominated: set = set()

    def update(self, sim_state):
        new_messages = []
        for target in sim_state.get("targets", []):
            tid = target["id"]
            is_detected = target.get("state", "UNDETECTED") != "UNDETECTED"
            t_type = target["type"]

            if is_detected and not self.last_detected.get(tid, False):
                msg = {
                    "type": "ASSISTANT_MESSAGE",
                    "text": f"NEW CONTACT: {t_type} localized at {target['lon']:.4f}, {target['lat']:.4f}",
                    "severity": "INFO",
                    "timestamp": time.strftime("%H:%M:%S")
                }
                new_messages.append(msg)
                # Fire ISR→Strategy→HITL pipeline for this new detection
                hitl_msg = _process_new_detection(target, self._nominated)
                if hitl_msg:
                    new_messages.append(hitl_msg)

            self.last_detected[tid] = is_detected

        return new_messages


def _process_new_detection(target: dict, nominated: set) -> dict | None:
    """
    Run ISR Observer → Strategy Analyst → HITL nomination for a newly
    detected target. Returns an ASSISTANT_MESSAGE dict if the target was
    nominated, otherwise None.

    This is intentionally synchronous (heuristic path only) so it can be
    called from the sync TacticalAssistant.update() without awaiting.
    """
    track_key = f"TRK-{target['id']}"
    if track_key in nominated:
        return None

    raw_json = json.dumps({
        "id": target["id"],
        "type": target["type"],
        "source": "UAV",
        "lat": target.get("lat", 0.0),
        "lon": target.get("lon", 0.0),
        "confidence": target.get("confidence", 0.75),
        "classification": target["type"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

    try:
        isr_output = isr_observer.process_sensor_data(raw_json)
        analyst_output = strategy_analyst.evaluate_tracks(isr_output)
    except Exception as exc:
        logger.error("isr_strategy_pipeline_failed", error=str(exc))
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
            "text": (
                f"NOMINATED: {target['type']} (id={target['id']}) "
                f"forwarded to strike board for HITL review."
            ),
            "severity": "WARNING",
            "timestamp": time.strftime("%H:%M:%S"),
        }

    return None


assistant = TacticalAssistant()
_get_demo_effectors = None
if settings.demo_mode:
    from mission_data.asset_registry import get_available_effectors as _get_demo_effectors


def _get_entry_if_status(entry_id: str, expected_status: str) -> dict | None:
    """Re-fetch a strike board entry and return it only if it still has the expected status."""
    for e in hitl.get_strike_board():
        if e["id"] == entry_id and e["status"] == expected_status:
            return e
    return None


def _find_nearest_available_uav(target_id: int) -> int | None:
    """Find the nearest idle/scanning UAV to a target and return its id."""
    target = sim._find_target(target_id)
    if not target:
        return None
    available = [u for u in sim.uavs if u.mode in ("IDLE", "SCANNING")]
    if not available:
        return None
    best = min(available, key=lambda u: (u.x - target.x) ** 2 + (u.y - target.y) ** 2)
    return best.id


async def demo_autopilot():
    """Auto-pilot loop: auto-approve nominations, dispatch UAVs to follow & paint targets."""
    APPROVAL_DELAY = 5.0
    FOLLOW_DELAY = 4.0
    PAINT_DELAY = 5.0

    logger.warning("demo_autopilot_started", note="HITL bypass active")

    await asyncio.sleep(2.0)
    await broadcast(json.dumps({
        "type": "ASSISTANT_MESSAGE",
        "text": "DEMO MODE ACTIVE — UAV intercept auto-pilot running.",
        "severity": "CRITICAL",
        "timestamp": time.strftime("%H:%M:%S"),
    }), target_type="DASHBOARD")

    in_flight: set[str] = set()

    while True:
        await asyncio.sleep(2.0)

        board = hitl.get_strike_board()
        for entry in board:
            if entry["status"] != "PENDING" or entry["id"] in in_flight:
                continue

            entry_id = entry["id"]
            target_id = entry["target_id"]
            in_flight.add(entry_id)

            # --- Gate 1: Auto-approve after delay ---
            await asyncio.sleep(APPROVAL_DELAY)
            entry = _get_entry_if_status(entry_id, "PENDING")
            if not entry:
                in_flight.discard(entry_id)
                continue

            try:
                hitl.approve_nomination(entry_id, "Demo auto-approved")
            except ValueError:
                in_flight.discard(entry_id)
                continue

            await broadcast(json.dumps({
                "type": "ASSISTANT_MESSAGE",
                "text": f"AUTO-APPROVED: {entry['target_type']} (id={target_id}) — dispatching nearest UAV...",
                "severity": "WARNING",
                "timestamp": time.strftime("%H:%M:%S"),
            }), target_type="DASHBOARD")
            await broadcast(json.dumps({
                "type": "HITL_UPDATE",
                "action": "approved",
                "entry": hitl.get_strike_board(),
            }), target_type="DASHBOARD")

            # --- Dispatch UAV: follow target ---
            uav_id = _find_nearest_available_uav(target_id)
            if uav_id is None:
                await broadcast(json.dumps({
                    "type": "ASSISTANT_MESSAGE",
                    "text": f"NO AVAILABLE UAV for {entry['target_type']} (id={target_id}) — all assets committed.",
                    "severity": "WARNING",
                    "timestamp": time.strftime("%H:%M:%S"),
                }), target_type="DASHBOARD")
                in_flight.discard(entry_id)
                continue

            sim.command_follow(uav_id, target_id)
            await broadcast(json.dumps({
                "type": "ASSISTANT_MESSAGE",
                "text": f"UAV-{uav_id} FOLLOWING: {entry['target_type']} (id={target_id}) — tracking in progress.",
                "severity": "INFO",
                "timestamp": time.strftime("%H:%M:%S"),
            }), target_type="DASHBOARD")

            # --- After follow delay, escalate to paint (laser lock) ---
            await asyncio.sleep(FOLLOW_DELAY)
            target = sim._find_target(target_id)
            if target and target.tracked_by_uav_id == uav_id:
                sim.command_paint(uav_id, target_id)
                await broadcast(json.dumps({
                    "type": "ASSISTANT_MESSAGE",
                    "text": f"UAV-{uav_id} PAINTING: {entry['target_type']} (id={target_id}) — laser lock established.",
                    "severity": "CRITICAL",
                    "timestamp": time.strftime("%H:%M:%S"),
                }), target_type="DASHBOARD")

                # Generate COAs while painting
                target_loc = entry.get("target_location", [0.0, 0.0])
                coas = tactical_planner._generate_coas_heuristic(
                    target_data={
                        "lat": target_loc[0] if len(target_loc) > 0 else 0.0,
                        "lon": target_loc[1] if len(target_loc) > 1 else 0.0,
                        "type": entry["target_type"],
                    },
                    assets=_get_demo_effectors(),
                )
                if coas:
                    hitl.propose_coas(entry_id, coas)
                    await broadcast(json.dumps({
                        "type": "HITL_UPDATE",
                        "action": "coas_proposed",
                        "entry_id": entry_id,
                        "coas": hitl.get_coas_for_entry(entry_id),
                    }), target_type="DASHBOARD")

                    coa_names = [f"{c.effector_name} (Pk={c.pk_estimate:.0%})" for c in coas]
                    await broadcast(json.dumps({
                        "type": "ASSISTANT_MESSAGE",
                        "text": f"COAs GENERATED: {' | '.join(coa_names)} — awaiting authorization.",
                        "severity": "INFO",
                        "timestamp": time.strftime("%H:%M:%S"),
                    }), target_type="DASHBOARD")

                    # Auto-authorize best COA
                    await asyncio.sleep(PAINT_DELAY)
                    entry = _get_entry_if_status(entry_id, "APPROVED")
                    if entry:
                        best_coa = coas[0]
                        try:
                            hitl.authorize_coa(entry_id, best_coa.id, "Demo auto-authorized")
                        except ValueError:
                            pass
                        else:
                            await broadcast(json.dumps({
                                "type": "ASSISTANT_MESSAGE",
                                "text": f"COA AUTHORIZED: {best_coa.effector_name} — Pk={best_coa.pk_estimate:.0%}. UAV-{uav_id} maintaining lock.",
                                "severity": "WARNING",
                                "timestamp": time.strftime("%H:%M:%S"),
                            }), target_type="DASHBOARD")
                            await broadcast(json.dumps({
                                "type": "HITL_UPDATE",
                                "action": "coa_authorized",
                                "entry_id": entry_id,
                                "coas": hitl.get_coas_for_entry(entry_id),
                            }), target_type="DASHBOARD")

            in_flight.discard(entry_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start event logger and simulation loop
    await start_event_logger()
    task = asyncio.create_task(simulation_loop())
    demo_task = None
    if settings.demo_mode:
        demo_task = asyncio.create_task(demo_autopilot())
    yield
    # Shutdown: Cancel tasks
    task.cancel()
    if demo_task:
        demo_task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    if demo_task:
        try:
            await demo_task
        except asyncio.CancelledError:
            pass
    await stop_event_logger()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = SimulationModel(theater_name=settings.default_theater)
hitl = HITLManager()
clients = {} # websocket -> info dict

async def broadcast(message: str, target_type: str = None, sender: WebSocket = None):
    """Parallel broadcast to all matching clients with a strict timeout."""
    if not clients:
        return

    targets = []
    for ws, info in clients.items():
        if ws == sender:
            continue
        if target_type and info.get("type") != target_type:
            continue
        targets.append(ws)

    if not targets:
        return

    async def _send(ws):
        try:
            await asyncio.wait_for(ws.send_text(message), timeout=0.1)
        except (asyncio.TimeoutError, WebSocketDisconnect, ConnectionError, OSError) as exc:
            logger.warning("broadcast_send_failed", error=str(exc))
            return ws

    # Run all sends in parallel
    results = await asyncio.gather(*[_send(t) for t in targets])

    # Cleanup failed clients
    for failed_ws in results:
        if failed_ws and failed_ws in clients:
            clients.pop(failed_ws, None)

async def simulation_loop():
    tick_interval = 1.0 / settings.simulation_hz
    logger.info("simulation_loop_started", hz=settings.simulation_hz)
    while True:
        sim.tick()
        if clients:
            state = sim.get_state()
            state["strike_board"] = hitl.get_strike_board()
            state["demo_mode"] = settings.demo_mode
            state_json = json.dumps({"type": "state", "data": state})
            # Only send simulation state to dashboard clients
            await broadcast(state_json, target_type="DASHBOARD")

            # Update assistant
            assistant_msgs = assistant.update(state)
            for msg in assistant_msgs:
                await broadcast(json.dumps(msg), target_type="DASHBOARD")

        await asyncio.sleep(tick_interval)

@app.post("/api/sitrep")
async def post_sitrep(body: dict):
    """REST endpoint for SITREP queries (mirrors the WebSocket SITREP_QUERY handler)."""
    query_text = body.get("query", "Provide current situation report.")
    state = sim.get_state()
    targets = state.get("targets", [])
    strike_board = hitl.get_strike_board()
    detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
    pending_hitl = [e for e in strike_board if e.get("status") == "PENDING"]

    if detected:
        threat_lines = [
            f"{t['type']} at ({t.get('lat', 0):.4f}, {t.get('lon', 0):.4f})"
            for t in detected[:5]
        ]
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

    return {
        "sitrep_narrative": narrative,
        "key_threats": key_threats,
        "recommended_actions": recommended_actions,
        "data_sources_consulted": ["sim_engine", "hitl_strike_board"],
        "confidence": 0.7 if detected else 0.9,
    }


@app.post("/api/environment")
async def set_environment(body: dict):
    time_of_day = body.get("time_of_day", 12.0)
    cloud_cover = body.get("cloud_cover", 0.0)
    precipitation = body.get("precipitation", 0.0)
    sim.set_environment(time_of_day, cloud_cover, precipitation)
    return {"status": "ok", "environment": {"time_of_day": time_of_day, "cloud_cover": cloud_cover, "precipitation": precipitation}}


@app.get("/api/theaters")
async def get_theaters():
    from theater_loader import list_theaters
    return {"theaters": list_theaters()}


@app.post("/api/theater")
async def switch_theater(body: dict):
    global sim
    theater_name = body.get("theater")
    if not theater_name:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Missing 'theater' field")
    sim = SimulationModel(theater_name=theater_name)
    return {"status": "ok", "theater": theater_name}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Connection limit check
    if len(clients) >= MAX_WS_CONNECTIONS:
        await websocket.accept()
        await websocket.close(code=1013, reason="Maximum connections reached")
        logger.warning("ws_connection_rejected", reason="max_connections", current=len(clients))
        return

    await websocket.accept()

    # Wait for the first message to identify the client
    try:
        ident_msg = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
        ident_payload = json.loads(ident_msg)
        if ident_payload.get("type") == "IDENTIFY":
            client_type = ident_payload.get("client_type", "DASHBOARD")
            clients[websocket] = {"type": client_type}
            logger.info("client_identified", client_type=client_type)
        else:
            # Fallback for older clients or immediate data
            clients[websocket] = {"type": "DASHBOARD"}
            await handle_payload(ident_payload, websocket, ident_msg)
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect) as exc:
        clients[websocket] = {"type": "DASHBOARD"}
        logger.warning("client_identification_failed", error=str(exc), fallback="DASHBOARD")

    try:
        while True:
            data = await websocket.receive_text()

            # Rate limiting
            client_info = clients.get(websocket)
            if client_info and not _check_rate_limit(client_info):
                logger.warning("ws_rate_limit_exceeded", client_type=client_info.get("type"))
                await _send_error(websocket, "Rate limit exceeded, message dropped")
                continue

            try:
                payload = json.loads(data)
            except json.JSONDecodeError as exc:
                logger.warning("ws_invalid_json", error=str(exc))
                await _send_error(websocket, "Invalid JSON payload")
                continue

            await handle_payload(payload, websocket, data)
    except WebSocketDisconnect:
        logger.info("client_disconnected")
    except (ConnectionError, OSError) as exc:
        logger.error("websocket_error", error=str(exc))
    finally:
        if websocket in clients:
            del clients[websocket]

async def _handle_sitrep_query(query_text: str, websocket: WebSocket) -> None:
    """
    Generate a SITREP using the SynthesisQueryAgent (heuristic fallback when
    no LLM is available) and reply directly to the requesting client.
    """
    state = sim.get_state()
    targets = state.get("targets", [])
    strike_board = hitl.get_strike_board()

    # Build a heuristic narrative without calling the LLM
    detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
    pending_hitl = [e for e in strike_board if e.get("status") == "PENDING"]

    if detected:
        threat_lines = [
            f"{t['type']} at ({t.get('lat', 0):.4f}, {t.get('lon', 0):.4f})"
            for t in detected[:5]
        ]
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
        recommended_actions.append(
            f"Review {len(pending_hitl)} pending strike board nomination(s)."
        )
    if not detected:
        recommended_actions.append("Continue ISR coverage.")

    response_payload = {
        "type": "SITREP_RESPONSE",
        "sitrep_narrative": narrative,
        "key_threats": key_threats,
        "recommended_actions": recommended_actions,
        "data_sources_consulted": ["sim_engine", "hitl_strike_board"],
        "confidence": 0.7 if detected else 0.9,
        "query": query_text,
    }

    try:
        await websocket.send_text(json.dumps(response_payload))
    except (WebSocketDisconnect, ConnectionError, OSError) as exc:
        logger.warning("sitrep_reply_failed", error=str(exc))


async def _handle_retask_sensors(payload: dict, websocket: WebSocket) -> None:
    """
    Handle a retask_sensors request. Expects payload keys:
      - target_id: int
      - target_type: str  (e.g. "SAM", "TEL")
      - lat / lon: floats
      - confidence: float (0.0–1.0)

    Calls ai_tasking_manager.evaluate_and_retask() with an empty asset list
    (no live sensor registry in sim mode); returns the tasking output to
    the requesting client.
    """
    try:
        detection = Detection(
            source=SensorSource.UAV,
            lat=float(payload.get("lat", 0.0)),
            lon=float(payload.get("lon", 0.0)),
            confidence=float(payload.get("confidence", 0.5)),
            classification=TargetClassification(
                payload.get("target_type", "Unknown")
                if payload.get("target_type") in TargetClassification._value2member_map_
                else "Unknown"
            ),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = ai_tasking_manager.evaluate_and_retask(detection, available_assets=[])
        response = {
            "type": "RETASK_RESPONSE",
            "tasking_orders": [o.model_dump(mode="json") for o in result.tasking_orders],
            "confidence_gap": result.confidence_gap,
            "reasoning": result.reasoning,
        }
    except Exception as exc:
        logger.error("retask_sensors_failed", error=str(exc))
        response = {"type": "RETASK_RESPONSE", "error": str(exc)}

    try:
        await websocket.send_text(json.dumps(response))
    except (WebSocketDisconnect, ConnectionError, OSError) as exc:
        logger.warning("retask_reply_failed", error=str(exc))


async def handle_payload(payload: dict, websocket: WebSocket, raw_data: str):
    """Handle incoming payloads based on type/action."""
    action = payload.get("action")
    p_type = payload.get("type")

    # Validate payload against schema if action has one
    if action in _ACTION_SCHEMAS:
        error = _validate_payload(payload, _ACTION_SCHEMAS[action])
        if error:
            logger.warning("ws_payload_validation_failed", action=action, error=error)
            await _send_error(websocket, error, action)
            return

    if action == "spike":
        sim.trigger_demand_spike(payload["lon"], payload["lat"])

    elif action == "move_drone":
        sim.command_move(payload["drone_id"], payload["target_lon"], payload["target_lat"])

    elif action == "SET_SCENARIO":
        # Forward command to SIMULATORS
        await broadcast(raw_data, target_type="SIMULATOR", sender=websocket)

    elif p_type in ["DRONE_FEED", "TRACK_UPDATE", "TRACK_UPDATE_BATCH"]:
        # Forward vision/track data to DASHBOARDs
        await broadcast(raw_data, target_type="DASHBOARD", sender=websocket)

    elif action == "follow_target":
        sim.command_follow(payload["drone_id"], payload["target_id"])
        log_event("command", {"action": "follow_target", "drone_id": payload["drone_id"], "target_id": payload["target_id"]})

    elif action == "paint_target":
        sim.command_paint(payload["drone_id"], payload["target_id"])
        log_event("command", {"action": "paint_target", "drone_id": payload["drone_id"], "target_id": payload["target_id"]})

    elif action == "intercept_target":
        sim.command_intercept(payload["drone_id"], payload["target_id"])
        log_event("command", {"action": "intercept_target", "drone_id": payload["drone_id"], "target_id": payload["target_id"]})

    elif action in ("cancel_track", "scan_area"):
        sim.cancel_track(payload["drone_id"])
        log_event("command", {"action": action, "drone_id": payload["drone_id"]})

    elif action == "approve_nomination":
        rationale = payload.get("rationale", "")
        try:
            hitl.approve_nomination(payload["entry_id"], rationale)
            log_event("nomination", {"action": "approved", "entry_id": payload["entry_id"]})
            response = json.dumps({"type": "HITL_UPDATE", "action": "approved", "entry": hitl.get_strike_board()})
            await broadcast(response, target_type="DASHBOARD")
        except ValueError as exc:
            logger.warning("approve_nomination_failed", error=str(exc))

    elif action == "reject_nomination":
        rationale = payload.get("rationale", "")
        try:
            hitl.reject_nomination(payload["entry_id"], rationale)
            response = json.dumps({"type": "HITL_UPDATE", "action": "rejected", "entry": hitl.get_strike_board()})
            await broadcast(response, target_type="DASHBOARD")
        except ValueError as exc:
            logger.warning("reject_nomination_failed", error=str(exc))

    elif action == "retask_nomination":
        rationale = payload.get("rationale", "")
        try:
            hitl.retask_nomination(payload["entry_id"], rationale)
            response = json.dumps({"type": "HITL_UPDATE", "action": "retasked", "entry": hitl.get_strike_board()})
            await broadcast(response, target_type="DASHBOARD")
        except ValueError as exc:
            logger.warning("retask_nomination_failed", error=str(exc))

    elif action == "authorize_coa":
        rationale = payload.get("rationale", "")
        try:
            hitl.authorize_coa(payload["entry_id"], payload["coa_id"], rationale)
            log_event("engagement", {"action": "coa_authorized", "entry_id": payload["entry_id"], "coa_id": payload["coa_id"]})
            response = json.dumps({
                "type": "HITL_UPDATE",
                "action": "coa_authorized",
                "entry_id": payload["entry_id"],
                "coas": hitl.get_coas_for_entry(payload["entry_id"]),
            })
            await broadcast(response, target_type="DASHBOARD")
        except ValueError as exc:
            logger.warning("authorize_coa_failed", error=str(exc))

    elif action == "reject_coa":
        rationale = payload.get("rationale", "")
        try:
            hitl.reject_coa(payload["entry_id"], rationale)
            response = json.dumps({
                "type": "HITL_UPDATE",
                "action": "coas_rejected",
                "entry_id": payload["entry_id"],
                "coas": hitl.get_coas_for_entry(payload["entry_id"]),
            })
            await broadcast(response, target_type="DASHBOARD")
        except ValueError as exc:
            logger.warning("reject_coa_failed", error=str(exc))

    elif action in ("sitrep_query", "generate_sitrep") or p_type == "SITREP_QUERY":
        query_text = payload.get("query", "Provide current situation report.")
        if not isinstance(query_text, str):
            await _send_error(websocket, "Field 'query' must be str", action or "sitrep_query")
            return
        await _handle_sitrep_query(query_text, websocket)

    elif action == "retask_sensors":
        await _handle_retask_sensors(payload, websocket)

    elif action == "reset":
        sim.reset_queues()
        logger.info("grid_state_reset")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
