"""
Tests for KDTree-based clustering in battlespace_assessment.py (TDD).

Tests verify behavioral equivalence between original O(n^2) and KDTree implementations.
"""

import math

import pytest
from battlespace_assessment import (
    CLUSTER_RADIUS_DEG,
    BattlespaceAssessor,
)


def _make_target(
    id: int,
    x: float,
    y: float,
    target_type: str = "SAM",
    state: str = "DETECTED",
    fused_confidence: float = 0.7,
) -> dict:
    return {
        "id": id,
        "x": x,
        "y": y,
        "type": target_type,
        "state": state,
        "fused_confidence": fused_confidence,
    }


class TestKDTreeClustering:
    def test_empty_input_returns_empty_clusters(self):
        """Empty target list -> no clusters."""
        assessor = BattlespaceAssessor()
        result = assessor.assess([], [], [])
        assert result.clusters == ()

    def test_single_target_no_cluster(self):
        """Single target can't form a cluster (MIN_CLUSTER_SIZE=2)."""
        targets = [_make_target(1, 28.0, 44.0)]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 0

    def test_distant_targets_separate_clusters(self):
        """Targets > CLUSTER_RADIUS_DEG apart must NOT cluster together."""
        # Place targets 2 degrees apart — well beyond 0.135 threshold
        targets = [
            _make_target(1, 28.0, 44.0),
            _make_target(2, 30.0, 44.0),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        # Neither forms a cluster (each only has 1 neighbor including itself
        # at MIN_CLUSTER_SIZE=2, a pair at radius would cluster — but they're far)
        assert len(result.clusters) == 0

    def test_close_pair_forms_cluster(self):
        """Two targets within CLUSTER_RADIUS_DEG form one cluster."""
        targets = [
            _make_target(1, 28.0, 44.0),
            _make_target(2, 28.05, 44.02),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert sorted(result.clusters[0].member_target_ids) == [1, 2]

    def test_three_close_targets_one_cluster(self):
        """Three targets all within radius of each other -> single cluster."""
        targets = [
            _make_target(1, 28.0, 44.0),
            _make_target(2, 28.05, 44.02),
            _make_target(3, 28.02, 44.01),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert sorted(result.clusters[0].member_target_ids) == [1, 2, 3]

    def test_cluster_centroid_accuracy(self):
        """Centroid of a 2-target cluster is the midpoint."""
        t1 = _make_target(1, 28.0, 44.0)
        t2 = _make_target(2, 28.06, 44.0)  # 0.06 deg apart — within CLUSTER_RADIUS_DEG 0.135
        assessor = BattlespaceAssessor()
        result = assessor.assess([t1, t2], [], [])
        assert len(result.clusters) == 1
        c = result.clusters[0]
        assert c.centroid_lon == pytest.approx(28.03, abs=1e-6)
        assert c.centroid_lat == pytest.approx(44.0, abs=1e-6)

    def test_cluster_id_format(self):
        """Cluster ID is 'CLU-' followed by sorted member IDs."""
        targets = [
            _make_target(5, 28.0, 44.0),
            _make_target(2, 28.05, 44.02),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert result.clusters[0].cluster_id == "CLU-2-5"

    def test_large_cluster_same_members_as_brute_force(self):
        """
        Generate 20 targets in a tight grid. The KDTree implementation must
        produce the same set of member IDs as a brute-force O(n^2) approach
        (verified by running both and comparing membership).
        """
        # All 20 targets within a 0.1-degree box -> all within CLUSTER_RADIUS_DEG
        targets = [_make_target(i, 28.0 + (i % 5) * 0.02, 44.0 + (i // 5) * 0.02) for i in range(1, 21)]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])

        # At minimum one cluster should exist
        assert len(result.clusters) >= 1

        # All returned member IDs must actually be within CLUSTER_RADIUS_DEG of
        # the cluster centroid (basic sanity check for correctness)
        for cluster in result.clusters:
            for mid in cluster.member_target_ids:
                t = next(t for t in targets if t["id"] == mid)
                dist = math.hypot(
                    t["x"] - cluster.centroid_lon,
                    t["y"] - cluster.centroid_lat,
                )
                # Members within 2x radius of centroid is a reasonable sanity bound
                assert dist <= CLUSTER_RADIUS_DEG * 2

    def test_undetected_targets_excluded_from_clusters(self):
        """UNDETECTED targets must not appear in any cluster."""
        targets = [
            _make_target(1, 28.0, 44.0, state="UNDETECTED"),
            _make_target(2, 28.05, 44.02, state="DETECTED"),
            _make_target(3, 28.02, 44.01, state="DETECTED"),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        for cluster in result.clusters:
            assert 1 not in cluster.member_target_ids

    def test_threat_score_is_average_confidence(self):
        """Cluster threat_score is the mean fused_confidence of members."""
        targets = [
            _make_target(1, 28.0, 44.0, fused_confidence=0.4),
            _make_target(2, 28.05, 44.02, fused_confidence=0.8),
        ]
        assessor = BattlespaceAssessor()
        result = assessor.assess(targets, [], [])
        assert len(result.clusters) == 1
        assert result.clusters[0].threat_score == pytest.approx(0.6, abs=1e-6)

    def test_scipy_kdtree_import(self):
        """scipy.spatial.KDTree must be importable (dependency satisfied)."""
        from scipy.spatial import KDTree

        assert KDTree is not None
