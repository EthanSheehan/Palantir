"""
test_dbscan_clustering.py
=========================
TDD tests for dbscan_clustering.py — written FIRST (RED phase).

Covers: DBSCAN clustering, persistent ID assignment, edge cases.
"""

import pytest
from dbscan_clustering import (
    ClusterResult,
    ClusterState,
    _haversine_km,
    match_clusters,
    run_dbscan,
    update_clustering,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_target(
    id: int,
    lat: float,
    lon: float,
    target_type: str = "SAM",
    state: str = "DETECTED",
    fused_confidence: float = 0.7,
) -> dict:
    return {
        "id": id,
        "lat": lat,
        "lon": lon,
        "type": target_type,
        "state": state,
        "fused_confidence": fused_confidence,
    }


# ---------------------------------------------------------------------------
# TestHaversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_zero_distance(self):
        assert _haversine_km(44.0, 28.0, 44.0, 28.0) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        # ~111 km per degree latitude
        d = _haversine_km(44.0, 28.0, 45.0, 28.0)
        assert 110.0 < d < 112.0

    def test_symmetry(self):
        d1 = _haversine_km(44.0, 28.0, 44.5, 28.3)
        d2 = _haversine_km(44.5, 28.3, 44.0, 28.0)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_equatorial_degree(self):
        # 1 degree longitude at equator ~ 111 km
        d = _haversine_km(0.0, 0.0, 0.0, 1.0)
        assert 110.0 < d < 112.0


# ---------------------------------------------------------------------------
# TestRunDBSCAN
# ---------------------------------------------------------------------------


class TestRunDBSCAN:
    def test_empty_targets_returns_empty(self):
        result = run_dbscan([], eps_km=2.0, min_samples=2)
        assert result == []

    def test_single_target_is_noise(self):
        targets = [_make_target(1, 44.0, 28.0)]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        # Single point with min_samples=2 -> no clusters
        assert result == []

    def test_two_close_targets_form_cluster(self):
        # ~1.1 km apart, well within eps=2.0
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.01, 28.0),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert len(result) == 1
        centroid, member_ids, threat_score = result[0]
        assert set(member_ids) == {1, 2}

    def test_two_far_targets_no_cluster(self):
        # ~111 km apart
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 45.0, 28.0),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert result == []

    def test_three_targets_two_clusters(self):
        # Two close pairs, one isolated
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),  # ~0.55 km from #1
            _make_target(3, 44.0, 29.0),  # ~80+ km away
            _make_target(4, 44.005, 29.0),  # close to #3
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert len(result) == 2

    def test_threat_score_is_average_confidence(self):
        targets = [
            _make_target(1, 44.0, 28.0, fused_confidence=0.6),
            _make_target(2, 44.005, 28.0, fused_confidence=0.8),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert len(result) == 1
        _, _, threat_score = result[0]
        assert threat_score == pytest.approx(0.7, rel=1e-6)

    def test_centroid_is_mean_of_members(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.0, 28.0),  # same point
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        centroid, _, _ = result[0]
        assert centroid[0] == pytest.approx(44.0)
        assert centroid[1] == pytest.approx(28.0)

    def test_undetected_targets_excluded(self):
        targets = [
            _make_target(1, 44.0, 28.0, state="UNDETECTED"),
            _make_target(2, 44.005, 28.0, state="UNDETECTED"),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert result == []

    def test_mixed_detected_undetected(self):
        targets = [
            _make_target(1, 44.0, 28.0, state="DETECTED"),
            _make_target(2, 44.005, 28.0, state="UNDETECTED"),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        # Only 1 detected -> noise
        assert result == []

    def test_member_ids_are_sorted(self):
        targets = [
            _make_target(5, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
            _make_target(8, 44.003, 28.001),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert len(result) == 1
        _, member_ids, _ = result[0]
        assert list(member_ids) == sorted(member_ids)

    def test_all_points_noise_returns_empty(self):
        # All isolated — each more than eps apart
        targets = [_make_target(i, 44.0 + i * 1.0, 28.0, state="DETECTED") for i in range(5)]
        result = run_dbscan(targets, eps_km=2.0, min_samples=2)
        assert result == []

    def test_min_samples_three_requires_three(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        # With min_samples=3 two points aren't enough
        result = run_dbscan(targets, eps_km=2.0, min_samples=3)
        assert result == []

    def test_min_samples_three_with_three_close(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
            _make_target(3, 44.003, 28.002),
        ]
        result = run_dbscan(targets, eps_km=2.0, min_samples=3)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestMatchClusters
# ---------------------------------------------------------------------------


class TestMatchClusters:
    def _make_cluster_result(self, cluster_id, lat, lon, members, threat=0.7):
        return ClusterResult(
            cluster_id=cluster_id,
            centroid=(lat, lon),
            members=tuple(members),
            threat_level=threat,
        )

    def test_empty_prev_assigns_new_ids(self):
        new_clusters = [((44.0, 28.0), (1, 2), 0.7)]
        matched, next_id = match_clusters((), new_clusters, max_match_km=5.0)
        assert len(matched) == 1
        assert matched[0].cluster_id == "CLU-0"
        assert next_id == 1

    def test_matching_cluster_keeps_id(self):
        prev = (self._make_cluster_result("CLU-5", 44.0, 28.0, [1, 2]),)
        new_clusters = [((44.001, 28.001), (1, 2), 0.8)]  # very close
        matched, next_id = match_clusters(prev, new_clusters, max_match_km=5.0)
        assert matched[0].cluster_id == "CLU-5"
        assert next_id == 6  # next available after CLU-5

    def test_far_cluster_gets_new_id(self):
        prev = (self._make_cluster_result("CLU-3", 44.0, 28.0, [1, 2]),)
        new_clusters = [((46.0, 30.0), (3, 4), 0.6)]  # far away
        matched, next_id = match_clusters(prev, new_clusters, max_match_km=5.0)
        assert matched[0].cluster_id != "CLU-3"
        assert matched[0].cluster_id == "CLU-4"
        assert next_id == 5

    def test_empty_new_clusters_returns_empty(self):
        prev = (self._make_cluster_result("CLU-0", 44.0, 28.0, [1, 2]),)
        matched, next_id = match_clusters(prev, [], max_match_km=5.0)
        assert matched == []
        assert next_id == 1  # CLU-0 consumed id 0

    def test_two_new_match_two_prev(self):
        prev = (
            self._make_cluster_result("CLU-0", 44.0, 28.0, [1, 2]),
            self._make_cluster_result("CLU-1", 44.0, 29.0, [3, 4]),
        )
        new_clusters = [
            ((44.001, 28.001), (1, 2), 0.7),
            ((44.001, 29.001), (3, 4), 0.8),
        ]
        matched, next_id = match_clusters(prev, new_clusters, max_match_km=5.0)
        ids = {m.cluster_id for m in matched}
        assert ids == {"CLU-0", "CLU-1"}
        assert next_id == 2

    def test_result_is_list_of_cluster_results(self):
        new_clusters = [((44.0, 28.0), (1, 2), 0.7)]
        matched, _ = match_clusters((), new_clusters)
        assert all(isinstance(m, ClusterResult) for m in matched)

    def test_next_id_increments_for_each_new(self):
        new_clusters = [
            ((44.0, 28.0), (1, 2), 0.7),
            ((44.0, 29.0), (3, 4), 0.6),
        ]
        matched, next_id = match_clusters((), new_clusters)
        assert next_id == 2
        assert {m.cluster_id for m in matched} == {"CLU-0", "CLU-1"}


# ---------------------------------------------------------------------------
# TestUpdateClustering
# ---------------------------------------------------------------------------


class TestUpdateClustering:
    def test_none_prev_state_initializes(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state = update_clustering(None, targets, eps_km=2.0)
        assert isinstance(state, ClusterState)
        assert len(state.clusters) == 1
        assert state.clusters[0].cluster_id == "CLU-0"
        assert state.next_id == 1

    def test_persistent_id_across_ticks(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state1 = update_clustering(None, targets, eps_km=2.0)
        # Slight movement
        targets2 = [
            _make_target(1, 44.001, 28.0),
            _make_target(2, 44.006, 28.0),
        ]
        state2 = update_clustering(state1, targets2, eps_km=2.0)
        assert state2.clusters[0].cluster_id == "CLU-0"

    def test_new_cluster_gets_next_id(self):
        targets1 = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state1 = update_clustering(None, targets1, eps_km=2.0)
        # Add a new distant cluster
        targets2 = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
            _make_target(3, 44.0, 29.0),
            _make_target(4, 44.005, 29.0),
        ]
        state2 = update_clustering(state1, targets2, eps_km=2.0)
        ids = {c.cluster_id for c in state2.clusters}
        assert "CLU-0" in ids
        assert "CLU-1" in ids

    def test_empty_targets_returns_empty_state(self):
        state = update_clustering(None, [], eps_km=2.0)
        assert isinstance(state, ClusterState)
        assert state.clusters == ()
        assert state.next_id == 0

    def test_state_is_frozen(self):
        from dataclasses import FrozenInstanceError

        state = update_clustering(None, [], eps_km=2.0)
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            state.next_id = 99  # type: ignore[misc]

    def test_cluster_result_is_frozen(self):
        from dataclasses import FrozenInstanceError

        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state = update_clustering(None, targets, eps_km=2.0)
        cluster = state.clusters[0]
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            cluster.threat_level = 0.0  # type: ignore[misc]

    def test_members_are_sorted(self):
        targets = [
            _make_target(5, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state = update_clustering(None, targets, eps_km=2.0)
        assert list(state.clusters[0].members) == sorted(state.clusters[0].members)

    def test_centroid_is_tuple_of_floats(self):
        targets = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state = update_clustering(None, targets, eps_km=2.0)
        c = state.clusters[0].centroid
        assert isinstance(c, tuple)
        assert len(c) == 2
        assert isinstance(c[0], float)
        assert isinstance(c[1], float)

    def test_cluster_vanishes_when_targets_disperse(self):
        targets1 = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 44.005, 28.0),
        ]
        state1 = update_clustering(None, targets1, eps_km=2.0)
        assert len(state1.clusters) == 1

        # Now targets are far apart
        targets2 = [
            _make_target(1, 44.0, 28.0),
            _make_target(2, 45.0, 29.0),
        ]
        state2 = update_clustering(state1, targets2, eps_km=2.0)
        assert len(state2.clusters) == 0
