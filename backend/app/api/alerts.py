from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..dependencies import ctx
from ..domain.state_machines import InvalidTransitionError

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    state: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None, alias="type"),
    source_type: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
):
    alerts = ctx.alert_service.list_alerts(
        state=state, severity=severity,
        alert_type=alert_type, source_type=source_type,
        source_id=source_id,
    )
    return {"alerts": [a.model_dump() for a in alerts], "count": len(alerts)}


@router.get("/{alert_id}")
def get_alert(alert_id: str):
    alert = ctx.alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return alert.model_dump()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    try:
        result = await ctx.alert_service.acknowledge(alert_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))


@router.post("/{alert_id}/clear")
async def clear_alert(alert_id: str):
    try:
        result = await ctx.alert_service.clear(alert_id)
        return result.model_dump()
    except (ValueError, InvalidTransitionError) as e:
        raise HTTPException(400, str(e))
