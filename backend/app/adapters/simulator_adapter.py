from __future__ import annotations
import math
import random
from typing import Any

from ..domain.models import Command
from ..domain.enums import CommandType, AssetStatus
from .base import ExecutionAdapter, AdapterResult, AdapterStatus, TelemetryUpdate


# Map sim.py UAV modes to our AssetStatus
_MODE_MAP = {
    "idle": "idle",
    "serving": "on_task",
    "repositioning": "transiting",
}


class SimulatorAdapter(ExecutionAdapter):
    """Wraps the existing sim.py SimulationModel behind the adapter interface."""

    def __init__(self, sim):
        self.sim = sim
        self._pending_commands: dict[str, Command] = {}
        self._tick_count = 0

    def send_command(self, command: Command) -> AdapterResult:
        if command.type == CommandType.move_to:
            dest = command.payload.get("destination", {})
            lon = dest.get("lon")
            lat = dest.get("lat")
            if lon is None or lat is None:
                return AdapterResult(success=False, error="Missing destination coordinates")

            # Extract numeric drone ID from asset ID like "ast_abc123" -> find matching UAV
            target_id = command.target_id
            uav = self._find_uav(target_id)
            if uav is None:
                return AdapterResult(success=False, error=f"UAV {target_id} not found in sim")

            alt = dest.get("alt_m")
            self.sim.command_move(uav.id, lon, lat, alt)
            self._pending_commands[command.id] = command
            return AdapterResult(success=True, correlation_id=command.id)

        elif command.type == CommandType.hold_position:
            uav = self._find_uav(command.target_id)
            if uav:
                uav.commanded_target = None
                uav.vx = 0
                uav.vy = 0
            return AdapterResult(success=True, correlation_id=command.id)

        elif command.type == CommandType.return_home:
            # Not fully supported in sim yet
            return AdapterResult(success=True, correlation_id=command.id)

        return AdapterResult(success=False, error=f"Unsupported command type: {command.type}")

    def fetch_asset_updates(self) -> list[TelemetryUpdate]:
        self._tick_count += 1
        updates = []
        for uav in self.sim.uavs:
            # Calculate heading from velocity
            heading = 0.0
            if abs(uav.vx) > 1e-8 or abs(uav.vy) > 1e-8:
                heading = math.degrees(math.atan2(uav.vx, uav.vy)) % 360

            # Simulate battery drain
            drain_rate = 0.001 if uav.mode == "idle" else 0.005
            battery = max(0.0, 100.0 - self._tick_count * drain_rate * 0.1)

            # Simulate link quality fluctuation
            link = min(1.0, max(0.0, 0.95 + random.gauss(0, 0.02)))

            status = _MODE_MAP.get(uav.mode, "idle")

            updates.append(TelemetryUpdate(
                asset_id=f"uav_{uav.id}",
                lon=uav.x,
                lat=uav.y,
                alt_m=uav.alt_m,
                vx_mps=uav.vx * 111000,  # rough deg/s to m/s
                vy_mps=uav.vy * 111000,
                heading_deg=heading,
                pitch_deg=uav.pitch_deg,
                roll_deg=uav.roll_deg,
                battery_pct=battery,
                link_quality=link,
                mode=status,
            ))

        # Launcher ground vehicles — stationary
        for launcher in self.sim.launchers:
            link = min(1.0, max(0.0, 0.95 + random.gauss(0, 0.02)))
            updates.append(TelemetryUpdate(
                asset_id=f"launcher_{launcher.id}",
                lon=launcher.x,
                lat=launcher.y,
                alt_m=0.0,
                vx_mps=0.0,
                vy_mps=0.0,
                heading_deg=launcher.heading,
                battery_pct=100.0,
                link_quality=link,
                mode=launcher.mode,
            ))

        return updates

    def get_connection_status(self) -> AdapterStatus:
        return AdapterStatus.simulated

    def _find_uav(self, asset_id: str):
        """Find UAV by asset_id like 'uav_0' or by raw int ID."""
        for uav in self.sim.uavs:
            if f"uav_{uav.id}" == asset_id or str(uav.id) == asset_id:
                return uav
        return None

    def check_completions(self) -> list[str]:
        """Check if any commanded UAVs have reached their target. Returns command IDs."""
        completed = []
        for cmd_id, cmd in list(self._pending_commands.items()):
            uav = self._find_uav(cmd.target_id)
            if uav and uav.commanded_target is None and uav.mode == "idle":
                completed.append(cmd_id)
                del self._pending_commands[cmd_id]
        return completed
