"""
Tests for swarm coordinator autonomy awareness (W2-006).

Verifies that evaluate_and_assign respects the autonomy_level parameter:
- AUTONOMOUS: assignments execute immediately (current behavior, default)
- SUPERVISED: returns SwarmRecommendation objects (no direct assignment)
- MANUAL: returns SwarmRecommendation objects (no direct assignment)

Uses lightweight stub classes — no sim_engine dependency.
"""

import pytest
from swarm_coordinator import (
    SwarmCoordinator,
    SwarmRecommendation,
    TaskingOrder,
)

# ---------------------------------------------------------------------------
# Stub classes
# ---------------------------------------------------------------------------


class StubUAV:
    def __init__(self, id, x, y, mode="IDLE", sensors=None, tracked_target_ids=None):
        self.id = id
        self.x = x
        self.y = y
        self.mode = mode
        self.sensors = sensors or ["EO_IR"]
        self.tracked_target_ids = tracked_target_ids or []


class StubTarget:
    def __init__(self, id, x, y, type="SAM", state="DETECTED", fused_confidence=0.3, sensor_contributions=None):
        self.id = id
        self.x = x
        self.y = y
        self.type = type
        self.state = state
        self.fused_confidence = fused_confidence
        self.sensor_contributions = sensor_contributions or []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup():
    """Return a coordinator, target with sensor gap, and enough UAVs."""
    coordinator = SwarmCoordinator(min_idle_count=1)
    target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
    uav1 = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
    uav2 = StubUAV(id=2, x=10.02, y=10.02, sensors=["SAR"])
    # Extra idle UAV to satisfy min_idle_count
    uav3 = StubUAV(id=3, x=10.03, y=10.03, sensors=["EO_IR"])
    return coordinator, target, [uav1, uav2, uav3]


# ---------------------------------------------------------------------------
# AUTONOMOUS mode (default, backward compatible)
# ---------------------------------------------------------------------------


class TestAutonomousMode:
    def test_default_returns_tasking_orders(self):
        """Default (no autonomy_level) returns TaskingOrder list — backward compatible."""
        coordinator, target, uavs = _setup()
        orders = coordinator.evaluate_and_assign([target], uavs)
        assert len(orders) >= 1
        assert all(isinstance(o, TaskingOrder) for o in orders)

    def test_explicit_autonomous_returns_tasking_orders(self):
        """Explicit AUTONOMOUS returns TaskingOrder list."""
        coordinator, target, uavs = _setup()
        orders = coordinator.evaluate_and_assign([target], uavs, autonomy_level="AUTONOMOUS")
        assert len(orders) >= 1
        assert all(isinstance(o, TaskingOrder) for o in orders)

    def test_autonomous_updates_active_tasks(self):
        """AUTONOMOUS mode updates internal _active_tasks tracking."""
        coordinator, target, uavs = _setup()
        coordinator.evaluate_and_assign([target], uavs, autonomy_level="AUTONOMOUS")
        tasks = coordinator.get_active_tasks()
        assert target.id in tasks


# ---------------------------------------------------------------------------
# MANUAL mode — recommendations only, no execution
# ---------------------------------------------------------------------------


class TestManualMode:
    def test_manual_returns_recommendations(self):
        """MANUAL mode returns SwarmRecommendation list, not TaskingOrders."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL")
        assert len(result) >= 1
        assert all(isinstance(r, SwarmRecommendation) for r in result)

    def test_manual_does_not_update_active_tasks(self):
        """MANUAL mode does NOT update _active_tasks (no auto-assign)."""
        coordinator, target, uavs = _setup()
        coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL")
        tasks = coordinator.get_active_tasks()
        assert len(tasks) == 0

    def test_manual_recommendation_has_correct_fields(self):
        """SwarmRecommendation contains uav_id, target_id, mode, reason, priority."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL")
        rec = result[0]
        assert rec.uav_id > 0
        assert rec.target_id == target.id
        assert rec.mode == "SUPPORT"
        assert rec.reason in ("EO_IR", "SAR", "SIGINT")
        assert rec.priority >= 1

    def test_manual_recommendation_is_frozen(self):
        """SwarmRecommendation must be immutable."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL")
        rec = result[0]
        with pytest.raises((AttributeError, TypeError)):
            rec.uav_id = 999


# ---------------------------------------------------------------------------
# SUPERVISED mode — recommendations surfaced (like MANUAL but distinct type)
# ---------------------------------------------------------------------------


class TestSupervisedMode:
    def test_supervised_returns_recommendations(self):
        """SUPERVISED mode returns SwarmRecommendation list."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="SUPERVISED")
        assert len(result) >= 1
        assert all(isinstance(r, SwarmRecommendation) for r in result)

    def test_supervised_does_not_update_active_tasks(self):
        """SUPERVISED mode does NOT auto-update _active_tasks."""
        coordinator, target, uavs = _setup()
        coordinator.evaluate_and_assign([target], uavs, autonomy_level="SUPERVISED")
        tasks = coordinator.get_active_tasks()
        assert len(tasks) == 0

    def test_supervised_recommendation_has_autonomy_context(self):
        """SUPERVISED recommendations carry autonomy_level='SUPERVISED'."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="SUPERVISED")
        rec = result[0]
        assert rec.autonomy_level == "SUPERVISED"

    def test_manual_recommendation_has_autonomy_context(self):
        """MANUAL recommendations carry autonomy_level='MANUAL'."""
        coordinator, target, uavs = _setup()
        result = coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL")
        rec = result[0]
        assert rec.autonomy_level == "MANUAL"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestAutonomyEdgeCases:
    def test_invalid_autonomy_level_raises(self):
        """Invalid autonomy_level raises ValueError."""
        coordinator, target, uavs = _setup()
        with pytest.raises(ValueError, match="autonomy_level"):
            coordinator.evaluate_and_assign([target], uavs, autonomy_level="INVALID")

    def test_force_flag_ignores_autonomy(self):
        """force=True always returns TaskingOrders regardless of autonomy_level."""
        coordinator, target, uavs = _setup()
        # Even with MANUAL, force=True should execute (operator override)
        orders = coordinator.evaluate_and_assign([target], uavs, autonomy_level="MANUAL", force=True)
        assert all(isinstance(o, TaskingOrder) for o in orders)

    def test_no_targets_returns_empty_for_all_levels(self):
        """Empty target list returns empty result for all autonomy levels."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        uavs = [StubUAV(id=1, x=10.0, y=10.0)]
        for level in ("MANUAL", "SUPERVISED", "AUTONOMOUS"):
            result = coordinator.evaluate_and_assign([], uavs, autonomy_level=level)
            assert result == []
