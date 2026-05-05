"""
weather_engine.py
=================
Dynamic weather front simulation for the Grid-Sentinel C2 system.

Implements zone-based weather states that advance through a CLEAR→OVERCAST→RAIN→STORM
cycle, degrading sensor performance based on sensor type and weather intensity.

WeatherState dataclasses are immutable (frozen). WeatherEngine is a stateful manager
that holds per-zone state and a seeded RNG; tick() returns a new WeatherEngine instance
rather than mutating in-place.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Weather state cycle
# ---------------------------------------------------------------------------

WEATHER_CYCLE = ("CLEAR", "OVERCAST", "RAIN", "STORM")

# Default duration ranges (seconds) per state before potential transition
_STATE_DURATION_RANGE: Dict[str, tuple] = {
    "CLEAR": (120.0, 600.0),
    "OVERCAST": (60.0, 300.0),
    "RAIN": (60.0, 240.0),
    "STORM": (30.0, 120.0),
}

# Intensity per state
_STATE_INTENSITY: Dict[str, float] = {
    "CLEAR": 0.0,
    "OVERCAST": 0.3,
    "RAIN": 0.65,
    "STORM": 1.0,
}

# Sensor degradation weight per sensor type for additive weather penalty.
# These multiply intensity to produce a weather penalty factor (0=immune, 1=fully degraded).
WEATHER_SENSOR_WEIGHTS: Dict[str, float] = {
    "EO_IR": 0.8,
    "SAR": 0.2,
    "SIGINT": 0.05,
}


# ---------------------------------------------------------------------------
# WeatherState — immutable per-zone weather snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherState:
    state: str  # CLEAR, OVERCAST, RAIN, STORM
    intensity: float  # 0-1
    duration_s: float  # seconds remaining in current state


# ---------------------------------------------------------------------------
# Pure Pd modification from weather
# ---------------------------------------------------------------------------


def apply_weather_to_pd(pd: float, weather: WeatherState, sensor_type: str) -> float:
    """Return Pd reduced by current weather state for a given sensor type.

    Penalty = weather_weight * intensity * 0.6 (matches sensor_model formula scale)
    """
    weight = WEATHER_SENSOR_WEIGHTS.get(sensor_type, 0.0)
    penalty = weight * weather.intensity * 0.6
    return float(max(0.0, min(1.0, pd - penalty)))


def get_zone_weather(engine: WeatherEngine, zone_id: str) -> WeatherState:
    """Helper: retrieve WeatherState for zone_id from a WeatherEngine."""
    return engine.get_zone_state(zone_id)


# ---------------------------------------------------------------------------
# WeatherEngine — immutable zone weather manager
# ---------------------------------------------------------------------------


class WeatherEngine:
    """Stateful weather engine.  tick() returns a new WeatherEngine instance with updated states."""

    def __init__(
        self,
        zone_ids: Optional[list] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._zones: Dict[str, WeatherState] = {}
        for zone_id in zone_ids or []:
            duration = self._rng.uniform(*_STATE_DURATION_RANGE["CLEAR"])
            self._zones[zone_id] = WeatherState(
                state="CLEAR",
                intensity=_STATE_INTENSITY["CLEAR"],
                duration_s=duration,
            )

    @classmethod
    def from_states(
        cls,
        states: Dict[str, WeatherState],
        seed: Optional[int] = None,
    ) -> WeatherEngine:
        """Create a WeatherEngine pre-loaded with explicit zone states."""
        engine = cls.__new__(cls)
        engine._rng = random.Random(seed)
        engine._zones = dict(states)
        return engine

    def get_zone_state(self, zone_id: str) -> WeatherState:
        """Return WeatherState for zone_id; returns CLEAR if zone is unknown."""
        return self._zones.get(
            zone_id,
            WeatherState(state="CLEAR", intensity=0.0, duration_s=0.0),
        )

    def tick(self, dt_s: float) -> WeatherEngine:
        """Advance all zone weather states by dt_s seconds.

        Returns a new WeatherEngine with updated states; does not mutate self.
        """
        new_states: Dict[str, WeatherState] = {}
        for zone_id, ws in self._zones.items():
            new_states[zone_id] = self._advance_state(ws, dt_s)

        new_engine = WeatherEngine.__new__(WeatherEngine)
        new_engine._rng = random.Random(self._rng.random())  # fork RNG
        new_engine._zones = new_states
        return new_engine

    def _advance_state(self, ws: WeatherState, dt_s: float) -> WeatherState:
        remaining = ws.duration_s - dt_s
        if remaining > 0.0:
            return WeatherState(
                state=ws.state,
                intensity=_STATE_INTENSITY[ws.state],
                duration_s=remaining,
            )

        # Transition to next state in cycle
        idx = WEATHER_CYCLE.index(ws.state)
        next_state = WEATHER_CYCLE[(idx + 1) % len(WEATHER_CYCLE)]
        new_duration = self._rng.uniform(*_STATE_DURATION_RANGE[next_state])
        return WeatherState(
            state=next_state,
            intensity=_STATE_INTENSITY[next_state],
            duration_s=new_duration,
        )
