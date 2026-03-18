from __future__ import annotations
from typing import Optional

from ..domain.models import Alert, DomainEvent, _now
from ..domain.enums import AlertType, AlertSeverity, AlertState, AlertSourceType
from ..domain.state_machines import validate_transition
from ..event_bus import EventBus
from ..persistence.repositories import AlertRepo


class AlertService:
    def __init__(self, repo: AlertRepo, bus: EventBus):
        self.repo = repo
        self.bus = bus

    async def setup_subscriptions(self):
        """Subscribe to events that should auto-generate alerts."""
        self.bus.subscribe("command.failed", self._on_command_failed)
        self.bus.subscribe("asset.status_changed", self._on_asset_status_changed)
        self.bus.subscribe("timeline.conflict_detected", self._on_timeline_conflict)

    async def create_alert(self, alert: Alert) -> Alert:
        self.repo.insert(alert)
        await self.bus.publish(DomainEvent(
            type="alert.created",
            source_service="alert_service",
            entity_type="alert",
            entity_id=alert.id,
            version=1,
            payload=alert.model_dump(),
        ))
        return alert

    async def acknowledge(self, alert_id: str, acknowledged_by: str = "operator") -> Alert:
        alert = self.repo.get(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        validate_transition("alert", alert.state.value, AlertState.acknowledged.value)
        alert.state = AlertState.acknowledged
        self.repo.update(alert)

        await self.bus.publish(DomainEvent(
            type="alert.acknowledged",
            source_service="alert_service",
            entity_type="alert",
            entity_id=alert.id,
            version=1,
            payload={
                "alert_id": alert.id,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": _now(),
            },
        ))
        return alert

    async def clear(self, alert_id: str, reason: str = "") -> Alert:
        alert = self.repo.get(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        validate_transition("alert", alert.state.value, AlertState.cleared.value)
        alert.state = AlertState.cleared
        self.repo.update(alert)

        await self.bus.publish(DomainEvent(
            type="alert.cleared",
            source_service="alert_service",
            entity_type="alert",
            entity_id=alert.id,
            version=1,
            payload={
                "alert_id": alert.id,
                "cleared_at": _now(),
                "cleared_by": "system",
                "reason": reason,
            },
        ))
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self.repo.get(alert_id)

    def list_alerts(self, **filters) -> list[Alert]:
        return self.repo.list_all(**filters)

    # ── Auto-alert handlers ──

    async def _on_command_failed(self, event: DomainEvent):
        await self.create_alert(Alert(
            type=AlertType.command_failed,
            severity=AlertSeverity.warning,
            source_type=AlertSourceType.command,
            source_id=event.entity_id,
            message=f"Command {event.entity_id} failed: {event.payload.get('reason', 'unknown')}",
            metadata=event.payload,
        ))

    async def _on_asset_status_changed(self, event: DomainEvent):
        new_status = event.payload.get("new_status", "")
        if new_status == "lost":
            await self.create_alert(Alert(
                type=AlertType.link_loss,
                severity=AlertSeverity.critical,
                source_type=AlertSourceType.asset,
                source_id=event.entity_id,
                message=f"Asset {event.entity_id} communication lost",
                metadata=event.payload,
            ))
        elif new_status == "degraded":
            await self.create_alert(Alert(
                type=AlertType.health_degraded,
                severity=AlertSeverity.warning,
                source_type=AlertSourceType.asset,
                source_id=event.entity_id,
                message=f"Asset {event.entity_id} health degraded",
                metadata=event.payload,
            ))

    async def _on_timeline_conflict(self, event: DomainEvent):
        await self.create_alert(Alert(
            type=AlertType.conflict_detected,
            severity=AlertSeverity.warning,
            source_type=AlertSourceType.asset,
            source_id=event.payload.get("asset_id", ""),
            message=f"Timeline conflict: {event.payload.get('conflict_type', 'unknown')}",
            metadata=event.payload,
        ))
