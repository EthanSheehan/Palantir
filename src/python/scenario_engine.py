"""
scenario_engine.py
==================
YAML scenario scripting engine for reproducible training and exercises (W5-002).

Provides:
  - ScenarioEvent  — frozen dataclass: time_offset_s, event_type, params
  - Scenario       — frozen dataclass: name, description, theater, events tuple
  - load_scenario  — parse a YAML file into a Scenario
  - ScenarioPlayer — stateful player that ticks time and fires due events

Supported event types:
  SPAWN_TARGET      — spawn a ground target at (x, y)
  SET_WEATHER       — force weather state on a zone
  TRIGGER_ENEMY_UAV — spawn an enemy UAV
  DEGRADE_COMMS     — apply comms degradation to a zone
  SET_SPEED         — change simulation speed multiplier

All state types are immutable.  ScenarioPlayer tracks elapsed time and
the index of the next un-fired event internally.
"""

from __future__ import annotations

import pathlib
import types
from dataclasses import dataclass
from typing import List, Tuple

import structlog
import yaml

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Valid event types
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = frozenset(
    {
        "SPAWN_TARGET",
        "SET_WEATHER",
        "TRIGGER_ENEMY_UAV",
        "DEGRADE_COMMS",
        "SET_SPEED",
    }
)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ScenarioError(Exception):
    """Raised for invalid scenario files or missing required fields."""


# ---------------------------------------------------------------------------
# ScenarioEvent — immutable event descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioEvent:
    time_offset_s: float
    event_type: str
    params: types.MappingProxyType


# ---------------------------------------------------------------------------
# Scenario — immutable scenario descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    theater: str
    events: Tuple[ScenarioEvent, ...]


# ---------------------------------------------------------------------------
# load_scenario — parse YAML into Scenario
# ---------------------------------------------------------------------------


def _validate_scenario_path(yaml_path: str) -> pathlib.Path:
    """Validate that the path does not contain path traversal sequences.

    Rejects paths with '..' components to prevent directory traversal attacks.
    Returns the resolved absolute Path on success; raises ScenarioError on failure.
    """
    raw = pathlib.Path(yaml_path)
    if ".." in raw.parts:
        raise ScenarioError(f"Scenario path {yaml_path!r} contains illegal '..' traversal")
    return raw.resolve()


_SCENARIOS_DIR = pathlib.Path(__file__).parent / "scenarios"


def load_scenario(yaml_path: str) -> Scenario:
    """Parse a YAML scenario file and return an immutable Scenario.

    Raises ScenarioError on any parse or validation failure.
    Rejects paths containing '..' traversal components.
    """
    resolved = _validate_scenario_path(yaml_path)

    try:
        with open(resolved, "r") as fh:
            raw = yaml.safe_load(fh)
    except FileNotFoundError:
        raise ScenarioError(f"Scenario file not found: {yaml_path!r}")
    except yaml.YAMLError as exc:
        raise ScenarioError(f"Failed to parse scenario YAML: {exc}")

    if not isinstance(raw, dict):
        raise ScenarioError("Scenario YAML must be a mapping at the top level")

    # Required field validation
    for field in ("name", "theater", "events"):
        if field not in raw:
            raise ScenarioError(f"Scenario YAML missing required field: '{field}'")

    name: str = str(raw["name"])
    description: str = str(raw.get("description", ""))
    theater: str = str(raw["theater"])

    raw_events = raw["events"]
    if not isinstance(raw_events, list):
        raise ScenarioError("'events' must be a list")

    parsed: List[ScenarioEvent] = []
    for i, item in enumerate(raw_events):
        if not isinstance(item, dict):
            raise ScenarioError(f"Event at index {i} must be a mapping")
        for field in ("time_offset_s", "event_type"):
            if field not in item:
                raise ScenarioError(f"Event at index {i} missing required field: '{field}'")
        event_type = str(item["event_type"])
        if event_type not in VALID_EVENT_TYPES:
            raise ScenarioError(
                f"Event at index {i} has unknown event_type {event_type!r}. Valid types: {sorted(VALID_EVENT_TYPES)}"
            )
        params = types.MappingProxyType(dict(item.get("params") or {}))
        parsed.append(
            ScenarioEvent(
                time_offset_s=float(item["time_offset_s"]),
                event_type=event_type,
                params=params,
            )
        )

    # Sort events chronologically
    parsed.sort(key=lambda ev: ev.time_offset_s)

    logger.info(
        "scenario_loaded",
        name=name,
        theater=theater,
        event_count=len(parsed),
    )
    return Scenario(
        name=name,
        description=description,
        theater=theater,
        events=tuple(parsed),
    )


# ---------------------------------------------------------------------------
# ScenarioPlayer — advances time, fires due events
# ---------------------------------------------------------------------------


class ScenarioPlayer:
    """Stateful scenario player.

    Tracks elapsed simulation time and fires ScenarioEvents when their
    time_offset_s is reached.  Events never fire more than once.
    """

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._elapsed_s: float = 0.0
        self._next_idx: int = 0  # index into sorted events tuple

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def elapsed_s(self) -> float:
        return self._elapsed_s

    @property
    def fired_count(self) -> int:
        return self._next_idx

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    # ------------------------------------------------------------------
    # tick — advance time and return newly fired events
    # ------------------------------------------------------------------

    def tick(self, dt_s: float) -> List[ScenarioEvent]:
        """Advance elapsed time by dt_s and return a list of events that fired.

        Events are returned in chronological order.  An event fires exactly
        once when elapsed_s first reaches or exceeds its time_offset_s.
        """
        self._elapsed_s += dt_s

        fired: List[ScenarioEvent] = []
        events = self._scenario.events
        while self._next_idx < len(events):
            ev = events[self._next_idx]
            if ev.time_offset_s <= self._elapsed_s:
                fired.append(ev)
                self._next_idx += 1
            else:
                break  # events are sorted; no need to look further

        if fired:
            logger.debug(
                "scenario_events_fired",
                count=len(fired),
                elapsed_s=self._elapsed_s,
                types=[ev.event_type for ev in fired],
            )

        return fired
