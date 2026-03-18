from __future__ import annotations
from ..domain.models import Command
from .base import ExecutionAdapter, AdapterResult, AdapterStatus, TelemetryUpdate


class PlaybackAdapter(ExecutionAdapter):
    """Replays recorded telemetry from the event log. Read-only."""

    def __init__(self, event_log_repo):
        self.event_log_repo = event_log_repo
        self._cursor_time = None
        self._playback_speed = 1.0

    def send_command(self, command: Command) -> AdapterResult:
        return AdapterResult(success=False, error="Playback mode is read-only")

    def fetch_asset_updates(self) -> list[TelemetryUpdate]:
        # In playback mode, updates come from the event log, not live telemetry
        # The timeline service handles replaying events
        return []

    def get_connection_status(self) -> AdapterStatus:
        return AdapterStatus.playback

    def set_cursor(self, timestamp: str):
        self._cursor_time = timestamp

    def set_speed(self, speed: float):
        self._playback_speed = speed
