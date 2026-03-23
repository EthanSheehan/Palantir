"""Event-based WebSocket endpoint /ws/events.

On connect: sends initial state snapshot.
Then forwards all EventBus events to connected clients.
Also accepts legacy actions (spike, move_drone, reset) for backward compatibility.
"""
from __future__ import annotations
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..dependencies import ctx
from ..domain.models import DomainEvent, Command
from ..domain.enums import CommandType, CommandTargetType

logger = logging.getLogger(__name__)
router = APIRouter()

_event_clients: set[WebSocket] = set()


async def _broadcast_event(event: DomainEvent):
    """EventBus handler: forward to all connected event WebSocket clients."""
    if not _event_clients:
        return
    msg = json.dumps(event.model_dump())
    dead = set()
    for ws in _event_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _event_clients.difference_update(dead)


def setup_event_broadcast():
    """Subscribe to all events on the bus and forward to WebSocket clients."""
    ctx.bus.subscribe("*", _broadcast_event)


@router.websocket("/ws/events")
async def websocket_events(ws: WebSocket):
    await ws.accept()
    _event_clients.add(ws)
    logger.info("Event WebSocket client connected (%d total)", len(_event_clients))

    # Send initial state snapshot
    try:
        assets = ctx.asset_service.list_assets()
        await ws.send_text(json.dumps({
            "type": "connection.established",
            "payload": {
                "asset_count": len(assets),
                "assets": [a.model_dump() for a in assets],
            },
        }))
    except Exception:
        logger.exception("Failed to send initial snapshot")

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action")

                if action == "spike":
                    # Legacy: trigger demand spike via sim
                    from ..dependencies import ctx as _ctx
                    if _ctx.adapter and hasattr(_ctx.adapter, 'sim'):
                        _ctx.adapter.sim.trigger_demand_spike(
                            msg.get("lon", 0), msg.get("lat", 0)
                        )

                elif action == "move_drone":
                    # Convert to command
                    cmd = Command(
                        type=CommandType.move_to,
                        target_type=CommandTargetType.asset,
                        target_id=str(msg.get("drone_id", "")),
                        payload={
                            "destination": {
                                "lon": msg.get("target_lon", 0),
                                "lat": msg.get("target_lat", 0),
                                "alt_m": msg.get("target_alt", 2000.0),
                            }
                        },
                    )
                    await ctx.command_service.create_command(cmd)

                elif action == "reset":
                    if _ctx.adapter and hasattr(_ctx.adapter, 'sim'):
                        _ctx.adapter.sim.reset_queues()

                elif action == "launch_drone":
                    from ..dependencies import ctx as _ctx
                    launcher_id = msg.get("launcher_id", 0)
                    if _ctx.adapter and hasattr(_ctx.adapter, 'sim'):
                        uav = _ctx.adapter.sim.launch_drone(launcher_id)
                        if uav:
                            # Dynamically register the new drone as an asset
                            from ..domain.models import Asset, Position
                            from ..domain.enums import AssetStatus, AssetMode
                            asset = Asset(
                                id=f"uav_{uav.id}",
                                name=f"UAV-{uav.id:02d}",
                                type="quadrotor",
                                status=AssetStatus.idle,
                                mode=AssetMode.simulated,
                                position=Position(lon=uav.x, lat=uav.y, alt_m=0.0),
                                home_location=Position(lon=uav.x, lat=uav.y, alt_m=0.0),
                                capabilities=["camera_rgb", "camera_ir"],
                            )
                            import asyncio
                            asyncio.create_task(ctx.asset_service.register_asset(asset))
                            logger.info("Launched drone uav_%d from launcher_%d", uav.id, launcher_id)

                elif action == "subscribe":
                    pass  # Future: channel-based subscription

                elif action == "unsubscribe":
                    pass  # Future

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        _event_clients.discard(ws)
        logger.info("Event WebSocket client disconnected (%d remaining)", len(_event_clients))
