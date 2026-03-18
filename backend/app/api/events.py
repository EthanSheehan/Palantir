from fastapi import APIRouter, Query
from typing import Optional
from ..dependencies import ctx

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def query_events(
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(1000, le=10000),
):
    events = ctx.event_log_repo.query(
        from_time=from_time, to_time=to_time,
        entity_type=entity_type, entity_id=entity_id,
        event_type=event_type, limit=limit,
    )
    return {"events": [e.model_dump() for e in events], "count": len(events)}
