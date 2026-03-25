"""
Tests for sensor_weighting.py — TDD RED phase written first.

All tests must fail before sensor_weighting.py exists, then pass after implementation.
"""

import pytest
from sensor_fusion import SensorContribution
from sensor_weighting import (
    SensorFitness,
    compute_sensor_fitness,
    recommend_sensor_type,
    weight_fusion_contributions,
)

# ---------------------------------------------------------------------------
# SensorFitness dataclass
# ---------------------------------------------------------------------------


class TestSensorFitnessDataclass:
    def test_is_frozen(self):
        sf = SensorFitness(
            sensor_type="EO_IR",
            weather_weight=0.8,
            time_weight=0.9,
            target_weight=0.7,
            combined_weight=0.5,
        )
        with pytest.raises((AttributeError, TypeError)):
            sf.weather_weight = 0.5  # type: ignore[misc]

    def test_fields_accessible(self):
        sf = SensorFitness(
            sensor_type="SAR",
            weather_weight=0.9,
            time_weight=0.7,
            target_weight=0.8,
            combined_weight=0.5,
        )
        assert sf.sensor_type == "SAR"
        assert sf.weather_weight == pytest.approx(0.9)
        assert sf.time_weight == pytest.approx(0.7)
        assert sf.target_weight == pytest.approx(0.8)
        assert sf.combined_weight == pytest.approx(0.5)

    def test_combined_weight_in_range(self):
        sf = compute_sensor_fitness("EO_IR", {"state": "CLEAR", "intensity": 0.0}, 12.0, "SAM")
        assert 0.0 <= sf.combined_weight <= 1.0


# ---------------------------------------------------------------------------
# compute_sensor_fitness — EO/IR
# ---------------------------------------------------------------------------


class TestComputeSensorFitnessEOIR:
    def test_eo_ir_clear_day_high_fitness(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        sf = compute_sensor_fitness("EO_IR", weather, 12.0, "SAM")
        # Clear daytime conditions — EO/IR should be near max
        assert sf.weather_weight >= 0.85
        assert sf.time_weight >= 0.85
        assert sf.combined_weight >= 0.7

    def test_eo_ir_storm_degraded(self):
        weather = {"state": "STORM", "intensity": 1.0}
        sf = compute_sensor_fitness("EO_IR", weather, 12.0, "SAM")
        # Storm heavily degrades EO/IR
        assert sf.weather_weight <= 0.3

    def test_eo_ir_night_degraded(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        sf_day = compute_sensor_fitness("EO_IR", weather, 12.0, "SAM")
        sf_night = compute_sensor_fitness("EO_IR", weather, 2.0, "SAM")  # 2am
        # Night should have lower time_weight than day
        assert sf_night.time_weight < sf_day.time_weight

    def test_eo_ir_rain_degraded(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        rain = {"state": "RAIN", "intensity": 0.65}
        sf_clear = compute_sensor_fitness("EO_IR", clear, 12.0, "SAM")
        sf_rain = compute_sensor_fitness("EO_IR", rain, 12.0, "SAM")
        assert sf_rain.weather_weight < sf_clear.weather_weight


# ---------------------------------------------------------------------------
# compute_sensor_fitness — SAR
# ---------------------------------------------------------------------------


class TestComputeSensorFitnessSAR:
    def test_sar_all_weather_capable(self):
        storm = {"state": "STORM", "intensity": 1.0}
        sf = compute_sensor_fitness("SAR", storm, 12.0, "SAM")
        # SAR works in all weather — should remain high
        assert sf.weather_weight >= 0.7

    def test_sar_clear_also_good(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        sf = compute_sensor_fitness("SAR", clear, 12.0, "SAM")
        assert sf.weather_weight >= 0.8

    def test_sar_small_target_degraded(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        sf_large = compute_sensor_fitness("SAR", clear, 12.0, "SAM")  # large RCS
        sf_small = compute_sensor_fitness("SAR", clear, 12.0, "MANPADS")  # small RCS
        # SAR resolves large targets better
        assert sf_small.target_weight < sf_large.target_weight

    def test_sar_time_neutral(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        sf_day = compute_sensor_fitness("SAR", weather, 12.0, "SAM")
        sf_night = compute_sensor_fitness("SAR", weather, 2.0, "SAM")
        # SAR is not significantly affected by time of day
        assert abs(sf_day.time_weight - sf_night.time_weight) <= 0.1


# ---------------------------------------------------------------------------
# compute_sensor_fitness — SIGINT
# ---------------------------------------------------------------------------


class TestComputeSensorFitnessSIGINT:
    def test_sigint_weather_immune(self):
        storm = {"state": "STORM", "intensity": 1.0}
        sf = compute_sensor_fitness("SIGINT", storm, 12.0, "C2_NODE")
        # SIGINT unaffected by weather
        assert sf.weather_weight >= 0.9

    def test_sigint_best_for_c2_node(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        sf_c2 = compute_sensor_fitness("SIGINT", clear, 12.0, "C2_NODE")
        sf_truck = compute_sensor_fitness("SIGINT", clear, 12.0, "TRUCK")
        # C2_NODE is an emitter — SIGINT excels
        assert sf_c2.target_weight > sf_truck.target_weight

    def test_sigint_best_for_radar_target(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        sf_radar = compute_sensor_fitness("SIGINT", clear, 12.0, "RADAR")
        sf_logistics = compute_sensor_fitness("SIGINT", clear, 12.0, "LOGISTICS")
        assert sf_radar.target_weight > sf_logistics.target_weight

    def test_sigint_time_neutral(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        sf_day = compute_sensor_fitness("SIGINT", weather, 12.0, "C2_NODE")
        sf_night = compute_sensor_fitness("SIGINT", weather, 2.0, "C2_NODE")
        assert abs(sf_day.time_weight - sf_night.time_weight) <= 0.1


# ---------------------------------------------------------------------------
# compute_sensor_fitness — combined_weight clipping
# ---------------------------------------------------------------------------


class TestCombinedWeightBounds:
    def test_combined_weight_never_exceeds_one(self):
        clear = {"state": "CLEAR", "intensity": 0.0}
        for sensor in ("EO_IR", "SAR", "SIGINT"):
            sf = compute_sensor_fitness(sensor, clear, 12.0, "SAM")
            assert sf.combined_weight <= 1.0

    def test_combined_weight_never_below_zero(self):
        storm = {"state": "STORM", "intensity": 1.0}
        for sensor in ("EO_IR", "SAR", "SIGINT"):
            sf = compute_sensor_fitness(sensor, storm, 2.0, "MANPADS")
            assert sf.combined_weight >= 0.0


# ---------------------------------------------------------------------------
# weight_fusion_contributions
# ---------------------------------------------------------------------------


class TestWeightFusionContributions:
    def _make_contribution(self, sensor_type: str, confidence: float) -> SensorContribution:
        return SensorContribution(
            uav_id=1,
            sensor_type=sensor_type,
            confidence=confidence,
            range_m=10000.0,
            bearing_deg=45.0,
            timestamp=0.0,
        )

    def test_returns_list_of_sensor_contributions(self):
        contributions = [
            self._make_contribution("EO_IR", 0.8),
            self._make_contribution("SAR", 0.7),
        ]
        weather = {"state": "CLEAR", "intensity": 0.0}
        result = weight_fusion_contributions(contributions, weather)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(c, SensorContribution) for c in result)

    def test_storm_reduces_eo_ir_confidence(self):
        contributions = [self._make_contribution("EO_IR", 0.8)]
        clear = {"state": "CLEAR", "intensity": 0.0}
        storm = {"state": "STORM", "intensity": 1.0}
        result_clear = weight_fusion_contributions(contributions, clear)
        result_storm = weight_fusion_contributions(contributions, storm)
        assert result_storm[0].confidence < result_clear[0].confidence

    def test_storm_preserves_sar_confidence(self):
        contributions = [self._make_contribution("SAR", 0.8)]
        clear = {"state": "CLEAR", "intensity": 0.0}
        storm = {"state": "STORM", "intensity": 1.0}
        result_clear = weight_fusion_contributions(contributions, clear)
        result_storm = weight_fusion_contributions(contributions, storm)
        # SAR in storm vs clear — should remain relatively high
        assert result_storm[0].confidence >= 0.5

    def test_confidence_clamped_zero_to_one(self):
        contributions = [self._make_contribution("EO_IR", 0.1)]
        storm = {"state": "STORM", "intensity": 1.0}
        result = weight_fusion_contributions(contributions, storm)
        assert 0.0 <= result[0].confidence <= 1.0

    def test_empty_list_returns_empty(self):
        result = weight_fusion_contributions([], {"state": "CLEAR", "intensity": 0.0})
        assert result == []

    def test_immutable_returns_new_objects(self):
        c = self._make_contribution("EO_IR", 0.8)
        result = weight_fusion_contributions([c], {"state": "STORM", "intensity": 1.0})
        # Original must not be mutated
        assert c.confidence == pytest.approx(0.8)
        # Result is a new object (different confidence in storm)
        assert result[0] is not c

    def test_time_of_day_affects_eo_ir(self):
        contributions = [self._make_contribution("EO_IR", 0.8)]
        clear = {"state": "CLEAR", "intensity": 0.0}
        result_day = weight_fusion_contributions(contributions, clear, time_of_day=12.0)
        result_night = weight_fusion_contributions(contributions, clear, time_of_day=2.0)
        assert result_night[0].confidence < result_day[0].confidence


# ---------------------------------------------------------------------------
# recommend_sensor_type
# ---------------------------------------------------------------------------


class TestRecommendSensorType:
    def test_recommend_eo_ir_clear_day(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        rec = recommend_sensor_type(weather, "SAM")
        # Clear day — EO/IR is best for most targets
        assert rec in ("EO_IR", "SAR", "SIGINT")  # must return a valid sensor
        assert rec == "EO_IR"

    def test_recommend_sar_in_storm(self):
        weather = {"state": "STORM", "intensity": 1.0}
        rec = recommend_sensor_type(weather, "SAM")
        # Storm — SAR should be preferred over EO/IR
        assert rec == "SAR"

    def test_recommend_sigint_for_c2_node_clear(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        rec = recommend_sensor_type(weather, "C2_NODE")
        # C2_NODE is an active emitter — SIGINT is best
        assert rec == "SIGINT"

    def test_recommend_sigint_for_radar_clear(self):
        weather = {"state": "CLEAR", "intensity": 0.0}
        rec = recommend_sensor_type(weather, "RADAR")
        assert rec == "SIGINT"

    def test_recommend_sar_for_truck_storm(self):
        weather = {"state": "STORM", "intensity": 1.0}
        rec = recommend_sensor_type(weather, "TRUCK")
        assert rec == "SAR"

    def test_recommend_returns_valid_sensor(self):
        valid_sensors = {"EO_IR", "SAR", "SIGINT"}
        weather_states = [
            {"state": "CLEAR", "intensity": 0.0},
            {"state": "RAIN", "intensity": 0.65},
            {"state": "STORM", "intensity": 1.0},
        ]
        target_types = ["SAM", "TRUCK", "C2_NODE", "RADAR", "MANPADS"]
        for weather in weather_states:
            for target in target_types:
                rec = recommend_sensor_type(weather, target)
                assert rec in valid_sensors, f"Invalid sensor {rec} for {weather}, {target}"
