"""
jammer_model.py
===============
Electronic Warfare jamming model for the AMC-Grid C2 system.

Implements spatial jammer effect radius and frequency-specific attenuation.
Enemy JAMMING UAVs degrade sensor confidence within their effect radius.

All public types are immutable frozen dataclasses. Pure functions only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# ---------------------------------------------------------------------------
# Frequency-specific attenuation per sensor type
# EO/IR = optical → not affected by RF jamming (0.0)
# SAR   = microwave radar → partially affected
# SIGINT = RF listener → heavily affected
# ---------------------------------------------------------------------------

FREQUENCY_ATTENUATION: dict[str, float] = {
    "EO_IR": 0.0,  # optical — immune to RF jamming
    "SAR": 0.4,  # microwave — moderate RF attenuation
    "SIGINT": 0.85,  # RF listener — heavily degraded
}

_DEG_TO_M = 111_320.0


# ---------------------------------------------------------------------------
# Immutable types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JammerState:
    jammer_id: int
    lat: float
    lon: float
    radius_m: float
    power: float  # 0-1 normalized jamming power


@dataclass(frozen=True)
class JammerEffect:
    attenuation_factor: float  # 0-1; 1.0 = no degradation, 0.0 = fully jammed
    contributing_jammer_ids: tuple


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mid_lat_rad = math.radians((lat1 + lat2) / 2.0)
    dy = (lat2 - lat1) * _DEG_TO_M
    dx = (lon2 - lon1) * _DEG_TO_M * math.cos(mid_lat_rad)
    return math.hypot(dy, dx)


# ---------------------------------------------------------------------------
# Core attenuation functions
# ---------------------------------------------------------------------------


def compute_jammer_attenuation(
    jammers: Sequence[JammerState],
    sensor_type: str,
) -> float:
    """Return combined attenuation factor for the given sensor type.

    With no active jammers (or zero-power jammers), returns 1.0 (no degradation).
    This function is position-agnostic; callers pass only in-range jammers.

    Attenuation factors from multiple jammers combine as:
        combined = product(1 - power_i * freq_att) for each jammer
    """
    freq_att = FREQUENCY_ATTENUATION.get(sensor_type, 0.0)
    if freq_att == 0.0:
        return 1.0

    complement = 1.0
    for jammer in jammers:
        complement *= 1.0 - jammer.power * freq_att

    return float(max(0.0, min(1.0, complement)))


def compute_jammer_pd_factor(
    target_lat: float,
    target_lon: float,
    jammers: Sequence[JammerState],
    sensor_type: str,
) -> float:
    """Return the Pd multiplier (0-1) from all jammers affecting target position.

    Only jammers whose radius_m encompasses the target contribute.
    Returns 1.0 when no jammers are in range or sensor is immune.
    """
    freq_att = FREQUENCY_ATTENUATION.get(sensor_type, 0.0)
    if freq_att == 0.0:
        return 1.0

    in_range = [j for j in jammers if _distance_m(j.lat, j.lon, target_lat, target_lon) <= j.radius_m]
    if not in_range:
        return 1.0

    return compute_jammer_attenuation(in_range, sensor_type)


# ---------------------------------------------------------------------------
# JammerModel — convenience wrapper
# ---------------------------------------------------------------------------


class JammerModel:
    """Stateless model for computing jammer effects on sensor detections."""

    def compute_pd_factor(
        self,
        target_lat: float,
        target_lon: float,
        jammers: Sequence[JammerState],
        sensor_type: str,
    ) -> float:
        """Return Pd multiplier at target_lat/lon given list of active jammers."""
        return compute_jammer_pd_factor(target_lat, target_lon, jammers, sensor_type)

    def get_effect(
        self,
        target_lat: float,
        target_lon: float,
        jammers: Sequence[JammerState],
        sensor_type: str,
    ) -> JammerEffect:
        """Return a JammerEffect dataclass for the target position."""
        freq_att = FREQUENCY_ATTENUATION.get(sensor_type, 0.0)
        if freq_att == 0.0:
            return JammerEffect(attenuation_factor=1.0, contributing_jammer_ids=())

        in_range = [j for j in jammers if _distance_m(j.lat, j.lon, target_lat, target_lon) <= j.radius_m]
        factor = compute_jammer_attenuation(in_range, sensor_type)
        ids = tuple(j.jammer_id for j in in_range)
        return JammerEffect(attenuation_factor=factor, contributing_jammer_ids=ids)
