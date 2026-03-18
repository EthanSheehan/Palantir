from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from ..dependencies import ctx
from ..domain.models import Command
from ..domain.enums import CommandType, CommandTargetType
from ..domain.state_machines import InvalidTransitionError

router = APIRouter(prefix="/commands", tags=["commands"])


class CreateCommandRequest(BaseModel):
    type: str
    target_type: str = "asset"
    target_id: str
    payload: dict = {}
    created_by: str = "operator"


class ApproveCommandRequest(BaseModel):
    approved_by: str = "operator"


@router.get("")
def list_commands(
    state: Optional[str] = Query(None),
    cmd_type: Optional[str] = Query(None, alias="type"),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
):
    commands = ctx.command_service.list_commands(
        state=state, cmd_type=cmd_type,
        target_type=target_type, target_id=target_id,
    )
    return {"commands": [c.model_dump() for c in commands], "count": len(commands)}


@router.get("/{cmd_id}")
def get_command(cmd_id: str):
    cmd = ctx.command_service.get_command(cmd_id)
    if not cmd:
        raise HTTPException(404, f"Command {cmd_id} not found")
    return cmd.model_dump()


@router.post("")
async def create_command(req: CreateCommandRequest):
    cmd = Command(
        type=CommandType(req.type) if req.type in CommandType.__members__ else CommandType.move_to,
        target_type=CommandTargetType(req.target_type) if req.target_type in CommandTargetType.__members__ else CommandTargetType.asset,
        target_id=req.target_id,
        payload=req.payload,
        created_by=req.created_by,
    )
    try:
        result = await ctx.command_service.create_command(cmd)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{cmd_id}/approve")
async def approve_command(cmd_id: str, req: ApproveCommandRequest = ApproveCommandRequest()):
    try:
        result = await ctx.command_service.approve_command(cmd_id, req.approved_by)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{cmd_id}/cancel")
async def cancel_command(cmd_id: str):
    try:
        result = await ctx.command_service.cancel_command(cmd_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))
