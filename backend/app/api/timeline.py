from fastapi import APIRouter, Query
from typing import Optional
from ..dependencies import ctx

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("")
def list_reservations(
    asset_id: Optional[str] = Query(None),
    mission_id: Optional[str] = Query(None),
    start_after: Optional[str] = Query(None),
    end_before: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    reservations = ctx.timeline_service.list_reservations(
        asset_id=asset_id, mission_id=mission_id,
        start_after=start_after, end_before=end_before,
        status=status, source=source,
    )
    return {"reservations": [r.model_dump() for r in reservations], "count": len(reservations)}


@router.get("/conflicts")
async def list_conflicts():
    conflicts = await ctx.timeline_service.detect_conflicts()
    return {"conflicts": conflicts, "count": len(conflicts)}


@router.get("/{res_id}")
def get_reservation(res_id: str):
    from fastapi import HTTPException
    res = ctx.timeline_service.get_reservation(res_id)
    if not res:
        raise HTTPException(404, f"Reservation {res_id} not found")
    return res.model_dump()
