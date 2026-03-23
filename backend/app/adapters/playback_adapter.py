from __future__ import annotations
from ..domain.models import Command
from .base import ExecutionAdapter, AdapterResult, AdapterStatus, TelemetryUpdate


class PlaybackAdapter(ExecutionAdapter):
    """Replays recorded telemetry from the event log. Read-only."""

    def __init__(self, event_log_repo):
        self.event_log_repo = event_log_repo
        self._cursor_time = None
        self._prev_cursor_time = None
        self._playback_speed = 1.0

    def send_command(self, command: Command) -> AdapterResult:
        return AdapterResult(success=False, error="Playback mode is read-only")

    def fetch_asset_updates(self) -> list[TelemetryUpdate]:
        """Replay telemetry events between previous and current cursor positions."""
        if not self._cursor_time or not self._prev_cursor_time:
            return []
        if self._cursor_time == self._prev_cursor_time:
            return []

        events = self.event_log_repo.query(
            from_time=self._prev_cursor_time,
            to_time=self._cursor_time,
            event_type="asset.telemetry_received",
            limit=10000,
        )

        updates = []
        for event in events:
            p = event.payload
            pos = p.get("position", {})
            vel = p.get("velocity", {})
            updates.append(TelemetryUpdate(
                asset_id=event.entity_id,
                lon=pos.get("lon", 0.0),
                lat=pos.get("lat", 0.0),
                alt_m=pos.get("alt_m", 0.0),
                vx_mps=vel.get("vx_mps", 0.0),
                vy_mps=vel.get("vy_mps", 0.0),
                vz_mps=vel.get("vz_mps", 0.0),
                heading_deg=p.get("heading_deg", 0.0),
                pitch_deg=p.get("pitch_deg", 0.0),
                roll_deg=p.get("roll_deg", 0.0),
                battery_pct=p.get("battery_pct", 100.0),
                link_quality=p.get("link_quality", 1.0),
            ))
        return updates

    def get_connection_status(self) -> AdapterStatus:
        return AdapterStatus.playback

    def set_cursor(self, timestamp: str):
        self._prev_cursor_time = self._cursor_time
        self._cursor_time = timestamp

    def set_speed(self, speed: float):
        self._playback_speed = speed
