"""
vectorized_detection.py
=======================
NumPy-vectorized detection loop for the AMC-Grid C2 simulation engine.

Replaces the O(T * U * S) scalar detection loop with broadcast array operations
yielding 10-50x speedup at large target/UAV counts.

All functions are pure (no side effects, no mutation).
"""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np
from sensor_model import (
    FALLBACK_RCS_M2,
    RCS_TABLE,
    SENSOR_CONFIGS,
    EnvironmentConditions,
    compute_pd,
)

# Detection threshold: only return pairs where Pd >= threshold
_DEFAULT_THRESHOLD = 0.1

# Metres-per-degree constants (equirectangular approximation)
_LAT_M_PER_DEG = 111_320.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def positions_to_array(entities: list[dict[str, Any]]) -> np.ndarray:
    """Extract (lat, lon) positions from a list of entity dicts into Nx2 float64 array.

    Parameters
    ----------
    entities : list of dicts with 'lat' and 'lon' keys.

    Returns
    -------
    np.ndarray of shape (N, 2), dtype float64. Columns: [lat, lon].
    """
    if not entities:
        return np.empty((0, 2), dtype=np.float64)
    return np.array([[e["lat"], e["lon"]] for e in entities], dtype=np.float64)


def pairwise_distances_km(uav_pos: np.ndarray, target_pos: np.ndarray) -> np.ndarray:
    """Compute the MxN pairwise distance matrix in kilometres.

    Uses a flat-earth equirectangular approximation (accurate < 1% within 200 km).

    Parameters
    ----------
    uav_pos    : (M, 2) array of UAV [lat, lon] in decimal degrees.
    target_pos : (N, 2) array of target [lat, lon] in decimal degrees.

    Returns
    -------
    np.ndarray of shape (M, N), dtype float64 — distance in km for each pair.
    """
    uav_lat = uav_pos[:, 0]  # (M,)
    uav_lon = uav_pos[:, 1]  # (M,)
    tgt_lat = target_pos[:, 0]  # (N,)
    tgt_lon = target_pos[:, 1]  # (N,)

    # Broadcast mid-latitude for longitude scaling: (M, N)
    mid_lat_rad = np.radians((uav_lat[:, np.newaxis] + tgt_lat[np.newaxis, :]) / 2.0)
    lon_m_per_deg = _LAT_M_PER_DEG * np.cos(mid_lat_rad)

    # Lat/lon deltas broadcast to (M, N)
    dlat_m = (tgt_lat[np.newaxis, :] - uav_lat[:, np.newaxis]) * _LAT_M_PER_DEG
    dlon_m = (tgt_lon[np.newaxis, :] - uav_lon[:, np.newaxis]) * lon_m_per_deg

    dist_m = np.sqrt(dlat_m**2 + dlon_m**2)
    return dist_m / 1000.0


def vectorized_detection_probability(
    distances: np.ndarray,
    rcs: np.ndarray,
    weather_factor: float,
    sensor_type: str,
) -> np.ndarray:
    """Compute element-wise probability of detection for all UAV-target pairs.

    Mirrors the logic of sensor_model.compute_pd() using array broadcast.

    Parameters
    ----------
    distances     : (M, N) distance matrix in km (from pairwise_distances_km).
    rcs           : (N,) array of target RCS values in m².
    weather_factor: Combined weather degradation factor in [0, 1].
                    Maps to EnvironmentConditions(cloud_cover=weather_factor).
    sensor_type   : Sensor key — 'EO_IR', 'SAR', or 'SIGINT'.

    Returns
    -------
    np.ndarray of shape (M, N), dtype float64 — Pd in [0, 1] for each pair.
    """
    if sensor_type not in SENSOR_CONFIGS:
        raise ValueError(f"Unknown sensor_type {sensor_type!r}. Valid types: {list(SENSOR_CONFIGS)}")
    sensor_cfg = SENSOR_CONFIGS[sensor_type]
    max_range_m = sensor_cfg.max_range_m
    ref_rcs = sensor_cfg.reference_rcs_m2
    weather_sens = sensor_cfg.weather_sensitivity

    # (M, N) distances in metres
    dist_m = distances * 1000.0

    # Normalised range term: 1 at zero, 0 at max_range, negative beyond — (M, N)
    range_term = 1.0 - (dist_m / max_range_m) ** 2

    # RCS gain: log ratio per target — (N,) broadcast to (M, N)
    safe_rcs = np.where(rcs > 0.0, rcs, 1e-6)
    safe_ref = ref_rcs if ref_rcs > 0.0 else 1e-6
    rcs_gain = np.log10(safe_rcs / safe_ref)  # (N,)

    # Weather penalty (scalar) — mirrors sensor_model.compute_pd
    weather_penalty = weather_sens * weather_factor * 0.6

    # SNR normalised — (M, N)
    snr_norm = range_term + rcs_gain[np.newaxis, :] * 0.3 - weather_penalty

    # Stable sigmoid: 1 / (1 + exp(-x)) where x = snr_norm * 10 - 5
    x = snr_norm * 10.0 - 5.0
    pd = 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))

    return np.clip(pd, 0.0, 1.0).astype(np.float64)


def detect_all(
    uavs: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    weather_factor: float = 0.0,
    sensor_type: str = "EO_IR",
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[tuple[str, str, float]]:
    """Return all (uav_id, target_id, pd) pairs where Pd >= threshold.

    Parameters
    ----------
    uavs          : list of dicts with 'id', 'lat', 'lon'.
    targets       : list of dicts with 'id', 'lat', 'lon', 'type'.
    weather_factor: Combined weather degradation in [0, 1].
    sensor_type   : Sensor modality key.
    threshold     : Minimum Pd to include in results (default 0.1).

    Returns
    -------
    list of (uav_id, target_id, pd) tuples — immutable, no mutation of inputs.
    """
    if not uavs or not targets:
        return []

    uav_pos = positions_to_array(uavs)
    tgt_pos = positions_to_array(targets)

    rcs = np.array(
        [RCS_TABLE.get(t.get("type", ""), FALLBACK_RCS_M2) for t in targets],
        dtype=np.float64,
    )

    if not np.all(np.isfinite(uav_pos)):
        raise ValueError("UAV position array contains NaN or inf values")
    if not np.all(np.isfinite(tgt_pos)):
        raise ValueError("Target position array contains NaN or inf values")
    if not np.all(np.isfinite(rcs)):
        raise ValueError("Target RCS array contains NaN or inf values")

    distances = pairwise_distances_km(uav_pos, tgt_pos)  # (M, N)
    pd_matrix = vectorized_detection_probability(distances, rcs, weather_factor, sensor_type)  # (M, N)

    rows, cols = np.where(pd_matrix >= threshold)
    return [(uavs[int(i)]["id"], targets[int(j)]["id"], float(pd_matrix[i, j])) for i, j in zip(rows, cols)]


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def benchmark_scalar_vs_vectorized(n_uavs: int = 100, n_targets: int = 500) -> dict[str, float]:
    """Compare scalar compute_pd vs vectorized at given scale.

    Returns dict with 'scalar_s', 'vectorized_s', 'speedup' keys.
    """

    sensor_type = "EO_IR"
    weather_factor = 0.2
    env = EnvironmentConditions(cloud_cover=weather_factor, precipitation=0.0)
    sensor_cfg = SENSOR_CONFIGS[sensor_type]

    rng = np.random.default_rng(99)
    uav_lats = rng.uniform(44.0, 46.0, n_uavs).tolist()
    uav_lons = rng.uniform(24.0, 26.0, n_uavs).tolist()
    tgt_lats = rng.uniform(44.0, 46.0, n_targets).tolist()
    tgt_lons = rng.uniform(24.0, 26.0, n_targets).tolist()
    rcs_list = rng.uniform(1.0, 20.0, n_targets).tolist()

    # Scalar timing
    t0 = time.perf_counter()
    for i in range(n_uavs):
        for j in range(n_targets):
            lat_m = _LAT_M_PER_DEG
            mid_lat_rad = math.radians((uav_lats[i] + tgt_lats[j]) / 2.0)
            lon_m = _LAT_M_PER_DEG * math.cos(mid_lat_rad)
            dist_m = math.hypot(
                (tgt_lats[j] - uav_lats[i]) * lat_m,
                (tgt_lons[j] - uav_lons[i]) * lon_m,
            )
            compute_pd(
                range_m=dist_m,
                rcs_m2=rcs_list[j],
                sensor_type=sensor_type,
                sensor_cfg=sensor_cfg,
                env=env,
            )
    scalar_s = time.perf_counter() - t0

    # Vectorized timing
    uavs = [{"id": f"u{i}", "lat": uav_lats[i], "lon": uav_lons[i]} for i in range(n_uavs)]
    targets = [{"id": f"t{j}", "lat": tgt_lats[j], "lon": tgt_lons[j], "type": "TRUCK"} for j in range(n_targets)]

    t0 = time.perf_counter()
    uav_pos = positions_to_array(uavs)
    tgt_pos = positions_to_array(targets)
    rcs_arr = np.array(rcs_list, dtype=np.float64)
    distances = pairwise_distances_km(uav_pos, tgt_pos)
    vectorized_detection_probability(distances, rcs_arr, weather_factor, sensor_type)
    vec_s = time.perf_counter() - t0

    speedup = scalar_s / max(vec_s, 1e-9)
    return {"scalar_s": scalar_s, "vectorized_s": vec_s, "speedup": speedup}


if __name__ == "__main__":
    for n in [100, 500, 1000]:
        result = benchmark_scalar_vs_vectorized(n_uavs=10, n_targets=n)
        print(
            f"targets={n:4d}: scalar={result['scalar_s'] * 1000:.1f}ms "
            f"vec={result['vectorized_s'] * 1000:.1f}ms "
            f"speedup={result['speedup']:.1f}x"
        )
