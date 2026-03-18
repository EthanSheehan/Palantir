from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..dependencies import ctx

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("")
def list_assets(
    status: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    health: Optional[str] = Query(None),
    mission_id: Optional[str] = Query(None),
    capability: Optional[str] = Query(None),
):
    assets = ctx.asset_service.list_assets(
        status=status, mode=mode, health=health,
        mission_id=mission_id, capability=capability,
    )
    return {"assets": [a.model_dump() for a in assets], "count": len(assets)}


@router.get("/{asset_id}")
def get_asset(asset_id: str):
    asset = ctx.asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return asset.model_dump()
