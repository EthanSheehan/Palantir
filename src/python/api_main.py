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
from typing import Optional

import structlog
import uvicorn
from aar_engine import AAREngine
from agents.ai_tasking_manager import AITaskingManagerAgent
from agents.battlespace_manager import BattlespaceManagerAgent
from agents.isr_observer import ISRObserverAgent
from agents.strategy_analyst import StrategyAnalystAgent
from agents.synthesis_query_agent import SynthesisQueryAgent
from agents.tactical_planner import TacticalPlannerAgent
from audit_log import audit_log
from auth import AuthConfig, AuthManager, TokenTier, _split_csv
from battlespace_assessment import BattlespaceAssessor
from config import load_settings
from event_logger import rotate_logs
from event_logger import start_logger as start_event_logger
from event_logger import stop_logger as stop_event_logger
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from hitl_manager import HITLManager
from intel_feed import IntelFeedRouter, _client_subscribed
from llm_adapter import LLMAdapter
from logging_config import configure_logging
from mission_store import MissionStore
from roe_engine import ROEEngine
from sim_engine import SimulationModel
from simulation_loop import SimulationLoopState, sensor_feed_loop, simulation_loop
from tactical_assistant import TacticalAssistant
from websocket_handlers import (
    HandlerContext,
    _send_error,
)
from websocket_handlers import (
    _build_sitrep_payload as _ws_build_sitrep_payload,
)
from websocket_handlers import (
    handle_payload as _ws_handle_payload,
)
import metrics as _metrics
from fastapi.responses import PlainTextResponse

configure_logging()
logger = structlog.get_logger()

settings = load_settings()
assessor = BattlespaceAssessor()

# ---------------------------------------------------------------------------
# Auth (W3-006)
# ---------------------------------------------------------------------------
_auth_tokens: dict[str, TokenTier] = {}
for _tok in _split_csv(settings.dashboard_tokens):
    _auth_tokens[_tok] = TokenTier.DASHBOARD
for _tok in _split_csv(settings.simulator_tokens):
    _auth_tokens[_tok] = TokenTier.SIMULATOR
for _tok in _split_csv(getattr(settings, "admin_tokens", "")):
    _auth_tokens[_tok] = TokenTier.ADMIN
auth_manager = AuthManager(
    AuthConfig(
        enabled=settings.auth_enabled,
        tokens=_auth_tokens,
        demo_token=settings.demo_token,
    )
)

# ---------------------------------------------------------------------------
# WebSocket hardening constants
# ---------------------------------------------------------------------------
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}
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
mission_store = MissionStore()
aar_engine = AAREngine(mission_store, audit_log)

# ROE engine — load theater-specific rules if available
import pathlib as _pathlib

_roe_path = (
    _pathlib.Path(__file__).resolve().parent.parent.parent / "theaters" / "roe" / f"{settings.default_theater}.yaml"
)
roe_engine: ROEEngine | None = ROEEngine.load_from_yaml(str(_roe_path)) if _roe_path.exists() else None

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
# Origin checking
# ---------------------------------------------------------------------------


def _is_origin_allowed(origin: str | None) -> bool:
    """Return True if the WebSocket Origin header is permitted.

    Localhost origins are always allowed (development mode).
    Non-localhost origins must appear in settings.allowed_origins.
    Missing origin header is treated as allowed (non-browser clients).
    """
    if origin is None:
        return True
    # Strip scheme to extract authority (host[:port])
    authority = origin
    for scheme in ("https://", "http://", "wss://", "ws://"):
        if authority.startswith(scheme):
            authority = authority[len(scheme):]
            break
    # Remove any path component
    authority = authority.split("/")[0]
    # IPv6 bracket notation: [::1]:port or [::1]
    if authority.startswith("["):
        host = authority[1:].split("]")[0]
    else:
        host = authority.split(":")[0]
    if host in _LOCALHOST_HOSTS:
        return True
    return origin in settings.allowed_origins


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
                roe_engine=roe_engine,
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
    return _ws_build_sitrep_payload(sim, hitl, query_text)


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


@app.get("/metrics")
async def get_metrics(request: Request):
    """Prometheus text exposition endpoint (format 0.0.4).

    Restricted to localhost to avoid leaking operational telemetry.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=403, detail="Metrics endpoint restricted to localhost")
    return PlainTextResponse(
        content=_metrics.generate_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/audit")
async def get_audit(
    action_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    autonomy_level: Optional[str] = None,
    target_id: Optional[int] = None,
):
    return audit_log.query(
        action_type=action_type,
        start_time=start_time,
        end_time=end_time,
        autonomy_level=autonomy_level,
        target_id=target_id,
    )


@app.get("/api/audit/verify")
async def get_audit_verify():
    return {"valid": audit_log.verify_chain(), "record_count": len(audit_log.to_json())}


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
# Mission persistence endpoints (W3-005)
# ---------------------------------------------------------------------------


@app.get("/api/missions")
async def list_missions():
    return {"missions": mission_store.list_missions()}


@app.post("/api/missions")
async def create_mission(body: dict):
    name = body.get("name")
    theater = body.get("theater")
    if not name or not theater:
        raise HTTPException(status_code=422, detail="Missing 'name' or 'theater' field")
    mid = mission_store.create_mission(name, theater)
    return {"mission_id": mid}


@app.get("/api/missions/{mission_id}")
async def get_mission(mission_id: int):
    mission = mission_store.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    summary = mission_store.get_mission_summary(mission_id)
    return {"mission": mission, "summary": summary}


@app.get("/api/missions/{mission_id}/targets/{target_id}")
async def get_target_history(mission_id: int, target_id: int):
    events = mission_store.get_target_history(mission_id, target_id)
    return {"events": events}


@app.get("/api/kill-chain")
async def get_kill_chain():
    """Return current F2T2EA kill chain phase breakdown."""
    if _loop_state.cached_kill_chain is not None:
        return _loop_state.cached_kill_chain
    # Compute fresh if no cached data yet
    from kill_chain_tracker import KillChainTracker

    tracker = KillChainTracker()
    state = sim.get_state()
    strike_board_data = hitl.get_strike_board()
    statuses = tracker.compute(
        targets=state.get("targets", []),
        drones=state.get("uavs", []),
        strike_board=strike_board_data,
    )
    return tracker.to_dict(statuses)


# ---------------------------------------------------------------------------
# AAR (After-Action Review) endpoints
# ---------------------------------------------------------------------------


@app.get("/api/aar/{mission_id}/timeline")
async def get_aar_timeline(mission_id: int):
    mission = mission_store.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    timeline = aar_engine.build_timeline(mission_id)
    return {
        "mission_id": timeline.mission_id,
        "phases": timeline.phases,
        "total_ticks": timeline.total_ticks,
        "duration_seconds": timeline.duration_seconds,
    }


@app.get("/api/aar/{mission_id}/report")
async def get_aar_report(mission_id: int):
    mission = mission_store.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    report = aar_engine.generate_report(mission_id)
    return {
        "mission_id": report.mission_id,
        "theater": report.theater,
        "duration_seconds": report.duration_seconds,
        "targets_detected": report.targets_detected,
        "targets_engaged": report.targets_engaged,
        "engagements_successful": report.engagements_successful,
        "operator_overrides": report.operator_overrides,
        "ai_acceptance_rate": report.ai_acceptance_rate,
        "phase_breakdown": report.phase_breakdown,
    }


@app.get("/api/aar/{mission_id}/replay")
async def get_aar_replay(
    mission_id: int,
    start: int = 0,
    end: Optional[int] = None,
    speed: int = 1,
):
    mission = mission_store.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    step = max(speed, 1)
    snapshots = aar_engine.get_snapshots(mission_id, start_tick=start, end_tick=end, step=step)
    return {
        "snapshots": [
            {
                "timestamp": s.timestamp,
                "tick": s.tick,
                "state_json": s.state_json,
                "decisions": s.decisions,
            }
            for s in snapshots
        ]
    }


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

    origin = websocket.headers.get("origin")
    if not _is_origin_allowed(origin):
        await websocket.close(code=4003, reason="Origin not allowed")
        logger.warning("ws_origin_rejected", origin=origin)
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

            # Auth check
            token = ident_payload.get("token")
            tier = auth_manager.authenticate(token)
            if auth_manager.config.enabled and tier is None:
                await _send_error(websocket, "Authentication failed: invalid or missing token")
                await websocket.close(code=4001, reason="Authentication failed")
                logger.warning("ws_auth_failed", client_type=client_type)
                return

            clients[websocket] = {"type": client_type, "tier": tier or TokenTier.DASHBOARD}
            logger.info("client_identified", client_type=client_type, tier=(tier or TokenTier.DASHBOARD).value)
        else:
            clients[websocket] = {"type": "DASHBOARD", "tier": TokenTier.DASHBOARD}
            ctx = _build_handler_context(websocket, ident_msg)
            await _ws_handle_payload(ident_payload, websocket, ident_msg, ctx)
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect) as exc:
        clients[websocket] = {"type": "DASHBOARD", "tier": TokenTier.DASHBOARD}
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

            # Auth check
            action = payload.get("action") or payload.get("type", "")
            client_tier = clients.get(websocket, {}).get("tier", TokenTier.DASHBOARD)
            if auth_manager.config.enabled and not auth_manager.is_authorized(client_tier, action):
                await _send_error(
                    websocket,
                    json.dumps(
                        {
                            "error": "unauthorized",
                            "action": action,
                            "required_tier": "DASHBOARD",
                        }
                    ),
                )
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
        roe_engine=roe_engine,
    )


async def handle_payload(payload: dict, websocket: WebSocket, raw_data: str, ctx: HandlerContext = None):
    """Backward-compatible wrapper — auto-builds ctx from module globals when not provided."""
    if ctx is None:
        ctx = _build_handler_context(websocket, raw_data)
    await _ws_handle_payload(payload, websocket, raw_data, ctx)


if __name__ == "__main__":
    ssl_kwargs = {}
    if settings.ssl_enabled:
        ssl_kwargs["ssl_certfile"] = settings.ssl_certfile
        ssl_kwargs["ssl_keyfile"] = settings.ssl_keyfile
    uvicorn.run(app, host=settings.host, port=settings.port, **ssl_kwargs)
