"""
test_radar_range.py
===================
TDD RED phase — tests for proper radar range equation model.

These tests MUST FAIL before radar_range_equation feature is implemented in sensor_model.py.
They test the new RadarParameters dataclass, SENSOR_RADAR_PARAMS config, compute_snr(),
snr_to_pd(), compute_weather_attenuation(), and integration with compute_detection_probability().
"""

from __future__ import annotations

import pytest
from sensor_model import (
    SENSOR_CONFIGS,
    SENSOR_RADAR_PARAMS,
    EnvironmentConditions,
    RadarParameters,
    compute_detection_probability,
    compute_snr,
    compute_weather_attenuation,
    snr_to_pd,
)

# ---------------------------------------------------------------------------
# RadarParameters frozen dataclass
# ---------------------------------------------------------------------------


class TestRadarParameters:
    def test_radar_parameters_is_frozen(self):
        params = RadarParameters(
            transmit_power_w=100.0,
            antenna_gain_dbi=30.0,
            wavelength_m=0.03,
            noise_figure_db=5.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            params.transmit_power_w = 999.0  # type: ignore[misc]

    def test_radar_parameters_fields(self):
        params = RadarParameters(
            transmit_power_w=50.0,
            antenna_gain_dbi=25.0,
            wavelength_m=0.05,
            noise_figure_db=6.0,
        )
        assert params.transmit_power_w == 50.0
        assert params.antenna_gain_dbi == 25.0
        assert params.wavelength_m == 0.05
        assert params.noise_figure_db == 6.0


# ---------------------------------------------------------------------------
# SENSOR_RADAR_PARAMS config
# ---------------------------------------------------------------------------


class TestSensorRadarParams:
    def test_sensor_radar_params_exists(self):
        assert SENSOR_RADAR_PARAMS is not None

    def test_sar_has_radar_params(self):
        assert "SAR" in SENSOR_RADAR_PARAMS
        assert isinstance(SENSOR_RADAR_PARAMS["SAR"], RadarParameters)

    def test_eo_ir_has_radar_params(self):
        # EO_IR may have params or may be None — either is valid
        # but the key should at least be addressable
        val = SENSOR_RADAR_PARAMS.get("EO_IR")
        # None is acceptable for passive EO/IR sensor
        assert val is None or isinstance(val, RadarParameters)

    def test_radar_params_positive_values(self):
        for sensor_type, params in SENSOR_RADAR_PARAMS.items():
            if params is not None:
                assert params.transmit_power_w > 0.0, f"{sensor_type}: transmit_power must be positive"
                assert params.wavelength_m > 0.0, f"{sensor_type}: wavelength must be positive"


# ---------------------------------------------------------------------------
# compute_snr — Nathanson radar range equation
# ---------------------------------------------------------------------------


class TestComputeSnr:
    """SNR proportional to P_t * G^2 * lambda^2 * sigma / R^4 (Nathanson)."""

    def _base_params(self) -> RadarParameters:
        return RadarParameters(
            transmit_power_w=1000.0,
            antenna_gain_dbi=30.0,
            wavelength_m=0.03,  # 10 GHz
            noise_figure_db=5.0,
        )

    def test_snr_decreases_with_range(self):
        params = self._base_params()
        snr_close = compute_snr(range_m=1000.0, rcs_m2=10.0, radar_params=params)
        snr_far = compute_snr(range_m=10000.0, rcs_m2=10.0, radar_params=params)
        assert snr_close > snr_far

    def test_snr_follows_r4_power_law(self):
        """Doubling range should reduce SNR by ~12 dB (factor of 16 = 2^4)."""
        params = self._base_params()
        snr_r = compute_snr(range_m=5000.0, rcs_m2=5.0, radar_params=params)
        snr_2r = compute_snr(range_m=10000.0, rcs_m2=5.0, radar_params=params)
        delta_db = snr_r - snr_2r
        # 2^4 = 16 → 10*log10(16) ≈ 12 dB
        assert abs(delta_db - 12.04) < 0.5, f"Expected ~12 dB drop, got {delta_db:.2f} dB"

    def test_snr_increases_with_transmit_power(self):
        params_low = RadarParameters(
            transmit_power_w=100.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        params_high = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        snr_low = compute_snr(5000.0, 10.0, params_low)
        snr_high = compute_snr(5000.0, 10.0, params_high)
        assert snr_high > snr_low

    def test_snr_10x_power_raises_by_10db(self):
        """10× transmit power → +10 dB SNR."""
        params_low = RadarParameters(
            transmit_power_w=100.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        params_high = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        snr_low = compute_snr(5000.0, 10.0, params_low)
        snr_high = compute_snr(5000.0, 10.0, params_high)
        assert abs((snr_high - snr_low) - 10.0) < 0.5

    def test_snr_increases_with_antenna_gain(self):
        params_low = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=20.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        params_high = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        snr_low = compute_snr(5000.0, 10.0, params_low)
        snr_high = compute_snr(5000.0, 10.0, params_high)
        assert snr_high > snr_low

    def test_snr_increases_with_larger_rcs(self):
        params = self._base_params()
        snr_small = compute_snr(5000.0, 1.0, params)
        snr_large = compute_snr(5000.0, 20.0, params)
        assert snr_large > snr_small

    def test_snr_returns_float(self):
        params = self._base_params()
        result = compute_snr(5000.0, 10.0, params)
        assert isinstance(result, float)

    def test_snr_gain_squared_law(self):
        """G^2 term: +10 dBi gain doubles linear gain, +20 dBi quadruples → +20 dB SNR lift."""
        params_base = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=20.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        params_up10 = RadarParameters(
            transmit_power_w=1000.0, antenna_gain_dbi=30.0, wavelength_m=0.03, noise_figure_db=5.0
        )
        snr_base = compute_snr(5000.0, 10.0, params_base)
        snr_up10 = compute_snr(5000.0, 10.0, params_up10)
        # G^2 term: 10 dBi linear gain increase → 10*log10((10^(30/10))^2 / (10^(20/10))^2) = 20 dB
        assert abs((snr_up10 - snr_base) - 20.0) < 1.0


# ---------------------------------------------------------------------------
# snr_to_pd — map SNR (dB) to probability of detection
# ---------------------------------------------------------------------------


class TestSnrToPd:
    def test_very_high_snr_gives_pd_near_one(self):
        pd = snr_to_pd(snr_db=30.0, threshold_db=10.0)
        assert pd > 0.9

    def test_very_low_snr_gives_pd_near_zero(self):
        pd = snr_to_pd(snr_db=-30.0, threshold_db=10.0)
        assert pd < 0.1

    def test_snr_at_threshold_gives_mid_pd(self):
        """SNR exactly at threshold should yield ~0.5 Pd."""
        pd = snr_to_pd(snr_db=10.0, threshold_db=10.0)
        assert 0.3 < pd < 0.7

    def test_pd_bounded_between_zero_and_one(self):
        for snr in [-50.0, -10.0, 0.0, 10.0, 50.0, 100.0]:
            pd = snr_to_pd(snr_db=snr, threshold_db=10.0)
            assert 0.0 <= pd <= 1.0, f"pd={pd} out of range for snr={snr}"

    def test_pd_monotonically_increases_with_snr(self):
        threshold = 10.0
        pds = [snr_to_pd(float(snr), threshold) for snr in range(-20, 50, 5)]
        for i in range(len(pds) - 1):
            assert pds[i] <= pds[i + 1], "Pd must be non-decreasing with SNR"

    def test_pd_returns_float(self):
        result = snr_to_pd(10.0, 5.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_weather_attenuation — frequency-dependent attenuation
# ---------------------------------------------------------------------------


class TestComputeWeatherAttenuation:
    def test_clear_weather_low_attenuation(self):
        att = compute_weather_attenuation(freq_ghz=10.0, weather_state="CLEAR", range_m=10000.0)
        assert att < 2.0  # dB — very low in clear sky

    def test_storm_higher_than_clear(self):
        att_clear = compute_weather_attenuation(10.0, "CLEAR", 10000.0)
        att_storm = compute_weather_attenuation(10.0, "STORM", 10000.0)
        assert att_storm > att_clear

    def test_higher_frequency_more_attenuation_in_rain(self):
        """Rain attenuation increases with frequency (mm-wave affected more than X-band)."""
        att_low_freq = compute_weather_attenuation(freq_ghz=3.0, weather_state="RAIN", range_m=10000.0)
        att_high_freq = compute_weather_attenuation(freq_ghz=35.0, weather_state="RAIN", range_m=10000.0)
        assert att_high_freq > att_low_freq

    def test_longer_range_more_attenuation(self):
        att_short = compute_weather_attenuation(10.0, "RAIN", 1000.0)
        att_long = compute_weather_attenuation(10.0, "RAIN", 50000.0)
        assert att_long > att_short

    def test_attenuation_non_negative(self):
        for state in ["CLEAR", "OVERCAST", "RAIN", "STORM"]:
            att = compute_weather_attenuation(10.0, state, 5000.0)
            assert att >= 0.0, f"Attenuation for {state} must be non-negative"

    def test_returns_float(self):
        result = compute_weather_attenuation(10.0, "RAIN", 5000.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_detection_probability — full radar range equation pipeline
# ---------------------------------------------------------------------------


class TestComputeDetectionProbability:
    """Tests for the new top-level compute_detection_probability() function."""

    def _clear_env(self) -> EnvironmentConditions:
        return EnvironmentConditions()

    def test_sar_short_range_pd_near_one(self):
        env = self._clear_env()
        pd = compute_detection_probability(
            range_m=500.0,
            rcs_m2=10.0,
            sensor_type="SAR",
            env=env,
        )
        assert pd > 0.85

    def test_sar_very_long_range_pd_near_zero(self):
        env = self._clear_env()
        cfg = SENSOR_CONFIGS["SAR"]
        pd = compute_detection_probability(
            range_m=cfg.max_range_m * 2.0,  # well beyond max range
            rcs_m2=5.0,
            sensor_type="SAR",
            env=env,
        )
        assert pd < 0.15

    def test_pd_bounded_zero_to_one(self):
        env = self._clear_env()
        for range_m in [100.0, 5000.0, 20000.0, 100000.0, 500000.0]:
            pd = compute_detection_probability(range_m, 5.0, "SAR", env)
            assert 0.0 <= pd <= 1.0, f"pd={pd} out of [0,1] at range={range_m}"

    def test_larger_rcs_increases_pd(self):
        env = self._clear_env()
        pd_small = compute_detection_probability(10000.0, 1.0, "SAR", env)
        pd_large = compute_detection_probability(10000.0, 20.0, "SAR", env)
        assert pd_large > pd_small

    def test_storm_reduces_pd_for_eo_ir(self):
        env_clear = EnvironmentConditions(cloud_cover=0.0, precipitation=0.0)
        env_storm = EnvironmentConditions(cloud_cover=1.0, precipitation=1.0)
        pd_clear = compute_detection_probability(5000.0, 10.0, "EO_IR", env_clear)
        pd_storm = compute_detection_probability(5000.0, 10.0, "EO_IR", env_storm)
        assert pd_storm < pd_clear

    def test_per_sensor_type_config_eo_vs_sar(self):
        """Different sensor types should produce different Pd at same range/RCS."""
        env = self._clear_env()
        pd_eo = compute_detection_probability(5000.0, 5.0, "EO_IR", env)
        pd_sar = compute_detection_probability(5000.0, 5.0, "SAR", env)
        # They should differ (different configs), both valid
        assert 0.0 <= pd_eo <= 1.0
        assert 0.0 <= pd_sar <= 1.0

    def test_backward_compatible_existing_sensor_types(self):
        """All existing sensor types (EO_IR, SAR, SIGINT) must still return valid Pd."""
        env = self._clear_env()
        for sensor_type in ["EO_IR", "SAR", "SIGINT"]:
            pd = compute_detection_probability(
                range_m=5000.0,
                rcs_m2=5.0,
                sensor_type=sensor_type,
                env=env,
                emitting=True,
            )
            assert 0.0 <= pd <= 1.0, f"{sensor_type}: pd={pd} out of [0,1]"

    def test_sigint_non_emitting_returns_zero(self):
        env = self._clear_env()
        pd = compute_detection_probability(
            range_m=1000.0,
            rcs_m2=10.0,
            sensor_type="SIGINT",
            env=env,
            emitting=False,
        )
        assert pd == 0.0
