"""Flight state and phase definitions."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any

import numpy as np


class Phase(Enum):
    CRUISE = 0
    DIVE = 1
    TERMINAL = 2


PHASE_NAMES = {Phase.CRUISE: "CRUISE", Phase.DIVE: "DIVE", Phase.TERMINAL: "IMPACT"}


@dataclass
class FlightState:
    position: np.ndarray
    pitch: float
    phase: Phase
    tracking: bool = False
    error_y: float = 0.0
    dist_to_target_cm: float = 0.0
    offset_cm: float = 0.0
    mission_count: int = 0
    should_reset: bool = False

    def altitude_above_target_cm(self, target_y: float) -> float:
        return self.position[1] - target_y

    def metadata(self, target_y: float, start_offset: float) -> Dict[str, Any]:
        alt_above = self.altitude_above_target_cm(target_y)
        return {
            "phase": PHASE_NAMES.get(self.phase, "?"),
            "pitch": float(self.pitch),
            "error_y": float(self.error_y),
            "state": "TRK" if self.tracking else "SCH",
            "altitude_m": float(alt_above / 100),
            "dist_to_target_m": float(self.dist_to_target_cm / 100),
            "offset_m": float(self.offset_cm / 100),
            "direction": "FWD",
            "pass_num": self.mission_count,
            "start_offset": float(start_offset),
            "overshoot": 0,
        }
