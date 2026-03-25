"""
corridor_detection.py
=====================
Douglas-Peucker path simplification + directional consistency for movement
corridor detection. Pure functions, no mutation, math stdlib only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KM_PER_DEG = 111.0  # approx km per degree lat/lon


# ---------------------------------------------------------------------------
# Frozen dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Corridor:
    corridor_id: str
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    waypoints: Tuple[Tuple[float, float], ...]
    target_ids: Tuple[str, ...]
    heading_deg: float
    speed_avg: float  # km/h
    time_start: Optional[float]
    time_end: Optional[float]
    confidence: float  # 0.0 – 1.0


# ---------------------------------------------------------------------------
# Douglas-Peucker path simplification
# ---------------------------------------------------------------------------


def _perp_distance(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float],
) -> float:
    """Perpendicular distance from point to the line defined by line_start→line_end."""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end

    dx = x2 - x1
    dy = y2 - y1
    denom = math.hypot(dx, dy)
    if denom == 0.0:
        return math.hypot(x0 - x1, y0 - y1)

    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / denom


def douglas_peucker(
    points: List[Tuple[float, float]],
    epsilon: float,
) -> List[Tuple[float, float]]:
    """
    Ramer-Douglas-Peucker path simplification.

    Returns a reduced list of points where no removed point was further than
    epsilon from the simplified line.  Endpoints are always preserved.
    """
    if len(points) <= 2:
        return list(points)

    # Find the point with maximum perpendicular distance from start→end
    max_dist = 0.0
    max_idx = 0
    start = points[0]
    end = points[-1]

    for i in range(1, len(points) - 1):
        dist = _perp_distance(points[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = douglas_peucker(points[: max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        # Merge — left ends at max_idx, right starts at max_idx; drop duplicate
        return left[:-1] + right

    return [start, end]


# ---------------------------------------------------------------------------
# Heading consistency
# ---------------------------------------------------------------------------


def _heading_deg(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Bearing in degrees [0, 360) from p1 to p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    return angle


def _angular_diff(a: float, b: float) -> float:
    """Smallest angular difference between two bearings in [0, 180]."""
    diff = abs(a - b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff


def compute_heading_consistency(points: List[Tuple[float, float]]) -> float:
    """
    Measure how consistently a path moves in a single direction.

    Returns a value in [0.0, 1.0]:
      1.0 = perfectly straight / constant direction
      0.0 = completely random headings or no movement
    """
    if len(points) < 2:
        return 0.0

    headings = [
        _heading_deg(points[i], points[i + 1])
        for i in range(len(points) - 1)
        if math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]) > 0.0
    ]

    if not headings:
        return 0.0

    if len(headings) == 1:
        return 1.0

    # Compute mean heading using circular mean
    sin_sum = sum(math.sin(math.radians(h)) for h in headings)
    cos_sum = sum(math.cos(math.radians(h)) for h in headings)
    mean_h = math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0

    # Mean absolute angular deviation
    mean_dev = sum(_angular_diff(h, mean_h) for h in headings) / len(headings)

    # Normalise: 0 dev → 1.0, 90 dev → 0.0
    consistency = max(0.0, 1.0 - mean_dev / 90.0)
    return consistency


# ---------------------------------------------------------------------------
# Speed calculation
# ---------------------------------------------------------------------------


def _compute_speed_kmh(
    points: List[Tuple[float, float]],
    timestamps: List[float],
) -> float:
    """
    Average speed in km/h over a path given timestamps in seconds.
    Returns 0.0 if time span is zero or fewer than 2 points.
    """
    if len(points) < 2 or len(timestamps) < 2:
        return 0.0

    total_dist_km = 0.0
    for i in range(1, len(points)):
        dx = (points[i][0] - points[i - 1][0]) * _KM_PER_DEG
        dy = (points[i][1] - points[i - 1][1]) * _KM_PER_DEG
        total_dist_km += math.hypot(dx, dy)

    elapsed_s = timestamps[-1] - timestamps[0]
    if elapsed_s <= 0.0:
        return 0.0

    return total_dist_km / (elapsed_s / 3600.0)


# ---------------------------------------------------------------------------
# detect_corridors
# ---------------------------------------------------------------------------


def detect_corridors(
    target_histories: Dict[str, List[dict]],
    min_points: int = 5,
    epsilon_km: float = 0.5,
    min_consistency: float = 0.6,
) -> List[Corridor]:
    """
    Detect movement corridors from per-target position histories.

    For each target with sufficient history:
      1. Extract (lon, lat) points and timestamps.
      2. Apply Douglas-Peucker simplification (epsilon in degrees).
      3. Compute directional consistency on simplified path.
      4. Emit a Corridor if consistency >= min_consistency.

    Args:
        target_histories: Mapping of target_id → list of dicts with
                          'lon'/'lat' (or 'x'/'y') and optional 'timestamp'.
        min_points:       Minimum raw history entries required.
        epsilon_km:       Douglas-Peucker tolerance in km (converted to degrees).
        min_consistency:  Minimum heading consistency to qualify as corridor.

    Returns:
        List of frozen Corridor objects.
    """
    epsilon_deg = epsilon_km / _KM_PER_DEG
    corridors: List[Corridor] = []

    for target_id, history in target_histories.items():
        if len(history) < min_points:
            continue

        points = _extract_points(history)
        timestamps = _extract_timestamps(history)

        simplified = douglas_peucker(points, epsilon_deg)
        if len(simplified) < 2:
            continue

        consistency = compute_heading_consistency(simplified)
        if consistency < min_consistency:
            continue

        start_pt = simplified[0]
        end_pt = simplified[-1]
        heading = _heading_deg(start_pt, end_pt)

        t_start = timestamps[0] if timestamps else None
        t_end = timestamps[-1] if timestamps else None

        speed = _compute_speed_kmh(simplified, timestamps) if timestamps else 0.0

        corridor_id = f"COR-{target_id}"

        corridors.append(
            Corridor(
                corridor_id=corridor_id,
                start_point=start_pt,
                end_point=end_pt,
                waypoints=tuple(simplified),
                target_ids=(target_id,),
                heading_deg=heading,
                speed_avg=speed,
                time_start=t_start,
                time_end=t_end,
                confidence=consistency,
            )
        )

    return corridors


# ---------------------------------------------------------------------------
# attribute_corridor
# ---------------------------------------------------------------------------


def attribute_corridor(
    corridor: Corridor,
    all_targets: Dict[str, dict],
) -> Corridor:
    """
    Return a new Corridor with target_ids filtered to those present in all_targets.

    Immutable — returns a new frozen Corridor rather than mutating the input.
    """
    valid_ids = tuple(tid for tid in corridor.target_ids if tid in all_targets)
    return Corridor(
        corridor_id=corridor.corridor_id,
        start_point=corridor.start_point,
        end_point=corridor.end_point,
        waypoints=corridor.waypoints,
        target_ids=valid_ids,
        heading_deg=corridor.heading_deg,
        speed_avg=corridor.speed_avg,
        time_start=corridor.time_start,
        time_end=corridor.time_end,
        confidence=corridor.confidence,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_points(history: List[dict]) -> List[Tuple[float, float]]:
    pts = []
    for entry in history:
        lon = entry.get("lon", entry.get("x", 0.0))
        lat = entry.get("lat", entry.get("y", 0.0))
        pts.append((float(lon), float(lat)))
    return pts


def _extract_timestamps(history: List[dict]) -> List[float]:
    ts = [entry.get("timestamp") for entry in history]
    if all(t is not None for t in ts):
        return [float(t) for t in ts]  # type: ignore[arg-type]
    return []
