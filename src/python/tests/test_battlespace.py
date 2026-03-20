"""
Tests for battlespace_assessment.py — written FIRST (TDD RED phase).

All tests must fail before battlespace_assessment.py exists, then pass after implementation.
"""

import pytest

from battlespace_assessment import (
    BattlespaceAssessor,
    ThreatCluster,
    CoverageGap,
    MovementCorridor,
    AssessmentResult,
)


def _make_target(
    id: int,
    x: float,
    y: float,
    target_type: str = "SAM",
    state: str = "DETECTED",
    fused_confidence: float = 0.7,
    position_history=None,
) -> dict:
    t = {
        "id": id,
        "x": x,
        "y": y,
        "type": target_type,
        "state": state,
        "fused_confidence": fused_confidence,
    }
    if position_history is not None:
        t["position_history"] = position_history
    return t


def _make_zone(x_idx: int, y_idx: int, lon: float, lat: float, uav_count: int = 0) -> dict:
    return {
        "x_idx": x_idx,
        "y_idx": y_idx,
        "lon": lon,
        "lat": lat,
        "width": 0.1,
        "height": 0.1,
        "uav_count": uav_count,
        "imbalance": 0.0,
    }


def _make_uav(id: int, lon: float, lat: float, mode: str = "SEARCH", x_idx: int = 0, y_idx: int = 0) -> dict:
    return {
        "id": id,
        "lon": lon,
        "lat": lat,
        "mode": mode,
        "zone_x": x_idx,
        "zone_y": y_idx,
    }


# ---------------------------------------------------------------------------
# TestClustering
# ---------------------------------------------------------------------------

class TestClustering:
    def test_two_sams_within_radius_form_cluster(self):
        """Two SAM targets close together -> 1 AD_NETWORK cluster."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(2, 28.05, 44.02, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert result.clusters[0].cluster_type == "AD_NETWORK"

    def test_targets_outside_radius_no_cluster(self):
        """Two targets 1.0 degree apart -> no clusters."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(2, 29.0, 45.0, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 0

    def test_cluster_type_by_majority(self):
        """2 TRUCK + 1 LOGISTICS -> cluster type CONVOY."""
        targets = [
            _make_target(1, 28.0, 44.0, "TRUCK"),
            _make_target(2, 28.05, 44.02, "TRUCK"),
            _make_target(3, 28.03, 44.01, "LOGISTICS"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert result.clusters[0].cluster_type == "CONVOY"

    def test_cluster_id_stability(self):
        """Cluster ID derived from sorted member IDs, not sequential numbering."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(3, 28.05, 44.02, "SAM"),
            _make_target(5, 28.02, 44.01, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert result.clusters[0].cluster_id == "CLU-1-3-5"

    def test_undetected_targets_excluded(self):
        """Targets with state=UNDETECTED are not clustered."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM", state="UNDETECTED"),
            _make_target(2, 28.05, 44.02, "SAM", state="UNDETECTED"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 0

    def test_convex_hull_computed(self):
        """Cluster with 4 targets has hull_points with >= 3 entries."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(2, 28.1, 44.0, "SAM"),
            _make_target(3, 28.05, 44.08, "SAM"),
            _make_target(4, 28.07, 44.03, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert len(result.clusters[0].hull_points) >= 3


# ---------------------------------------------------------------------------
# TestCoverageGaps
# ---------------------------------------------------------------------------

class TestCoverageGaps:
    def test_zone_with_no_uav_is_gap(self):
        """Zone with uav_count=0 and no UAV in SEARCH mode -> is a gap."""
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=0)]
        assessor = BattlespaceAssessor()
        result = assessor.assess([], [], zones)
        assert len(result.coverage_gaps) == 1
        assert result.coverage_gaps[0].zone_x == 0
        assert result.coverage_gaps[0].zone_y == 0

    def test_zone_with_uav_not_gap(self):
        """Zone with uav_count=1 -> not a gap."""
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=1)]
        assessor = BattlespaceAssessor()
        result = assessor.assess([], [], zones)
        assert len(result.coverage_gaps) == 0

    def test_covered_by_search_uav_not_gap(self):
        """Zone with uav_count=0 but UAV at same x_idx/y_idx in SEARCH mode -> not a gap."""
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=0)]
        uavs = [_make_uav(1, 28.05, 44.05, mode="SEARCH", x_idx=0, y_idx=0)]
        assessor = BattlespaceAssessor()
        result = assessor.assess([], uavs, zones)
        assert len(result.coverage_gaps) == 0


# ---------------------------------------------------------------------------
# TestZoneThreatScoring
# ---------------------------------------------------------------------------

class TestZoneThreatScoring:
    def test_single_target_in_zone(self):
        """One detected target with fused_confidence=0.7 at zone (0,0) -> score 0.7."""
        # Zone center at (28.05, 44.05) with width/height 0.1
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=0)]
        targets = [_make_target(1, 28.05, 44.05, "SAM", fused_confidence=0.7)]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], zones)
        score = result.zone_threat_scores.get((0, 0), 0.0)
        assert score == pytest.approx(0.7)

    def test_multiple_targets_sum_capped(self):
        """Two targets with 0.6 each -> score capped at 1.0."""
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=0)]
        targets = [
            _make_target(1, 28.05, 44.05, "SAM", fused_confidence=0.6),
            _make_target(2, 28.02, 44.02, "SAM", fused_confidence=0.6),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], zones)
        score = result.zone_threat_scores.get((0, 0), 0.0)
        assert score == pytest.approx(1.0)

    def test_undetected_target_ignored(self):
        """Undetected target -> zone score 0.0."""
        zones = [_make_zone(0, 0, 28.0, 44.0, uav_count=0)]
        targets = [_make_target(1, 28.05, 44.05, "SAM", state="UNDETECTED", fused_confidence=0.9)]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], zones)
        score = result.zone_threat_scores.get((0, 0), 0.0)
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestMovementCorridors
# ---------------------------------------------------------------------------

class TestMovementCorridors:
    def test_moving_target_produces_corridor(self):
        """Target with 15 history entries spread > 0.005 deg -> 1 corridor."""
        # Spread across 0.01 degrees to exceed threshold
        history = [(28.0 + i * 0.001, 44.0 + i * 0.0005) for i in range(15)]
        targets = [
            _make_target(1, 28.014, 44.007, "TRUCK", position_history=history)
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.movement_corridors) == 1
        assert result.movement_corridors[0].target_id == 1

    def test_stationary_target_no_corridor(self):
        """Target with 15 entries at same position -> no corridor."""
        history = [(28.0, 44.0)] * 15
        targets = [
            _make_target(1, 28.0, 44.0, "TRUCK", position_history=history)
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.movement_corridors) == 0

    def test_short_history_no_corridor(self):
        """Target with 5 entries -> no corridor (needs >= 10)."""
        history = [(28.0 + i * 0.001, 44.0 + i * 0.001) for i in range(5)]
        targets = [
            _make_target(1, 28.005, 44.005, "TRUCK", position_history=history)
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.movement_corridors) == 0


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_targets_returns_empty_result(self):
        """No targets -> AssessmentResult with empty tuples."""
        assessor = BattlespaceAssessor()
        result = assessor.assess([], [], [])
        assert result.clusters == ()
        assert result.coverage_gaps == ()
        assert result.movement_corridors == ()
        assert isinstance(result.zone_threat_scores, dict)
        assert result.assessed_at > 0

    def test_empty_zones_returns_empty_gaps(self):
        """No zones -> empty coverage_gaps."""
        targets = [_make_target(1, 28.0, 44.0, "SAM")]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert result.coverage_gaps == ()

    def test_single_point_hull(self):
        """1 target in cluster range -> no cluster (need >= 2)."""
        targets = [_make_target(1, 28.0, 44.0, "SAM")]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 0

    def test_two_point_hull(self):
        """2 targets -> cluster with 2 hull points (degenerate but valid)."""
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(2, 28.05, 44.02, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert len(result.clusters[0].hull_points) == 2

    def test_result_is_frozen(self):
        """AssessmentResult is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        assessor = BattlespaceAssessor()
        result = assessor.assess([], [], [])
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            result.clusters = ()  # type: ignore[misc]

    def test_cluster_is_frozen(self):
        """ThreatCluster is immutable."""
        from dataclasses import FrozenInstanceError
        targets = [
            _make_target(1, 28.0, 44.0, "SAM"),
            _make_target(2, 28.05, 44.02, "SAM"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        cluster = result.clusters[0]
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            cluster.cluster_type = "MIXED"  # type: ignore[misc]
