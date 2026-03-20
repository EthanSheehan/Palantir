"""
test_adaptive_isr.py
====================
Unit tests for the ISR priority queue builder (isr_priority.py).
TDD RED phase — all tests import from isr_priority which does not yet exist.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from isr_priority import build_isr_queue, ISRRequirement, THREAT_WEIGHTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_target(
    id: int,
    type: str,
    fused_confidence: float,
    state: str = "DETECTED",
    sensor_contributions=None,
    time_in_state_sec: float = 0.0,
    lon: float = 28.0,
    lat: float = 44.0,
) -> dict:
    if sensor_contributions is None:
        sensor_contributions = []
    return {
        "id": id,
        "lon": lon,
        "lat": lat,
        "type": type,
        "state": state,
        "fused_confidence": fused_confidence,
        "sensor_count": len(sensor_contributions),
        "sensor_contributions": sensor_contributions,
        "time_in_state_sec": time_in_state_sec,
    }


def make_uav(
    id: int,
    mode: str = "IDLE",
    sensors=None,
    lon: float = 28.0,
    lat: float = 44.0,
) -> dict:
    if sensors is None:
        sensors = ["EO_IR"]
    return {
        "id": id,
        "lon": lon,
        "lat": lat,
        "mode": mode,
        "sensors": sensors,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildISRQueue:

    def test_isr_queue_ranking(self):
        """SAM at 0.3 confidence ranks above TRUCK at 0.3 confidence."""
        targets = [
            make_target(1, "TRUCK", 0.3),
            make_target(2, "SAM", 0.3),
        ]
        result = build_isr_queue(targets, [])
        assert len(result) == 2
        assert result[0].target_id == 2  # SAM first
        assert result[1].target_id == 1  # TRUCK second

    def test_threat_weight_ordering(self):
        """THREAT_WEIGHTS ordering: SAM > TEL > MANPADS > RADAR > TRUCK > LOGISTICS."""
        assert THREAT_WEIGHTS["SAM"] > THREAT_WEIGHTS["TEL"]
        assert THREAT_WEIGHTS["TEL"] > THREAT_WEIGHTS["MANPADS"]
        assert THREAT_WEIGHTS["MANPADS"] > THREAT_WEIGHTS["RADAR"]
        assert THREAT_WEIGHTS["RADAR"] > THREAT_WEIGHTS["TRUCK"]
        assert THREAT_WEIGHTS["TRUCK"] > THREAT_WEIGHTS["LOGISTICS"]
        # Specific canonical values
        assert THREAT_WEIGHTS["SAM"] == 1.0
        assert THREAT_WEIGHTS["LOGISTICS"] == 0.3

    def test_empty_state(self):
        """Empty targets list returns empty queue without exception."""
        result = build_isr_queue([], [])
        assert result == []

    def test_verified_targets_low_urgency(self):
        """Target with fused_confidence=0.9 has urgency_score < 0.15."""
        targets = [make_target(1, "SAM", 0.9, state="VERIFIED")]
        result = build_isr_queue(targets, [])
        assert len(result) == 1
        assert result[0].urgency_score < 0.15

    def test_max_requirements(self):
        """5 targets with max_requirements=2 returns exactly 2 items."""
        targets = [make_target(i, "TRUCK", 0.3) for i in range(5)]
        result = build_isr_queue(targets, [], max_requirements=2)
        assert len(result) == 2

    def test_missing_sensor_types(self):
        """Target with EO_IR contribution is missing SAR and SIGINT."""
        contributions = [{"uav_id": 1, "sensor_type": "EO_IR", "confidence": 0.5}]
        targets = [make_target(1, "SAM", 0.5, sensor_contributions=contributions)]
        result = build_isr_queue(targets, [])
        assert len(result) == 1
        missing = result[0].missing_sensor_types
        assert "EO_IR" not in missing
        assert "SAR" in missing
        assert "SIGINT" in missing

    def test_recommended_uav_ids_idle_only(self):
        """IDLE UAV with matching sensor is recommended; non-IDLE UAV is excluded."""
        contributions = [{"uav_id": 1, "sensor_type": "EO_IR", "confidence": 0.5}]
        targets = [make_target(1, "SAM", 0.4, sensor_contributions=contributions)]
        uavs = [
            make_uav(10, mode="IDLE", sensors=["SAR"]),      # IDLE, has SAR (missing)
            make_uav(11, mode="FOLLOW", sensors=["SAR"]),    # busy, should be excluded
            make_uav(12, mode="IDLE", sensors=["EO_IR"]),    # IDLE but EO_IR already contributing
        ]
        result = build_isr_queue(targets, uavs)
        assert len(result) == 1
        recommended = result[0].recommended_uav_ids
        assert 10 in recommended      # IDLE with SAR
        assert 11 not in recommended  # non-IDLE

    def test_min_idle_constraint(self):
        """Non-IDLE UAVs are never included in recommended_uav_ids."""
        targets = [make_target(1, "TEL", 0.2)]
        uavs = [
            make_uav(1, mode="FOLLOW", sensors=["EO_IR"]),
            make_uav(2, mode="PAINT", sensors=["SAR"]),
            make_uav(3, mode="INTERCEPT", sensors=["SIGINT"]),
        ]
        result = build_isr_queue(targets, uavs)
        assert len(result) == 1
        assert result[0].recommended_uav_ids == ()

    def test_destroyed_excluded(self):
        """DESTROYED targets not in queue."""
        targets = [
            make_target(1, "SAM", 0.3, state="DESTROYED"),
            make_target(2, "TEL", 0.3, state="DETECTED"),
        ]
        result = build_isr_queue(targets, [])
        ids = [r.target_id for r in result]
        assert 1 not in ids
        assert 2 in ids

    def test_escaped_excluded(self):
        """ESCAPED targets not in queue."""
        targets = [
            make_target(1, "SAM", 0.3, state="ESCAPED"),
            make_target(2, "TEL", 0.3, state="DETECTED"),
        ]
        result = build_isr_queue(targets, [])
        ids = [r.target_id for r in result]
        assert 1 not in ids
        assert 2 in ids

    def test_undetected_excluded(self):
        """UNDETECTED targets not in queue."""
        targets = [
            make_target(1, "SAM", 0.0, state="UNDETECTED"),
            make_target(2, "TEL", 0.3, state="DETECTED"),
        ]
        result = build_isr_queue(targets, [])
        ids = [r.target_id for r in result]
        assert 1 not in ids
        assert 2 in ids

    def test_time_factor(self):
        """Target stuck for 60s scores higher than same target at 0s."""
        t_new = make_target(1, "SAM", 0.5, time_in_state_sec=0.0)
        t_old = make_target(2, "SAM", 0.5, time_in_state_sec=60.0)
        result = build_isr_queue([t_new, t_old], [])
        assert len(result) == 2
        # t_old (id=2) should rank first (higher urgency)
        assert result[0].target_id == 2
        assert result[0].urgency_score > result[1].urgency_score

    def test_frozen_dataclass(self):
        """ISRRequirement is immutable (frozen=True)."""
        req = ISRRequirement(
            target_id=1,
            target_type="SAM",
            urgency_score=0.5,
            verification_gap=0.5,
            missing_sensor_types=("SAR",),
            recommended_uav_ids=(1, 2),
        )
        with pytest.raises((AttributeError, TypeError)):
            req.urgency_score = 0.99  # type: ignore

    def test_verification_gap_field(self):
        """verification_gap = 1.0 - fused_confidence."""
        targets = [make_target(1, "SAM", 0.6)]
        result = build_isr_queue(targets, [])
        assert len(result) == 1
        assert abs(result[0].verification_gap - 0.4) < 0.001

    def test_assessment_result_accepted(self):
        """build_isr_queue accepts optional assessment_result dict without error."""
        targets = [make_target(1, "SAM", 0.3)]
        assessment = {
            "coverage_gaps": [],
            "zone_threat_scores": [],
            "clusters": [],
            "movement_corridors": [],
        }
        result = build_isr_queue(targets, [], assessment_result=assessment)
        assert len(result) == 1

    def test_returns_isrrequirement_instances(self):
        """Each element in the returned list is an ISRRequirement instance."""
        targets = [make_target(1, "TEL", 0.4)]
        result = build_isr_queue(targets, [])
        assert len(result) == 1
        assert isinstance(result[0], ISRRequirement)


# ---------------------------------------------------------------------------
# TestCoverageMode — tests for sim_engine.py coverage_mode + adaptive dispatch
# ---------------------------------------------------------------------------

from sim_engine import SimulationModel, UAV


def _make_sim_with_idle_uavs(n_idle: int = 5) -> SimulationModel:
    """Create a minimal SimulationModel with n_idle UAVs all set to IDLE."""
    sim = SimulationModel()
    # Trim to n_idle UAVs
    sim.uavs = sim.uavs[:n_idle]
    for u in sim.uavs:
        u.mode = "IDLE"
        u.x = 28.0
        u.y = 44.0
    return sim


class TestCoverageMode:

    def test_coverage_mode_default(self):
        """SimulationModel().coverage_mode == 'balanced' by default."""
        sim = SimulationModel()
        assert sim.coverage_mode == "balanced"

    def test_set_coverage_mode_valid(self):
        """set_coverage_mode('threat_adaptive') sets coverage_mode."""
        sim = SimulationModel()
        sim.set_coverage_mode("threat_adaptive")
        assert sim.coverage_mode == "threat_adaptive"

    def test_set_coverage_mode_back_to_balanced(self):
        """set_coverage_mode('balanced') switches back."""
        sim = SimulationModel()
        sim.set_coverage_mode("threat_adaptive")
        sim.set_coverage_mode("balanced")
        assert sim.coverage_mode == "balanced"

    def test_set_coverage_mode_invalid(self):
        """set_coverage_mode with unknown value does not change coverage_mode."""
        sim = SimulationModel()
        sim.set_coverage_mode("invalid_mode")
        assert sim.coverage_mode == "balanced"

    def test_last_assessment_default_none(self):
        """sim._last_assessment is None at initialisation."""
        sim = SimulationModel()
        assert sim._last_assessment is None

    def test_threat_adaptive_dispatches_empty_assessment(self):
        """_threat_adaptive_dispatches() returns [] when _last_assessment is None."""
        sim = _make_sim_with_idle_uavs(5)
        assert sim._last_assessment is None
        result = sim._threat_adaptive_dispatches()
        assert result == []

    def test_min_idle_constraint(self):
        """_threat_adaptive_dispatches() returns [] when idle UAVs <= MIN_IDLE_COUNT (3)."""
        from sim_engine import MIN_IDLE_COUNT
        sim = _make_sim_with_idle_uavs(MIN_IDLE_COUNT)
        sim._last_assessment = {
            "coverage_gaps": [{"zone_x": 0, "zone_y": 0, "lon": 29.0, "lat": 45.0, "threat_score": 0.9}],
        }
        result = sim._threat_adaptive_dispatches()
        assert result == []

    def test_threat_adaptive_dispatches_targets_gap(self):
        """With idle > MIN_IDLE_COUNT and coverage_gaps, dispatches UAV toward gap."""
        sim = _make_sim_with_idle_uavs(5)
        gap_lon, gap_lat = 29.5, 45.5
        sim._last_assessment = {
            "coverage_gaps": [{"zone_x": 0, "zone_y": 0, "lon": gap_lon, "lat": gap_lat, "threat_score": 0.8}],
        }
        dispatches = sim._threat_adaptive_dispatches()
        assert len(dispatches) == 1
        assert dispatches[0]["target_coord"] == (gap_lon, gap_lat)

    def test_threat_adaptive_dispatches_empty_gaps(self):
        """With empty coverage_gaps list, returns no dispatches."""
        sim = _make_sim_with_idle_uavs(5)
        sim._last_assessment = {"coverage_gaps": []}
        result = sim._threat_adaptive_dispatches()
        assert result == []

    def test_tasking_source_default(self):
        """UAV.tasking_source defaults to 'ZONE_BALANCE'."""
        sim = SimulationModel()
        for u in sim.uavs:
            assert u.tasking_source == "ZONE_BALANCE"

    def test_tasking_source_in_get_state(self):
        """get_state() UAV dicts contain 'tasking_source' key."""
        sim = SimulationModel()
        state = sim.get_state()
        for uav_dict in state["uavs"]:
            assert "tasking_source" in uav_dict
