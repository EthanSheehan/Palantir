from __future__ import annotations
from typing import Optional

from ..domain.models import Aimpoint, Target, DomainEvent, _now
from ..domain.enums import AimpointType, TargetState
from ..event_bus import EventBus
from ..persistence.repositories import AimpointRepo, TargetRepo


class TargetService:
    def __init__(self, aimpoint_repo: AimpointRepo, target_repo: TargetRepo, bus: EventBus):
        self.aimpoint_repo = aimpoint_repo
        self.target_repo = target_repo
        self.bus = bus

    # ── Aimpoint CRUD ──

    async def create_aimpoint(self, aimpoint: Aimpoint) -> Aimpoint:
        self.aimpoint_repo.insert(aimpoint)
        await self.bus.publish(DomainEvent(
            type="aimpoint.created",
            source_service="target_service",
            entity_type="aimpoint",
            entity_id=aimpoint.id,
            version=aimpoint.version,
            payload=aimpoint.model_dump(),
        ))
        return aimpoint

    async def update_aimpoint(self, aimpoint_id: str, **fields) -> Aimpoint:
        apt = self.aimpoint_repo.get(aimpoint_id)
        if not apt:
            raise ValueError(f"Aimpoint {aimpoint_id} not found")

        for key, value in fields.items():
            if hasattr(apt, key):
                setattr(apt, key, value)
        apt.version += 1
        apt.updated_at = _now()
        self.aimpoint_repo.update(apt)

        await self.bus.publish(DomainEvent(
            type="aimpoint.updated",
            source_service="target_service",
            entity_type="aimpoint",
            entity_id=apt.id,
            version=apt.version,
            payload=apt.model_dump(),
        ))
        return apt

    async def delete_aimpoint(self, aimpoint_id: str):
        apt = self.aimpoint_repo.get(aimpoint_id)
        if not apt:
            raise ValueError(f"Aimpoint {aimpoint_id} not found")

        # Remove from parent target if assigned
        if apt.target_id:
            tgt = self.target_repo.get(apt.target_id)
            if tgt and aimpoint_id in tgt.aimpoint_ids:
                tgt.aimpoint_ids.remove(aimpoint_id)
                tgt.version += 1
                tgt.updated_at = _now()
                self.target_repo.update(tgt)
                await self.bus.publish(DomainEvent(
                    type="target.updated",
                    source_service="target_service",
                    entity_type="target",
                    entity_id=tgt.id,
                    version=tgt.version,
                    payload=tgt.model_dump(),
                ))

        self.aimpoint_repo.delete(aimpoint_id)
        await self.bus.publish(DomainEvent(
            type="aimpoint.deleted",
            source_service="target_service",
            entity_type="aimpoint",
            entity_id=aimpoint_id,
            version=apt.version,
            payload={"id": aimpoint_id},
        ))

    def get_aimpoint(self, aimpoint_id: str) -> Optional[Aimpoint]:
        return self.aimpoint_repo.get(aimpoint_id)

    def list_aimpoints(self, **filters) -> list[Aimpoint]:
        return self.aimpoint_repo.list_all(**filters)

    # ── Target CRUD ──

    async def create_target(self, target: Target) -> Target:
        # Insert target first (so FK on aimpoints can reference it)
        self.target_repo.insert(target)

        # Link aimpoints to this target
        for apt_id in target.aimpoint_ids:
            apt = self.aimpoint_repo.get(apt_id)
            if apt:
                apt.target_id = target.id
                apt.version += 1
                apt.updated_at = _now()
                self.aimpoint_repo.update(apt)
        await self.bus.publish(DomainEvent(
            type="target.created",
            source_service="target_service",
            entity_type="target",
            entity_id=target.id,
            version=target.version,
            payload=target.model_dump(),
        ))
        return target

    async def update_target(self, target_id: str, **fields) -> Target:
        tgt = self.target_repo.get(target_id)
        if not tgt:
            raise ValueError(f"Target {target_id} not found")

        for key, value in fields.items():
            if hasattr(tgt, key):
                setattr(tgt, key, value)
        tgt.version += 1
        tgt.updated_at = _now()
        self.target_repo.update(tgt)

        await self.bus.publish(DomainEvent(
            type="target.updated",
            source_service="target_service",
            entity_type="target",
            entity_id=tgt.id,
            version=tgt.version,
            payload=tgt.model_dump(),
        ))
        return tgt

    async def delete_target(self, target_id: str):
        tgt = self.target_repo.get(target_id)
        if not tgt:
            raise ValueError(f"Target {target_id} not found")

        # Soft-delete: set state to deleted
        tgt.state = TargetState.deleted
        tgt.version += 1
        tgt.updated_at = _now()
        self.target_repo.update(tgt)

        # Unlink aimpoints
        for apt_id in tgt.aimpoint_ids:
            apt = self.aimpoint_repo.get(apt_id)
            if apt:
                apt.target_id = None
                apt.version += 1
                apt.updated_at = _now()
                self.aimpoint_repo.update(apt)

        await self.bus.publish(DomainEvent(
            type="target.deleted",
            source_service="target_service",
            entity_type="target",
            entity_id=target_id,
            version=tgt.version,
            payload={"id": target_id},
        ))

    async def add_aimpoint_to_target(self, target_id: str, aimpoint_id: str) -> Target:
        tgt = self.target_repo.get(target_id)
        if not tgt:
            raise ValueError(f"Target {target_id} not found")
        apt = self.aimpoint_repo.get(aimpoint_id)
        if not apt:
            raise ValueError(f"Aimpoint {aimpoint_id} not found")

        if aimpoint_id not in tgt.aimpoint_ids:
            tgt.aimpoint_ids.append(aimpoint_id)
            tgt.version += 1
            tgt.updated_at = _now()
            if len(tgt.aimpoint_ids) > 1:
                tgt.type = "multi-aim"
            self.target_repo.update(tgt)

        apt.target_id = target_id
        apt.version += 1
        apt.updated_at = _now()
        self.aimpoint_repo.update(apt)

        await self.bus.publish(DomainEvent(
            type="target.aimpoint_added",
            source_service="target_service",
            entity_type="target",
            entity_id=target_id,
            version=tgt.version,
            payload={"target_id": target_id, "aimpoint_id": aimpoint_id,
                      **tgt.model_dump()},
        ))
        return tgt

    async def remove_aimpoint_from_target(self, target_id: str, aimpoint_id: str) -> Target:
        tgt = self.target_repo.get(target_id)
        if not tgt:
            raise ValueError(f"Target {target_id} not found")

        if aimpoint_id in tgt.aimpoint_ids:
            tgt.aimpoint_ids.remove(aimpoint_id)
            tgt.version += 1
            tgt.updated_at = _now()
            if len(tgt.aimpoint_ids) <= 1:
                tgt.type = "single"
            self.target_repo.update(tgt)

        apt = self.aimpoint_repo.get(aimpoint_id)
        if apt:
            apt.target_id = None
            apt.version += 1
            apt.updated_at = _now()
            self.aimpoint_repo.update(apt)

        await self.bus.publish(DomainEvent(
            type="target.aimpoint_removed",
            source_service="target_service",
            entity_type="target",
            entity_id=target_id,
            version=tgt.version,
            payload={"target_id": target_id, "aimpoint_id": aimpoint_id,
                      **tgt.model_dump()},
        ))
        return tgt

    def get_target(self, target_id: str) -> Optional[Target]:
        return self.target_repo.get(target_id)

    def get_target_with_aimpoints(self, target_id: str) -> Optional[dict]:
        tgt = self.target_repo.get(target_id)
        if not tgt:
            return None
        aimpoints = [self.aimpoint_repo.get(aid) for aid in tgt.aimpoint_ids]
        aimpoints = [a for a in aimpoints if a is not None]
        result = tgt.model_dump()
        result["aimpoints"] = [a.model_dump() for a in aimpoints]
        return result

    def list_targets(self, **filters) -> list[Target]:
        return self.target_repo.list_all(**filters)
