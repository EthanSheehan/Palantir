from __future__ import annotations
from ..domain.models import Command
from .base import ExecutionAdapter, AdapterResult, AdapterStatus, TelemetryUpdate


class MAVLinkAdapter(ExecutionAdapter):
    """Interface-only stub for future MAVLink/PX4/ArduPilot integration.

    Contract:
    - send_command() translates Command objects into MAV_CMD messages
      (e.g., MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_RETURN_TO_LAUNCH)
    - fetch_asset_updates() parses incoming MAVLink telemetry messages
      (HEARTBEAT, GLOBAL_POSITION_INT, SYS_STATUS, BATTERY_STATUS)
    - get_connection_status() checks the serial/UDP link state
    """

    def send_command(self, command: Command) -> AdapterResult:
        raise NotImplementedError(
            "MAVLink adapter not implemented. "
            "This stub defines the interface for future real-vehicle integration."
        )

    def fetch_asset_updates(self) -> list[TelemetryUpdate]:
        raise NotImplementedError(
            "MAVLink adapter not implemented. "
            "Future implementation will parse GLOBAL_POSITION_INT and SYS_STATUS messages."
        )

    def get_connection_status(self) -> AdapterStatus:
        return AdapterStatus.disconnected
