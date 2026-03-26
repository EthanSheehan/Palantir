"""
sensor_weighting.py
===================
Per-sensor fitness functions for dynamic sensor weighting in Palantir C2.

Computes fitness multipliers per sensor type based on environment (weather,
time of day, target type). Used by the fusion pipeline to up/down-weight
sensor contributions each tick rather than treating all sensors equally.

All types are immutable frozen dataclasses. No state, no side effects.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from typing import List

from sensor_fusion import SensorContribution

# ---------------------------------------------------------------------------
# Target sets — which targets each sensor is optimised to track
# ---------------------------------------------------------------------------

# Emitting targets (SIGINT is best) — active electronic emitters only
_EMITTING_TARGETS = frozenset({"C2_NODE", "RADAR"})

# Large RCS metal targets (SAR resolves well)
_LARGE_RCS_TARGETS = frozenset({"SAM", "TEL", "TRUCK", "CP", "RADAR", "C2_NODE", "LOGISTICS", "APC", "ARTILLERY"})

# Small / low-profile targets (SAR degrades)
_SMALL_RCS_TARGETS = frozenset({"MANPADS", "ENEMY_UAV"})


# ---------------------------------------------------------------------------
# SensorFitness — immutable result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensorFitness:
    sensor_type: str
    weather_weight: float  # [0, 1] — 1 = ideal conditions, 0 = fully degraded
    time_weight: float  # [0, 1] — 1 = ideal time of day
    target_weight: float  # [0, 1] — 1 = best match for target type
    combined_weight: float  # [0, 1] — geometric mean of the three weights


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _eo_ir_weather_weight(weather: dict) -> float:
    """EO/IR degrades strongly in rain/fog/storm."""
    intensity = float(weather.get("intensity", 0.0))
    if not math.isfinite(intensity):
        intensity = 0.0
    intensity = max(0.0, min(1.0, intensity))
    state = weather.get("state", "CLEAR")
    base = 1.0 - 0.85 * intensity
    # Extra penalty for storm (heavy rain, cloud)
    if state == "STORM":
        base = base * 0.6
    elif state == "RAIN":
        base = base * 0.8
    return _clamp(base)


def _eo_ir_time_weight(time_of_day: float) -> float:
    """EO degrades at night; IR partially compensates but still lower."""
    # Peak at noon (12.0), minimum at midnight (0/24)
    # Uses a cosine curve: 1.0 at 12h, ~0.35 at 0h/24h
    hours_from_noon = abs(time_of_day - 12.0)
    if hours_from_noon > 12.0:
        hours_from_noon = 24.0 - hours_from_noon
    # cos(0)=1, cos(π)=-1 — map 0..12h to cos(0..π)
    weight = 0.5 + 0.5 * math.cos(math.pi * hours_from_noon / 12.0)
    # IR extends low-light capability — floor at 0.35
    return _clamp(0.35 + weight * 0.65)


def _eo_ir_target_weight(target_type: str) -> float:
    """EO/IR is good for visual targets; worse for camouflaged/small."""
    if target_type in _SMALL_RCS_TARGETS:
        return 0.55
    return 0.85


def _sar_weather_weight(weather: dict) -> float:
    """SAR is largely weather-immune — minimal degradation."""
    intensity = float(weather.get("intensity", 0.0))
    if not math.isfinite(intensity):
        intensity = 0.0
    intensity = max(0.0, min(1.0, intensity))
    # SAR degrades only slightly — max 15% penalty in full storm
    return _clamp(1.0 - 0.15 * intensity)


def _sar_time_weight(_time_of_day: float) -> float:
    """SAR is time-of-day neutral — active radar."""
    return 0.9


def _sar_target_weight(target_type: str) -> float:
    """SAR resolves metal/large targets well; small targets degrade."""
    if target_type in _SMALL_RCS_TARGETS:
        return 0.45
    if target_type in _LARGE_RCS_TARGETS:
        return 0.85
    return 0.7


def _sigint_weather_weight(_weather: dict) -> float:
    """SIGINT is radio-based — unaffected by weather."""
    return 0.95


def _sigint_time_weight(_time_of_day: float) -> float:
    """SIGINT is time-of-day neutral."""
    return 0.9


def _sigint_target_weight(target_type: str) -> float:
    """SIGINT excels against emitting targets (C2_NODE, RADAR); poor vs silent."""
    if target_type in _EMITTING_TARGETS:
        return 1.0  # strong domain advantage for active emitters
    if target_type in _SMALL_RCS_TARGETS or target_type == "MANPADS":
        return 0.35
    return 0.5


def _combined(w: float, t: float, tgt: float) -> float:
    """Geometric mean of three weights, clamped to [0, 1]."""
    return _clamp((w * t * tgt) ** (1.0 / 3.0))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_sensor_fitness(
    sensor_type: str,
    weather: dict,
    time_of_day: float,
    target_type: str,
) -> SensorFitness:
    """Return a SensorFitness for the given environment and target combination.

    Parameters
    ----------
    sensor_type  : "EO_IR", "SAR", or "SIGINT"
    weather      : dict with keys "state" (str) and "intensity" (float 0-1)
    time_of_day  : hours in [0, 24)
    target_type  : key from RCS_TABLE (e.g. "SAM", "TRUCK", "C2_NODE")

    Returns
    -------
    SensorFitness — frozen dataclass with per-axis weights and combined weight.
    """
    if not math.isfinite(time_of_day) or not (0.0 <= time_of_day < 24.0):
        raise ValueError(f"time_of_day must be in [0, 24); got {time_of_day!r}")

    if sensor_type == "EO_IR":
        w = _eo_ir_weather_weight(weather)
        t = _eo_ir_time_weight(time_of_day)
        tgt = _eo_ir_target_weight(target_type)
    elif sensor_type == "SAR":
        w = _sar_weather_weight(weather)
        t = _sar_time_weight(time_of_day)
        tgt = _sar_target_weight(target_type)
    elif sensor_type == "SIGINT":
        w = _sigint_weather_weight(weather)
        t = _sigint_time_weight(time_of_day)
        tgt = _sigint_target_weight(target_type)
    else:
        # Unknown sensor — neutral weights
        logging.warning("Unknown sensor type %r — using neutral fitness 0.5", sensor_type)
        w = t = tgt = 0.5

    return SensorFitness(
        sensor_type=sensor_type,
        weather_weight=_clamp(w),
        time_weight=_clamp(t),
        target_weight=_clamp(tgt),
        combined_weight=_combined(w, t, tgt),
    )


def weight_fusion_contributions(
    contributions: List[SensorContribution],
    weather: dict,
    time_of_day: float = 12.0,
    target_type: str = "TRUCK",
) -> List[SensorContribution]:
    """Return a new list of SensorContributions with confidence adjusted by fitness.

    The original contributions are not mutated. Each returned SensorContribution
    is a new frozen instance with confidence scaled by the sensor's combined_weight.

    Parameters
    ----------
    contributions : Existing sensor contributions (immutable).
    weather       : Current weather dict with "state" and "intensity".
    time_of_day   : Hour of day in [0, 24) — default noon.
    target_type   : Target type string for sensor fitness lookup — default "TRUCK".

    Returns
    -------
    List of new SensorContribution instances with updated confidence values.
    """
    if not contributions:
        return []

    result = []
    for c in contributions:
        fitness = compute_sensor_fitness(c.sensor_type, weather, time_of_day, target_type)
        adjusted = _clamp(c.confidence * fitness.combined_weight)
        result.append(replace(c, confidence=adjusted))
    return result


def recommend_sensor_type(
    weather: dict,
    target_type: str,
    time_of_day: float = 12.0,
) -> str:
    """Return the sensor type most fit for the given conditions and target.

    Evaluates EO_IR, SAR, SIGINT and returns the one with the highest
    combined_weight.

    Parameters
    ----------
    weather     : dict with "state" and "intensity".
    target_type : Target type string.
    time_of_day : Hour in [0, 24) — default noon.

    Returns
    -------
    Sensor type string: "EO_IR", "SAR", or "SIGINT".
    """
    candidates = ("EO_IR", "SAR", "SIGINT")
    best = max(
        candidates,
        key=lambda s: compute_sensor_fitness(s, weather, time_of_day, target_type).combined_weight,
    )
    return best
