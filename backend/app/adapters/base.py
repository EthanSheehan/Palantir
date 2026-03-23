from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional

from ..domain.models import Command


class AdapterStatus(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
    playback = "playback"
    simulated = "simulated"


@dataclass
class AdapterResult:
    success: bool
    correlation_id: Optional[str] = None
    error: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelemetryUpdate:
    asset_id: str
    lon: float
    lat: float
    alt_m: float = 0.0
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    vz_mps: float = 0.0
    heading_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    battery_pct: float = 100.0
    link_quality: float = 1.0
    mode: str = "idle"


class ExecutionAdapter(ABC):
    """Abstract base class for execution adapters.

    The core backend services interact only with this interface.
    """

    @abstractmethod
    def send_command(self, command: Command) -> AdapterResult:
        """Send a command to the execution backend."""
        ...

    @abstractmethod
    def fetch_asset_updates(self) -> list[TelemetryUpdate]:
        """Fetch current asset telemetry from the execution backend."""
        ...

    @abstractmethod
    def get_connection_status(self) -> AdapterStatus:
        """Return the current connection status of this adapter."""
        ...
