"""
sensor_fusion.py
================
Pure-function multi-sensor fusion module for Palantir C2.

Implements complementary fusion across sensor types (1 - product(1-ci))
with max-within-type deduplication. No state, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SensorContribution:
    uav_id: int
    sensor_type: str
    confidence: float
    range_m: float
    bearing_deg: float
    timestamp: float


@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float
    sensor_count: int
    sensor_types: tuple[str, ...]
    contributing_uav_ids: tuple[int, ...]
    contributions: tuple[SensorContribution, ...]


def fuse_detections(contributions: Sequence[SensorContribution]) -> FusedDetection:
    if not contributions:
        return FusedDetection(
            fused_confidence=0.0,
            sensor_count=0,
            sensor_types=(),
            contributing_uav_ids=(),
            contributions=(),
        )

    per_type: dict[str, float] = {}
    for c in contributions:
        if c.sensor_type not in per_type or c.confidence > per_type[c.sensor_type]:
            per_type[c.sensor_type] = c.confidence

    complement = 1.0
    for ci in per_type.values():
        complement *= (1.0 - ci)
    fused = max(0.0, min(1.0, 1.0 - complement))

    sensor_types = tuple(sorted(per_type.keys()))
    contributing_uav_ids = tuple(sorted({c.uav_id for c in contributions}))

    return FusedDetection(
        fused_confidence=fused,
        sensor_count=len(contributions),
        sensor_types=sensor_types,
        contributing_uav_ids=contributing_uav_ids,
        contributions=tuple(contributions),
    )
