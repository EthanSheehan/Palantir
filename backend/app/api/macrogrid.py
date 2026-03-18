from fastapi import APIRouter, HTTPException
from ..dependencies import ctx

router = APIRouter(prefix="/macrogrid", tags=["macrogrid"])


@router.get("/zones")
def get_zones():
    if not ctx.macrogrid_service:
        raise HTTPException(503, "Macro-grid service not initialized")
    zones = ctx.macrogrid_service.get_zone_states()
    return {"zones": zones, "count": len(zones)}


@router.get("/recommendations")
def get_recommendations():
    if not ctx.macrogrid_service:
        raise HTTPException(503, "Macro-grid service not initialized")
    recs = ctx.macrogrid_service.get_recommendations()
    return {"recommendations": recs, "count": len(recs)}


@router.post("/recommendations/{rec_id}/convert")
async def convert_recommendation(rec_id: str):
    if not ctx.macrogrid_service:
        raise HTTPException(503, "Macro-grid service not initialized")

    mission = ctx.macrogrid_service.convert_to_mission(rec_id)
    if not mission:
        raise HTTPException(404, f"Recommendation {rec_id} not found")

    result = await ctx.mission_service.create_mission(mission)
    return result.model_dump()
