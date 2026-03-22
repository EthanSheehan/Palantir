"""Tests for ScenarioEngine — YAML scenario scripting (W5-002).

TDD: these tests are written BEFORE implementation. They define the contract.
"""

from __future__ import annotations

import os
import textwrap

import pytest

# These imports will fail until scenario_engine.py is created (RED phase).
from scenario_engine import (
    Scenario,
    ScenarioError,
    ScenarioEvent,
    ScenarioPlayer,
    load_scenario,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path, content: str) -> str:
    p = tmp_path / "scenario.yaml"
    p.write_text(textwrap.dedent(content))
    return str(p)


MINIMAL_YAML = """\
    name: minimal
    description: Minimal test scenario
    theater: romania
    events: []
"""

SPAWN_TARGET_YAML = """\
    name: spawn_test
    description: Spawn a SAM at T+10
    theater: romania
    events:
      - time_offset_s: 10
        event_type: SPAWN_TARGET
        params:
          target_type: SAM
          x: 25.0
          y: 45.0
"""

SET_WEATHER_YAML = """\
    name: weather_test
    description: Set weather at T+20
    theater: romania
    events:
      - time_offset_s: 20
        event_type: SET_WEATHER
        params:
          zone_id: zone_1
          state: STORM
"""

TRIGGER_ENEMY_UAV_YAML = """\
    name: enemy_uav_test
    description: Trigger enemy UAV at T+5
    theater: romania
    events:
      - time_offset_s: 5
        event_type: TRIGGER_ENEMY_UAV
        params:
          uav_id: 99
          x: 26.0
          y: 46.0
          mode: ATTACK
"""

MULTI_SAME_TIMESTAMP_YAML = """\
    name: multi_same_ts
    description: Two events at the same timestamp
    theater: romania
    events:
      - time_offset_s: 15
        event_type: SPAWN_TARGET
        params:
          target_type: TRUCK
          x: 24.0
          y: 44.0
      - time_offset_s: 15
        event_type: SET_WEATHER
        params:
          zone_id: zone_2
          state: RAIN
"""

MULTI_ORDERED_YAML = """\
    name: multi_ordered
    description: Events at different timestamps
    theater: romania
    events:
      - time_offset_s: 30
        event_type: SPAWN_TARGET
        params:
          target_type: CP
          x: 27.0
          y: 47.0
      - time_offset_s: 5
        event_type: TRIGGER_ENEMY_UAV
        params:
          uav_id: 10
          x: 25.0
          y: 45.0
          mode: RECON
      - time_offset_s: 15
        event_type: SET_WEATHER
        params:
          zone_id: zone_3
          state: OVERCAST
"""

DEGRADE_COMMS_YAML = """\
    name: degrade_test
    description: Degrade comms at T+25
    theater: romania
    events:
      - time_offset_s: 25
        event_type: DEGRADE_COMMS
        params:
          zone_id: zone_1
          degradation: 0.8
"""

SET_SPEED_YAML = """\
    name: speed_test
    description: Set speed at T+2
    theater: romania
    events:
      - time_offset_s: 2
        event_type: SET_SPEED
        params:
          multiplier: 10
"""


# ---------------------------------------------------------------------------
# ScenarioEvent frozen dataclass
# ---------------------------------------------------------------------------


class TestScenarioEvent:
    def test_frozen(self):
        ev = ScenarioEvent(time_offset_s=5.0, event_type="SPAWN_TARGET", params={"x": 1.0})
        with pytest.raises((AttributeError, TypeError)):
            ev.time_offset_s = 10.0

    def test_fields(self):
        ev = ScenarioEvent(time_offset_s=10.0, event_type="SET_WEATHER", params={"zone_id": "z1"})
        assert ev.time_offset_s == 10.0
        assert ev.event_type == "SET_WEATHER"
        assert ev.params == {"zone_id": "z1"}

    def test_empty_params_allowed(self):
        ev = ScenarioEvent(time_offset_s=0.0, event_type="SET_SPEED", params={})
        assert ev.params == {}


# ---------------------------------------------------------------------------
# Scenario frozen dataclass
# ---------------------------------------------------------------------------


class TestScenario:
    def test_frozen(self, tmp_path):
        s = Scenario(name="x", description="d", theater="romania", events=())
        with pytest.raises((AttributeError, TypeError)):
            s.name = "y"

    def test_fields(self, tmp_path):
        ev = ScenarioEvent(time_offset_s=1.0, event_type="SPAWN_TARGET", params={})
        s = Scenario(name="test", description="desc", theater="romania", events=(ev,))
        assert s.name == "test"
        assert s.theater == "romania"
        assert len(s.events) == 1


# ---------------------------------------------------------------------------
# load_scenario — YAML parsing
# ---------------------------------------------------------------------------


class TestLoadScenario:
    def test_load_minimal(self, tmp_path):
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        s = load_scenario(path)
        assert s.name == "minimal"
        assert s.theater == "romania"
        assert len(s.events) == 0

    def test_load_spawn_target_event(self, tmp_path):
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        assert len(s.events) == 1
        ev = s.events[0]
        assert ev.event_type == "SPAWN_TARGET"
        assert ev.time_offset_s == 10.0
        assert ev.params["target_type"] == "SAM"

    def test_load_set_weather_event(self, tmp_path):
        path = _write_yaml(tmp_path, SET_WEATHER_YAML)
        s = load_scenario(path)
        ev = s.events[0]
        assert ev.event_type == "SET_WEATHER"
        assert ev.params["zone_id"] == "zone_1"
        assert ev.params["state"] == "STORM"

    def test_load_trigger_enemy_uav_event(self, tmp_path):
        path = _write_yaml(tmp_path, TRIGGER_ENEMY_UAV_YAML)
        s = load_scenario(path)
        ev = s.events[0]
        assert ev.event_type == "TRIGGER_ENEMY_UAV"
        assert ev.params["mode"] == "ATTACK"

    def test_invalid_yaml_raises_scenario_error(self, tmp_path):
        path = _write_yaml(tmp_path, "name: [unclosed bracket\n")
        with pytest.raises(ScenarioError, match="parse"):
            load_scenario(path)

    def test_missing_name_raises_scenario_error(self, tmp_path):
        path = _write_yaml(tmp_path, "description: d\ntheater: romania\nevents: []\n")
        with pytest.raises(ScenarioError, match="name"):
            load_scenario(path)

    def test_missing_theater_raises_scenario_error(self, tmp_path):
        path = _write_yaml(tmp_path, "name: x\ndescription: d\nevents: []\n")
        with pytest.raises(ScenarioError, match="theater"):
            load_scenario(path)

    def test_missing_events_raises_scenario_error(self, tmp_path):
        path = _write_yaml(tmp_path, "name: x\ndescription: d\ntheater: romania\n")
        with pytest.raises(ScenarioError, match="events"):
            load_scenario(path)

    def test_file_not_found_raises_scenario_error(self):
        with pytest.raises(ScenarioError, match="not found"):
            load_scenario("/nonexistent/path/scenario.yaml")

    def test_events_are_sorted_chronologically(self, tmp_path):
        path = _write_yaml(tmp_path, MULTI_ORDERED_YAML)
        s = load_scenario(path)
        times = [ev.time_offset_s for ev in s.events]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# ScenarioPlayer — tick advances and event firing
# ---------------------------------------------------------------------------


class TestScenarioPlayerInit:
    def test_initial_elapsed_zero(self, tmp_path):
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)
        assert player.elapsed_s == 0.0

    def test_initial_fired_events_empty(self, tmp_path):
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)
        assert player.fired_count == 0


class TestScenarioPlayerTick:
    def test_no_events_returns_empty(self, tmp_path):
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)
        fired = player.tick(5.0)
        assert fired == []

    def test_event_fires_when_elapsed_reaches_offset(self, tmp_path):
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)

        # Advance to just before the event
        fired = player.tick(9.9)
        assert fired == []

        # Advance past the event threshold
        fired = player.tick(0.2)
        assert len(fired) == 1
        assert fired[0].event_type == "SPAWN_TARGET"

    def test_event_does_not_fire_twice(self, tmp_path):
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)

        player.tick(15.0)  # past the event
        fired_again = player.tick(1.0)  # another tick after event already fired
        assert fired_again == []

    def test_multiple_events_same_timestamp_all_fire(self, tmp_path):
        path = _write_yaml(tmp_path, MULTI_SAME_TIMESTAMP_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)
        fired = player.tick(20.0)
        assert len(fired) == 2
        types = {ev.event_type for ev in fired}
        assert types == {"SPAWN_TARGET", "SET_WEATHER"}

    def test_events_fire_in_chronological_order(self, tmp_path):
        path = _write_yaml(tmp_path, MULTI_ORDERED_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)

        # Advance past all events
        fired = player.tick(35.0)
        assert len(fired) == 3
        times = [ev.time_offset_s for ev in fired]
        assert times == sorted(times)

    def test_elapsed_accumulates_across_ticks(self, tmp_path):
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)

        player.tick(5.0)
        player.tick(3.0)
        assert player.elapsed_s == pytest.approx(8.0)

    def test_fired_count_increments(self, tmp_path):
        path = _write_yaml(tmp_path, MULTI_SAME_TIMESTAMP_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)
        player.tick(20.0)
        assert player.fired_count == 2

    def test_past_events_not_refired_after_reset(self, tmp_path):
        """Events fired should not be re-fired even after several subsequent ticks."""
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        player = ScenarioPlayer(s)

        player.tick(15.0)
        for _ in range(5):
            fired = player.tick(1.0)
            assert fired == []


# ---------------------------------------------------------------------------
# Scenario state immutability
# ---------------------------------------------------------------------------


class TestScenarioImmutability:
    def test_scenario_events_tuple(self, tmp_path):
        """Events collection should be a tuple (immutable)."""
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        assert isinstance(s.events, tuple)

    def test_tick_does_not_mutate_scenario(self, tmp_path):
        path = _write_yaml(tmp_path, SPAWN_TARGET_YAML)
        s = load_scenario(path)
        events_before = s.events
        player = ScenarioPlayer(s)
        player.tick(15.0)
        assert s.events is events_before


# ---------------------------------------------------------------------------
# Demo scenario YAML
# ---------------------------------------------------------------------------


class TestDemoScenario:
    def test_demo_yaml_loads(self):
        demo_path = os.path.join(os.path.dirname(__file__), "../../../scenarios/demo.yaml")
        demo_path = os.path.normpath(demo_path)
        s = load_scenario(demo_path)
        assert s.name
        assert s.theater
        assert len(s.events) > 0

    def test_demo_yaml_has_expected_event_types(self):
        demo_path = os.path.join(os.path.dirname(__file__), "../../../scenarios/demo.yaml")
        demo_path = os.path.normpath(demo_path)
        s = load_scenario(demo_path)
        types = {ev.event_type for ev in s.events}
        # Demo should include at least spawning a target and triggering an enemy UAV
        assert "SPAWN_TARGET" in types or "TRIGGER_ENEMY_UAV" in types
