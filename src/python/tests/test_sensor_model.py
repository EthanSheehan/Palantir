"""
Tests for sensor_model.py — written FIRST (TDD RED phase).

All tests must fail before sensor_model.py exists, then pass after implementation.
"""

import math

import pytest

# Import the module under test — will fail until sensor_model.py is created
from sensor_model import (
    RCS_TABLE,
    SENSOR_CONFIGS,
    DetectionResult,
    EnvironmentConditions,
    compute_aspect_rcs,
    compute_pd,
    deg_to_meters,
    evaluate_detection,
)

# ---------------------------------------------------------------------------
# deg_to_meters
# ---------------------------------------------------------------------------


class TestDegToMeters:
    def test_same_point_returns_zero(self):
        result = deg_to_meters(0.0, 0.0, 0.0, 0.0)
        assert result == 0.0

    def test_one_degree_latitude_approx_111320m(self):
        # Move 1 degree north from equator; longitude unchanged
        result = deg_to_meters(0.0, 0.0, 1.0, 0.0)
        assert abs(result - 111_320.0) < 500.0  # within 500m tolerance

    def test_longitude_scaling_by_cos_lat(self):
        # At 60° lat, 1 deg lon ≈ 111320 * cos(60°) ≈ 55660m
        result = deg_to_meters(60.0, 0.0, 60.0, 1.0)
        expected = 111_320.0 * math.cos(math.radians(60.0))
        assert abs(result - expected) < 500.0

    def test_symmetry_lat_lon(self):
        # Swapping lat/lon with appropriate scaling gives consistent geometry
        d_lat = deg_to_meters(0.0, 0.0, 1.0, 0.0)
        d_lon = deg_to_meters(0.0, 0.0, 0.0, 1.0)
        # At equator lon and lat degrees are roughly equal
        assert abs(d_lat - d_lon) < 1000.0

    def test_negative_delta_gives_positive_distance(self):
        result = deg_to_meters(0.0, 0.0, -1.0, 0.0)
        assert result > 0.0

    def test_small_separation_proportional(self):
        d1 = deg_to_meters(45.0, 25.0, 45.1, 25.0)
        d2 = deg_to_meters(45.0, 25.0, 45.2, 25.0)
        # Doubling delta should roughly double distance
        assert abs(d2 / d1 - 2.0) < 0.01


# ---------------------------------------------------------------------------
# compute_aspect_rcs
# ---------------------------------------------------------------------------


class TestComputeAspectRcs:
    def test_head_on_reduces_rcs(self):
        base = 10.0
        result = compute_aspect_rcs(base, 0.0)
        assert abs(result - base * 0.3) < 0.01

    def test_broadside_increases_rcs(self):
        base = 10.0
        result = compute_aspect_rcs(base, 90.0)
        assert abs(result - base * 1.5) < 0.01

    def test_symmetry_90_equals_270(self):
        base = 5.0
        r90 = compute_aspect_rcs(base, 90.0)
        r270 = compute_aspect_rcs(base, 270.0)
        assert abs(r90 - r270) < 0.001

    def test_symmetry_0_equals_180(self):
        # Both 0° and 180° are axial aspects — head-on or tail-on
        base = 8.0
        r0 = compute_aspect_rcs(base, 0.0)
        r180 = compute_aspect_rcs(base, 180.0)
        assert abs(r0 - r180) < 0.001

    def test_45_degrees_between_min_and_max(self):
        base = 10.0
        r45 = compute_aspect_rcs(base, 45.0)
        r_min = compute_aspect_rcs(base, 0.0)
        r_max = compute_aspect_rcs(base, 90.0)
        assert r_min < r45 < r_max

    def test_returns_float(self):
        result = compute_aspect_rcs(5.0, 45.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_pd
# ---------------------------------------------------------------------------


class TestComputePd:
    """Tests for the probability-of-detection sigmoid function."""

    def _default_env(self) -> EnvironmentConditions:
        return EnvironmentConditions()

    def test_zero_range_pd_near_one(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["EO_IR"]
        pd = compute_pd(
            range_m=0.0,
            rcs_m2=cfg.reference_rcs_m2,
            sensor_type="EO_IR",
            sensor_cfg=cfg,
            env=env,
        )
        assert pd > 0.9

    def test_at_max_range_pd_near_zero(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["EO_IR"]
        pd = compute_pd(
            range_m=cfg.max_range_m,
            rcs_m2=cfg.reference_rcs_m2,
            sensor_type="EO_IR",
            sensor_cfg=cfg,
            env=env,
        )
        assert pd < 0.15

    def test_larger_rcs_increases_pd(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["SAR"]
        mid_range = cfg.max_range_m * 0.5
        pd_small = compute_pd(mid_range, 1.0, "SAR", cfg, env)
        pd_large = compute_pd(mid_range, 20.0, "SAR", cfg, env)
        assert pd_large > pd_small

    def test_sigint_non_emitting_target_returns_zero(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["SIGINT"]
        # requires_emitter=True; emitting=False means Pd must be 0
        pd = compute_pd(
            range_m=1000.0,
            rcs_m2=10.0,
            sensor_type="SIGINT",
            sensor_cfg=cfg,
            env=env,
            emitting=False,
        )
        assert pd == 0.0

    def test_sigint_emitting_target_nonzero_pd(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["SIGINT"]
        pd = compute_pd(
            range_m=1000.0,
            rcs_m2=10.0,
            sensor_type="SIGINT",
            sensor_cfg=cfg,
            env=env,
            emitting=True,
        )
        assert pd > 0.0

    def test_eo_ir_full_cloud_cover_reduces_pd(self):
        clear_env = EnvironmentConditions(cloud_cover=0.0)
        cloudy_env = EnvironmentConditions(cloud_cover=1.0)
        cfg = SENSOR_CONFIGS["EO_IR"]
        mid_range = cfg.max_range_m * 0.4
        pd_clear = compute_pd(mid_range, 5.0, "EO_IR", cfg, clear_env)
        pd_cloudy = compute_pd(mid_range, 5.0, "EO_IR", cfg, cloudy_env)
        assert pd_cloudy < pd_clear

    def test_sar_cloud_cover_nearly_unchanged(self):
        clear_env = EnvironmentConditions(cloud_cover=0.0)
        cloudy_env = EnvironmentConditions(cloud_cover=1.0)
        cfg = SENSOR_CONFIGS["SAR"]
        mid_range = cfg.max_range_m * 0.4
        pd_clear = compute_pd(mid_range, 5.0, "SAR", cfg, clear_env)
        pd_cloudy = compute_pd(mid_range, 5.0, "SAR", cfg, cloudy_env)
        # SAR weather_sensitivity=0.2, so change should be small (<10% relative)
        assert abs(pd_clear - pd_cloudy) < 0.10

    def test_pd_bounded_between_zero_and_one(self):
        env = self._default_env()
        cfg = SENSOR_CONFIGS["EO_IR"]
        for range_m in [0.0, 100.0, 5000.0, 8000.0, 20000.0]:
            pd = compute_pd(range_m, 5.0, "EO_IR", cfg, env)
            assert 0.0 <= pd <= 1.0, f"Pd={pd} out of bounds at range={range_m}"


# ---------------------------------------------------------------------------
# evaluate_detection
# ---------------------------------------------------------------------------


class TestEvaluateDetection:
    """Tests for the top-level per-sensor-pair detection evaluation."""

    def _default_env(self) -> EnvironmentConditions:
        return EnvironmentConditions()

    def test_returns_detection_result_type(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.001,
            target_lon=25.001,
            target_type="TRUCK",
            sensor_type="EO_IR",
            env=env,
        )
        assert isinstance(result, DetectionResult)

    def test_result_has_all_required_fields(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.001,
            target_lon=25.001,
            target_type="SAM",
            sensor_type="SAR",
            env=env,
        )
        assert hasattr(result, "detected")
        assert hasattr(result, "pd")
        assert hasattr(result, "range_m")
        assert hasattr(result, "sensor_type")
        assert hasattr(result, "confidence")
        assert hasattr(result, "bearing_deg")

    def test_sensor_type_recorded_in_result(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.001,
            target_lon=25.001,
            target_type="TEL",
            sensor_type="SIGINT",
            env=env,
            emitting=True,
        )
        assert result.sensor_type == "SIGINT"

    def test_very_close_large_rcs_nearly_always_detected(self):
        """100 trials: close range + large RCS should yield >90% detection rate."""
        env = self._default_env()
        detections = 0
        trials = 100
        for _ in range(trials):
            # 10m separation, SAM (RCS=15m²), EO_IR sensor
            result = evaluate_detection(
                uav_lat=45.0,
                uav_lon=25.0,
                target_lat=45.00009,
                target_lon=25.00009,  # ~12m away
                target_type="SAM",
                sensor_type="EO_IR",
                env=env,
            )
            if result.detected:
                detections += 1
        detection_rate = detections / trials
        assert detection_rate > 0.90, f"Detection rate {detection_rate:.2f} too low for close+large target"

    def test_very_far_tiny_rcs_nearly_never_detected(self):
        """100 trials: beyond max range + tiny RCS should yield <10% detection rate."""
        env = self._default_env()
        detections = 0
        trials = 100
        for _ in range(trials):
            # ~120km away (well beyond EO_IR 50km max), MANPADS (RCS=0.5m²)
            result = evaluate_detection(
                uav_lat=45.0,
                uav_lon=25.0,
                target_lat=46.08,
                target_lon=25.0,  # ~120km north
                target_type="MANPADS",
                sensor_type="EO_IR",
                env=env,
            )
            if result.detected:
                detections += 1
        detection_rate = detections / trials
        assert detection_rate < 0.10, f"Detection rate {detection_rate:.2f} too high for far+tiny target"

    def test_range_computed_correctly(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=46.0,
            target_lon=25.0,  # 1 degree north ≈ 111320m
            target_type="SAM",
            sensor_type="SAR",
            env=env,
        )
        assert abs(result.range_m - 111_320.0) < 1000.0

    def test_bearing_deg_within_valid_range(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.5,
            target_lon=25.5,
            target_type="CP",
            sensor_type="EO_IR",
            env=env,
        )
        assert 0.0 <= result.bearing_deg < 360.0

    def test_confidence_bounded_zero_to_one(self):
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.1,
            target_lon=25.1,
            target_type="TRUCK",
            sensor_type="SAR",
            env=env,
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_unknown_target_type_uses_fallback_rcs(self):
        """evaluate_detection should not raise for target types not in RCS_TABLE."""
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.001,
            target_lon=25.001,
            target_type="UNKNOWN_BOGUS",
            sensor_type="EO_IR",
            env=env,
        )
        assert isinstance(result, DetectionResult)

    def test_result_is_immutable(self):
        """DetectionResult is a frozen dataclass — mutation must raise."""
        env = self._default_env()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.001,
            target_lon=25.001,
            target_type="SAM",
            sensor_type="EO_IR",
            env=env,
        )
        with pytest.raises((AttributeError, TypeError)):
            result.detected = not result.detected  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RCS_TABLE and SENSOR_CONFIGS sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_rcs_table_has_required_keys(self):
        required = {"SAM", "TEL", "TRUCK", "CP"}
        assert required.issubset(set(RCS_TABLE.keys()))

    def test_rcs_values_positive(self):
        for key, value in RCS_TABLE.items():
            assert value > 0.0, f"RCS for {key} must be positive"

    def test_sensor_configs_has_required_keys(self):
        required = {"EO_IR", "SAR", "SIGINT"}
        assert required.issubset(set(SENSOR_CONFIGS.keys()))

    def test_sensor_configs_are_frozen_dataclasses(self):
        cfg = SENSOR_CONFIGS["EO_IR"]
        with pytest.raises((AttributeError, TypeError)):
            cfg.max_range_m = 99999  # type: ignore[misc]

    def test_sensor_max_range_positive(self):
        for name, cfg in SENSOR_CONFIGS.items():
            assert cfg.max_range_m > 0.0, f"{name} max_range_m must be positive"

    def test_weather_sensitivity_bounded(self):
        for name, cfg in SENSOR_CONFIGS.items():
            assert 0.0 <= cfg.weather_sensitivity <= 1.0, (
                f"{name} weather_sensitivity {cfg.weather_sensitivity} out of [0,1]"
            )
