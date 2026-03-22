"""
terrain_model.py
================
Terrain and line-of-sight analysis for the Palantir C2 system.

Provides a geometric terrain model using simplified TerrainFeature obstacles
(hills/mountains defined by center point, radius, and peak elevation). Supports:

  - Line-of-sight checks via ray-marching along the great-circle path
  - Dead-zone computation (grid of blocked positions from an observer)
  - Optional per-theater terrain configuration via YAML

All public types are immutable frozen dataclasses. No mutation anywhere.
Integration with sensor_model: when LOS is blocked, Pd is forced to 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerrainFeature:
    """A simplified terrain obstacle (hill or mountain).

    Modelled as a cone: elevation is peak_elevation_m at the center and
    linearly falls off to 0 at radius_km from the center.
    """

    center_lat: float
    center_lon: float
    radius_km: float
    peak_elevation_m: float


@dataclass(frozen=True)
class TerrainModel:
    """Immutable collection of terrain features for a theater."""

    features: tuple[TerrainFeature, ...]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

_LAT_M_PER_DEG = 111_320.0


def _horiz_dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate horizontal distance in metres (equirectangular)."""
    mid_lat_rad = math.radians((lat1 + lat2) / 2.0)
    lon_m_per_deg = _LAT_M_PER_DEG * math.cos(mid_lat_rad)
    dy = (lat2 - lat1) * _LAT_M_PER_DEG
    dx = (lon2 - lon1) * lon_m_per_deg
    return math.hypot(dy, dx)


def _elevation_at(feature: TerrainFeature, lat: float, lon: float) -> float:
    """Return terrain elevation at (lat, lon) due to this feature (conical)."""
    dist_m = _horiz_dist_m(feature.center_lat, feature.center_lon, lat, lon)
    radius_m = feature.radius_km * 1_000.0
    if dist_m >= radius_m:
        return 0.0
    # Conical profile: full peak at center, zero at edge
    return feature.peak_elevation_m * (1.0 - dist_m / radius_m)


def _max_terrain_elevation(features: tuple[TerrainFeature, ...], lat: float, lon: float) -> float:
    """Return the maximum terrain elevation from all features at (lat, lon)."""
    if not features:
        return 0.0
    return max(_elevation_at(f, lat, lon) for f in features)


# ---------------------------------------------------------------------------
# Line-of-sight
# ---------------------------------------------------------------------------

_RAY_STEPS = 50  # number of samples along the ray


def has_line_of_sight(
    terrain: Optional[TerrainModel],
    observer_lat: float,
    observer_lon: float,
    observer_alt_m: float,
    target_lat: float,
    target_lon: float,
    target_alt_m: float,
) -> bool:
    """Return True if there is unobstructed line-of-sight between observer and target.

    Uses ray-marching: samples _RAY_STEPS points along the straight line between
    observer and target, checking whether terrain elevation at each sample
    exceeds the interpolated altitude of the ray at that point.

    Parameters
    ----------
    terrain          : TerrainModel (or None for flat/no terrain → always True)
    observer_lat/lon : Observer position in decimal degrees
    observer_alt_m   : Observer altitude above sea level in metres
    target_lat/lon   : Target position in decimal degrees
    target_alt_m     : Target altitude above sea level in metres
    """
    if terrain is None or not terrain.features:
        return True

    # Sample points along the ray (excluding endpoints — they're in the air)
    for i in range(1, _RAY_STEPS):
        t = i / _RAY_STEPS
        sample_lat = observer_lat + t * (target_lat - observer_lat)
        sample_lon = observer_lon + t * (target_lon - observer_lon)
        ray_alt = observer_alt_m + t * (target_alt_m - observer_alt_m)

        terrain_elev = _max_terrain_elevation(terrain.features, sample_lat, sample_lon)
        if terrain_elev > ray_alt:
            return False

    return True


# ---------------------------------------------------------------------------
# Dead zone computation
# ---------------------------------------------------------------------------


def compute_dead_zones(
    terrain: TerrainModel,
    observer_lat: float,
    observer_lon: float,
    observer_alt_m: float,
    grid_resolution: float = 0.5,
) -> list[tuple[float, float]]:
    """Return a list of (lat, lon) grid points not visible from the observer.

    Sweeps a grid covering the bounding box of all terrain features plus a
    small margin and tests LOS from the observer to each grid point at ground
    level (alt_m = 0).

    Parameters
    ----------
    terrain          : TerrainModel with terrain features
    observer_lat/lon : Observer position in decimal degrees
    observer_alt_m   : Observer altitude in metres
    grid_resolution  : Grid step size in decimal degrees (default 0.5°)

    Returns
    -------
    List of (lat, lon) tuples where LOS is blocked.
    """
    if not terrain.features:
        return []

    # Build bounding box from all features
    min_lat = min(f.center_lat - f.radius_km / 111.32 for f in terrain.features)
    max_lat = max(f.center_lat + f.radius_km / 111.32 for f in terrain.features)
    min_lon = min(f.center_lon - f.radius_km / 111.32 for f in terrain.features)
    max_lon = max(f.center_lon + f.radius_km / 111.32 for f in terrain.features)

    # Small margin
    margin = grid_resolution
    min_lat -= margin
    max_lat += margin
    min_lon -= margin
    max_lon += margin

    blocked: list[tuple[float, float]] = []

    lat = min_lat
    while lat <= max_lat + 1e-9:
        lon = min_lon
        while lon <= max_lon + 1e-9:
            if not has_line_of_sight(
                terrain,
                observer_lat,
                observer_lon,
                observer_alt_m,
                lat,
                lon,
                0.0,
            ):
                blocked.append((lat, lon))
            lon += grid_resolution
        lat += grid_resolution

    return blocked


# ---------------------------------------------------------------------------
# Theater YAML loader
# ---------------------------------------------------------------------------


def load_terrain_from_config(config: dict) -> TerrainModel:
    """Build a TerrainModel from a theater YAML config dict.

    Expects an optional top-level ``terrain_features`` list. Each entry must
    have: center_lat, center_lon, radius_km, peak_elevation_m.

    If the key is absent or empty, returns an empty TerrainModel (backwards
    compatible — all existing theaters without terrain data work as before).
    """
    raw_features = config.get("terrain_features", [])
    features = tuple(
        TerrainFeature(
            center_lat=float(f["center_lat"]),
            center_lon=float(f["center_lon"]),
            radius_km=float(f["radius_km"]),
            peak_elevation_m=float(f["peak_elevation_m"]),
        )
        for f in raw_features
    )
    return TerrainModel(features=features)
