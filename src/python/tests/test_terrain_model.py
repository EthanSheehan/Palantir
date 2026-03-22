"""
Tests for terrain_model.py — written FIRST (TDD RED phase).

All tests must fail before terrain_model.py exists, then pass after implementation.
"""

import pytest
from sensor_model import (
    EnvironmentConditions,
    evaluate_detection,
)
from terrain_model import (
    TerrainFeature,
    TerrainModel,
    compute_dead_zones,
    has_line_of_sight,
    load_terrain_from_config,
)

# ---------------------------------------------------------------------------
# TerrainFeature / TerrainModel immutability
# ---------------------------------------------------------------------------


class TestTerrainModelImmutable:
    def test_terrain_feature_is_frozen(self):
        feat = TerrainFeature(
            center_lat=45.0,
            center_lon=25.0,
            radius_km=10.0,
            peak_elevation_m=2000.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            feat.center_lat = 46.0  # type: ignore[misc]

    def test_terrain_model_is_frozen(self):
        model = TerrainModel(features=())
        with pytest.raises((AttributeError, TypeError)):
            model.features = ()  # type: ignore[misc]

    def test_terrain_model_stores_features(self):
        feat = TerrainFeature(
            center_lat=45.0,
            center_lon=25.0,
            radius_km=10.0,
            peak_elevation_m=1500.0,
        )
        model = TerrainModel(features=(feat,))
        assert len(model.features) == 1
        assert model.features[0].peak_elevation_m == 1500.0


# ---------------------------------------------------------------------------
# Flat terrain (no features) — LOS always True
# ---------------------------------------------------------------------------


class TestFlatTerrain:
    def setup_method(self):
        self.flat = TerrainModel(features=())

    def test_flat_terrain_same_point_has_los(self):
        assert has_line_of_sight(self.flat, 45.0, 25.0, 0.0, 45.0, 25.0, 0.0) is True

    def test_flat_terrain_short_range_has_los(self):
        assert has_line_of_sight(self.flat, 45.0, 25.0, 100.0, 45.1, 25.1, 0.0) is True

    def test_flat_terrain_long_range_has_los(self):
        assert has_line_of_sight(self.flat, 45.0, 25.0, 3000.0, 46.0, 26.0, 0.0) is True

    def test_flat_terrain_observer_at_ground_level(self):
        assert has_line_of_sight(self.flat, 45.0, 25.0, 0.0, 45.5, 25.5, 0.0) is True


# ---------------------------------------------------------------------------
# Mountain blocking LOS
# ---------------------------------------------------------------------------


class TestMountainBlocksLOS:
    def setup_method(self):
        # Mountain at 45.5, 25.5 with 20km radius and 3000m peak
        mountain = TerrainFeature(
            center_lat=45.5,
            center_lon=25.5,
            radius_km=20.0,
            peak_elevation_m=3000.0,
        )
        self.model = TerrainModel(features=(mountain,))

    def test_mountain_blocks_los_at_ground_level(self):
        # Observer at 45.0, 25.0 altitude 100m, target at 46.0, 26.0 altitude 0m
        # Mountain sits between them at 45.5, 25.5
        result = has_line_of_sight(
            self.model,
            45.0,
            25.0,
            100.0,  # observer: lat, lon, alt_m
            46.0,
            26.0,
            0.0,  # target: lat, lon, alt_m
        )
        assert result is False

    def test_no_mountain_between_points_has_los(self):
        # Both points on same side of mountain — clear path
        result = has_line_of_sight(
            self.model,
            45.0,
            24.0,
            100.0,  # west of mountain
            45.1,
            24.2,
            0.0,  # also west of mountain
        )
        assert result is True

    def test_mountain_blocks_from_other_direction(self):
        # Reverse direction — still blocked
        result = has_line_of_sight(
            self.model,
            46.0,
            26.0,
            100.0,  # observer east of mountain
            45.0,
            25.0,
            0.0,  # target west of mountain
        )
        assert result is False


# ---------------------------------------------------------------------------
# High altitude clears LOS over mountain
# ---------------------------------------------------------------------------


class TestHighAltitudeClearsLOS:
    def setup_method(self):
        mountain = TerrainFeature(
            center_lat=45.5,
            center_lon=25.5,
            radius_km=20.0,
            peak_elevation_m=2000.0,
        )
        self.model = TerrainModel(features=(mountain,))

    def test_observer_above_mountain_has_los(self):
        # Observer at 5000m altitude — well above the 2000m mountain
        result = has_line_of_sight(
            self.model,
            45.0,
            25.0,
            5000.0,  # observer high above mountain
            46.0,
            26.0,
            0.0,  # target on other side
        )
        assert result is True

    def test_observer_slightly_below_mountain_blocked(self):
        # Observer at 500m altitude — mountain peak at 2000m blocks
        result = has_line_of_sight(
            self.model,
            45.0,
            25.0,
            500.0,
            46.0,
            26.0,
            0.0,
        )
        assert result is False

    def test_target_also_elevated_has_los_when_both_above_mountain(self):
        # Both observer and target at 4000m — above 2000m mountain
        result = has_line_of_sight(
            self.model,
            45.0,
            25.0,
            4000.0,
            46.0,
            26.0,
            4000.0,
        )
        assert result is True


# ---------------------------------------------------------------------------
# Grazing angle edge case
# ---------------------------------------------------------------------------


class TestGrazingAngle:
    def test_observer_at_exactly_mountain_peak_has_los(self):
        # Both observer and target at mountain peak elevation — ray stays at or above peak
        mountain = TerrainFeature(
            center_lat=45.5,
            center_lon=25.5,
            radius_km=5.0,
            peak_elevation_m=1000.0,
        )
        model = TerrainModel(features=(mountain,))
        # Both endpoints at 1000m — ray stays at 1000m throughout, grazes the peak
        result = has_line_of_sight(
            model,
            45.0,
            25.0,
            1000.0,  # at exactly peak elevation
            46.0,
            26.0,
            1000.0,  # target also at peak elevation
        )
        # Ray at constant 1000m; terrain peak is 1000m — strict > means not blocked
        assert result is True

    def test_points_not_on_line_through_mountain_have_los(self):
        # Points whose connecting line doesn't pass through the mountain feature
        mountain = TerrainFeature(
            center_lat=44.0,
            center_lon=24.0,
            radius_km=10.0,
            peak_elevation_m=3000.0,
        )
        model = TerrainModel(features=(mountain,))
        # Path goes 45 -> 46 (far north of mountain at 44)
        result = has_line_of_sight(
            model,
            45.0,
            25.0,
            100.0,
            46.0,
            26.0,
            0.0,
        )
        assert result is True


# ---------------------------------------------------------------------------
# Dead zone computation
# ---------------------------------------------------------------------------


class TestDeadZones:
    def setup_method(self):
        mountain = TerrainFeature(
            center_lat=45.5,
            center_lon=25.5,
            radius_km=15.0,
            peak_elevation_m=2500.0,
        )
        self.model = TerrainModel(features=(mountain,))
        self.observer_lat = 45.0
        self.observer_lon = 25.0
        self.observer_alt = 200.0

    def test_dead_zones_returns_list(self):
        result = compute_dead_zones(
            self.model,
            self.observer_lat,
            self.observer_lon,
            self.observer_alt,
            grid_resolution=0.5,
        )
        assert isinstance(result, list)

    def test_dead_zones_contains_tuples(self):
        result = compute_dead_zones(
            self.model,
            self.observer_lat,
            self.observer_lon,
            self.observer_alt,
            grid_resolution=0.5,
        )
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_dead_zones_non_empty_when_mountain_blocks(self):
        # There should be blocked areas when a mountain is present at low altitude
        result = compute_dead_zones(
            self.model,
            self.observer_lat,
            self.observer_lon,
            self.observer_alt,
            grid_resolution=0.5,
        )
        assert len(result) > 0

    def test_dead_zones_empty_for_flat_terrain(self):
        flat = TerrainModel(features=())
        result = compute_dead_zones(
            flat,
            self.observer_lat,
            self.observer_lon,
            self.observer_alt,
            grid_resolution=0.5,
        )
        assert result == []

    def test_dead_zones_fewer_when_observer_altitude_high(self):
        low_zones = compute_dead_zones(
            self.model,
            self.observer_lat,
            self.observer_lon,
            200.0,
            grid_resolution=0.2,
        )
        high_zones = compute_dead_zones(
            self.model,
            self.observer_lat,
            self.observer_lon,
            5000.0,
            grid_resolution=0.2,
        )
        assert len(high_zones) < len(low_zones)


# ---------------------------------------------------------------------------
# load_terrain_from_config
# ---------------------------------------------------------------------------


class TestLoadTerrainFromConfig:
    def test_load_no_terrain_features_returns_empty_model(self):
        config = {"environment": {"terrain": "mixed"}}
        model = load_terrain_from_config(config)
        assert isinstance(model, TerrainModel)
        assert len(model.features) == 0

    def test_load_with_terrain_features(self):
        config = {
            "terrain_features": [
                {
                    "center_lat": 45.5,
                    "center_lon": 25.5,
                    "radius_km": 20.0,
                    "peak_elevation_m": 2500.0,
                }
            ]
        }
        model = load_terrain_from_config(config)
        assert len(model.features) == 1
        assert model.features[0].center_lat == 45.5
        assert model.features[0].peak_elevation_m == 2500.0

    def test_load_multiple_terrain_features(self):
        config = {
            "terrain_features": [
                {"center_lat": 45.0, "center_lon": 25.0, "radius_km": 10.0, "peak_elevation_m": 1000.0},
                {"center_lat": 46.0, "center_lon": 26.0, "radius_km": 5.0, "peak_elevation_m": 500.0},
            ]
        }
        model = load_terrain_from_config(config)
        assert len(model.features) == 2

    def test_load_empty_config_returns_empty_model(self):
        model = load_terrain_from_config({})
        assert isinstance(model, TerrainModel)
        assert len(model.features) == 0

    def test_load_empty_terrain_features_list(self):
        config = {"terrain_features": []}
        model = load_terrain_from_config(config)
        assert len(model.features) == 0


# ---------------------------------------------------------------------------
# Default (no terrain) — LOS always True
# ---------------------------------------------------------------------------


class TestDefaultNoTerrain:
    def test_none_terrain_model_always_has_los(self):
        # When no terrain model provided, default returns True
        result = has_line_of_sight(
            None,
            45.0,
            25.0,
            100.0,
            46.0,
            26.0,
            0.0,
        )
        assert result is True

    def test_empty_terrain_model_always_has_los(self):
        empty = TerrainModel(features=())
        result = has_line_of_sight(
            empty,
            45.0,
            25.0,
            100.0,
            46.0,
            26.0,
            0.0,
        )
        assert result is True


# ---------------------------------------------------------------------------
# Integration: blocked LOS → Pd = 0 in sensor_model
# ---------------------------------------------------------------------------


class TestIntegrationWithSensorModel:
    def test_blocked_los_yields_zero_pd_for_all_trials(self):
        # Mountain blocks the path between observer and target
        mountain = TerrainFeature(
            center_lat=45.5,
            center_lon=25.5,
            radius_km=20.0,
            peak_elevation_m=3000.0,
        )
        model = TerrainModel(features=(mountain,))
        env = EnvironmentConditions()

        # Confirm LOS is blocked first
        los = has_line_of_sight(model, 45.0, 25.0, 100.0, 46.0, 26.0, 0.0)
        assert los is False

        # Run many trials — all must have pd=0 and detected=False
        for _ in range(20):
            result = evaluate_detection(
                uav_lat=45.0,
                uav_lon=25.0,
                target_lat=46.0,
                target_lon=26.0,
                target_type="SAM",
                sensor_type="EO_IR",
                env=env,
                altitude_m=100.0,
                terrain_model=model,
            )
            assert result.pd == 0.0
            assert result.detected is False

    def test_clear_los_yields_nonzero_pd(self):
        # No mountain — should have normal detection probability
        flat = TerrainModel(features=())
        env = EnvironmentConditions()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.05,
            target_lon=25.05,
            target_type="SAM",
            sensor_type="EO_IR",
            env=env,
            altitude_m=3000.0,
            terrain_model=flat,
        )
        assert result.pd > 0.0

    def test_no_terrain_model_backwards_compatible(self):
        # evaluate_detection without terrain_model param still works
        env = EnvironmentConditions()
        result = evaluate_detection(
            uav_lat=45.0,
            uav_lon=25.0,
            target_lat=45.05,
            target_lon=25.05,
            target_type="TRUCK",
            sensor_type="SAR",
            env=env,
            altitude_m=3000.0,
        )
        assert isinstance(result.pd, float)
        assert 0.0 <= result.pd <= 1.0
