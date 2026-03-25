"""
Tests for vectorized_detection.py — written FIRST (TDD RED phase).

Tests cover:
  - positions_to_array: extract lat/lon as Nx2 numpy array
  - pairwise_distances_km: MxN distance matrix via flat-earth approximation
  - vectorized_detection_probability: element-wise Pd matching sensor_model.py
  - detect_all: returns (uav_id, target_id, pd) tuples above threshold
  - benchmark_comparison: scalar vs vectorized equivalence
"""

import numpy as np
import pytest
from vectorized_detection import (
    detect_all,
    pairwise_distances_km,
    positions_to_array,
    vectorized_detection_probability,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entity(uid: str, lat: float, lon: float) -> dict:
    return {"id": uid, "lat": lat, "lon": lon}


# ---------------------------------------------------------------------------
# positions_to_array
# ---------------------------------------------------------------------------


class TestPositionsToArray:
    def test_empty_list_returns_empty_array(self):
        result = positions_to_array([])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 2)

    def test_single_entity(self):
        entity = _make_entity("u1", 45.0, 25.0)
        result = positions_to_array([entity])
        assert result.shape == (1, 2)
        assert result[0, 0] == pytest.approx(45.0)
        assert result[0, 1] == pytest.approx(25.0)

    def test_multiple_entities_ordered(self):
        entities = [
            _make_entity("u1", 45.0, 25.0),
            _make_entity("u2", 46.0, 26.0),
            _make_entity("u3", 47.0, 27.0),
        ]
        result = positions_to_array(entities)
        assert result.shape == (3, 2)
        assert result[0, 0] == pytest.approx(45.0)
        assert result[1, 1] == pytest.approx(26.0)
        assert result[2, 0] == pytest.approx(47.0)

    def test_returns_float64(self):
        entities = [_make_entity("u1", 45.0, 25.0)]
        result = positions_to_array(entities)
        assert result.dtype == np.float64

    def test_original_list_not_mutated(self):
        entities = [_make_entity("u1", 45.0, 25.0)]
        original_lat = entities[0]["lat"]
        positions_to_array(entities)
        assert entities[0]["lat"] == original_lat


# ---------------------------------------------------------------------------
# pairwise_distances_km
# ---------------------------------------------------------------------------


class TestPairwiseDistancesKm:
    def test_same_positions_give_zero_distance(self):
        pos = np.array([[45.0, 25.0]], dtype=np.float64)
        result = pairwise_distances_km(pos, pos)
        assert result.shape == (1, 1)
        assert result[0, 0] == pytest.approx(0.0, abs=1e-6)

    def test_output_shape_mxn(self):
        uav_pos = np.array([[45.0, 25.0], [46.0, 26.0]], dtype=np.float64)
        target_pos = np.array([[47.0, 27.0], [48.0, 28.0], [49.0, 29.0]], dtype=np.float64)
        result = pairwise_distances_km(uav_pos, target_pos)
        assert result.shape == (2, 3)

    def test_known_distance_one_degree_lat(self):
        # 1 degree latitude ≈ 111.32 km
        uav_pos = np.array([[0.0, 0.0]], dtype=np.float64)
        target_pos = np.array([[1.0, 0.0]], dtype=np.float64)
        result = pairwise_distances_km(uav_pos, target_pos)
        assert result[0, 0] == pytest.approx(111.32, abs=1.0)

    def test_matches_scalar_deg_to_meters(self):
        from sensor_model import deg_to_meters

        uav_pos = np.array([[45.0, 25.0]], dtype=np.float64)
        target_pos = np.array([[45.5, 25.5]], dtype=np.float64)
        result_km = pairwise_distances_km(uav_pos, target_pos)[0, 0]
        result_m = deg_to_meters(45.0, 25.0, 45.5, 25.5)
        assert result_km == pytest.approx(result_m / 1000.0, rel=0.01)

    def test_all_distances_non_negative(self):
        rng = np.random.default_rng(42)
        uav_pos = rng.uniform(-90, 90, (5, 2))
        target_pos = rng.uniform(-90, 90, (10, 2))
        result = pairwise_distances_km(uav_pos, target_pos)
        assert np.all(result >= 0.0)

    def test_returns_float64(self):
        uav_pos = np.array([[45.0, 25.0]], dtype=np.float64)
        target_pos = np.array([[46.0, 26.0]], dtype=np.float64)
        result = pairwise_distances_km(uav_pos, target_pos)
        assert result.dtype == np.float64


# ---------------------------------------------------------------------------
# vectorized_detection_probability
# ---------------------------------------------------------------------------


class TestVectorizedDetectionProbability:
    def test_output_shape_matches_input(self):
        distances = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], dtype=np.float64)
        rcs = np.array([5.0, 10.0, 15.0], dtype=np.float64)
        result = vectorized_detection_probability(distances, rcs, 0.0, "EO_IR")
        assert result.shape == (2, 3)

    def test_values_in_zero_to_one(self):
        distances = np.array([[1.0, 10.0, 50.0, 100.0]], dtype=np.float64)
        rcs = np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
        result = vectorized_detection_probability(distances, rcs, 0.0, "EO_IR")
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_closer_targets_have_higher_pd(self):
        # Close vs far target with same RCS
        distances = np.array([[5.0, 100.0]], dtype=np.float64)
        rcs = np.array([5.0, 5.0], dtype=np.float64)
        result = vectorized_detection_probability(distances, rcs, 0.0, "EO_IR")
        assert result[0, 0] > result[0, 1]

    def test_larger_rcs_increases_pd(self):
        distances = np.array([[30.0, 30.0]], dtype=np.float64)
        rcs_small = np.array([0.5, 0.5], dtype=np.float64)
        rcs_large = np.array([20.0, 20.0], dtype=np.float64)
        pd_small = vectorized_detection_probability(distances, rcs_small, 0.0, "EO_IR")
        pd_large = vectorized_detection_probability(distances, rcs_large, 0.0, "EO_IR")
        assert pd_large[0, 0] > pd_small[0, 0]

    def test_weather_factor_reduces_pd(self):
        distances = np.array([[20.0]], dtype=np.float64)
        rcs = np.array([5.0], dtype=np.float64)
        pd_clear = vectorized_detection_probability(distances, rcs, 0.0, "EO_IR")
        pd_bad = vectorized_detection_probability(distances, rcs, 1.0, "EO_IR")
        assert pd_clear[0, 0] >= pd_bad[0, 0]

    def test_eo_ir_sensor_max_range(self):
        # EO_IR max_range_m = 50_000 m = 50 km
        # At 200 km, Pd should be very low
        distances_km = np.array([[200.0]], dtype=np.float64)
        rcs = np.array([5.0], dtype=np.float64)
        result = vectorized_detection_probability(distances_km, rcs, 0.0, "EO_IR")
        assert result[0, 0] < 0.1

    def test_sar_sensor_longer_range(self):
        # SAR max_range = 100 km; at 80 km should still have moderate Pd
        distances_km = np.array([[80.0]], dtype=np.float64)
        rcs = np.array([10.0], dtype=np.float64)
        eo_pd = vectorized_detection_probability(distances_km, rcs, 0.0, "EO_IR")
        sar_pd = vectorized_detection_probability(distances_km, rcs, 0.0, "SAR")
        # SAR range is 100km vs EO_IR 50km; at 80km, SAR should detect better
        assert sar_pd[0, 0] > eo_pd[0, 0]

    def test_matches_scalar_compute_pd(self):
        from sensor_model import SENSOR_CONFIGS, EnvironmentConditions, compute_pd

        # Single pair — vectorized should match scalar within tolerance
        distance_km = 20.0
        rcs_val = 5.0
        sensor_type = "EO_IR"
        weather_factor = 0.3

        env = EnvironmentConditions(cloud_cover=weather_factor, precipitation=0.0)
        scalar_pd = compute_pd(
            range_m=distance_km * 1000.0,
            rcs_m2=rcs_val,
            sensor_type=sensor_type,
            sensor_cfg=SENSOR_CONFIGS[sensor_type],
            env=env,
        )

        distances = np.array([[distance_km]], dtype=np.float64)
        rcs = np.array([rcs_val], dtype=np.float64)
        vec_pd = vectorized_detection_probability(distances, rcs, weather_factor, sensor_type)

        assert vec_pd[0, 0] == pytest.approx(scalar_pd, abs=1e-4)

    def test_returns_float64(self):
        distances = np.array([[10.0]], dtype=np.float64)
        rcs = np.array([5.0], dtype=np.float64)
        result = vectorized_detection_probability(distances, rcs, 0.0, "EO_IR")
        assert result.dtype == np.float64


# ---------------------------------------------------------------------------
# detect_all
# ---------------------------------------------------------------------------


class TestDetectAll:
    def _make_uavs(self):
        return [
            {"id": "uav_1", "lat": 45.0, "lon": 25.0},
            {"id": "uav_2", "lat": 45.5, "lon": 25.5},
        ]

    def _make_targets(self):
        return [
            {"id": "tgt_1", "lat": 45.01, "lon": 25.01, "type": "TRUCK"},
            {"id": "tgt_2", "lat": 50.0, "lon": 35.0, "type": "SAM"},  # far away
        ]

    def test_returns_list_of_tuples(self):
        result = detect_all(self._make_uavs(), self._make_targets())
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3

    def test_tuple_contains_ids_and_float(self):
        result = detect_all(self._make_uavs(), self._make_targets())
        for uav_id, target_id, pd in result:
            assert isinstance(uav_id, str)
            assert isinstance(target_id, str)
            assert isinstance(pd, float)
            assert 0.0 <= pd <= 1.0

    def test_close_target_above_default_threshold(self):
        uavs = [{"id": "uav_1", "lat": 45.0, "lon": 25.0}]
        targets = [{"id": "tgt_1", "lat": 45.01, "lon": 25.01, "type": "TRUCK"}]
        result = detect_all(uavs, targets)
        assert len(result) == 1
        assert result[0][0] == "uav_1"
        assert result[0][1] == "tgt_1"

    def test_very_far_target_below_threshold(self):
        uavs = [{"id": "uav_1", "lat": 45.0, "lon": 25.0}]
        targets = [{"id": "tgt_far", "lat": 60.0, "lon": 40.0, "type": "TRUCK"}]
        result = detect_all(uavs, targets, threshold=0.3)
        assert len(result) == 0

    def test_empty_uavs(self):
        result = detect_all([], self._make_targets())
        assert result == []

    def test_empty_targets(self):
        result = detect_all(self._make_uavs(), [])
        assert result == []

    def test_custom_threshold_filters_results(self):
        uavs = [{"id": "uav_1", "lat": 45.0, "lon": 25.0}]
        targets = [{"id": "tgt_1", "lat": 45.01, "lon": 25.01, "type": "TRUCK"}]
        result_low = detect_all(uavs, targets, threshold=0.0)
        result_high = detect_all(uavs, targets, threshold=0.9999)
        assert len(result_low) >= len(result_high)

    def test_does_not_mutate_input_lists(self):
        uavs = [{"id": "uav_1", "lat": 45.0, "lon": 25.0}]
        targets = [{"id": "tgt_1", "lat": 45.01, "lon": 25.01, "type": "TRUCK"}]
        uavs_copy = [dict(u) for u in uavs]
        targets_copy = [dict(t) for t in targets]
        detect_all(uavs, targets)
        assert uavs == uavs_copy
        assert targets == targets_copy

    def test_unknown_target_type_uses_fallback_rcs(self):
        uavs = [{"id": "uav_1", "lat": 45.0, "lon": 25.0}]
        targets = [{"id": "tgt_1", "lat": 45.01, "lon": 25.01, "type": "UNKNOWN_TYPE"}]
        result = detect_all(uavs, targets)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Benchmark: scalar vs vectorized equivalence
# ---------------------------------------------------------------------------


class TestBenchmarkEquivalence:
    def test_vectorized_matches_scalar_bulk(self):
        """Vectorized Pd values must match scalar compute_pd within tolerance for all pairs."""
        from sensor_model import SENSOR_CONFIGS, EnvironmentConditions, compute_pd

        rng = np.random.default_rng(7)
        n_uavs, n_targets = 5, 20
        sensor_type = "EO_IR"
        weather_factor = 0.2

        uav_lats = rng.uniform(44.0, 46.0, n_uavs)
        uav_lons = rng.uniform(24.0, 26.0, n_uavs)
        tgt_lats = rng.uniform(44.0, 46.0, n_targets)
        tgt_lons = rng.uniform(24.0, 26.0, n_targets)
        rcs_values = rng.uniform(1.0, 20.0, n_targets)

        uav_pos = np.column_stack([uav_lats, uav_lons])
        tgt_pos = np.column_stack([tgt_lats, tgt_lons])
        rcs_arr = rcs_values

        distances = pairwise_distances_km(uav_pos, tgt_pos)
        vec_pds = vectorized_detection_probability(distances, rcs_arr, weather_factor, sensor_type)

        env = EnvironmentConditions(cloud_cover=weather_factor, precipitation=0.0)
        sensor_cfg = SENSOR_CONFIGS[sensor_type]

        for i in range(n_uavs):
            for j in range(n_targets):
                scalar_pd = compute_pd(
                    range_m=distances[i, j] * 1000.0,
                    rcs_m2=float(rcs_values[j]),
                    sensor_type=sensor_type,
                    sensor_cfg=sensor_cfg,
                    env=env,
                )
                assert vec_pds[i, j] == pytest.approx(scalar_pd, abs=1e-4), (
                    f"Mismatch at uav={i}, tgt={j}: vec={vec_pds[i, j]:.6f} scalar={scalar_pd:.6f}"
                )
