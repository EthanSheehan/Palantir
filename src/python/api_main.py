"""Palantir C2 — FastAPI entry point (slim orchestrator).

All heavy logic lives in extracted modules:
  - websocket_handlers.py — command dispatch table, action handlers
  - simulation_loop.py   — 10Hz simulation tick, sensor feed broadcast
  - autopilot.py          — demo auto-pilot loop
  - tactical_assistant.py — TacticalAssistant + ISR pipeline
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
import time
from contextlib import asynccontextmanager

import structlog
import uvicorn
from agents.ai_tasking_manager import AITaskingManagerAgent
from agents.battlespace_manager import BattlespaceManagerAgent
from agents.isr_observer import ISRObserverAgent
from agents.strategy_analyst import StrategyAnalystAgent
from agents.synthesis_query_agent import SynthesisQueryAgent
from agents.tactical_planner import TacticalPlannerAgent
from battlespace_assessment import BattlespaceAssessor
from config import load_settings
from event_logger import rotate_logs
from event_logger import start_logger as start_event_logger
from event_logger import stop_logger as stop_event_logger
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from hitl_manager import HITLManager
from intel_feed import IntelFeedRouter, _client_subscribed
from llm_adapter import LLMAdapter
from logging_config import configure_logging
from sim_engine import SimulationModel
from simulation_loop import SimulationLoopState, sensor_feed_loop, simulation_loop
from tactical_assistant import TacticalAssistant
from websocket_handlers import (
    HandlerContext,
    _send_error,
)
from websocket_handlers import (
    handle_payload as _ws_handle_payload,
)

configure_logging()
logger = structlog.get_logger()

settings = load_settings()
assessor = BattlespaceAssessor()

# ---------------------------------------------------------------------------
# WebSocket hardening constants
# ---------------------------------------------------------------------------
MAX_WS_CONNECTIONS = 20
RATE_LIMIT_MAX_MESSAGES = 30  # per second
RATE_LIMIT_WINDOW = 1.0  # seconds
MAX_WS_MESSAGE_SIZE = 65536  # 64KB

# ---------------------------------------------------------------------------
# Agent instantiation (heuristic mode)
# ---------------------------------------------------------------------------
llm_adapter = LLMAdapter()
isr_observer = ISRObserverAgent()
strategy_analyst = StrategyAnalystAgent()
tactical_planner = TacticalPlannerAgent()
ai_tasking_manager = AITaskingManagerAgent(llm_client=None)
battlespace_manager = BattlespaceManagerAgent(llm_client=None)
synthesis_query = SynthesisQueryAgent(llm_client=None)

# ---------------------------------------------------------------------------
# Shared mutable state
# ---------------------------------------------------------------------------
sim = SimulationModel(theater_name=settings.default_theater)
sim.demo_fast = settings.demo_mode
hitl = HITLManager()
clients: dict = {}  # websocket -> info dict
assistant = TacticalAssistant()

# Simulation loop state — exposed at module level for backward compat with tests
_loop_state = SimulationLoopState()
_prev_target_states: dict[int, str] = _loop_state.prev_target_states
_last_assessment_time: float = 0.0
_cached_assessment: dict | None = None
_cached_isr_queue: list | None = None

_get_demo_effectors = None
if settings.demo_mode:
    from mission_data.asset_registry import get_available_effectors as _get_demo_effectors


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


async def broadcast(message: str, target_type: str = None, sender: WebSocket = None, feed: str = None):
    """Parallel broadcast to all matching clients with a strict timeout."""
    if not clients:
        return

    targets = []
    for ws, info in clients.items():
        if ws == sender:
            continue
        if target_type and info.get("type") != target_type:
            continue
        if feed is not None:
            if not _client_subscribed(info, feed):
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

    results = await asyncio.gather(*[_send(t) for t in targets])

    for failed_ws in results:
        if failed_ws and failed_ws in clients:
            clients.pop(failed_ws, None)


intel_router = IntelFeedRouter(broadcast_fn=broadcast, max_history=200)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def _check_rate_limit(client_info: dict) -> bool:
    """Return True if within rate limits, False if exceeded."""
    now = time.monotonic()
    timestamps = client_info.setdefault("msg_timestamps", collections.deque())
    while timestamps and timestamps[0] < now - RATE_LIMIT_WINDOW:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_MAX_MESSAGES:
        return False
    timestamps.append(now)
    return True


# ---------------------------------------------------------------------------
# SITREP helpers (shared by REST and WS)
# ---------------------------------------------------------------------------


def _build_sitrep_payload(query_text: str = "") -> dict:
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
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_event_logger()
    rotate_logs(max_days=7)

    sim_task = asyncio.create_task(
        simulation_loop(
            sim=sim,
            hitl=hitl,
            assistant=assistant,
            assessor=assessor,
            intel_router=intel_router,
            broadcast_fn=broadcast,
            clients=clients,
            settings=settings,
            loop_state=_loop_state,
        )
    )
    sensor_task = asyncio.create_task(sensor_feed_loop(sim=sim, intel_router=intel_router, clients=clients))
    demo_task = None
    if settings.demo_mode:
        from autopilot import demo_autopilot

        demo_task = asyncio.create_task(
            demo_autopilot(
                sim=sim,
                hitl=hitl,
                broadcast_fn=broadcast,
                clients=clients,
                intel_router=intel_router,
                tactical_planner=tactical_planner,
                get_effectors=_get_demo_effectors,
            )
        )
    yield
    sim_task.cancel()
    sensor_task.cancel()
    if demo_task:
        demo_task.cancel()
    for t in [sim_task, sensor_task] + ([demo_task] if demo_task else []):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await stop_event_logger()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.post("/api/sitrep")
async def post_sitrep(body: dict):
    query_text = body.get("query", "Provide current situation report.")
    return _build_sitrep_payload(query_text)


@app.post("/api/environment")
async def set_environment(body: dict):
    time_of_day = body.get("time_of_day", 12.0)
    cloud_cover = body.get("cloud_cover", 0.0)
    precipitation = body.get("precipitation", 0.0)
    sim.set_environment(time_of_day, cloud_cover, precipitation)
    return {
        "status": "ok",
        "environment": {"time_of_day": time_of_day, "cloud_cover": cloud_cover, "precipitation": precipitation},
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "sim_initialized": sim is not None}


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

    # Preserve autonomy level across theater switch
    prev_autonomy = sim.autonomy_level
    sim = SimulationModel(theater_name=theater_name)

    if prev_autonomy != "MANUAL":
        logging.getLogger("api_main").warning(
            "Restoring autonomy level %s after theater switch to %s",
            prev_autonomy,
            theater_name,
        )
    sim.autonomy_level = prev_autonomy

    return {"status": "ok", "theater": theater_name}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if len(clients) >= MAX_WS_CONNECTIONS:
        await websocket.accept()
        await websocket.close(code=1013, reason="Maximum connections reached")
        logger.warning("ws_connection_rejected", reason="max_connections", current=len(clients))
        return

    await websocket.accept()

    try:
        ident_msg = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
        if len(ident_msg) > MAX_WS_MESSAGE_SIZE:
            logger.warning("ident_message_too_large", size=len(ident_msg))
            await websocket.close(code=1009)
            return
        ident_payload = json.loads(ident_msg)
        if ident_payload.get("type") == "IDENTIFY":
            raw_type = ident_payload.get("client_type", "DASHBOARD")
            client_type = raw_type if raw_type in ("DASHBOARD", "SIMULATOR") else "DASHBOARD"
            clients[websocket] = {"type": client_type}
            logger.info("client_identified", client_type=client_type)
        else:
            clients[websocket] = {"type": "DASHBOARD"}
            ctx = _build_handler_context(websocket, ident_msg)
            await _ws_handle_payload(ident_payload, websocket, ident_msg, ctx)
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect) as exc:
        clients[websocket] = {"type": "DASHBOARD"}
        logger.warning("client_identification_failed", error=str(exc), fallback="DASHBOARD")

    try:
        while True:
            data = await websocket.receive_text()

            if len(data) > MAX_WS_MESSAGE_SIZE:
                logger.warning("ws_message_too_large", size=len(data), limit=MAX_WS_MESSAGE_SIZE)
                await _send_error(websocket, f"Message exceeds {MAX_WS_MESSAGE_SIZE // 1024}KB limit")
                continue

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

            ctx = _build_handler_context(websocket, data)
            await _ws_handle_payload(payload, websocket, data, ctx)
    except WebSocketDisconnect:
        logger.info("client_disconnected")
    except (ConnectionError, OSError) as exc:
        logger.error("websocket_error", error=str(exc))
    finally:
        if websocket in clients:
            del clients[websocket]


def _build_handler_context(websocket: WebSocket, raw_data: str) -> HandlerContext:
    """Create a HandlerContext with current module-level dependencies."""
    return HandlerContext(
        sim=sim,
        hitl=hitl,
        intel_router=intel_router,
        broadcast=broadcast,
        clients=clients,
        ai_tasking_manager=ai_tasking_manager,
        raw_data=raw_data,
    )


async def handle_payload(payload: dict, websocket: WebSocket, raw_data: str, ctx: HandlerContext = None):
    """Backward-compatible wrapper — auto-builds ctx from module globals when not provided."""
    if ctx is None:
        ctx = _build_handler_context(websocket, raw_data)
    await _ws_handle_payload(payload, websocket, raw_data, ctx)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
