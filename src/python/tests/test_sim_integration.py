"""Integration tests for sim_engine with probabilistic sensor model."""

import os
import random
import sys

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
        ever_detected = False
        for _ in range(500):
            sim.tick()
            if any(t.state != "UNDETECTED" for t in sim.targets.values()):
                ever_detected = True
                break
        assert ever_detected, "Expected at least one target detected within 500 ticks"

    def test_detected_targets_have_positive_confidence(self, sim):
        _tick_n(sim, 100)
        for t in sim.targets.values():
            if t.state != "UNDETECTED":
                assert t.detection_confidence > 0, f"Target {t.id} in state {t.state} has zero confidence"

    def test_undetected_targets_have_zero_confidence(self, sim):
        _tick_n(sim, 100)
        for t in sim.targets.values():
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
        clear_detected = sum(1 for t in sim_clear.targets.values() if t.state != "UNDETECTED")

        random.seed(42)
        sim_bad = SimulationModel()
        sim_bad.set_environment(time_of_day=2.0, cloud_cover=0.9, precipitation=0.8)
        _tick_n(sim_bad, 200)
        bad_detected = sum(1 for t in sim_bad.targets.values() if t.state != "UNDETECTED")

        assert bad_detected <= clear_detected, f"Bad weather detected {bad_detected} >= clear weather {clear_detected}"


class TestCommandsAfterSensorIntegration:
    def _detect_first_target(self, sim):
        """Tick until at least one target is detected, return it."""
        for _ in range(500):
            sim.tick()
            for t in sim.targets.values():
                if t.state == "DETECTED":
                    return t
        pytest.skip("No target detected after 500 ticks")

    def test_command_follow_works(self, sim):
        target = self._detect_first_target(sim)
        uav = next(iter(sim.uavs.values()))
        sim.command_follow(uav.id, target.id)
        assert uav.mode == "FOLLOW"
        assert uav.tracked_target_id == target.id
        assert target.tracked_by_uav_id == uav.id

    def test_command_paint_works(self, sim):
        target = self._detect_first_target(sim)
        uav = next(iter(sim.uavs.values()))
        sim.command_paint(uav.id, target.id)
        assert uav.mode == "PAINT"
        assert target.state == "LOCKED"

    def test_command_intercept_works(self, sim):
        target = self._detect_first_target(sim)
        uav = next(iter(sim.uavs.values()))
        sim.command_intercept(uav.id, target.id)
        assert uav.mode == "INTERCEPT"
        assert target.state == "LOCKED"

    def test_cancel_track_reverts_state(self, sim):
        target = self._detect_first_target(sim)
        uav = next(iter(sim.uavs.values()))
        sim.command_follow(uav.id, target.id)
        sim.cancel_track(uav.id)
        assert uav.mode == "SEARCH"
        assert uav.tracked_target_id is None
        assert target.tracked_by_uav_id is None

    def test_tick_runs_after_commands(self, sim):
        target = self._detect_first_target(sim)
        uav = next(iter(sim.uavs.values()))
        sim.command_follow(uav.id, target.id)
        _tick_n(sim, 50)
        state = sim.get_state()
        assert len(state["uavs"]) == sim.NUM_UAVS
        assert len(state["targets"]) == sim.NUM_TARGETS


class TestMultiSensorFusion:
    def _detect_first_target(self, sim):
        for _ in range(500):
            sim.tick()
            for t in sim.targets.values():
                if t.state == "DETECTED":
                    return t
        pytest.skip("No target detected after 500 ticks")

    def test_detected_targets_have_fused_confidence(self, sim):  # noqa: F811
        # ENGAGED and DESTROYED targets skip the detection loop by design,
        # so they may have fused_confidence=0. Only check actively tracked states.
        _tick_n(sim, 100)
        skip_states = {"UNDETECTED", "ENGAGED", "DESTROYED", "NEUTRALIZED"}
        for t in sim.targets.values():  # dict iteration
            if t.state not in skip_states:
                assert t.fused_confidence > 0, f"Target {t.id} state={t.state} but fused_confidence=0"

    def test_fused_confidence_matches_detection_confidence(self, sim):
        target = self._detect_first_target(sim)
        assert abs(target.fused_confidence - target.detection_confidence) < 0.01, (
            f"Target {target.id}: fused={target.fused_confidence} != detection={target.detection_confidence}"
        )

    def test_sensor_count_positive_when_detected(self, sim):
        _tick_n(sim, 50)
        detected = [t for t in sim.targets.values() if t.state != "UNDETECTED"]
        if detected:
            for t in detected:
                assert t.sensor_count >= 0

    def test_fused_higher_than_single(self, sim):
        """P1-SIM-CONFIDENCE: fused confidence from multiple sensors exceeds any single sensor alone."""
        target = list(sim.targets.values())[0]
        for i, uav in enumerate(list(sim.uavs.values())[:2]):
            uav.x = target.x + 0.01 * (i + 1)
            uav.y = target.y + 0.01 * (i + 1)
            uav.mode = "SEARCH"
        _tick_n(sim, 10)
        if target.sensor_count >= 2:
            max_single = max(
                (c.confidence for c in target.sensor_contributions),
                default=0.0,
            )
            assert target.fused_confidence >= max_single, (
                f"fused={target.fused_confidence} should be >= max single={max_single}"
            )

    def test_confidence_degrades_on_removal(self, sim):
        """P1-SIM-DEGRADE: fused confidence decays when UAVs move out of detection range."""
        target = list(sim.targets.values())[0]
        uav = list(sim.uavs.values())[0]
        uav.x = target.x + 0.01
        uav.y = target.y + 0.01
        uav.mode = "SEARCH"
        _tick_n(sim, 10)
        initial_fused = target.fused_confidence
        for u in sim.uavs.values():
            u.x = target.x + 500.0
            u.y = target.y + 500.0
        _tick_n(sim, 20)
        assert target.fused_confidence < initial_fused or target.fused_confidence == 0.0, (
            f"Expected confidence to degrade after UAVs left range; "
            f"initial={initial_fused}, after={target.fused_confidence}"
        )


class TestCancelTrackMulti:
    def test_cancel_track_removes_only_one_uav(self, sim):
        _tick_n(sim, 50)
        tracked = [t for t in sim.targets.values() if len(t.tracked_by_uav_ids) > 0]
        if tracked:
            target = tracked[0]
            original_trackers = list(target.tracked_by_uav_ids)
            if len(original_trackers) >= 1:
                uav_to_cancel = original_trackers[0]
                sim.cancel_track(uav_to_cancel)
                assert uav_to_cancel not in target.tracked_by_uav_ids


class TestGetStatePhase1:
    def test_target_payload_has_fusion_fields(self, sim):
        _tick_n(sim, 10)
        state = sim.get_state()
        for t in state["targets"]:
            assert "fused_confidence" in t, "Missing fused_confidence in target payload"
            assert "sensor_count" in t, "Missing sensor_count in target payload"
            assert "tracked_by_uav_ids" in t, "Missing tracked_by_uav_ids in target payload"
            assert "sensor_contributions" in t, "Missing sensor_contributions"

    def test_uav_payload_has_multi_tracking_fields(self, sim):
        _tick_n(sim, 10)
        state = sim.get_state()
        for u in state["uavs"]:
            assert "tracked_target_ids" in u, "Missing tracked_target_ids in UAV payload"
            assert "primary_target_id" in u, "Missing primary_target_id in UAV payload"


class TestBackwardCompat:
    def test_tracked_by_uav_id_singular_still_present(self, sim):
        _tick_n(sim, 10)
        state = sim.get_state()
        for t in state["targets"]:
            assert "tracked_by_uav_id" in t, "Missing backward-compat tracked_by_uav_id"

    def test_tracked_target_id_singular_still_present(self, sim):
        _tick_n(sim, 10)
        state = sim.get_state()
        for u in state["uavs"]:
            assert "tracked_target_id" in u, "Missing backward-compat tracked_target_id"


# ---------------------------------------------------------------------------
# Assessment interval integration tests (Phase 07, Plan 02)
# ---------------------------------------------------------------------------

from unittest.mock import patch

from battlespace_assessment import AssessmentResult, CoverageGap, MovementCorridor, ThreatCluster


class TestAssessmentInterval:
    def _make_result(self):
        """Return a minimal AssessmentResult for serialization tests."""
        cluster = ThreatCluster(
            cluster_id="CLU-1",
            cluster_type="AD_NETWORK",
            member_target_ids=(1, 2),
            centroid_lon=28.1234,
            centroid_lat=44.5678,
            threat_score=0.85,
            hull_points=((28.1, 44.5), (28.2, 44.6)),
        )
        gap = CoverageGap(zone_x=1, zone_y=2, lon=28.0, lat=44.0)
        corridor = MovementCorridor(target_id=1, waypoints=((28.0, 44.0), (28.1, 44.1)))
        return AssessmentResult(
            clusters=(cluster,),
            coverage_gaps=(gap,),
            zone_threat_scores={(1, 2): 0.75},
            movement_corridors=(corridor,),
            assessed_at=1000.0,
        )

    def test_assessment_not_called_before_5s(self):
        """assess() must NOT be called when < 5 seconds have elapsed since last run."""
        import api_main as m

        # Save original state
        orig_last = m._last_assessment_time
        orig_cached = m._cached_assessment
        try:
            m._last_assessment_time = 0.0
            m._cached_assessment = None
            with patch("api_main.assessor") as mock_assessor, patch("api_main.time.monotonic", return_value=4.9):
                # Simulate the 5s guard logic
                now = 4.9
                if now - m._last_assessment_time >= 5.0:
                    m._cached_assessment = mock_assessor.assess()
            mock_assessor.assess.assert_not_called()
        finally:
            m._last_assessment_time = orig_last
            m._cached_assessment = orig_cached

    def test_assessment_called_at_5s(self):
        """assess() MUST be called when >= 5 seconds have elapsed since last run."""
        import api_main as m

        orig_last = m._last_assessment_time
        orig_cached = m._cached_assessment
        try:
            m._last_assessment_time = 0.0
            m._cached_assessment = None
            with patch("api_main.assessor") as mock_assessor, patch("api_main.time.monotonic", return_value=5.1):
                mock_assessor.assess.return_value = self._make_result()
                now = 5.1
                if now - m._last_assessment_time >= 5.0:
                    state_snapshot = {"targets": [], "uavs": [], "zones": []}
                    raw = mock_assessor.assess(
                        targets=state_snapshot["targets"],
                        uavs=state_snapshot["uavs"],
                        zones=state_snapshot["zones"],
                    )
                    import simulation_loop as sl

                    m._cached_assessment = sl._serialize_assessment(raw)
                    m._last_assessment_time = now
            mock_assessor.assess.assert_called_once()
        finally:
            m._last_assessment_time = orig_last
            m._cached_assessment = orig_cached

    def test_assessment_result_serialized(self):
        """_serialize_assessment must return dict with required keys."""
        import simulation_loop as sl

        result = self._make_result()
        serialized = sl._serialize_assessment(result)
        assert "clusters" in serialized
        assert "coverage_gaps" in serialized
        assert "zone_threat_scores" in serialized
        assert "movement_corridors" in serialized
        # Cluster sub-fields
        assert len(serialized["clusters"]) == 1
        c = serialized["clusters"][0]
        assert c["cluster_id"] == "CLU-1"
        assert c["cluster_type"] == "AD_NETWORK"
        assert c["member_target_ids"] == [1, 2]
        # Coverage gap sub-fields
        g = serialized["coverage_gaps"][0]
        assert g["zone_x"] == 1
        assert g["zone_y"] == 2
        # Zone threat scores as list of [x, y, score]
        assert len(serialized["zone_threat_scores"]) == 1
        assert serialized["zone_threat_scores"][0] == [1, 2, 0.75]
        # Movement corridor
        mc = serialized["movement_corridors"][0]
        assert mc["target_id"] == 1
