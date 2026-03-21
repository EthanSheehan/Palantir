"""
battlespace_assessment.py
=========================
Pure-function battlespace assessment module for Palantir C2.

Provides threat clustering, coverage gap identification, zone threat scoring,
and movement corridor detection. No state, no side effects.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import KDTree


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLUSTER_RADIUS_DEG = 0.135          # 15km / 111km per degree
MIN_CLUSTER_SIZE = 2
POSITION_HISTORY_MIN = 10           # minimum entries for corridor
CORRIDOR_MIN_MOVEMENT_DEG = 0.005   # min total displacement for a corridor

CLUSTER_AFFINITY: Dict[str, str] = {
    "SAM": "AD_NETWORK",
    "RADAR": "AD_NETWORK",
    "MANPADS": "AD_NETWORK",
    "TEL": "SAM_BATTERY",
    "CP": "CP_COMPLEX",
    "C2_NODE": "CP_COMPLEX",
    "TRUCK": "CONVOY",
    "LOGISTICS": "CONVOY",
    "APC": "CONVOY",
    "ARTILLERY": "CONVOY",
}


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThreatCluster:
    cluster_id: str
    cluster_type: str
    member_target_ids: tuple
    centroid_lon: float
    centroid_lat: float
    threat_score: float
    hull_points: tuple


@dataclass(frozen=True)
class CoverageGap:
    zone_x: int
    zone_y: int
    lon: float
    lat: float


@dataclass(frozen=True)
class MovementCorridor:
    target_id: int
    waypoints: tuple


@dataclass(frozen=True)
class AssessmentResult:
    clusters: tuple
    coverage_gaps: tuple
    zone_threat_scores: dict
    movement_corridors: tuple
    assessed_at: float


# ---------------------------------------------------------------------------
# BattlespaceAssessor
# ---------------------------------------------------------------------------

def _get_xy(t: dict) -> Tuple[float, float]:
    """Extract lon/lat from a target dict, supporting both 'x'/'y' and 'lon'/'lat' keys."""
    return (t.get("x") or t.get("lon", 0.0), t.get("y") or t.get("lat", 0.0))


class BattlespaceAssessor:
    """
    Compute a frozen AssessmentResult from raw sim state dicts.

    All methods are pure — no mutation of inputs or internal state.
    """

    def assess(
        self,
        targets: List[dict],
        uavs: List[dict],
        zones: List[dict],
    ) -> AssessmentResult:
        clusters = self._cluster_targets(targets)
        coverage_gaps = self._identify_coverage_gaps(zones, uavs, targets)
        zone_threat_scores = self._score_zone_threats(zones, targets)
        movement_corridors = self._detect_movement_corridors(targets)

        return AssessmentResult(
            clusters=tuple(clusters),
            coverage_gaps=tuple(coverage_gaps),
            zone_threat_scores=zone_threat_scores,
            movement_corridors=tuple(movement_corridors),
            assessed_at=time.time(),
        )

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def _cluster_targets(self, targets: List[dict]) -> List[ThreatCluster]:
        detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
        if not detected:
            return []

        positions = np.array([list(_get_xy(t)) for t in detected], dtype=float)
        tree = KDTree(positions)
        neighbor_indices = tree.query_ball_point(positions, r=CLUSTER_RADIUS_DEG)

        visited = set()
        clusters: List[ThreatCluster] = []

        for i, anchor in enumerate(detected):
            if anchor["id"] in visited:
                continue

            idxs = neighbor_indices[i]
            neighbors = [detected[j] for j in idxs]

            if len(neighbors) < MIN_CLUSTER_SIZE:
                continue

            member_ids = tuple(sorted(t["id"] for t in neighbors))
            for mid in member_ids:
                visited.add(mid)

            cluster_id = "CLU-" + "-".join(str(mid) for mid in member_ids)

            # Majority vote for cluster type
            type_votes: Dict[str, int] = {}
            for t in neighbors:
                affinity = CLUSTER_AFFINITY.get(t.get("type", ""), "MIXED")
                type_votes[affinity] = type_votes.get(affinity, 0) + 1
            cluster_type = max(type_votes, key=lambda k: type_votes[k]) if type_votes else "MIXED"

            centroid_lon = sum(_get_xy(t)[0] for t in neighbors) / len(neighbors)
            centroid_lat = sum(_get_xy(t)[1] for t in neighbors) / len(neighbors)

            threat_score = sum(t.get("fused_confidence", 0.0) for t in neighbors) / len(neighbors)

            points = [_get_xy(t) for t in neighbors]
            hull_points = _compute_convex_hull(points)

            clusters.append(ThreatCluster(
                cluster_id=cluster_id,
                cluster_type=cluster_type,
                member_target_ids=member_ids,
                centroid_lon=centroid_lon,
                centroid_lat=centroid_lat,
                threat_score=threat_score,
                hull_points=hull_points,
            ))

        return clusters

    # ------------------------------------------------------------------
    # Coverage gaps
    # ------------------------------------------------------------------

    def _identify_coverage_gaps(
        self, zones: List[dict], uavs: List[dict],
        targets: Optional[List[dict]] = None,
    ) -> List[CoverageGap]:
        if not zones:
            return []

        # Build set of zone keys that have detected targets nearby
        zones_with_targets: set = set()
        if targets:
            for target in targets:
                if target.get("state", "UNDETECTED") == "UNDETECTED":
                    continue
                tx, ty = _get_xy(target)
                best_dist = float("inf")
                best_zone = None
                for zone in zones:
                    dist = math.hypot(zone["lon"] - tx, zone["lat"] - ty)
                    if dist < best_dist:
                        best_dist = dist
                        best_zone = (zone["x_idx"], zone["y_idx"])
                if best_zone is not None:
                    zones_with_targets.add(best_zone)

        gaps: List[CoverageGap] = []
        for zone in zones:
            x_idx = zone["x_idx"]
            y_idx = zone["y_idx"]
            if zone.get("uav_count", 0) == 0 and (x_idx, y_idx) in zones_with_targets:
                gaps.append(CoverageGap(
                    zone_x=x_idx,
                    zone_y=y_idx,
                    lon=zone["lon"],
                    lat=zone["lat"],
                ))

        return gaps

    # ------------------------------------------------------------------
    # Zone threat scoring
    # ------------------------------------------------------------------

    def _score_zone_threats(
        self, zones: List[dict], targets: List[dict]
    ) -> Dict[Tuple[int, int], float]:
        if not zones:
            return {}

        detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
        scores: Dict[Tuple[int, int], float] = {}

        for target in detected:
            tx, ty = _get_xy(target)
            best_dist = float("inf")
            best_zone = None
            for zone in zones:
                dist = math.hypot(zone["lon"] - tx, zone["lat"] - ty)
                if dist < best_dist:
                    best_dist = dist
                    best_zone = (zone["x_idx"], zone["y_idx"])

            if best_zone is not None:
                conf = target.get("fused_confidence", 0.0)
                scores[best_zone] = min(1.0, scores.get(best_zone, 0.0) + conf)

        return scores

    # ------------------------------------------------------------------
    # Movement corridors
    # ------------------------------------------------------------------

    def _detect_movement_corridors(self, targets: List[dict]) -> List[MovementCorridor]:
        corridors: List[MovementCorridor] = []

        for target in targets:
            history = target.get("position_history")
            if history is None:
                continue

            history_list = list(history)
            if len(history_list) < POSITION_HISTORY_MIN:
                continue

            # Total displacement: sum of step distances
            total_displacement = 0.0
            for j in range(1, len(history_list)):
                dx = history_list[j][0] - history_list[j - 1][0]
                dy = history_list[j][1] - history_list[j - 1][1]
                total_displacement += math.hypot(dx, dy)

            if total_displacement <= CORRIDOR_MIN_MOVEMENT_DEG:
                continue

            # Sample every 5th entry for waypoints
            waypoints = tuple(history_list[::5])

            corridors.append(MovementCorridor(
                target_id=target["id"],
                waypoints=waypoints,
            ))

        return corridors


# ---------------------------------------------------------------------------
# Convex hull (Jarvis march / gift-wrapping)
# ---------------------------------------------------------------------------

def _compute_convex_hull(
    points: List[Tuple[float, float]]
) -> Tuple[Tuple[float, float], ...]:
    """
    Compute the convex hull of a set of 2D points using Jarvis march.

    Edge cases:
    - 0 points -> empty tuple
    - 1 point  -> single-point tuple
    - 2 points -> two-point tuple (degenerate hull)
    - 3+ points -> true convex hull
    """
    n = len(points)
    if n == 0:
        return ()
    if n == 1:
        return (points[0],)
    if n == 2:
        return (points[0], points[1])

    # Find leftmost point
    start = min(range(n), key=lambda i: (points[i][0], points[i][1]))

    hull = []
    current = start
    while True:
        hull.append(points[current])
        next_idx = (current + 1) % n
        for i in range(n):
            # cross product: if points[i] is more counter-clockwise than next_idx
            ox = points[current][0]
            oy = points[current][1]
            ax = points[next_idx][0]
            ay = points[next_idx][1]
            bx = points[i][0]
            by = points[i][1]
            cross = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
            if cross < 0:
                next_idx = i
        current = next_idx
        if current == start:
            break
        if len(hull) > n:  # Safety guard against infinite loops
            break

    return tuple(hull)
