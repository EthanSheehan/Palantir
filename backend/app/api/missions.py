from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from ..dependencies import ctx
from ..domain.models import Mission, MissionConstraints
from ..domain.enums import MissionType, Priority
from ..domain.state_machines import InvalidTransitionError

router = APIRouter(prefix="/missions", tags=["missions"])


class CreateMissionRequest(BaseModel):
    name: str = ""
    type: str = "custom"
    priority: str = "normal"
    objective: str = ""
    constraints: dict = {}
    tags: list[str] = []


class ApproveRequest(BaseModel):
    approved_by: str = "operator"


@router.get("")
def list_missions(
    state: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    mission_type: Optional[str] = Query(None, alias="type"),
    asset_id: Optional[str] = Query(None),
):
    missions = ctx.mission_service.list_missions(
        state=state, priority=priority,
        mission_type=mission_type, asset_id=asset_id,
    )
    return {"missions": [m.model_dump() for m in missions], "count": len(missions)}


@router.get("/{mission_id}")
def get_mission(mission_id: str):
    mission = ctx.mission_service.get_mission(mission_id)
    if not mission:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return mission.model_dump()


@router.post("")
async def create_mission(req: CreateMissionRequest):
    mission = Mission(
        name=req.name,
        type=MissionType(req.type) if req.type in MissionType.__members__ else MissionType.custom,
        priority=Priority(req.priority) if req.priority in Priority.__members__ else Priority.normal,
        objective=req.objective,
        constraints=MissionConstraints(**req.constraints) if req.constraints else MissionConstraints(),
        tags=req.tags,
    )
    result = await ctx.mission_service.create_mission(mission)
    return result.model_dump()


@router.post("/{mission_id}/propose")
async def propose_mission(mission_id: str):
    try:
        result = await ctx.mission_service.propose(mission_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/approve")
async def approve_mission(mission_id: str, req: ApproveRequest = ApproveRequest()):
    try:
        result = await ctx.mission_service.approve(mission_id, req.approved_by)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/pause")
async def pause_mission(mission_id: str):
    try:
        result = await ctx.mission_service.pause(mission_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/resume")
async def resume_mission(mission_id: str):
    try:
        result = await ctx.mission_service.resume(mission_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/abort")
async def abort_mission(mission_id: str):
    try:
        result = await ctx.mission_service.abort(mission_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{mission_id}/archive")
async def archive_mission(mission_id: str):
    try:
        result = await ctx.mission_service.archive(mission_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))
