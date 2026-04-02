"""
dbscan_clustering.py
====================
Density-based clustering with persistent cluster IDs for AMC-Grid C2.

Implements DBSCAN from scratch (no scikit-learn dependency) to avoid adding
a large dependency for ~30 lines of algorithm.

All data structures are frozen/immutable (tuples, frozen dataclasses).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClusterResult:
    cluster_id: str
    centroid: tuple  # (lat, lon)
    members: tuple  # sorted tuple of target IDs
    threat_level: float


@dataclass(frozen=True)
class ClusterState:
    clusters: tuple  # tuple of ClusterResult
    next_id: int  # next available integer for new cluster IDs


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

_EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2.0 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# DBSCAN (scratch implementation)
# ---------------------------------------------------------------------------

# Safety cap: DBSCAN is O(n²) in neighbors computation; cap inputs to bound
# worst-case runtime. 500 targets covers all realistic simulation scenarios.
MAX_TARGETS = 500


def _neighbors(points: list, idx: int, eps_km: float) -> list:
    """Return indices of all points within eps_km of points[idx]."""
    lat0, lon0 = points[idx]
    return [i for i, (lat, lon) in enumerate(points) if _haversine_km(lat0, lon0, lat, lon) <= eps_km]


def _expand_cluster(
    points: list,
    labels: list,
    idx: int,
    cluster_label: int,
    eps_km: float,
    min_samples: int,
) -> None:
    """Expand cluster from seed point idx (BFS over density-reachable points).

    Intentionally mutates `labels` in-place: this is a private helper called
    only from run_dbscan, which owns the labels list and expects mutation as
    part of the standard DBSCAN algorithm.
    """
    queue = list(_neighbors(points, idx, eps_km))
    labels[idx] = cluster_label

    visited = {idx}
    head = 0
    while head < len(queue):
        neighbor = queue[head]
        head += 1
        if neighbor in visited:
            continue
        visited.add(neighbor)
        labels[neighbor] = cluster_label
        nbrs = _neighbors(points, neighbor, eps_km)
        if len(nbrs) >= min_samples:
            for n in nbrs:
                if n not in visited:
                    queue.append(n)


def run_dbscan(
    targets: list,
    eps_km: float = 2.0,
    min_samples: int = 2,
) -> list:
    """
    Run DBSCAN on a list of target dicts.

    Returns a list of (centroid, member_ids, threat_score) tuples,
    one entry per discovered cluster. Noise points are discarded.

    centroid: (lat, lon) tuple of floats
    member_ids: sorted tuple of target IDs
    threat_score: mean fused_confidence of cluster members
    """
    # Cap inputs to bound O(n²) runtime.
    targets = targets[:MAX_TARGETS]

    detected = [t for t in targets if t.get("state", "UNDETECTED") != "UNDETECTED"]
    if not detected:
        return []

    # Extract lat/lon, skipping any malformed target dicts.
    valid_detected = []
    valid_points = []
    for t in detected:
        try:
            lat = float(t["lat"])
            lon = float(t["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        valid_detected.append(t)
        valid_points.append((lat, lon))

    detected = valid_detected
    if not detected:
        return []

    points = valid_points
    n = len(points)
    labels = [-1] * n  # -1 = unvisited/noise
    cluster_label = 0

    for i in range(n):
        if labels[i] != -1:
            continue
        nbrs = _neighbors(points, i, eps_km)
        if len(nbrs) < min_samples:
            labels[i] = 0  # noise marker (0 = noise in our scheme)
            continue
        cluster_label += 1
        _expand_cluster(points, labels, i, cluster_label, eps_km, min_samples)

    # Build result list from labeled clusters
    results = []
    for label in range(1, cluster_label + 1):
        members = [detected[i] for i, lbl in enumerate(labels) if lbl == label]
        if not members:
            continue
        lat_c = sum(t["lat"] for t in members) / len(members)
        lon_c = sum(t["lon"] for t in members) / len(members)
        centroid = (float(lat_c), float(lon_c))
        member_ids = tuple(sorted(t["id"] for t in members))
        threat_score = sum(t.get("fused_confidence", 0.0) for t in members) / len(members)
        results.append((centroid, member_ids, threat_score))

    return results


# ---------------------------------------------------------------------------
# Persistent ID matching
# ---------------------------------------------------------------------------


def match_clusters(
    prev_clusters: tuple,
    new_clusters: list,
    max_match_km: float = 5.0,
) -> tuple:
    """
    Match new clusters to previous clusters by nearest centroid.

    Assigns the previous cluster's ID if the centroid is within max_match_km,
    otherwise assigns a new ID from the running counter.

    Returns: (matched_results: list[ClusterResult], next_id: int)

    Complexity: O(N²) in the number of clusters — acceptable because cluster
    counts are bounded by MAX_TARGETS (≤500) and are typically very small
    (< 20 clusters) in practice.
    """
    # Determine next_id as max existing numeric id + 1 (or 0)
    used_ids = set()
    for c in prev_clusters:
        try:
            num = int(c.cluster_id.replace("CLU-", ""))
            used_ids.add(num)
        except (ValueError, AttributeError):
            pass
    next_id = max(used_ids) + 1 if used_ids else 0

    matched: list = []
    available_prev = list(prev_clusters)  # track which prev clusters are still free

    for centroid, member_ids, threat_score in new_clusters:
        lat_new, lon_new = centroid
        best_prev = None
        best_dist = float("inf")

        for prev in available_prev:
            lat_p, lon_p = prev.centroid
            dist = _haversine_km(lat_new, lon_new, lat_p, lon_p)
            if dist < best_dist:
                best_dist = dist
                best_prev = prev

        if best_prev is not None and best_dist <= max_match_km:
            cluster_id = best_prev.cluster_id
            available_prev.remove(best_prev)
            # Ensure next_id stays beyond all assigned ids
            try:
                num = int(cluster_id.replace("CLU-", ""))
                if num >= next_id:
                    next_id = num + 1
            except (ValueError, AttributeError):
                pass
        else:
            cluster_id = f"CLU-{next_id}"
            next_id += 1

        matched.append(
            ClusterResult(
                cluster_id=cluster_id,
                centroid=(float(centroid[0]), float(centroid[1])),
                members=tuple(sorted(member_ids)),
                threat_level=float(threat_score),
            )
        )

    return matched, next_id


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def update_clustering(
    prev_state: Optional[ClusterState],
    targets: list,
    eps_km: float = 2.0,
) -> ClusterState:
    """
    Full pipeline: run DBSCAN then assign/preserve persistent cluster IDs.

    Returns a new frozen ClusterState.
    """
    raw_clusters = run_dbscan(targets, eps_km=eps_km)

    prev_clusters = prev_state.clusters if prev_state is not None else ()
    matched, next_id = match_clusters(prev_clusters, raw_clusters)

    return ClusterState(
        clusters=tuple(matched),
        next_id=next_id,
    )
