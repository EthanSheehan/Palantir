from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..dependencies import ctx
from ..domain.models import Aimpoint, Target
from ..domain.enums import AimpointType

router = APIRouter(prefix="/targets", tags=["targets"])


class CreateTargetRequest(BaseModel):
    name: str = ""
    description: str = ""
    aimpoint_ids: list[str] = []


class UpdateTargetRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None


@router.get("")
def list_targets(
    state: Optional[str] = Query(None),
    tgt_type: Optional[str] = Query(None, alias="type"),
):
    targets = ctx.target_service.list_targets(state=state, tgt_type=tgt_type)
    return {"targets": [t.model_dump() for t in targets], "count": len(targets)}


@router.post("")
async def create_target(req: CreateTargetRequest):
    tgt_type = "multi-aim" if len(req.aimpoint_ids) > 1 else "single"
    target = Target(
        name=req.name,
        type=tgt_type,
        description=req.description,
        aimpoint_ids=req.aimpoint_ids,
    )
    result = await ctx.target_service.create_target(target)
    return result.model_dump()


@router.get("/{target_id}")
def get_target(target_id: str):
    result = ctx.target_service.get_target_with_aimpoints(target_id)
    if not result:
        raise HTTPException(404, f"Target {target_id} not found")
    return result


@router.put("/{target_id}")
async def update_target(target_id: str, req: UpdateTargetRequest):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    try:
        result = await ctx.target_service.update_target(target_id, **fields)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result.model_dump()


@router.delete("/{target_id}")
async def delete_target(target_id: str):
    try:
        await ctx.target_service.delete_target(target_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@router.post("/{target_id}/aimpoints")
async def add_aimpoint_to_target(target_id: str, aimpoint_id: str = Query(...)):
    try:
        result = await ctx.target_service.add_aimpoint_to_target(target_id, aimpoint_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result.model_dump()


@router.delete("/{target_id}/aimpoints/{aimpoint_id}")
async def remove_aimpoint_from_target(target_id: str, aimpoint_id: str):
    try:
        result = await ctx.target_service.remove_aimpoint_from_target(target_id, aimpoint_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result.model_dump()
