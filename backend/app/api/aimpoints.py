from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..dependencies import ctx
from ..domain.models import Aimpoint
from ..domain.enums import AimpointType

router = APIRouter(prefix="/aimpoints", tags=["aimpoints"])


class CreateAimpointRequest(BaseModel):
    lon: float
    lat: float
    type: str = "unknown"
    description: str = ""


class UpdateAimpointRequest(BaseModel):
    lon: Optional[float] = None
    lat: Optional[float] = None
    type: Optional[str] = None
    description: Optional[str] = None


@router.get("")
def list_aimpoints(
    target_id: Optional[str] = Query(None),
    apt_type: Optional[str] = Query(None, alias="type"),
):
    aimpoints = ctx.target_service.list_aimpoints(target_id=target_id, apt_type=apt_type)
    return {"aimpoints": [a.model_dump() for a in aimpoints], "count": len(aimpoints)}


@router.post("")
async def create_aimpoint(req: CreateAimpointRequest):
    apt = Aimpoint(
        lon=req.lon,
        lat=req.lat,
        type=AimpointType(req.type) if req.type in AimpointType.__members__ else AimpointType.unknown,
        description=req.description,
    )
    result = await ctx.target_service.create_aimpoint(apt)
    return result.model_dump()


@router.get("/{aimpoint_id}")
def get_aimpoint(aimpoint_id: str):
    apt = ctx.target_service.get_aimpoint(aimpoint_id)
    if not apt:
        raise HTTPException(404, f"Aimpoint {aimpoint_id} not found")
    return apt.model_dump()


@router.put("/{aimpoint_id}")
async def update_aimpoint(aimpoint_id: str, req: UpdateAimpointRequest):
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if "type" in fields:
        try:
            fields["type"] = AimpointType(fields["type"])
        except ValueError:
            fields["type"] = AimpointType.unknown
    if not fields:
        raise HTTPException(400, "No fields to update")
    try:
        result = await ctx.target_service.update_aimpoint(aimpoint_id, **fields)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return result.model_dump()


@router.delete("/{aimpoint_id}")
async def delete_aimpoint(aimpoint_id: str):
    try:
        await ctx.target_service.delete_aimpoint(aimpoint_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}
