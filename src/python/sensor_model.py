"""
sensor_model.py
===============
Physics-informed probabilistic sensor model for the Palantir C2 system.

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
from typing import Optional


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
    time_of_day: float = 12.0   # 0-24 h
    cloud_cover: float = 0.0    # 0-1
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
}

_FALLBACK_RCS_M2 = 3.0

SENSOR_CONFIGS: dict[str, SensorConfig] = {
    "EO_IR": SensorConfig(
        max_range_m=50_000.0,       # ~50km effective range (simulation scale)
        reference_rcs_m2=5.0,
        resolution_factor=1.0,
        weather_sensitivity=0.8,
        requires_emitter=False,
    ),
    "SAR": SensorConfig(
        max_range_m=100_000.0,      # ~100km SAR range (simulation scale)
        reference_rcs_m2=5.0,
        resolution_factor=0.7,
        weather_sensitivity=0.2,
        requires_emitter=False,
    ),
    "SIGINT": SensorConfig(
        max_range_m=200_000.0,      # ~200km SIGINT range (simulation scale)
        reference_rcs_m2=1.0,
        resolution_factor=0.3,
        weather_sensitivity=0.0,
        requires_emitter=True,
    ),
}


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
) -> float:
    """Return probability of detection in [0, 1].

    Formula (from spec):
        snr_norm = (1 - (range/max_range)^2)
                   + rcs_gain * 0.3
                   - altitude_penalty          (unused; kept for future)
                   - weather_penalty
        Pd = sigmoid(snr_norm * 10 - 5)

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
    weather_penalty = (
        sensor_cfg.weather_sensitivity
        * (env.cloud_cover + env.precipitation * 0.5)
        * 0.6
    )

    snr_norm = range_term + rcs_gain * 0.3 - weather_penalty
    pd = _sigmoid(snr_norm * 10.0 - 5.0)
    return float(max(0.0, min(1.0, pd)))


# ---------------------------------------------------------------------------
# Top-level detection evaluation
# ---------------------------------------------------------------------------

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
    """
    sensor_cfg = SENSOR_CONFIGS[sensor_type]

    range_m = deg_to_meters(uav_lat, uav_lon, target_lat, target_lon)

    base_rcs = RCS_TABLE.get(target_type, _FALLBACK_RCS_M2)
    effective_rcs = compute_aspect_rcs(base_rcs, aspect_deg)

    pd = compute_pd(
        range_m=range_m,
        rcs_m2=effective_rcs,
        sensor_type=sensor_type,
        sensor_cfg=sensor_cfg,
        env=env,
        emitting=emitting,
    )

    detected = random.random() < pd

    # Confidence is Pd scaled by the sensor's resolution factor
    confidence = float(max(0.0, min(1.0, pd * sensor_cfg.resolution_factor)))

    # Bearing from UAV to target (degrees from north, clockwise)
    dlat = target_lat - uav_lat
    dlon = (target_lon - uav_lon) * math.cos(math.radians((uav_lat + target_lat) / 2.0))
    bearing_rad = math.atan2(dlon, dlat)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

    return DetectionResult(
        detected=detected,
        pd=pd,
        range_m=range_m,
        sensor_type=sensor_type,
        confidence=confidence,
        bearing_deg=bearing_deg,
    )
