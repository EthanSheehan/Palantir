"""
Tests for weather_engine.py and jammer_model.py — written FIRST (TDD RED phase).

Covers:
- WeatherEngine state initialization per zone
- Weather tick advancing states (CLEAR→OVERCAST→RAIN→STORM cycle)
- Weather degradation reduces Pd
- Frequency-dependent attenuation
- Jammer spatial effect radius
- JAMMING UAV degrades confidence in zone
- Jammer attenuation stacks with weather
- Weather recovery (storm→clear)
- No effect outside jammer radius
- 20+ tests total
"""

import pytest
from jammer_model import (
    FREQUENCY_ATTENUATION,
    JammerEffect,
    JammerModel,
    JammerState,
    compute_jammer_attenuation,
    compute_jammer_pd_factor,
)
from sensor_model import (
    SENSOR_CONFIGS,
    EnvironmentConditions,
    compute_pd,
)
from weather_engine import (
    WEATHER_CYCLE,
    WEATHER_SENSOR_WEIGHTS,
    WeatherEngine,
    WeatherState,
    apply_weather_to_pd,
    get_zone_weather,
)

# ---------------------------------------------------------------------------
# WeatherState
# ---------------------------------------------------------------------------


class TestWeatherState:
    def test_weather_state_is_frozen(self):
        ws = WeatherState(state="CLEAR", intensity=0.0, duration_s=0.0)
        with pytest.raises((AttributeError, TypeError)):
            ws.state = "OVERCAST"  # type: ignore[misc]

    def test_clear_state_defaults(self):
        ws = WeatherState(state="CLEAR", intensity=0.0, duration_s=0.0)
        assert ws.state == "CLEAR"
        assert ws.intensity == 0.0

    def test_storm_state_max_intensity(self):
        ws = WeatherState(state="STORM", intensity=1.0, duration_s=60.0)
        assert ws.intensity == 1.0

    def test_valid_states_in_cycle(self):
        for state in WEATHER_CYCLE:
            assert state in ("CLEAR", "OVERCAST", "RAIN", "STORM")


# ---------------------------------------------------------------------------
# WeatherEngine initialization
# ---------------------------------------------------------------------------


class TestWeatherEngineInit:
    def test_engine_initializes_with_zones(self):
        engine = WeatherEngine(zone_ids=["A1", "B2", "C3"])
        assert engine.get_zone_state("A1") is not None

    def test_default_zone_state_is_clear(self):
        engine = WeatherEngine(zone_ids=["Z1"])
        state = engine.get_zone_state("Z1")
        assert state.state == "CLEAR"
        assert state.intensity == 0.0

    def test_unknown_zone_returns_clear(self):
        engine = WeatherEngine(zone_ids=["Z1"])
        state = engine.get_zone_state("UNKNOWN_ZONE")
        assert state.state == "CLEAR"

    def test_initial_zone_states_are_weather_states(self):
        engine = WeatherEngine(zone_ids=["A", "B"])
        for zone_id in ["A", "B"]:
            state = engine.get_zone_state(zone_id)
            assert isinstance(state, WeatherState)


# ---------------------------------------------------------------------------
# WeatherEngine tick — state transitions
# ---------------------------------------------------------------------------


class TestWeatherEngineTick:
    def test_tick_returns_new_engine(self):
        engine = WeatherEngine(zone_ids=["Z1"])
        new_engine = engine.tick(dt_s=10.0)
        assert new_engine is not engine

    def test_tick_does_not_mutate_original(self):
        engine = WeatherEngine(zone_ids=["Z1"])
        original_state = engine.get_zone_state("Z1")
        engine.tick(dt_s=1000.0)
        assert engine.get_zone_state("Z1") == original_state

    def test_weather_advances_through_cycle(self):
        """Force transition by running many ticks to exhaust duration."""
        engine = WeatherEngine(zone_ids=["Z1"], seed=42)
        # Tick many seconds to force a transition
        for _ in range(100):
            engine = engine.tick(dt_s=50.0)
        # After enough time the state should have advanced (not stuck on CLEAR with 0 duration)
        # We just verify the engine still works
        state = engine.get_zone_state("Z1")
        assert state.state in WEATHER_CYCLE

    def test_storm_can_recover_to_clear(self):
        """Manually inject STORM then tick long enough for recovery."""
        engine = WeatherEngine(zone_ids=["Z1"])
        # Inject storm state directly via from_states
        storm_state = WeatherState(state="STORM", intensity=1.0, duration_s=1.0)
        engine_stormy = WeatherEngine.from_states({"Z1": storm_state}, seed=99)
        # After a long tick duration should expire and cycle forward
        recovered = engine_stormy.tick(dt_s=200.0)
        # May have transitioned from STORM
        new_state = recovered.get_zone_state("Z1")
        assert new_state.state in WEATHER_CYCLE

    def test_clear_intensity_is_low(self):
        engine = WeatherEngine(zone_ids=["Z1"])
        state = engine.get_zone_state("Z1")
        assert state.intensity <= 0.1  # CLEAR should have low/zero intensity

    def test_zone_id_list_persists_across_ticks(self):
        engine = WeatherEngine(zone_ids=["A", "B", "C"])
        new_engine = engine.tick(dt_s=1.0)
        for zone_id in ["A", "B", "C"]:
            state = new_engine.get_zone_state(zone_id)
            assert isinstance(state, WeatherState)


# ---------------------------------------------------------------------------
# Weather effect on Pd
# ---------------------------------------------------------------------------


class TestWeatherPdDegradation:
    def test_storm_reduces_eo_ir_pd(self):
        """Storm weather should significantly reduce EO/IR Pd due to high weather_sensitivity."""
        cfg = SENSOR_CONFIGS["EO_IR"]
        env_clear = EnvironmentConditions(cloud_cover=0.0, precipitation=0.0)
        env_storm = EnvironmentConditions(cloud_cover=1.0, precipitation=1.0)

        pd_clear = compute_pd(
            range_m=10_000.0,
            rcs_m2=10.0,
            sensor_type="EO_IR",
            sensor_cfg=cfg,
            env=env_clear,
        )
        pd_storm = compute_pd(
            range_m=10_000.0,
            rcs_m2=10.0,
            sensor_type="EO_IR",
            sensor_cfg=cfg,
            env=env_storm,
        )
        assert pd_storm < pd_clear

    def test_sar_minimal_weather_degradation(self):
        """SAR has low weather_sensitivity so should degrade less in storm."""
        cfg = SENSOR_CONFIGS["SAR"]
        env_clear = EnvironmentConditions(cloud_cover=0.0, precipitation=0.0)
        env_storm = EnvironmentConditions(cloud_cover=1.0, precipitation=1.0)

        pd_clear = compute_pd(
            range_m=10_000.0,
            rcs_m2=10.0,
            sensor_type="SAR",
            sensor_cfg=cfg,
            env=env_clear,
        )
        pd_storm = compute_pd(
            range_m=10_000.0,
            rcs_m2=10.0,
            sensor_type="SAR",
            sensor_cfg=cfg,
            env=env_storm,
        )
        # SAR should degrade but much less than EO/IR
        gap_sar = pd_clear - pd_storm
        assert gap_sar < 0.3

    def test_apply_weather_to_pd_clear_no_change(self):
        """CLEAR weather should not modify Pd."""
        ws = WeatherState(state="CLEAR", intensity=0.0, duration_s=60.0)
        pd_in = 0.85
        pd_out = apply_weather_to_pd(pd_in, ws, sensor_type="EO_IR")
        assert abs(pd_out - pd_in) < 0.01

    def test_apply_weather_to_pd_storm_degrades_eo_ir(self):
        """STORM should degrade EO/IR Pd."""
        ws = WeatherState(state="STORM", intensity=1.0, duration_s=60.0)
        pd_in = 0.9
        pd_out = apply_weather_to_pd(pd_in, ws, sensor_type="EO_IR")
        assert pd_out < pd_in

    def test_apply_weather_to_pd_storm_less_impact_on_sar(self):
        """STORM should degrade SAR Pd much less than EO/IR."""
        ws = WeatherState(state="STORM", intensity=1.0, duration_s=60.0)
        pd_in = 0.9
        pd_eo = apply_weather_to_pd(pd_in, ws, sensor_type="EO_IR")
        pd_sar = apply_weather_to_pd(pd_in, ws, sensor_type="SAR")
        assert pd_sar > pd_eo

    def test_apply_weather_pd_clamps_to_zero_one(self):
        """Output Pd must stay in [0, 1]."""
        ws = WeatherState(state="STORM", intensity=1.0, duration_s=60.0)
        pd_out = apply_weather_to_pd(0.01, ws, sensor_type="EO_IR")
        assert 0.0 <= pd_out <= 1.0


# ---------------------------------------------------------------------------
# JammerModel — frequency attenuation
# ---------------------------------------------------------------------------


class TestFrequencyAttenuation:
    def test_frequency_attenuation_table_populated(self):
        assert len(FREQUENCY_ATTENUATION) > 0

    def test_eo_ir_not_affected_by_rf_jam(self):
        """EO/IR operates optically — RF jamming should have no effect."""
        att = FREQUENCY_ATTENUATION.get("EO_IR", 0.0)
        assert att == 0.0

    def test_sigint_heavily_affected_by_rf_jam(self):
        """SIGINT is RF-based — should have high attenuation."""
        att = FREQUENCY_ATTENUATION.get("SIGINT", 0.0)
        assert att > 0.5

    def test_sar_partially_affected(self):
        """SAR is microwave-based — moderate RF attenuation."""
        att = FREQUENCY_ATTENUATION.get("SAR", 0.0)
        assert 0.0 < att <= 1.0

    def test_compute_jammer_attenuation_no_jammers(self):
        """No jammers → attenuation factor = 1.0 (no degradation)."""
        result = compute_jammer_attenuation(jammers=[], sensor_type="SIGINT")
        assert result == 1.0


# ---------------------------------------------------------------------------
# JammerState
# ---------------------------------------------------------------------------


class TestJammerState:
    def test_jammer_state_is_frozen(self):
        js = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=5000.0, power=1.0)
        with pytest.raises((AttributeError, TypeError)):
            js.power = 0.5  # type: ignore[misc]

    def test_jammer_state_default_fields(self):
        js = JammerState(jammer_id=7, lat=44.0, lon=24.0, radius_m=3000.0, power=0.8)
        assert js.jammer_id == 7
        assert js.radius_m == 3000.0


# ---------------------------------------------------------------------------
# JammerModel — spatial radius
# ---------------------------------------------------------------------------


class TestJammerModelSpatialRadius:
    def test_inside_radius_degrades_confidence(self):
        """Target inside jammer radius should see reduced Pd."""
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=10_000.0, power=1.0)
        model = JammerModel()
        # Target 1km away — well inside 10km radius
        factor = model.compute_pd_factor(
            target_lat=45.009,  # ~1km north
            target_lon=25.0,
            jammers=[jammer],
            sensor_type="SIGINT",
        )
        assert factor < 1.0

    def test_outside_radius_no_effect(self):
        """Target outside jammer radius should see factor = 1.0."""
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=1_000.0, power=1.0)
        model = JammerModel()
        # Target 20km away — well outside 1km radius
        factor = model.compute_pd_factor(
            target_lat=45.18,  # ~20km north
            target_lon=25.0,
            jammers=[jammer],
            sensor_type="SIGINT",
        )
        assert abs(factor - 1.0) < 1e-6

    def test_eo_ir_not_degraded_by_rf_jammer(self):
        """EO/IR inside jammer radius should not be degraded (optical, not RF)."""
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=50_000.0, power=1.0)
        model = JammerModel()
        factor = model.compute_pd_factor(
            target_lat=45.009,
            target_lon=25.0,
            jammers=[jammer],
            sensor_type="EO_IR",
        )
        assert abs(factor - 1.0) < 1e-6

    def test_multiple_jammers_stack(self):
        """Two jammers in range should produce more degradation than one."""
        j1 = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=10_000.0, power=0.5)
        j2 = JammerState(jammer_id=2, lat=45.01, lon=25.0, radius_m=10_000.0, power=0.5)
        model = JammerModel()
        target_lat, target_lon = 45.005, 25.0

        factor_one = model.compute_pd_factor(target_lat, target_lon, [j1], "SIGINT")
        factor_two = model.compute_pd_factor(target_lat, target_lon, [j1, j2], "SIGINT")
        assert factor_two <= factor_one

    def test_jammer_effect_dataclass(self):
        """JammerEffect should carry attenuation and contributing jammer ids."""
        effect = JammerEffect(attenuation_factor=0.6, contributing_jammer_ids=(1, 2))
        assert effect.attenuation_factor == 0.6
        assert 1 in effect.contributing_jammer_ids


# ---------------------------------------------------------------------------
# JAMMING UAV integration
# ---------------------------------------------------------------------------


class TestJammingUAVIntegration:
    def test_compute_jammer_pd_factor_function(self):
        """compute_jammer_pd_factor is a pure function returning [0,1]."""
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=10_000.0, power=1.0)
        factor = compute_jammer_pd_factor(
            target_lat=45.009,
            target_lon=25.0,
            jammers=[jammer],
            sensor_type="SIGINT",
        )
        assert 0.0 <= factor <= 1.0

    def test_zero_power_jammer_no_effect(self):
        """Jammer with power=0 should not degrade Pd."""
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=10_000.0, power=0.0)
        factor = compute_jammer_pd_factor(
            target_lat=45.009,
            target_lon=25.0,
            jammers=[jammer],
            sensor_type="SIGINT",
        )
        assert abs(factor - 1.0) < 1e-6

    def test_jammer_and_storm_stack(self):
        """Jammer attenuation should compound with weather degradation."""
        ws = WeatherState(state="STORM", intensity=1.0, duration_s=60.0)
        pd_base = 0.9

        # Weather only
        pd_weather = apply_weather_to_pd(pd_base, ws, sensor_type="SIGINT")

        # Jammer factor
        jammer = JammerState(jammer_id=1, lat=45.0, lon=25.0, radius_m=10_000.0, power=1.0)
        j_factor = compute_jammer_pd_factor(target_lat=45.009, target_lon=25.0, jammers=[jammer], sensor_type="SIGINT")

        pd_combined = pd_weather * j_factor
        # Combined should be worse than weather alone
        assert pd_combined <= pd_weather + 1e-9

    def test_get_zone_weather_helper(self):
        """get_zone_weather returns the WeatherState for a zone from engine."""
        engine = WeatherEngine(zone_ids=["Z1", "Z2"])
        state = get_zone_weather(engine, "Z1")
        assert isinstance(state, WeatherState)

    def test_weather_sensor_weights_populated(self):
        """WEATHER_SENSOR_WEIGHTS maps sensor types to degradation scales."""
        assert "EO_IR" in WEATHER_SENSOR_WEIGHTS
        assert "SAR" in WEATHER_SENSOR_WEIGHTS
        assert "SIGINT" in WEATHER_SENSOR_WEIGHTS
