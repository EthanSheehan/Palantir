"""sim_controller.py — Simulation fidelity controls (W5-001).

Provides pause/resume, time compression (1x/5x/10x/50x), and single-step
mode for the Palantir simulation loop.

All state is immutable (frozen dataclass). Methods return new SimController
instances rather than mutating in place.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Tuple

VALID_SPEEDS = frozenset({1, 5, 10, 50})


@dataclass(frozen=True)
class SimControlState:
    paused: bool = False
    speed_multiplier: int = 1
    step_requested: bool = False


class SimController:
    """Immutable simulation fidelity controller.

    Every mutating method returns a new SimController with updated state.
    The original instance is never modified.
    """

    def __init__(self, state: SimControlState | None = None) -> None:
        self._state = state if state is not None else SimControlState()

    @property
    def state(self) -> SimControlState:
        return self._state

    def pause(self) -> SimController:
        return SimController(replace(self._state, paused=True))

    def resume(self) -> SimController:
        return SimController(replace(self._state, paused=False))

    def set_speed(self, multiplier: int) -> SimController:
        if multiplier not in VALID_SPEEDS:
            raise ValueError(f"Invalid speed multiplier {multiplier!r}. Must be one of: {sorted(VALID_SPEEDS)}")
        return SimController(replace(self._state, speed_multiplier=multiplier))

    def step(self) -> SimController:
        return SimController(replace(self._state, step_requested=True))

    def consume_step(self) -> SimController:
        """Clear step_requested after the single step has been executed."""
        return SimController(replace(self._state, step_requested=False))

    def should_tick(self, base_dt: float) -> Tuple[bool, float]:
        """Return (should_run, effective_dt).

        - Paused with no step_requested: (False, 0.0)
        - Paused with step_requested:    (True, base_dt)   [single tick]
        - Running:                       (True, base_dt * speed_multiplier)
        """
        if self._state.paused:
            if self._state.step_requested:
                return True, base_dt
            return False, 0.0
        return True, base_dt * self._state.speed_multiplier

    def get_state(self) -> dict:
        return {
            "paused": self._state.paused,
            "speed_multiplier": self._state.speed_multiplier,
            "step_requested": self._state.step_requested,
            "valid_speeds": sorted(VALID_SPEEDS),
        }
