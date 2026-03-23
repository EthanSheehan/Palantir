from __future__ import annotations
import math
from typing import Optional

from ..domain.models import Asset, DomainEvent, Position, Velocity, _now
from ..domain.enums import AssetStatus, AssetHealth
from ..domain.state_machines import validate_transition, InvalidTransitionError
from ..event_bus import EventBus
from ..persistence.repositories import AssetRepo


class AssetService:
    def __init__(self, repo: AssetRepo, bus: EventBus):
        self.repo = repo
        self.bus = bus

    async def register_asset(self, asset: Asset) -> Asset:
        self.repo.upsert(asset)
        await self.bus.publish(DomainEvent(
            type="asset.created",
            source_service="asset_service",
            entity_type="asset",
            entity_id=asset.id,
            version=asset.version,
            payload=asset.model_dump(),
        ))
        return asset

    async def update_telemetry(self, asset_id: str, position: Position,
                                velocity: Velocity, heading_deg: float,
                                pitch_deg: float = 0.0,
                                roll_deg: float = 0.0,
                                battery_pct: float = 100.0,
                                link_quality: float = 1.0,
                                persist_to_log: bool = True) -> Optional[Asset]:
        asset = self.repo.get(asset_id)
        if not asset:
            return None

        asset.position = position
        asset.velocity = velocity
        asset.heading_deg = heading_deg
        asset.pitch_deg = pitch_deg
        asset.roll_deg = roll_deg
        asset.battery_pct = battery_pct
        asset.link_quality = link_quality
        asset.last_telemetry_time = _now()
        asset.version += 1
        asset.updated_at = _now()
        self.repo.upsert(asset)

        if persist_to_log:
            await self.bus.publish(DomainEvent(
                type="asset.telemetry_received",
                source_service="asset_service",
                entity_type="asset",
                entity_id=asset.id,
                version=asset.version,
                payload={
                    "position": position.model_dump(),
                    "velocity": velocity.model_dump(),
                    "heading_deg": heading_deg,
                    "pitch_deg": pitch_deg,
                    "roll_deg": roll_deg,
                    "battery_pct": battery_pct,
                    "link_quality": link_quality,
                },
            ))
        return asset

    async def change_status(self, asset_id: str, new_status: AssetStatus,
                            reason: str = "") -> Asset:
        asset = self.repo.get(asset_id)
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        old_status = asset.status
        validate_transition("asset", old_status.value, new_status.value)

        asset.status = new_status
        asset.version += 1
        asset.updated_at = _now()
        self.repo.upsert(asset)

        await self.bus.publish(DomainEvent(
            type="asset.status_changed",
            source_service="asset_service",
            entity_type="asset",
            entity_id=asset.id,
            version=asset.version,
            payload={
                "old_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason,
            },
        ))
        return asset

    def get_asset(self, asset_id: str) -> Optional[Asset]:
        return self.repo.get(asset_id)

    def list_assets(self, **filters) -> list[Asset]:
        return self.repo.list_all(**filters)
