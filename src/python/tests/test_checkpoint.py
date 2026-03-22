"""Tests for checkpoint.py — simulation state serialization/restore."""

import json
import os
import sys
import tempfile
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from checkpoint import (
    CHECKPOINT_VERSION,
    CheckpointError,
    load_checkpoint,
    load_from_file,
    save_checkpoint,
    save_to_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sim(tick_count: int = 42) -> MagicMock:
    """Return a mock SimulationModel with a realistic get_state() return."""
    sim = MagicMock()
    sim.tick_count = tick_count
    sim.get_state.return_value = {
        "autonomy_level": "MANUAL",
        "uavs": [
            {
                "id": 0,
                "lon": 26.5,
                "lat": 44.3,
                "mode": "SEARCH",
                "altitude_m": 1500.0,
                "sensor_type": "EO",
                "sensors": ["EO", "IR"],
                "heading_deg": 90.0,
                "tracked_target_id": None,
                "tracked_target_ids": [],
                "primary_target_id": None,
                "fuel_hours": 8.5,
                "autonomy_override": None,
                "mode_source": "operator",
                "tasking_source": "ZONE_BALANCE",
                "pending_transition": None,
                "fov_targets": [],
                "sensor_quality": 0.6,
            }
        ],
        "zones": [
            {
                "x_idx": 0,
                "y_idx": 0,
                "lon": 26.0,
                "lat": 44.0,
                "width": 0.5,
                "height": 0.4,
                "queue": 0,
                "uav_count": 1,
                "imbalance": 0,
            }
        ],
        "flows": [],
        "targets": [
            {
                "id": 0,
                "lon": 26.2,
                "lat": 44.1,
                "type": "SAM",
                "detected": True,
                "state": "DETECTED",
                "detection_confidence": 0.75,
                "detected_by_sensor": "EO",
                "is_emitting": False,
                "heading_deg": 180.0,
                "tracked_by_uav_id": 0,
                "tracked_by_uav_ids": [0],
                "fused_confidence": 0.75,
                "sensor_count": 1,
                "sensor_contributions": [],
                "threat_range_km": 40.0,
                "detection_range_km": None,
                "time_in_state_sec": 5.0,
                "next_threshold": 0.9,
                "concealed": False,
            }
        ],
        "enemy_uavs": [
            {
                "id": 1001,
                "lon": 26.8,
                "lat": 44.5,
                "mode": "RECON",
                "behavior": "recon",
                "heading_deg": 270.0,
                "detected": False,
                "fused_confidence": 0.0,
                "sensor_count": 0,
                "is_jamming": False,
            }
        ],
        "environment": {
            "time_of_day": 12.0,
            "cloud_cover": 0.0,
            "precipitation": 0.0,
        },
        "theater": {
            "name": "romania",
            "bounds": {
                "min_lon": 25.0,
                "max_lon": 30.0,
                "min_lat": 43.5,
                "max_lat": 46.0,
            },
        },
        "swarm_tasks": [],
    }
    return sim


# ---------------------------------------------------------------------------
# save_checkpoint
# ---------------------------------------------------------------------------


class TestSaveCheckpoint:
    def test_returns_dict(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        assert isinstance(result, dict)

    def test_contains_state_key(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        assert "state" in result

    def test_state_matches_get_state_output(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        assert result["state"] == sim.get_state()

    def test_contains_metadata(self):
        sim = _make_sim(tick_count=99)
        result = save_checkpoint(sim)
        assert "metadata" in result
        meta = result["metadata"]
        assert "timestamp" in meta
        assert "tick_count" in meta
        assert "checkpoint_version" in meta

    def test_tick_count_in_metadata(self):
        sim = _make_sim(tick_count=77)
        result = save_checkpoint(sim)
        assert result["metadata"]["tick_count"] == 77

    def test_checkpoint_version_in_metadata(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        assert result["metadata"]["checkpoint_version"] == CHECKPOINT_VERSION

    def test_timestamp_is_recent(self):
        sim = _make_sim()
        before = time.time()
        result = save_checkpoint(sim)
        after = time.time()
        ts = result["metadata"]["timestamp"]
        assert before <= ts <= after

    def test_result_is_json_serializable(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_includes_all_state_fields(self):
        sim = _make_sim()
        result = save_checkpoint(sim)
        state = result["state"]
        for key in ("uavs", "targets", "zones", "enemy_uavs"):
            assert key in state, f"Missing key: {key}"

    def test_tick_count_zero_by_default(self):
        sim = MagicMock()
        sim.get_state.return_value = {"uavs": [], "targets": [], "zones": [], "enemy_uavs": []}
        del sim.tick_count  # simulate missing attribute
        sim.tick_count = 0
        result = save_checkpoint(sim)
        assert result["metadata"]["tick_count"] == 0


# ---------------------------------------------------------------------------
# load_checkpoint
# ---------------------------------------------------------------------------


class TestLoadCheckpoint:
    def test_load_valid_checkpoint_returns_dict(self):
        sim = _make_sim()
        blob = save_checkpoint(sim)
        result = load_checkpoint(blob)
        assert isinstance(result, dict)

    def test_load_returns_state(self):
        sim = _make_sim()
        blob = save_checkpoint(sim)
        result = load_checkpoint(blob)
        assert "state" in result
        assert "metadata" in result

    def test_load_invalid_json_raises(self):
        with pytest.raises(CheckpointError, match="Invalid"):
            load_checkpoint("not a dict")

    def test_load_missing_state_key_raises(self):
        bad_blob = {"metadata": {"checkpoint_version": CHECKPOINT_VERSION, "tick_count": 0, "timestamp": 0.0}}
        with pytest.raises(CheckpointError, match="Missing"):
            load_checkpoint(bad_blob)

    def test_load_missing_metadata_raises(self):
        bad_blob = {"state": {}}
        with pytest.raises(CheckpointError, match="Missing"):
            load_checkpoint(bad_blob)

    def test_load_incompatible_version_raises(self):
        sim = _make_sim()
        blob = save_checkpoint(sim)
        blob["metadata"]["checkpoint_version"] = 9999
        with pytest.raises(CheckpointError, match="[Vv]ersion"):
            load_checkpoint(blob)

    def test_round_trip_state_identical(self):
        sim = _make_sim()
        saved = save_checkpoint(sim)
        loaded = load_checkpoint(saved)
        assert loaded["state"] == sim.get_state()

    def test_round_trip_metadata_preserved(self):
        sim = _make_sim(tick_count=55)
        saved = save_checkpoint(sim)
        loaded = load_checkpoint(saved)
        assert loaded["metadata"]["tick_count"] == 55
        assert loaded["metadata"]["checkpoint_version"] == CHECKPOINT_VERSION


# ---------------------------------------------------------------------------
# Round-trip: save → load → save produces identical output
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_double_round_trip_identical(self):
        sim = _make_sim(tick_count=10)
        first_save = save_checkpoint(sim)
        loaded = load_checkpoint(first_save)

        # Build a second mock sim from the loaded state
        sim2 = MagicMock()
        sim2.tick_count = loaded["metadata"]["tick_count"]
        sim2.get_state.return_value = loaded["state"]

        second_save = save_checkpoint(sim2)
        assert first_save["state"] == second_save["state"]
        assert first_save["metadata"]["tick_count"] == second_save["metadata"]["tick_count"]
        assert first_save["metadata"]["checkpoint_version"] == second_save["metadata"]["checkpoint_version"]


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


class TestFileIO:
    def test_save_to_file_creates_file(self):
        sim = _make_sim()
        blob = save_checkpoint(sim)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_to_file(blob, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_save_to_file_writes_valid_json(self):
        sim = _make_sim()
        blob = save_checkpoint(sim)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_to_file(blob, path)
            with open(path) as fh:
                data = json.load(fh)
            assert "state" in data
            assert "metadata" in data
        finally:
            os.unlink(path)

    def test_load_from_file_restores_checkpoint(self):
        sim = _make_sim(tick_count=33)
        blob = save_checkpoint(sim)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_to_file(blob, path)
            loaded = load_from_file(path)
            assert loaded["metadata"]["tick_count"] == 33
            assert loaded["state"] == sim.get_state()
        finally:
            os.unlink(path)

    def test_load_from_file_missing_file_raises(self):
        with pytest.raises((FileNotFoundError, CheckpointError)):
            load_from_file("/tmp/nonexistent_checkpoint_99999.json")

    def test_load_from_file_corrupt_json_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{not valid json")
            path = f.name
        try:
            with pytest.raises(CheckpointError):
                load_from_file(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Golden snapshot — known state → known JSON structure
# ---------------------------------------------------------------------------


class TestGoldenSnapshot:
    def test_golden_snapshot_schema(self):
        """Known sim state → checkpoint has expected top-level schema."""
        sim = _make_sim(tick_count=1)
        blob = save_checkpoint(sim)

        # Top-level keys
        assert set(blob.keys()) == {"state", "metadata"}

        # Metadata keys
        assert set(blob["metadata"].keys()) >= {"timestamp", "tick_count", "checkpoint_version"}

        # State has required top-level keys
        state = blob["state"]
        for key in ("uavs", "targets", "zones", "enemy_uavs", "environment", "theater"):
            assert key in state, f"Golden snapshot missing state key: {key}"

        # UAV shape
        uav = state["uavs"][0]
        for field in ("id", "lon", "lat", "mode", "fuel_hours"):
            assert field in uav, f"UAV missing field: {field}"

        # Target shape
        target = state["targets"][0]
        for field in ("id", "lon", "lat", "type", "state", "fused_confidence"):
            assert field in target, f"Target missing field: {field}"

        # Enemy UAV shape
        enemy = state["enemy_uavs"][0]
        for field in ("id", "lon", "lat", "mode", "is_jamming"):
            assert field in enemy, f"EnemyUAV missing field: {field}"


# ---------------------------------------------------------------------------
# Large state serialization (performance sanity)
# ---------------------------------------------------------------------------


class TestLargeStateSerialization:
    def test_large_state_serializes_quickly(self):
        """Checkpoint with 200 UAVs and 500 targets completes in < 2 seconds."""
        sim = MagicMock()
        sim.tick_count = 10000
        sim.get_state.return_value = {
            "autonomy_level": "SUPERVISED",
            "uavs": [{"id": i, "lon": 26.0 + i * 0.001, "lat": 44.0, "mode": "SEARCH"} for i in range(200)],
            "zones": [],
            "flows": [],
            "targets": [{"id": i, "lon": 26.0, "lat": 44.0, "type": "SAM", "state": "DETECTED"} for i in range(500)],
            "enemy_uavs": [{"id": 1000 + i, "lon": 27.0, "lat": 44.0, "mode": "RECON"} for i in range(50)],
            "environment": {"time_of_day": 12.0, "cloud_cover": 0.0, "precipitation": 0.0},
            "theater": {"name": "romania", "bounds": {}},
            "swarm_tasks": [],
        }

        start = time.time()
        blob = save_checkpoint(sim)
        serialized = json.dumps(blob)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Serialization took {elapsed:.2f}s, expected < 2s"
        assert len(serialized) > 100
