import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os

# Add parent dir to path so we can import romania_grid
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import SimulationModel

# ── New app layer imports ──
from app.persistence.database import init_db
from app.dependencies import ctx
from app.adapters.simulator_adapter import SimulatorAdapter
from app.api.router import api_router
from app.api.ws import router as ws_router, setup_event_broadcast
from app.domain.models import Asset, Position, Velocity, _now
from app.domain.enums import AssetStatus, AssetMode
from app.config import TELEMETRY_PERSIST_INTERVAL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AMS Mission Operations Platform", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check (used by start.py to wait for readiness) ──
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ── Mount new API and WebSocket routers ──
app.include_router(api_router)
app.include_router(ws_router)

# ── Existing simulation ──
sim = SimulationModel()
clients = set()  # Legacy WebSocket clients

# ── Adapter ──
adapter = SimulatorAdapter(sim)


async def simulation_loop():
    """10Hz simulation loop — ticks sim and broadcasts to legacy WS clients."""
    logger.info("Starting simulation loop at 10Hz")
    while True:
        sim.tick()
        if clients:
            state = sim.get_state()
            state_json = json.dumps({"type": "state", "data": state})

            disconnected = set()
            for client in list(clients):
                try:
                    await client.send_text(state_json)
                except Exception:
                    disconnected.add(client)

            for client in disconnected:
                clients.discard(client)

        await asyncio.sleep(0.1)


async def _do_telemetry_batch(tick_count, persist):
    """Single telemetry batch — runs as a detached task to avoid blocking sim loop."""
    try:
        updates = adapter.fetch_asset_updates()
        for update in updates:
            await ctx.asset_service.update_telemetry(
                asset_id=update.asset_id,
                position=Position(lon=update.lon, lat=update.lat, alt_m=update.alt_m),
                velocity=Velocity(vx_mps=update.vx_mps, vy_mps=update.vy_mps, vz_mps=update.vz_mps),
                heading_deg=update.heading_deg,
                pitch_deg=update.pitch_deg,
                roll_deg=update.roll_deg,
                battery_pct=update.battery_pct,
                link_quality=update.link_quality,
                persist_to_log=persist,
            )
            # Yield after each asset so sim loop can interleave
            await asyncio.sleep(0)

        completed_cmds = adapter.check_completions()
        for cmd_id in completed_cmds:
            try:
                await ctx.command_service.handle_completion(cmd_id)
            except Exception:
                pass

        if ctx.macrogrid_service and hasattr(sim, 'active_flows'):
            await ctx.macrogrid_service.process_dispatches(sim.active_flows)

    except Exception:
        logger.exception("Error in telemetry ingestion")


async def telemetry_ingestion_loop():
    """Reads telemetry from SimulatorAdapter and feeds into AssetService at 1Hz."""
    tick_count = 0
    logger.info("Starting telemetry ingestion loop at 1Hz")
    while True:
        tick_count += 1
        persist = (tick_count % TELEMETRY_PERSIST_INTERVAL == 0)
        # Fire-and-forget so it doesn't block the simulation broadcast loop
        asyncio.create_task(_do_telemetry_batch(tick_count, persist))
        await asyncio.sleep(1.0)


async def register_initial_assets():
    """Register all sim UAVs as canonical assets on first startup."""
    existing = ctx.asset_service.list_assets()
    existing_ids = {a.id for a in existing}

    for uav in sim.uavs:
        asset_id = f"uav_{uav.id}"
        if asset_id not in existing_ids:
            asset = Asset(
                id=asset_id,
                name=f"UAV-{uav.id:02d}",
                type="quadrotor",
                status=AssetStatus.idle,
                mode=AssetMode.simulated,
                position=Position(lon=uav.x, lat=uav.y, alt_m=2000.0),
                home_location=Position(lon=uav.x, lat=uav.y, alt_m=0.0),
                capabilities=["camera_rgb", "camera_ir"],
            )
            await ctx.asset_service.register_asset(asset)
            logger.info("Registered asset %s", asset_id)

    for launcher in sim.launchers:
        asset_id = f"launcher_{launcher.id}"
        if asset_id not in existing_ids:
            asset = Asset(
                id=asset_id,
                name=f"Launcher-{launcher.id:02d}",
                type="launcher",
                status=AssetStatus.idle,
                mode=AssetMode.simulated,
                position=Position(lon=launcher.x, lat=launcher.y, alt_m=0.0),
                home_location=Position(lon=launcher.x, lat=launcher.y, alt_m=0.0),
                capabilities=["missile_launch"],
            )
            await ctx.asset_service.register_asset(asset)
            logger.info("Registered launcher asset %s", asset_id)


@app.on_event("startup")
async def startup_event():
    # Initialize database
    init_db()

    # Initialize application context
    ctx.init(adapter=adapter, grid=sim.grid)

    # Setup event broadcast to WebSocket clients
    setup_event_broadcast()

    # Setup alert auto-generation subscriptions
    await ctx.alert_service.setup_subscriptions()

    # Register initial assets
    await register_initial_assets()

    # Start background loops
    asyncio.create_task(simulation_loop())
    asyncio.create_task(telemetry_ingestion_loop())

    logger.info("AMS platform started — API at /api/v1, events at /ws/events, legacy at /ws/stream")


# ── Legacy WebSocket (unchanged) ──
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "spike":
                lon = payload.get("lon")
                lat = payload.get("lat")
                if lon is not None and lat is not None:
                    sim.trigger_demand_spike(lon, lat)

            elif payload.get("action") == "move_drone":
                drone_id = payload.get("drone_id")
                lon = payload.get("target_lon")
                lat = payload.get("target_lat")
                alt = payload.get("target_alt")
                if drone_id is not None and lon is not None and lat is not None:
                    sim.command_move(drone_id, lon, lat, alt)

            elif payload.get("action") == "reset":
                sim.reset_queues()

    except WebSocketDisconnect:
        clients.discard(websocket)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8012)
