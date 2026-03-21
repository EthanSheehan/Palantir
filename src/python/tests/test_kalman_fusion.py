"""
Tests for Kalman fusion tracking in sensor_fusion.py — TDD RED phase.
"""

import pytest
from sensor_fusion import (
    KalmanTracker,
    KalmanTrackState,
    SensorContribution,
    fuse_detections,
)


def _make_contrib(
    uav_id=1,
    sensor_type="EO_IR",
    confidence=0.7,
    range_m=5000.0,
    bearing_deg=45.0,
    timestamp=100.0,
    lat=44.0,
    lon=26.0,
):
    return SensorContribution(
        uav_id=uav_id,
        sensor_type=sensor_type,
        confidence=confidence,
        range_m=range_m,
        bearing_deg=bearing_deg,
        timestamp=timestamp,
        lat=lat,
        lon=lon,
    )


class TestKalmanTrackState:
    def test_is_frozen(self):
        state = KalmanTrackState(
            target_id=1,
            position_estimate=(44.0, 26.0),
            position_covariance=(0.01, 0.01),
            velocity_estimate=(0.0, 0.0),
            last_update_time=100.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            state.target_id = 2  # type: ignore[misc]

    def test_fields(self):
        state = KalmanTrackState(
            target_id=5,
            position_estimate=(44.5, 26.5),
            position_covariance=(0.02, 0.03),
            velocity_estimate=(0.001, -0.001),
            last_update_time=200.0,
        )
        assert state.target_id == 5
        assert state.position_estimate == (44.5, 26.5)
        assert state.position_covariance == (0.02, 0.03)
        assert state.velocity_estimate == (0.001, -0.001)
        assert state.last_update_time == 200.0


class TestKalmanTrackerInit:
    def test_no_tracks_initially(self):
        tracker = KalmanTracker()
        assert tracker.get_track(1) is None

    def test_get_nonexistent_track(self):
        tracker = KalmanTracker()
        assert tracker.get_track(999) is None


class TestKalmanTrackerUpdate:
    def test_single_measurement_creates_track(self):
        tracker = KalmanTracker()
        contribs = [_make_contrib(lat=44.0, lon=26.0, timestamp=100.0)]
        state = tracker.update(target_id=1, measurements=contribs, timestamp=100.0)
        assert state.target_id == 1
        assert state.position_estimate[0] == pytest.approx(44.0, abs=0.1)
        assert state.position_estimate[1] == pytest.approx(26.0, abs=0.1)
        assert state.last_update_time == 100.0

    def test_multiple_updates_reduce_covariance(self):
        tracker = KalmanTracker()
        c1 = [_make_contrib(lat=44.0, lon=26.0, timestamp=100.0)]
        state1 = tracker.update(target_id=1, measurements=c1, timestamp=100.0)

        c2 = [_make_contrib(lat=44.001, lon=26.001, timestamp=101.0)]
        state2 = tracker.update(target_id=1, measurements=c2, timestamp=101.0)

        c3 = [_make_contrib(lat=44.002, lon=26.002, timestamp=102.0)]
        state3 = tracker.update(target_id=1, measurements=c3, timestamp=102.0)

        assert state3.position_covariance[0] <= state1.position_covariance[0]
        assert state3.position_covariance[1] <= state1.position_covariance[1]

    def test_multi_sensor_update(self):
        tracker = KalmanTracker()
        contribs = [
            _make_contrib(sensor_type="EO_IR", lat=44.0, lon=26.0, confidence=0.8, timestamp=100.0),
            _make_contrib(sensor_type="SAR", lat=44.001, lon=26.001, confidence=0.6, timestamp=100.0, uav_id=2),
        ]
        state = tracker.update(target_id=1, measurements=contribs, timestamp=100.0)
        assert state.target_id == 1
        assert state.position_estimate[0] == pytest.approx(44.0, abs=0.05)

    def test_with_realistic_sensor_data(self):
        tracker = KalmanTracker()
        eo = _make_contrib(sensor_type="EO_IR", lat=44.43, lon=26.10, confidence=0.85, range_m=3000, timestamp=50.0)
        sar = _make_contrib(
            sensor_type="SAR", lat=44.431, lon=26.101, confidence=0.6, range_m=8000, timestamp=50.0, uav_id=2
        )
        sigint = _make_contrib(
            sensor_type="SIGINT", lat=44.432, lon=26.099, confidence=0.4, range_m=15000, timestamp=50.0, uav_id=3
        )
        state = tracker.update(target_id=10, measurements=[eo, sar, sigint], timestamp=50.0)
        assert state.target_id == 10
        assert 44.4 < state.position_estimate[0] < 44.5


class TestKalmanTrackerPredict:
    def test_predict_forward(self):
        tracker = KalmanTracker()
        contribs = [_make_contrib(lat=44.0, lon=26.0, timestamp=100.0)]
        tracker.update(target_id=1, measurements=contribs, timestamp=100.0)

        predicted = tracker.predict(target_id=1, dt=5.0)
        assert predicted is not None
        assert predicted.target_id == 1
        assert predicted.last_update_time == pytest.approx(105.0)

    def test_predict_nonexistent_returns_none(self):
        tracker = KalmanTracker()
        assert tracker.predict(target_id=99, dt=1.0) is None


class TestKalmanTrackerRemove:
    def test_remove_track(self):
        tracker = KalmanTracker()
        contribs = [_make_contrib(lat=44.0, lon=26.0, timestamp=100.0)]
        tracker.update(target_id=1, measurements=contribs, timestamp=100.0)
        assert tracker.get_track(1) is not None

        tracker.remove_track(1)
        assert tracker.get_track(1) is None

    def test_remove_nonexistent_is_noop(self):
        tracker = KalmanTracker()
        tracker.remove_track(999)


class TestTemporalDecay:
    def test_stale_contributions_reduced(self):
        tracker = KalmanTracker()
        fresh = _make_contrib(lat=44.0, lon=26.0, confidence=0.8, timestamp=100.0)
        stale = _make_contrib(lat=44.001, lon=26.001, confidence=0.8, timestamp=50.0, uav_id=2, sensor_type="SAR")

        result = fuse_detections([fresh, stale], current_time=100.0)
        stale_only = fuse_detections([stale], current_time=100.0)
        fresh_only = fuse_detections([fresh], current_time=100.0)

        assert stale_only.fused_confidence < fresh_only.fused_confidence
        assert stale_only.fused_confidence == pytest.approx(0.4)

    def test_no_decay_within_threshold(self):
        contrib = _make_contrib(lat=44.0, lon=26.0, confidence=0.8, timestamp=85.0)
        result = fuse_detections([contrib], current_time=100.0)
        assert result.fused_confidence == pytest.approx(0.8)


class TestCrossSensorDisagreement:
    def test_disagreement_flagged_when_positions_differ(self):
        eo = _make_contrib(sensor_type="EO_IR", lat=44.0, lon=26.0, timestamp=100.0)
        sar = _make_contrib(sensor_type="SAR", lat=44.01, lon=26.01, timestamp=100.0, uav_id=2)
        result = fuse_detections([eo, sar])
        assert result.disagreement is True

    def test_no_disagreement_when_positions_close(self):
        eo = _make_contrib(sensor_type="EO_IR", lat=44.0, lon=26.0, timestamp=100.0)
        sar = _make_contrib(sensor_type="SAR", lat=44.0001, lon=26.0001, timestamp=100.0, uav_id=2)
        result = fuse_detections([eo, sar])
        assert result.disagreement is False

    def test_no_disagreement_single_sensor_type(self):
        c1 = _make_contrib(sensor_type="EO_IR", lat=44.0, lon=26.0, timestamp=100.0)
        c2 = _make_contrib(sensor_type="EO_IR", lat=44.01, lon=26.01, timestamp=100.0, uav_id=2)
        result = fuse_detections([c1, c2])
        assert result.disagreement is False


class TestFusedDetectionNewFields:
    def test_position_estimate_optional(self):
        result = fuse_detections([])
        assert result.position_estimate is None
        assert result.position_covariance is None

    def test_position_fields_present(self):
        c = _make_contrib(lat=44.0, lon=26.0)
        result = fuse_detections([c])
        assert result.position_estimate is None or isinstance(result.position_estimate, tuple)

    def test_disagreement_field_default(self):
        result = fuse_detections([])
        assert result.disagreement is False


class TestEmptyAndBadMeasurements:
    def test_empty_measurements(self):
        tracker = KalmanTracker()
        state = tracker.update(target_id=1, measurements=[], timestamp=100.0)
        assert state is None

    def test_nan_measurements_rejected(self):
        tracker = KalmanTracker()
        bad = _make_contrib(lat=float("nan"), lon=float("nan"), timestamp=100.0)
        state = tracker.update(target_id=1, measurements=[bad], timestamp=100.0)
        assert state is None

    def test_inf_measurements_rejected(self):
        tracker = KalmanTracker()
        bad = _make_contrib(lat=float("inf"), lon=float("inf"), timestamp=100.0)
        state = tracker.update(target_id=1, measurements=[bad], timestamp=100.0)
        assert state is None


class TestBackwardCompatibility:
    def test_fuse_detections_without_current_time(self):
        contribs = [
            SensorContribution(
                uav_id=1,
                sensor_type="EO_IR",
                confidence=0.6,
                range_m=5000,
                bearing_deg=0.0,
                timestamp=1.0,
            ),
            SensorContribution(
                uav_id=2,
                sensor_type="SAR",
                confidence=0.5,
                range_m=6000,
                bearing_deg=10.0,
                timestamp=1.0,
            ),
        ]
        result = fuse_detections(contribs)
        assert result.fused_confidence == pytest.approx(0.8)
        assert result.sensor_count == 2

    def test_sensor_contribution_backward_compatible(self):
        old_style = SensorContribution(
            uav_id=1,
            sensor_type="EO_IR",
            confidence=0.7,
            range_m=5000,
            bearing_deg=45.0,
            timestamp=1000.0,
        )
        assert old_style.confidence == 0.7
        assert old_style.lat is None
        assert old_style.lon is None
