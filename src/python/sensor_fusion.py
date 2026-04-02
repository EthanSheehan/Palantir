"""
sensor_fusion.py
================
Pure-function multi-sensor fusion module for AMC-Grid C2.

Implements complementary fusion across sensor types (1 - product(1-ci))
with max-within-type deduplication. No state, no side effects.

Also provides KalmanTracker for UKF per-target track state with position,
covariance, temporal decay, and cross-sensor disagreement detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
from filterpy.kalman import MerweScaledSigmaPoints, UnscentedKalmanFilter

_STALE_THRESHOLD_S = 30.0
_STALE_DECAY_FACTOR = 0.5
_DISAGREEMENT_THRESHOLD_M = 500.0
_DEG_TO_M = 111_320.0


@dataclass(frozen=True)
class SensorContribution:
    uav_id: int
    sensor_type: str
    confidence: float
    range_m: float
    bearing_deg: float
    timestamp: float
    lat: Optional[float] = None
    lon: Optional[float] = None


@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float
    sensor_count: int
    sensor_types: tuple
    contributing_uav_ids: tuple
    contributions: tuple
    position_estimate: Optional[tuple] = None
    position_covariance: Optional[tuple] = None
    disagreement: bool = False


@dataclass(frozen=True)
class KalmanTrackState:
    target_id: int
    position_estimate: tuple
    position_covariance: tuple
    velocity_estimate: tuple
    last_update_time: float


def _position_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mid_lat_rad = math.radians((lat1 + lat2) / 2.0)
    dy = (lat2 - lat1) * _DEG_TO_M
    dx = (lon2 - lon1) * _DEG_TO_M * math.cos(mid_lat_rad)
    return math.hypot(dy, dx)


def _detect_disagreement(contributions: Sequence[SensorContribution]) -> bool:
    by_type: Dict[str, list] = {}
    for c in contributions:
        if c.lat is not None and c.lon is not None:
            by_type.setdefault(c.sensor_type, []).append(c)

    types_with_pos = list(by_type.keys())
    if len(types_with_pos) < 2:
        return False

    centroids = {}
    for stype, contribs in by_type.items():
        avg_lat = sum(c.lat for c in contribs) / len(contribs)
        avg_lon = sum(c.lon for c in contribs) / len(contribs)
        centroids[stype] = (avg_lat, avg_lon)

    for i, t1 in enumerate(types_with_pos):
        for t2 in types_with_pos[i + 1 :]:
            dist = _position_distance_m(
                centroids[t1][0],
                centroids[t1][1],
                centroids[t2][0],
                centroids[t2][1],
            )
            if dist > _DISAGREEMENT_THRESHOLD_M:
                return True
    return False


def fuse_detections(
    contributions: Sequence[SensorContribution],
    current_time: Optional[float] = None,
) -> FusedDetection:
    if not contributions:
        return FusedDetection(
            fused_confidence=0.0,
            sensor_count=0,
            sensor_types=(),
            contributing_uav_ids=(),
            contributions=(),
        )

    effective_contributions = []
    for c in contributions:
        conf = c.confidence
        if current_time is not None and (current_time - c.timestamp) > _STALE_THRESHOLD_S:
            conf = conf * _STALE_DECAY_FACTOR
        effective_contributions.append((c, conf))

    per_type: dict = {}
    for c, conf in effective_contributions:
        if c.sensor_type not in per_type or conf > per_type[c.sensor_type]:
            per_type[c.sensor_type] = conf

    complement = 1.0
    for ci in per_type.values():
        complement *= 1.0 - ci
    fused = max(0.0, min(1.0, 1.0 - complement))

    sensor_types = tuple(sorted(per_type.keys()))
    contributing_uav_ids = tuple(sorted({c.uav_id for c in contributions}))
    disagreement = _detect_disagreement(contributions)

    return FusedDetection(
        fused_confidence=fused,
        sensor_count=len(contributions),
        sensor_types=sensor_types,
        contributing_uav_ids=contributing_uav_ids,
        contributions=tuple(contributions),
        disagreement=disagreement,
    )


def _fx(x: np.ndarray, dt: float) -> np.ndarray:
    """State transition: constant velocity model. x = [lat, lon, vlat, vlon]"""
    return np.array(
        [
            x[0] + x[2] * dt,
            x[1] + x[3] * dt,
            x[2],
            x[3],
        ]
    )


def _hx(x: np.ndarray) -> np.ndarray:
    """Measurement function: observe position only."""
    return np.array([x[0], x[1]])


class KalmanTracker:
    def __init__(self) -> None:
        self._filters: Dict[int, UnscentedKalmanFilter] = {}
        self._last_times: Dict[int, float] = {}

    def _create_filter(self, lat: float, lon: float, timestamp: float) -> UnscentedKalmanFilter:
        points = MerweScaledSigmaPoints(n=4, alpha=0.1, beta=2.0, kappa=0.0)
        ukf = UnscentedKalmanFilter(dim_x=4, dim_z=2, dt=1.0, fx=_fx, hx=_hx, points=points)
        ukf.x = np.array([lat, lon, 0.0, 0.0])
        ukf.P = np.diag([0.01, 0.01, 0.001, 0.001])
        ukf.R = np.diag([0.005, 0.005])
        ukf.Q = np.diag([1e-5, 1e-5, 1e-4, 1e-4])
        return ukf

    def _extract_state(self, target_id: int, ukf: UnscentedKalmanFilter) -> KalmanTrackState:
        return KalmanTrackState(
            target_id=target_id,
            position_estimate=(float(ukf.x[0]), float(ukf.x[1])),
            position_covariance=(float(ukf.P[0, 0]), float(ukf.P[1, 1])),
            velocity_estimate=(float(ukf.x[2]), float(ukf.x[3])),
            last_update_time=self._last_times[target_id],
        )

    def update(
        self,
        target_id: int,
        measurements: list,
        timestamp: float,
    ) -> Optional[KalmanTrackState]:
        valid = [
            m
            for m in measurements
            if m.lat is not None and m.lon is not None and math.isfinite(m.lat) and math.isfinite(m.lon)
        ]
        if not valid:
            return None

        avg_lat = sum(m.lat for m in valid) / len(valid)
        avg_lon = sum(m.lon for m in valid) / len(valid)

        if target_id not in self._filters:
            self._filters[target_id] = self._create_filter(avg_lat, avg_lon, timestamp)
            self._last_times[target_id] = timestamp
            return self._extract_state(target_id, self._filters[target_id])

        ukf = self._filters[target_id]
        dt = max(0.01, timestamp - self._last_times[target_id])
        ukf.predict(dt=dt)
        ukf.update(np.array([avg_lat, avg_lon]))
        self._last_times[target_id] = timestamp
        return self._extract_state(target_id, ukf)

    def predict(self, target_id: int, dt: float) -> Optional[KalmanTrackState]:
        if target_id not in self._filters:
            return None
        ukf = self._filters[target_id]
        ukf.predict(dt=dt)
        self._last_times[target_id] = self._last_times[target_id] + dt
        return self._extract_state(target_id, ukf)

    def get_track(self, target_id: int) -> Optional[KalmanTrackState]:
        if target_id not in self._filters:
            return None
        return self._extract_state(target_id, self._filters[target_id])

    def remove_track(self, target_id: int) -> None:
        self._filters.pop(target_id, None)
        self._last_times.pop(target_id, None)
