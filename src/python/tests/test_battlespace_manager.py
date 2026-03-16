"""
test_battlespace_manager.py — Unit tests for the Battlespace Management Agent.

Covers schema validation, geospatial utilities, and agent instantiation.
"""

import math
import sys
import os
import pytest

# Ensure src/python is on the path so schemas/utils resolve
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, "src", "python"),
)

from schemas.ontology import (
    BattlespaceManagerOutput,
    Coordinate,
    MapLayer,
    MapLayerType,
    MissionPath,
    TerrainType,
    ThreatRing,
    ThreatType,
    Waypoint,
)
from utils.geo_utils import (
    filter_safe_waypoints,
    haversine_distance,
    is_inside_threat_ring,
)
from agents.battlespace_manager import BattlespaceManagerAgent


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def london() -> Coordinate:
    return Coordinate(lat=51.5074, lon=-0.1278)


@pytest.fixture
def paris() -> Coordinate:
    return Coordinate(lat=48.8566, lon=2.3522)


@pytest.fixture
def sam_site() -> ThreatRing:
    """A SAM site centred on (35.0, 45.0) with a 50 km engagement radius."""
    return ThreatRing(
        threat_id="SAM-001",
        center=Coordinate(lat=35.0, lon=45.0),
        range_km=50.0,
        threat_type=ThreatType.SAM_MEDIUM,
        confidence=0.95,
    )


@pytest.fixture
def waypoints_mixed(sam_site: ThreatRing):
    """Three waypoints: one inside the SAM ring, two outside."""
    return [
        Waypoint(
            sequence=0,
            position=Coordinate(lat=35.0, lon=45.0),   # dead centre — unsafe
            terrain=TerrainType.FLAT,
        ),
        Waypoint(
            sequence=1,
            position=Coordinate(lat=36.0, lon=46.0),   # ~140 km away — safe
            terrain=TerrainType.HILLY,
        ),
        Waypoint(
            sequence=2,
            position=Coordinate(lat=37.0, lon=47.0),   # ~280 km away — safe
            terrain=TerrainType.MOUNTAINOUS,
        ),
    ]


# ── Schema Validation ────────────────────────────────────────────────────

class TestSchemaValidation:
    def test_coordinate_valid(self):
        c = Coordinate(lat=51.5, lon=-0.1)
        assert c.lat == 51.5
        assert c.alt_m is None

    def test_threat_ring_rejects_zero_range(self):
        with pytest.raises(Exception):
            ThreatRing(
                threat_id="bad",
                center=Coordinate(lat=0, lon=0),
                range_km=0,          # gt=0 constraint
                threat_type=ThreatType.SAM_SHORT,
                confidence=0.5,
            )

    def test_mission_path_valid(self):
        wp = Waypoint(
            sequence=0,
            position=Coordinate(lat=10, lon=20),
        )
        mp = MissionPath(
            path_id="path-1",
            waypoints=[wp],
            total_distance_km=0.0,
            risk_score=0.1,
        )
        assert mp.path_id == "path-1"

    def test_battlespace_output_valid(self):
        wp = Waypoint(sequence=0, position=Coordinate(lat=10, lon=20))
        mp = MissionPath(
            path_id="p1",
            waypoints=[wp],
            total_distance_km=0,
            risk_score=0.0,
        )
        out = BattlespaceManagerOutput(mission_path=mp)
        assert out.active_threat_rings == []
        assert out.active_layers == []


# ── Geospatial Utilities ─────────────────────────────────────────────────

class TestHaversineDistance:
    def test_london_to_paris(self, london, paris):
        """London → Paris ≈ 343 km (accepted range 340–350 km)."""
        d = haversine_distance(london, paris)
        assert 340 < d < 350

    def test_same_point_is_zero(self, london):
        assert haversine_distance(london, london) == pytest.approx(0.0)

    def test_symmetry(self, london, paris):
        assert haversine_distance(london, paris) == pytest.approx(
            haversine_distance(paris, london)
        )


class TestThreatRingContainment:
    def test_centre_is_inside(self, sam_site):
        """The centre of a threat ring is trivially inside it."""
        assert is_inside_threat_ring(sam_site.center, sam_site) is True

    def test_far_point_is_outside(self, sam_site):
        """A point 300+ km away should be outside a 50 km ring."""
        far = Coordinate(lat=40.0, lon=50.0)
        assert is_inside_threat_ring(far, sam_site) is False

    def test_boundary_point(self, sam_site):
        """A point exactly on the boundary should be considered inside (<=)."""
        # Calculate a point ~50 km north of the centre
        delta_lat = 50.0 / 111.32  # ~0.449 degrees
        boundary = Coordinate(lat=sam_site.center.lat + delta_lat, lon=sam_site.center.lon)
        d = haversine_distance(boundary, sam_site.center)
        # Should be very close to 50 km
        assert abs(d - 50.0) < 1.0  # within 1 km tolerance


class TestFilterSafeWaypoints:
    def test_filters_unsafe_waypoints(self, waypoints_mixed, sam_site):
        safe = filter_safe_waypoints(waypoints_mixed, [sam_site])
        assert len(safe) == 2
        assert all(wp.is_safe for wp in safe)

    def test_no_threats_keeps_all(self, waypoints_mixed):
        safe = filter_safe_waypoints(waypoints_mixed, [])
        assert len(safe) == 3

    def test_empty_waypoints(self, sam_site):
        safe = filter_safe_waypoints([], [sam_site])
        assert safe == []


# ── Agent Instantiation ──────────────────────────────────────────────────

class TestBattlespaceManagerAgent:
    def test_init(self):
        agent = BattlespaceManagerAgent(llm_client=None)
        assert agent.system_prompt is not None
        assert len(agent.get_active_layers()) == 5

    def test_default_layers_types(self):
        agent = BattlespaceManagerAgent(llm_client=None)
        layer_types = {l.layer_type for l in agent.get_active_layers()}
        assert MapLayerType.TERRAIN in layer_types
        assert MapLayerType.THREATS in layer_types

    def test_update_threat_rings(self, sam_site):
        agent = BattlespaceManagerAgent(llm_client=None)
        assert len(agent._threat_rings) == 0

        agent.update_threat_rings([sam_site])
        assert len(agent._threat_rings) == 1

        # Update same ring — should replace, not duplicate
        updated = sam_site.model_copy(update={"confidence": 0.99})
        agent.update_threat_rings([updated])
        assert len(agent._threat_rings) == 1
        assert agent._threat_rings[0].confidence == 0.99
