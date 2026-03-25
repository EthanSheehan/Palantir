# W5-009: Sensor Detection Upgrade — Radar Range Equation

**Status: PASS**

## Summary

Replaced the simple `1-(r/r_max)^2` detection proxy in `sensor_model.py` with a proper Nathanson radar range equation for active radar sensors.

## What Was Built

### New Types Added to `src/python/sensor_model.py`

- `RadarParameters` — frozen dataclass with fields: `transmit_power_w`, `antenna_gain_dbi`, `wavelength_m`, `noise_figure_db`
- `SENSOR_RADAR_PARAMS` — config dict mapping sensor types to `RadarParameters` (or `None` for passive sensors)
  - `EO_IR` → `None` (passive optical/IR)
  - `SAR` → 1 kW / 30 dBi / 10 GHz X-band radar params
  - `SIGINT` → `None` (passive intercept)

### New Functions Added

- `compute_snr(range_m, rcs_m2, radar_params) -> float (dB)` — Nathanson SNR equation: `P_t * G^2 * λ^2 * σ / ((4π)^3 * R^4 * kTBF)`
- `snr_to_pd(snr_db, threshold_db) -> float [0,1]` — sigmoid SNR→Pd mapping
- `compute_weather_attenuation(freq_ghz, weather_state, range_m) -> float (dB)` — simplified ITU-R P.838 frequency-dependent attenuation
- `compute_detection_probability(range_m, rcs_m2, sensor_type, env, ...) -> float [0,1]` — top-level function using radar range equation for active sensors, falling back to legacy `compute_pd()` for passive sensors

### Physics Verified

- SNR follows 1/R^4 power law: doubling range → −12 dB (tested)
- 10× transmit power → +10 dB SNR (tested)
- +10 dBi gain → +20 dB SNR (G^2 term, tested)
- Higher frequency → more rain attenuation (tested)
- Weather attenuates EO_IR; SAR less sensitive (via legacy path)

## Test Results

- **New tests**: 34 in `src/python/tests/test_radar_range.py` — all PASS
- **Existing sensor model tests**: 36 in `test_sensor_model.py` — all PASS (backward compatible)
- **Full suite**: 1370 tests — all PASS, 0 failures

## Backward Compatibility

The existing `compute_pd()` function is unchanged. All existing sensor types (EO_IR, SAR, SIGINT) return valid Pd values. The SIGINT `emitting=False` gate is preserved. All existing test thresholds pass without modification.
