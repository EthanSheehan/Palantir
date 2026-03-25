"""
Tests for corridor_detection.py — Douglas-Peucker + directional consistency.

Run: ./venv/bin/python3 -m pytest src/python/tests/test_corridor_detection.py -v
"""

from __future__ import annotations

import math

import pytest
from corridor_detection import (
    Corridor,
    attribute_corridor,
    compute_heading_consistency,
    detect_corridors,
    douglas_peucker,
)

# ---------------------------------------------------------------------------
# douglas_peucker
# ---------------------------------------------------------------------------


class TestDouglasPeucker:
    def test_empty_returns_empty(self):
        assert douglas_peucker([], 0.1) == []

    def test_single_point_returned(self):
        pts = [(1.0, 2.0)]
        assert douglas_peucker(pts, 0.5) == [(1.0, 2.0)]

    def test_two_points_returned(self):
        pts = [(0.0, 0.0), (1.0, 1.0)]
        assert douglas_peucker(pts, 0.5) == [(0.0, 0.0), (1.0, 1.0)]

    def test_collinear_points_simplified(self):
        # Three collinear points — middle should be dropped
        pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        result = douglas_peucker(pts, 0.01)
        assert result == [(0.0, 0.0), (1.0, 1.0)]

    def test_zigzag_preserved_with_small_epsilon(self):
        pts = [(0.0, 0.0), (0.5, 1.0), (1.0, 0.0), (1.5, 1.0), (2.0, 0.0)]
        result = douglas_peucker(pts, 0.01)
        assert len(result) == 5  # all preserved at tight tolerance

    def test_zigzag_simplified_with_large_epsilon(self):
        pts = [(0.0, 0.0), (0.5, 0.1), (1.0, 0.0), (1.5, 0.1), (2.0, 0.0)]
        result = douglas_peucker(pts, 0.5)
        # endpoints always preserved
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (2.0, 0.0)
        assert len(result) < len(pts)

    def test_endpoints_always_preserved(self):
        pts = [(0.0, 0.0), (0.3, 0.2), (0.6, 0.1), (1.0, 0.0)]
        result = douglas_peucker(pts, 10.0)  # huge epsilon
        assert result[0] == (0.0, 0.0)
        assert result[-1] == (1.0, 0.0)

    def test_straight_line_many_points(self):
        pts = [(float(i), float(i)) for i in range(10)]
        result = douglas_peucker(pts, 0.001)
        assert result == [(0.0, 0.0), (9.0, 9.0)]

    def test_returns_list_of_tuples(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 1.0)]
        result = douglas_peucker(pts, 0.01)
        assert isinstance(result, list)
        assert all(isinstance(p, tuple) for p in result)


# ---------------------------------------------------------------------------
# compute_heading_consistency
# ---------------------------------------------------------------------------


class TestComputeHeadingConsistency:
    def test_empty_returns_zero(self):
        assert compute_heading_consistency([]) == 0.0

    def test_single_point_returns_zero(self):
        assert compute_heading_consistency([(0.0, 0.0)]) == 0.0

    def test_two_points_returns_one(self):
        result = compute_heading_consistency([(0.0, 0.0), (1.0, 0.0)])
        assert result == pytest.approx(1.0)

    def test_straight_line_high_consistency(self):
        pts = [(float(i), 0.0) for i in range(10)]
        result = compute_heading_consistency(pts)
        assert result > 0.95

    def test_random_walk_low_consistency(self):
        # Points alternating direction — very inconsistent
        pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]
        result = compute_heading_consistency(pts)
        assert result < 0.5

    def test_gradual_curve_medium_consistency(self):
        # Quarter circle arc
        pts = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in range(0, 91, 10)]
        result = compute_heading_consistency(pts)
        # Curved but directional — should be moderate
        assert 0.3 < result < 0.95

    def test_returns_float_in_range(self):
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.5), (3.0, 1.5)]
        result = compute_heading_consistency(pts)
        assert 0.0 <= result <= 1.0

    def test_reverse_direction_low_consistency(self):
        # Go right then go left
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 0.0), (0.0, 0.0)]
        result = compute_heading_consistency(pts)
        assert result < 0.5


# ---------------------------------------------------------------------------
# detect_corridors
# ---------------------------------------------------------------------------


def _make_history(points: list[tuple[float, float]], t_start: float = 0.0) -> list[dict]:
    """Helper: build position history records from a list of (lon, lat) points."""
    return [{"lon": p[0], "lat": p[1], "timestamp": t_start + i * 10.0} for i, p in enumerate(points)]


def _straight_path(n: int = 10, dx: float = 0.01) -> list[tuple[float, float]]:
    """Straight path of n points moving east."""
    return [(i * dx, 0.0) for i in range(n)]


def _patrol_loop(n: int = 20) -> list[tuple[float, float]]:
    """Closed patrol loop — displacement-only would see movement but no corridor."""
    pts = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        pts.append((math.cos(angle) * 0.05, math.sin(angle) * 0.05))
    return pts


class TestDetectCorridors:
    def test_empty_histories_returns_empty(self):
        assert detect_corridors({}) == []

    def test_insufficient_points_skipped(self):
        histories = {"t1": _make_history(_straight_path(3))}
        assert detect_corridors(histories, min_points=5) == []

    def test_straight_path_detected(self):
        histories = {"t1": _make_history(_straight_path(15))}
        result = detect_corridors(histories, min_points=5, epsilon_km=0.1, min_consistency=0.6)
        assert len(result) >= 1
        assert isinstance(result[0], Corridor)

    def test_patrol_loop_not_detected(self):
        # Circular patrol loop should fail directional consistency check
        histories = {"t1": _make_history(_patrol_loop(20))}
        result = detect_corridors(histories, min_points=5, epsilon_km=0.001, min_consistency=0.6)
        assert len(result) == 0

    def test_corridor_has_correct_fields(self):
        histories = {"t1": _make_history(_straight_path(15))}
        result = detect_corridors(histories, min_points=5, epsilon_km=0.1, min_consistency=0.6)
        assert len(result) >= 1
        c = result[0]
        assert isinstance(c.corridor_id, str)
        assert isinstance(c.waypoints, tuple)
        assert len(c.waypoints) >= 2
        assert 0.0 <= c.confidence <= 1.0
        assert c.heading_deg >= 0.0
        assert c.speed_avg >= 0.0

    def test_multiple_targets_multiple_corridors(self):
        histories = {
            "t1": _make_history(_straight_path(15, dx=0.01)),
            "t2": _make_history(_straight_path(15, dx=0.01), t_start=100.0),
        }
        result = detect_corridors(histories, min_points=5, epsilon_km=0.1, min_consistency=0.6)
        assert len(result) >= 2

    def test_corridor_is_frozen(self):
        histories = {"t1": _make_history(_straight_path(15))}
        result = detect_corridors(histories)
        assert len(result) >= 1
        c = result[0]
        with pytest.raises((AttributeError, TypeError)):
            c.confidence = 0.99  # type: ignore[misc]

    def test_start_end_points_populated(self):
        histories = {"t1": _make_history(_straight_path(15, dx=0.01))}
        result = detect_corridors(histories, min_points=5)
        assert len(result) >= 1
        c = result[0]
        assert c.start_point is not None
        assert c.end_point is not None
        assert len(c.start_point) == 2
        assert len(c.end_point) == 2

    def test_time_range_populated(self):
        histories = {"t1": _make_history(_straight_path(15, dx=0.01), t_start=1000.0)}
        result = detect_corridors(histories, min_points=5)
        assert len(result) >= 1
        c = result[0]
        assert c.time_start is not None
        assert c.time_end is not None
        assert c.time_end >= c.time_start

    def test_target_ids_in_corridor(self):
        histories = {"t1": _make_history(_straight_path(15))}
        result = detect_corridors(histories, min_points=5)
        assert len(result) >= 1
        assert "t1" in result[0].target_ids


# ---------------------------------------------------------------------------
# attribute_corridor
# ---------------------------------------------------------------------------


class TestAttributeCorridor:
    def _make_corridor(self, target_ids=("t1",)):
        return Corridor(
            corridor_id="COR-001",
            start_point=(0.0, 0.0),
            end_point=(1.0, 0.0),
            waypoints=((0.0, 0.0), (0.5, 0.0), (1.0, 0.0)),
            target_ids=target_ids,
            heading_deg=90.0,
            speed_avg=10.0,
            time_start=1000.0,
            time_end=1100.0,
            confidence=0.8,
        )

    def test_returns_corridor(self):
        c = self._make_corridor()
        all_targets = {"t1": {"id": "t1", "type": "TRUCK"}}
        result = attribute_corridor(c, all_targets)
        assert isinstance(result, Corridor)

    def test_known_targets_preserved(self):
        c = self._make_corridor(target_ids=("t1", "t2"))
        all_targets = {"t1": {"id": "t1"}, "t2": {"id": "t2"}}
        result = attribute_corridor(c, all_targets)
        assert "t1" in result.target_ids
        assert "t2" in result.target_ids

    def test_unknown_targets_excluded(self):
        c = self._make_corridor(target_ids=("t1", "ghost"))
        all_targets = {"t1": {"id": "t1"}}
        result = attribute_corridor(c, all_targets)
        assert "ghost" not in result.target_ids
        assert "t1" in result.target_ids

    def test_returns_frozen_dataclass(self):
        c = self._make_corridor()
        all_targets = {"t1": {"id": "t1"}}
        result = attribute_corridor(c, all_targets)
        with pytest.raises((AttributeError, TypeError)):
            result.confidence = 0.1  # type: ignore[misc]

    def test_empty_all_targets(self):
        c = self._make_corridor(target_ids=("t1",))
        result = attribute_corridor(c, {})
        assert result.target_ids == ()

    def test_corridor_id_preserved(self):
        c = self._make_corridor()
        all_targets = {"t1": {"id": "t1"}}
        result = attribute_corridor(c, all_targets)
        assert result.corridor_id == "COR-001"
