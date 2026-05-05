"""
sensor_model.py
===============
Physics-informed probabilistic sensor model for the Grid-Sentinel C2 system.

Replaces the hard 0.5° proximity check in sim_engine.py with a Pd (probability
of detection) model based on:
  - Range vs sensor maximum range
  - Target radar cross-section (RCS) modulated by aspect angle
  - Environmental conditions (cloud cover, precipitation)
  - Sensor modality characteristics (EO/IR, SAR, SIGINT)

All public types are immutable frozen dataclasses. No mutation anywhere.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from terrain_model import TerrainModel

# ---------------------------------------------------------------------------
# Sensor configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensorConfig:
    max_range_m: float
    reference_rcs_m2: float
    resolution_factor: float
    weather_sensitivity: float  # 0.0 = immune, 1.0 = fully degraded by weather
    requires_emitter: bool


@dataclass(frozen=True)
class EnvironmentConditions:
    time_of_day: float = 12.0  # 0-24 h
    cloud_cover: float = 0.0  # 0-1
    precipitation: float = 0.0  # 0-1


@dataclass(frozen=True)
class DetectionResult:
    detected: bool
    pd: float
    range_m: float
    sensor_type: str
    confidence: float
    bearing_deg: float


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

RCS_TABLE: dict[str, float] = {
    "SAM": 15.0,
    "TEL": 10.0,
    "TRUCK": 5.0,
    "CP": 8.0,
    "MANPADS": 0.5,
    "RADAR": 20.0,
    "C2_NODE": 6.0,
    "LOGISTICS": 4.0,
    "ENEMY_UAV": 2.0,
}

FALLBACK_RCS_M2 = 3.0
# Backwards-compatible alias (private name kept for any external references)
_FALLBACK_RCS_M2 = FALLBACK_RCS_M2

SENSOR_CONFIGS: dict[str, SensorConfig] = {
    "EO_IR": SensorConfig(
        max_range_m=50_000.0,  # ~50km effective range (simulation scale)
        reference_rcs_m2=5.0,
        resolution_factor=1.0,
        weather_sensitivity=0.8,
        requires_emitter=False,
    ),
    "SAR": SensorConfig(
        max_range_m=100_000.0,  # ~100km SAR range (simulation scale)
        reference_rcs_m2=5.0,
        resolution_factor=0.7,
        weather_sensitivity=0.2,
        requires_emitter=False,
    ),
    "SIGINT": SensorConfig(
        max_range_m=200_000.0,  # ~200km SIGINT range (simulation scale)
        reference_rcs_m2=1.0,
        resolution_factor=0.3,
        weather_sensitivity=0.0,
        requires_emitter=True,
    ),
}


# ---------------------------------------------------------------------------
# Radar range equation — Nathanson model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RadarParameters:
    """Per-sensor radar hardware parameters for the Nathanson range equation.

    SNR ∝ P_t * G^2 * lambda^2 * sigma / R^4
    """

    transmit_power_w: float  # Transmitter peak power (Watts)
    antenna_gain_dbi: float  # Antenna gain (dBi)
    wavelength_m: float  # Carrier wavelength (meters), λ = c/f
    noise_figure_db: float  # Receiver noise figure (dB)


# Radar parameters per sensor type. None = passive sensor (no transmit).
# SAR: X-band (10 GHz), λ=0.03 m, 1 kW typical airborne SAR
# SIGINT: passive intercept receiver — no transmit power
# EO_IR: electro-optical/IR — passive, no radar transmit
SENSOR_RADAR_PARAMS: dict[str, Optional[RadarParameters]] = {
    "EO_IR": None,  # passive optical/IR sensor
    "SAR": RadarParameters(
        transmit_power_w=1_000.0,  # 1 kW peak, typical airborne SAR
        antenna_gain_dbi=30.0,  # 30 dBi phased array
        wavelength_m=0.03,  # 10 GHz X-band
        noise_figure_db=5.0,
    ),
    "SIGINT": None,  # passive intercept — no transmit
}

# Boltzmann constant (J/K)
_K_BOLTZMANN = 1.380649e-23
# System noise temperature (K) — standard ~290 K receiver temperature
_NOISE_TEMP_K = 290.0
# Reference bandwidth (Hz) — 1 MHz typical pulse compression output
_NOISE_BW_HZ = 1e6

# Detection threshold SNR (dB): Pd=0.5 at this SNR for snr_to_pd()
_DETECTION_THRESHOLD_DB = 13.0  # ~13 dB for Pd=0.5 in Swerling Case 1

# Rain-specific specific attenuation model coefficients (ITU-R P.838 simplified)
# α (dB/km) = k * R_rain^α_exp where R_rain is rain rate in mm/h
# Approximate specific attenuation at 10 GHz in moderate rain: ~0.01 dB/km/mm/h
_RAIN_ATTENUATION_RATE_DB_PER_KM_PER_MH = {
    "CLEAR": 0.0,
    "OVERCAST": 0.0002,
    "RAIN": 0.005,
    "STORM": 0.025,
}
# Frequency scaling exponent — higher freq = more attenuation
_FREQ_ATTENUATION_EXPONENT = 1.6


def compute_snr(range_m: float, rcs_m2: float, radar_params: RadarParameters) -> float:
    """Return received SNR in dB using the Nathanson radar range equation.

    SNR = (P_t * G^2 * lambda^2 * sigma) / ((4*pi)^3 * R^4 * k * T * B * F)

    Parameters
    ----------
    range_m      : Slant range to target (metres).
    rcs_m2       : Target radar cross-section (m²).
    radar_params : Sensor-specific radar hardware parameters.

    Returns
    -------
    SNR in dB.  May be negative for long-range / low-RCS targets.
    """
    P_t = radar_params.transmit_power_w
    # Convert dBi to linear gain
    G = 10.0 ** (radar_params.antenna_gain_dbi / 10.0)
    lam = radar_params.wavelength_m
    sigma = max(rcs_m2, 1e-6)  # guard against zero RCS
    R = max(range_m, 1.0)  # guard against zero range
    F = 10.0 ** (radar_params.noise_figure_db / 10.0)

    numerator = P_t * (G**2) * (lam**2) * sigma
    denominator = ((4.0 * math.pi) ** 3) * (R**4) * _K_BOLTZMANN * _NOISE_TEMP_K * _NOISE_BW_HZ * F

    snr_linear = numerator / denominator
    return float(10.0 * math.log10(max(snr_linear, 1e-20)))


def snr_to_pd(snr_db: float, threshold_db: float) -> float:
    """Map SNR (dB) to probability of detection using a sigmoid function.

    Pd = sigmoid((SNR_dB - threshold_dB) * 0.5)
    At SNR == threshold → Pd ≈ 0.5; well above threshold → Pd → 1; below → Pd → 0.

    Returns float in [0, 1].
    """
    x = (snr_db - threshold_db) * 0.5
    if x >= 0:
        pd = 1.0 / (1.0 + math.exp(-x))
    else:
        exp_x = math.exp(x)
        pd = exp_x / (1.0 + exp_x)
    return float(max(0.0, min(1.0, pd)))


def compute_weather_attenuation(freq_ghz: float, weather_state: str, range_m: float) -> float:
    """Return one-way path attenuation (dB) due to weather at given frequency.

    Uses a simplified ITU-R P.838 model:
        attenuation (dB) = base_rate * (freq_ghz / 10.0)^1.6 * range_km

    Parameters
    ----------
    freq_ghz    : Radar carrier frequency in GHz.
    weather_state : Weather state string (CLEAR, OVERCAST, RAIN, STORM).
    range_m     : One-way path length in metres.

    Returns
    -------
    Attenuation in dB (non-negative).
    """
    base_rate = _RAIN_ATTENUATION_RATE_DB_PER_KM_PER_MH.get(weather_state, 0.0)
    range_km = range_m / 1000.0
    freq_scale = (freq_ghz / 10.0) ** _FREQ_ATTENUATION_EXPONENT
    attenuation_db = base_rate * freq_scale * range_km
    return float(max(0.0, attenuation_db))


def compute_detection_probability(
    range_m: float,
    rcs_m2: float,
    sensor_type: str,
    env: EnvironmentConditions,
    emitting: bool = True,
    altitude_m: float = 0.0,
) -> float:
    """Return Pd in [0,1] using the radar range equation for active sensors.

    For passive sensors (EO_IR, SIGINT), falls back to the legacy compute_pd()
    model so backward compatibility is maintained.

    Parameters
    ----------
    range_m      : Slant range to target (metres).
    rcs_m2       : Target radar cross-section (m²).
    sensor_type  : Key into SENSOR_CONFIGS and SENSOR_RADAR_PARAMS.
    env          : Environmental conditions.
    emitting     : Whether the target is actively emitting (SIGINT gate).
    altitude_m   : Sensor altitude (for altitude penalty on passive sensors).
    """
    sensor_cfg = SENSOR_CONFIGS[sensor_type]

    # SIGINT hard gate
    if sensor_cfg.requires_emitter and not emitting:
        return 0.0

    radar_params = SENSOR_RADAR_PARAMS.get(sensor_type)

    if radar_params is not None:
        # Active radar sensor — use Nathanson range equation
        # Determine carrier frequency from wavelength (c = f*λ)
        freq_ghz = 3e8 / (radar_params.wavelength_m * 1e9)

        # Two-way path weather attenuation (dB)
        weather_state = _env_to_weather_state(env)
        weather_att_db = compute_weather_attenuation(freq_ghz, weather_state, range_m) * 2.0

        snr_db = compute_snr(range_m, rcs_m2, radar_params) - weather_att_db
        pd = snr_to_pd(snr_db, _DETECTION_THRESHOLD_DB)
    else:
        # Passive sensor (EO_IR, SIGINT) — use legacy sigmoid model
        pd = compute_pd(
            range_m=range_m,
            rcs_m2=rcs_m2,
            sensor_type=sensor_type,
            sensor_cfg=sensor_cfg,
            env=env,
            emitting=emitting,
            altitude_m=altitude_m,
        )

    return float(max(0.0, min(1.0, pd)))


def _env_to_weather_state(env: EnvironmentConditions) -> str:
    """Map EnvironmentConditions to a weather state string for attenuation lookup."""
    combined = env.cloud_cover + env.precipitation
    if combined >= 1.5:
        return "STORM"
    if combined >= 0.8:
        return "RAIN"
    if combined >= 0.3:
        return "OVERCAST"
    return "CLEAR"


# ---------------------------------------------------------------------------
# Core geometry
# ---------------------------------------------------------------------------


def deg_to_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the approximate great-circle distance in metres between two WGS-84
    points given as (lat, lon) pairs in decimal degrees.

    Uses the equirectangular approximation — accurate to <0.5% within 100 km.
    """
    lat_m_per_deg = 111_320.0
    mid_lat_rad = math.radians((lat1 + lat2) / 2.0)
    lon_m_per_deg = 111_320.0 * math.cos(mid_lat_rad)

    dy = (lat2 - lat1) * lat_m_per_deg
    dx = (lon2 - lon1) * lon_m_per_deg
    return math.hypot(dy, dx)


# ---------------------------------------------------------------------------
# RCS aspect modulation
# ---------------------------------------------------------------------------


def compute_aspect_rcs(base_rcs_m2: float, aspect_deg: float) -> float:
    """Return RCS modulated by the aspect angle of the sensor relative to the
    target's heading.

    Aspect 0° / 180° = axial (head-on / tail-on) → minimum RCS (~0.3× base).
    Aspect 90° / 270° = broadside → maximum RCS (~1.5× base).

    Uses a cosine model:
        factor = 0.9 - 0.6 * |cos(aspect)|
    which yields:
        aspect 0° → 0.9 - 0.6 = 0.3
        aspect 90° → 0.9 - 0.0 = 0.9   (scale up to 1.5 via separate multiplier)

    Actual formula to hit both anchors exactly:
        factor = 0.3 + 1.2 * sin²(aspect)
    """
    rad = math.radians(aspect_deg)
    sin2 = math.sin(rad) ** 2
    factor = 0.3 + 1.2 * sin2
    return float(base_rcs_m2 * factor)


# ---------------------------------------------------------------------------
# Probability of detection
# ---------------------------------------------------------------------------


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def compute_pd(
    range_m: float,
    rcs_m2: float,
    sensor_type: str,
    sensor_cfg: SensorConfig,
    env: EnvironmentConditions,
    emitting: bool = True,
    altitude_m: float = 0.0,
) -> float:
    """Return probability of detection in [0, 1].

    Formula (from spec):
        snr_norm = (1 - (range/max_range)^2)
                   + rcs_gain * 0.3
                   - altitude_penalty
                   - weather_penalty
        Pd = sigmoid(snr_norm * 10 - 5)

    altitude_penalty: higher sensor altitude degrades resolution.
        penalty = max(0, (altitude_m - 1000) / 10000)
        At 3000m default: penalty = 0.2 (small degradation).

    Hard gates:
      - SIGINT with emitting=False → 0.0
      - range > max_range → very low but still sigmoid-bounded
    """
    if sensor_cfg.requires_emitter and not emitting:
        return 0.0

    max_range = sensor_cfg.max_range_m
    # Normalised range term: 1 at zero range, 0 at max_range, negative beyond
    range_term = 1.0 - (range_m / max_range) ** 2

    # RCS gain: log ratio of target RCS to sensor reference RCS
    if rcs_m2 > 0.0 and sensor_cfg.reference_rcs_m2 > 0.0:
        rcs_gain = math.log10(rcs_m2 / sensor_cfg.reference_rcs_m2)
    else:
        rcs_gain = 0.0

    # Weather penalty: cloud cover degrades weather-sensitive sensors
    weather_penalty = sensor_cfg.weather_sensitivity * (env.cloud_cover + env.precipitation * 0.5) * 0.6

    # Altitude penalty: higher altitude degrades sensor resolution
    altitude_penalty = max(0.0, (altitude_m - 1000.0) / 10000.0)

    snr_norm = range_term + rcs_gain * 0.3 - altitude_penalty - weather_penalty
    pd = _sigmoid(snr_norm * 10.0 - 5.0)
    return float(max(0.0, min(1.0, pd)))


# ---------------------------------------------------------------------------
# Top-level detection evaluation
# ---------------------------------------------------------------------------


def _compute_bearing(uav_lat: float, uav_lon: float, target_lat: float, target_lon: float) -> float:
    dlat = target_lat - uav_lat
    dlon = (target_lon - uav_lon) * math.cos(math.radians((uav_lat + target_lat) / 2.0))
    bearing_rad = math.atan2(dlon, dlat)
    return (math.degrees(bearing_rad) + 360.0) % 360.0


def evaluate_detection(
    uav_lat: float,
    uav_lon: float,
    target_lat: float,
    target_lon: float,
    target_type: str,
    sensor_type: str,
    env: EnvironmentConditions,
    aspect_deg: float = 90.0,
    emitting: bool = True,
    altitude_m: float = 0.0,
    terrain_model: "Optional[TerrainModel]" = None,
) -> DetectionResult:
    """Evaluate whether a UAV sensor detects a ground target in a single pass.

    Returns a frozen DetectionResult. No state is mutated.

    Parameters
    ----------
    uav_lat/lon      : UAV position in decimal degrees.
    target_lat/lon   : Target position in decimal degrees.
    target_type      : Key into RCS_TABLE; unknown types use fallback RCS.
    sensor_type      : Key into SENSOR_CONFIGS (EO_IR, SAR, SIGINT).
    env              : Environmental conditions (cloud, precipitation, ToD).
    aspect_deg       : Sensor-to-target aspect angle in degrees (default 90°).
    emitting         : Whether the target is actively emitting (SIGINT gate).
    terrain_model    : Optional TerrainModel; if LOS is blocked, Pd = 0.
    """
    sensor_cfg = SENSOR_CONFIGS[sensor_type]

    range_m = deg_to_meters(uav_lat, uav_lon, target_lat, target_lon)

    # Terrain LOS gate — import deferred to avoid circular imports
    if terrain_model is not None:
        from terrain_model import has_line_of_sight  # noqa: PLC0415

        if not has_line_of_sight(
            terrain_model,
            uav_lat,
            uav_lon,
            altitude_m,
            target_lat,
            target_lon,
            0.0,
        ):
            bearing_deg = _compute_bearing(uav_lat, uav_lon, target_lat, target_lon)
            return DetectionResult(
                detected=False,
                pd=0.0,
                range_m=range_m,
                sensor_type=sensor_type,
                confidence=0.0,
                bearing_deg=bearing_deg,
            )

    base_rcs = RCS_TABLE.get(target_type, _FALLBACK_RCS_M2)
    effective_rcs = compute_aspect_rcs(base_rcs, aspect_deg)

    pd = compute_pd(
        range_m=range_m,
        rcs_m2=effective_rcs,
        sensor_type=sensor_type,
        sensor_cfg=sensor_cfg,
        env=env,
        emitting=emitting,
        altitude_m=altitude_m,
    )

    detected = random.random() < pd

    # Confidence is Pd scaled by the sensor's resolution factor
    confidence = float(max(0.0, min(1.0, pd * sensor_cfg.resolution_factor)))

    # Bearing from UAV to target (degrees from north, clockwise)
    bearing_deg = _compute_bearing(uav_lat, uav_lon, target_lat, target_lon)

    return DetectionResult(
        detected=detected,
        pd=pd,
        range_m=range_m,
        sensor_type=sensor_type,
        confidence=confidence,
        bearing_deg=bearing_deg,
    )
