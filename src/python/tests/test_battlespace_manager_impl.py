"""
New tests for BattlespaceManagerAgent._generate_response() heuristic.
These must FAIL before implementation and PASS after.
"""

import pytest
from agents.battlespace_manager import BattlespaceManagerAgent
from schemas.ontology import (
    BattlespaceManagerOutput,
    Coordinate,
    TargetClassification,
    ThreatRing,
    ThreatType,
    Track,
)


def _make_track(track_id: str) -> Track:
    return Track(
        track_id=track_id,
        lat=33.4,
        lon=44.3,
        classification=TargetClassification.SAM,
        confidence=0.8,
        detections=[],
    )


def _make_threat_ring(threat_id: str, lat: float = 33.5, lon: float = 44.5) -> ThreatRing:
    return ThreatRing(
        threat_id=threat_id,
        center=Coordinate(lat=lat, lon=lon),
        range_km=50.0,
        threat_type=ThreatType.SAM_MEDIUM,
        confidence=0.9,
    )


@pytest.fixture
def agent_no_llm():
    return BattlespaceManagerAgent(llm_client=None)


class TestBattlespaceManagerHeuristicResponse:
    def test_battlespace_manager_returns_path(self, agent_no_llm):
        tracks = [_make_track("T-1")]
        threat_rings = [_make_threat_ring("SAM-001")]
        result = agent_no_llm.generate_mission_path(tracks, threat_rings, "Flat terrain")
        assert isinstance(result, BattlespaceManagerOutput)
        assert result.mission_path is not None

    def test_battlespace_manager_handles_no_zones(self, agent_no_llm):
        result = agent_no_llm.generate_mission_path([], [], "No terrain data")
        assert isinstance(result, BattlespaceManagerOutput)
        assert result.mission_path is not None

    def test_battlespace_manager_path_has_waypoints(self, agent_no_llm):
        tracks = [_make_track("T-1")]
        result = agent_no_llm.generate_mission_path(tracks, [], "Standard terrain")
        assert len(result.mission_path.waypoints) >= 1

    def test_battlespace_manager_sets_active_threat_rings(self, agent_no_llm):
        threat_rings = [_make_threat_ring("SAM-001")]
        result = agent_no_llm.generate_mission_path([], threat_rings, "")
        assert len(result.active_threat_rings) == 1

    def test_battlespace_manager_sets_active_layers(self, agent_no_llm):
        result = agent_no_llm.generate_mission_path([], [], "")
        assert len(result.active_layers) == 5

    def test_no_agent_raises_not_implemented(self, agent_no_llm):
        try:
            agent_no_llm.generate_mission_path([], [], "")
        except NotImplementedError:
            pytest.fail("generate_mission_path raised NotImplementedError with llm_client=None")
