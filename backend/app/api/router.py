from fastapi import APIRouter

from . import assets, missions, tasks, commands, timeline, alerts, macrogrid, events
from . import targets as targets_api, aimpoints as aimpoints_api

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(assets.router)
api_router.include_router(missions.router)
api_router.include_router(tasks.router)
api_router.include_router(commands.router)
api_router.include_router(timeline.router)
api_router.include_router(alerts.router)
api_router.include_router(macrogrid.router)
api_router.include_router(events.router)
api_router.include_router(targets_api.router)
api_router.include_router(aimpoints_api.router)
