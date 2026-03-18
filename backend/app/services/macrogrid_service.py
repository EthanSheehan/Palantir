from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..domain.models import DomainEvent, Mission, Task, _now
from ..domain.enums import MissionType, Priority, TaskType, TargetKind
from ..event_bus import EventBus


class MacroGridRecommendation:
    def __init__(self, source_zone: dict, target_zone: dict,
                 suggested_asset_count: int, pressure_delta: float):
        self.id = f"rec_{uuid.uuid4().hex[:12]}"
        self.type = "rebalance"
        self.source_zone = source_zone
        self.target_zone = target_zone
        self.suggested_asset_count = suggested_asset_count
        self.pressure_delta = pressure_delta
        self.confidence = min(1.0, abs(pressure_delta) / 20.0)
        self.created_at = _now()
        self.expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source_zone": self.source_zone,
            "target_zone": self.target_zone,
            "suggested_asset_count": self.suggested_asset_count,
            "pressure_delta": self.pressure_delta,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class MacroGridService:
    def __init__(self, grid, bus: EventBus):
        self.grid = grid  # RomaniaMacroGrid instance
        self.bus = bus
        self.recommendations: dict[str, MacroGridRecommendation] = {}

    async def process_dispatches(self, dispatches: list[dict]):
        """Convert raw grid dispatches into recommendations."""
        now = datetime.now(timezone.utc)

        # Expire old recommendations
        expired = [rid for rid, r in self.recommendations.items()
                   if r.expires_at < now.isoformat()]
        for rid in expired:
            del self.recommendations[rid]

        for dispatch in dispatches:
            source_zone = self.grid.zones.get(dispatch["source_id"])
            target_zone = self.grid.zones.get(dispatch["target_id"])
            if not source_zone or not target_zone:
                continue

            rec = MacroGridRecommendation(
                source_zone={
                    "id": list(dispatch["source_id"]),
                    "lon": source_zone.lon,
                    "lat": source_zone.lat,
                },
                target_zone={
                    "id": list(dispatch["target_id"]),
                    "lon": target_zone.lon,
                    "lat": target_zone.lat,
                },
                suggested_asset_count=dispatch.get("count", 1),
                pressure_delta=source_zone.imbalance - target_zone.imbalance,
            )
            self.recommendations[rec.id] = rec

            await self.bus.publish(DomainEvent(
                type="macrogrid.recommendation_emitted",
                source_service="macrogrid_service",
                entity_type="macrogrid",
                entity_id=rec.id,
                version=1,
                payload=rec.to_dict(),
            ))

    def get_recommendations(self) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            r.to_dict() for r in self.recommendations.values()
            if r.expires_at > now
        ]

    def get_zone_states(self) -> list[dict]:
        return [
            {
                "id": list(zid),
                "lon": z.lon,
                "lat": z.lat,
                "width_deg": z.width_deg,
                "height_deg": z.height_deg,
                "queue": z.queue,
                "uav_count": z.uav_count,
                "imbalance": z.imbalance,
                "demand_rate": z.demand_rate,
            }
            for zid, z in self.grid.zones.items()
        ]

    def convert_to_mission(self, rec_id: str) -> Optional[Mission]:
        """Convert a recommendation into a draft rebalance mission."""
        rec = self.recommendations.get(rec_id)
        if not rec:
            return None

        mission = Mission(
            name=f"Rebalance: zone {rec.source_zone['id']} → {rec.target_zone['id']}",
            type=MissionType.rebalance,
            priority=Priority.normal,
            objective=f"Rebalance {rec.suggested_asset_count} asset(s) from zone "
                      f"{rec.source_zone['id']} to zone {rec.target_zone['id']}",
        )
        return mission
