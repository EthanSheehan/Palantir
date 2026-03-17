"""Integration tests for sim_engine with probabilistic sensor model."""

import random
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim_engine import SimulationModel


@pytest.fixture
def sim():
    random.seed(42)
    return SimulationModel()


def _tick_n(sim: SimulationModel, n: int):
    for _ in range(n):
        sim.tick()


class TestProbabilisticDetection:
    def test_some_targets_detected_after_100_ticks(self, sim):
        _tick_n(sim, 100)
        detected = [t for t in sim.targets if t.state != "UNDETECTED"]
        assert len(detected) > 0, "Expected at least one target detected after 100 ticks"

    def test_detected_targets_have_positive_confidence(self, sim):
        _tick_n(sim, 100)
        for t in sim.targets:
            if t.state != "UNDETECTED":
                assert t.detection_confidence > 0, (
                    f"Target {t.id} in state {t.state} has zero confidence"
                )

    def test_undetected_targets_have_zero_confidence(self, sim):
        _tick_n(sim, 100)
        for t in sim.targets:
            if t.state == "UNDETECTED":
                assert t.detection_confidence == 0.0, (
                    f"Target {t.id} is UNDETECTED but confidence={t.detection_confidence}"
                )

    def test_environment_defaults_to_clear_day(self, sim):
        env = sim.environment
        assert env.time_of_day == 12.0
        assert env.cloud_cover == 0.0
        assert env.precipitation == 0.0


class TestSetEnvironment:
    def test_set_environment_updates_conditions(self, sim):
        sim.set_environment(time_of_day=22.0, cloud_cover=0.8, precipitation=0.6)
        assert sim.environment.time_of_day == 22.0
        assert sim.environment.cloud_cover == 0.8
        assert sim.environment.precipitation == 0.6

    def test_bad_weather_reduces_detection_rate(self):
        random.seed(42)
        sim_clear = SimulationModel()
        _tick_n(sim_clear, 200)
        clear_detected = sum(1 for t in sim_clear.targets if t.state != "UNDETECTED")

        random.seed(42)
        sim_bad = SimulationModel()
        sim_bad.set_environment(time_of_day=2.0, cloud_cover=0.9, precipitation=0.8)
        _tick_n(sim_bad, 200)
        bad_detected = sum(1 for t in sim_bad.targets if t.state != "UNDETECTED")

        assert bad_detected <= clear_detected, (
            f"Bad weather detected {bad_detected} >= clear weather {clear_detected}"
        )


class TestCommandsAfterSensorIntegration:
    def _detect_first_target(self, sim):
        """Tick until at least one target is detected, return it."""
        for _ in range(500):
            sim.tick()
            for t in sim.targets:
                if t.state == "DETECTED":
                    return t
        pytest.skip("No target detected after 500 ticks")

    def test_command_view_works(self, sim):
        target = self._detect_first_target(sim)
        uav = sim.uavs[0]
        sim.command_view(uav.id, target.id)
        assert uav.mode == "VIEWING"
        assert uav.tracked_target_id == target.id
        assert target.tracked_by_uav_id == uav.id

    def test_command_follow_works(self, sim):
        target = self._detect_first_target(sim)
        uav = sim.uavs[0]
        sim.command_follow(uav.id, target.id)
        assert uav.mode == "FOLLOWING"
        assert target.tracked_by_uav_id == uav.id

    def test_command_paint_works(self, sim):
        target = self._detect_first_target(sim)
        uav = sim.uavs[0]
        sim.command_paint(uav.id, target.id)
        assert uav.mode == "PAINTING"
        assert target.state == "LOCKED"

    def test_cancel_track_reverts_state(self, sim):
        target = self._detect_first_target(sim)
        uav = sim.uavs[0]
        sim.command_view(uav.id, target.id)
        sim.cancel_track(uav.id)
        assert uav.mode == "SCANNING"
        assert uav.tracked_target_id is None
        assert target.tracked_by_uav_id is None

    def test_tick_runs_after_commands(self, sim):
        target = self._detect_first_target(sim)
        uav = sim.uavs[0]
        sim.command_follow(uav.id, target.id)
        _tick_n(sim, 50)
        state = sim.get_state()
        assert len(state["uavs"]) == sim.NUM_UAVS
        assert len(state["targets"]) == sim.NUM_TARGETS
