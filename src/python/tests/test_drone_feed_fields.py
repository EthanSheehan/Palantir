"""Tests for fov_targets and sensor_quality fields added to UAV serialization in get_state()."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim_engine import SimulationModel


@pytest.fixture
def sim():
    return SimulationModel()


class TestFovTargetsAndSensorQuality:
    def test_fov_targets_and_sensor_quality(self, sim):
        """get_state() UAV dicts must include fov_targets and sensor_quality."""
        # Run enough ticks to populate detection state
        for _ in range(200):
            sim.tick()

        state = sim.get_state()

        for uav in state["uavs"]:
            # fov_targets must be present and be a list
            assert "fov_targets" in uav, f"UAV {uav['id']} missing fov_targets"
            assert isinstance(uav["fov_targets"], list), f"UAV {uav['id']} fov_targets is not a list"
            # all entries must be ints
            for tid in uav["fov_targets"]:
                assert isinstance(tid, int), f"UAV {uav['id']} fov_targets contains non-int: {tid}"

            # sensor_quality must be present and be a float in [0, 1]
            assert "sensor_quality" in uav, f"UAV {uav['id']} missing sensor_quality"
            sq = uav["sensor_quality"]
            assert isinstance(sq, float), f"UAV {uav['id']} sensor_quality is not a float: {type(sq)}"
            assert 0.0 <= sq <= 1.0, f"UAV {uav['id']} sensor_quality out of range: {sq}"

    def test_sensor_quality_paint_mode(self, sim):
        """PAINT mode UAV must have sensor_quality == 1.0."""
        # Force a UAV into PAINT mode by commanding it
        uav = sim.uavs[0]
        uav.mode = "PAINT"

        state = sim.get_state()
        uav_dict = next(u for u in state["uavs"] if u["id"] == uav.id)
        assert uav_dict["sensor_quality"] == 1.0

    def test_sensor_quality_follow_mode(self, sim):
        """FOLLOW mode UAV must have sensor_quality == 0.8."""
        uav = sim.uavs[0]
        uav.mode = "FOLLOW"

        state = sim.get_state()
        uav_dict = next(u for u in state["uavs"] if u["id"] == uav.id)
        assert uav_dict["sensor_quality"] == 0.8

    def test_sensor_quality_other_mode(self, sim):
        """SEARCH mode (non-special) UAV must have sensor_quality == 0.6."""
        uav = sim.uavs[0]
        uav.mode = "SEARCH"

        state = sim.get_state()
        uav_dict = next(u for u in state["uavs"] if u["id"] == uav.id)
        assert uav_dict["sensor_quality"] == 0.6

    def test_fov_targets_contains_detected_targets_in_range(self, sim):
        """fov_targets must include IDs of detected targets within detection range."""
        # Run long enough for detections
        for _ in range(500):
            sim.tick()

        state = sim.get_state()

        # Verify: any UAV with non-empty fov_targets only contains detected (non-UNDETECTED) target IDs
        detected_ids = {t["id"] for t in state["targets"] if t["state"] != "UNDETECTED"}

        for uav_dict in state["uavs"]:
            for tid in uav_dict["fov_targets"]:
                assert tid in detected_ids, f"UAV {uav_dict['id']} fov_targets contains undetected target ID {tid}"
