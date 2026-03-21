"""
geo_utils.py — Pure-Python geospatial helpers for the Battlespace Management Agent.

Provides SAM-ring containment checks and safe-waypoint filtering without
heavy geospatial dependencies.
"""

import math
from typing import List

from schemas.ontology import Coordinate, ThreatRing, Waypoint

# Earth mean radius in kilometres (WGS-84 approximation)
_EARTH_RADIUS_KM = 6_371.0


def haversine_distance(a: Coordinate, b: Coordinate) -> float:
    """
    Calculate the great-circle distance between two coordinates using
    the Haversine formula.

    Args:
        a: First coordinate (lat/lon in decimal degrees).
        b: Second coordinate (lat/lon in decimal degrees).

    Returns:
        Distance in kilometres.
    """
    lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def is_inside_threat_ring(point: Coordinate, threat: ThreatRing) -> bool:
    """
    Determine whether a point falls inside a threat ring's engagement envelope.

    Args:
        point:  The coordinate to test.
        threat: The threat ring to check against.

    Returns:
        True if *point* is within the threat's range_km of its center.
    """
    return haversine_distance(point, threat.center) <= threat.range_km


def filter_safe_waypoints(
    waypoints: List[Waypoint],
    threat_rings: List[ThreatRing],
) -> List[Waypoint]:
    """
    Remove waypoints that penetrate any active threat ring and mark
    surviving ones as safe.

    Args:
        waypoints:    Candidate waypoints for a mission path.
        threat_rings: Currently known threat envelopes.

    Returns:
        A new list containing only waypoints outside all threat rings,
        each with ``is_safe`` set to True.
    """
    safe: List[Waypoint] = []
    for wp in waypoints:
        dominated = any(is_inside_threat_ring(wp.position, tr) for tr in threat_rings)
        if not dominated:
            safe.append(wp.model_copy(update={"is_safe": True}))
    return safe
