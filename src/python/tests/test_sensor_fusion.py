"""
Tests for sensor_fusion.py — written FIRST (TDD RED phase).

All tests must fail before sensor_fusion.py exists, then pass after implementation.
"""

from dataclasses import FrozenInstanceError

import pytest
from sensor_fusion import SensorContribution, fuse_detections

# ---------------------------------------------------------------------------
# TestFuseDetections
# ---------------------------------------------------------------------------


class TestFuseDetections:
    def test_empty_contributions(self):
        result = fuse_detections([])
        assert result.fused_confidence == 0.0
        assert result.sensor_count == 0
        assert result.sensor_types == ()
        assert result.contributing_uav_ids == ()
        assert result.contributions == ()

    def test_single_contribution(self):
        contrib = SensorContribution(
            uav_id=1,
            sensor_type="EO_IR",
            confidence=0.7,
            range_m=5000,
            bearing_deg=45.0,
            timestamp=1000.0,
        )
        result = fuse_detections([contrib])
        assert result.fused_confidence == pytest.approx(0.7)
        assert result.sensor_count == 1

    def test_two_types_fuse_higher(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.6, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="SAR", confidence=0.5, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        # 1 - (1-0.6)*(1-0.5) = 1 - 0.4*0.5 = 0.8
        assert result.fused_confidence == pytest.approx(0.8)

    def test_three_types(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.6, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="SAR", confidence=0.5, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=3, sensor_type="SIGINT", confidence=0.4, range_m=7000, bearing_deg=20.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        # 1 - (1-0.6)*(1-0.5)*(1-0.4) = 1 - 0.4*0.5*0.6 = 1 - 0.12 = 0.88
        assert result.fused_confidence == pytest.approx(0.88)

    def test_same_type_uses_max(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.6, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="EO_IR", confidence=0.4, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        # max(EO_IR) = 0.6, only one type so fused = 0.6
        assert result.fused_confidence == pytest.approx(0.6)

    def test_same_type_plus_different(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.6, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="EO_IR", confidence=0.4, range_m=5500, bearing_deg=5.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=3, sensor_type="SAR", confidence=0.5, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        # max(EO_IR)=0.6, SAR=0.5, fused=1-(0.4*0.5)=0.8
        assert result.fused_confidence == pytest.approx(0.8)

    def test_confidence_bounded(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.99, range_m=100, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="SAR", confidence=0.99, range_m=200, bearing_deg=10.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=3, sensor_type="SIGINT", confidence=0.99, range_m=300, bearing_deg=20.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        assert 0.0 <= result.fused_confidence <= 1.0

    def test_confidence_zero(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.0, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="SAR", confidence=0.0, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        assert result.fused_confidence == pytest.approx(0.0)

    def test_contributing_uav_ids_sorted(self):
        contribs = [
            SensorContribution(
                uav_id=5, sensor_type="EO_IR", confidence=0.5, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="SAR", confidence=0.5, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=8, sensor_type="SIGINT", confidence=0.5, range_m=7000, bearing_deg=20.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        assert result.contributing_uav_ids == (2, 5, 8)

    def test_sensor_types_sorted(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="SIGINT", confidence=0.5, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=2, sensor_type="EO_IR", confidence=0.5, range_m=6000, bearing_deg=10.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=3, sensor_type="SAR", confidence=0.5, range_m=7000, bearing_deg=20.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        assert result.sensor_types == ("EO_IR", "SAR", "SIGINT")

    def test_dual_sensor_uav(self):
        contribs = [
            SensorContribution(
                uav_id=1, sensor_type="EO_IR", confidence=0.6, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
            SensorContribution(
                uav_id=1, sensor_type="SAR", confidence=0.5, range_m=5000, bearing_deg=0.0, timestamp=1.0
            ),
        ]
        result = fuse_detections(contribs)
        assert result.contributing_uav_ids == (1,)
        assert result.sensor_types == ("EO_IR", "SAR")
        assert result.fused_confidence == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# TestImmutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_frozen_sensor_contribution(self):
        contrib = SensorContribution(
            uav_id=1,
            sensor_type="EO_IR",
            confidence=0.5,
            range_m=5000,
            bearing_deg=45.0,
            timestamp=1000.0,
        )
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            contrib.confidence = 0.9  # type: ignore[misc]

    def test_frozen_fused_detection(self):
        result = fuse_detections([])
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            result.fused_confidence = 0.5  # type: ignore[misc]
