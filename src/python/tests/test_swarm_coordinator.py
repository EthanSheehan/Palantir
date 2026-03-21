"""
Tests for swarm_coordinator.py — written FIRST (TDD RED phase).

All tests must fail before swarm_coordinator.py exists, then pass after implementation.
Uses lightweight stub classes for Target and UAV — does NOT import sim_engine.
"""

from dataclasses import FrozenInstanceError

import pytest
from sensor_fusion import SensorContribution
from swarm_coordinator import SENSOR_TYPES, SwarmCoordinator, SwarmTask, TaskingOrder

# ---------------------------------------------------------------------------
# Stub classes — pure test helpers, no sim_engine dependency
# ---------------------------------------------------------------------------


class StubUAV:
    def __init__(self, id, x, y, mode="IDLE", sensors=None, tracked_target_ids=None):
        self.id = id
        self.x = x  # lon
        self.y = y  # lat
        self.mode = mode
        self.sensors = sensors or ["EO_IR"]
        self.tracked_target_ids = tracked_target_ids or []


class StubTarget:
    def __init__(self, id, x, y, type="SAM", state="DETECTED", fused_confidence=0.3, sensor_contributions=None):
        self.id = id
        self.x = x  # lon
        self.y = y  # lat
        self.type = type
        self.state = state
        self.fused_confidence = fused_confidence
        self.sensor_contributions = sensor_contributions or []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_contrib(uav_id: int, sensor_type: str, confidence: float = 0.5) -> SensorContribution:
    return SensorContribution(
        uav_id=uav_id,
        sensor_type=sensor_type,
        confidence=confidence,
        range_m=5000.0,
        bearing_deg=45.0,
        timestamp=0.0,
    )


# ---------------------------------------------------------------------------
# TestSwarmCoordinator
# ---------------------------------------------------------------------------


class TestSwarmCoordinator:
    def test_assigns_nearest_matching_uav(self):
        """Given 2 IDLE UAVs with EO_IR (one near, one far) and a DETECTED target
        missing EO_IR, coordinator returns TaskingOrder for the nearer UAV."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        # Target at (10.0, 10.0)
        target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        # Near UAV at (10.01, 10.01) — distance ~0.014
        uav_near = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
        # Far UAV at (10.5, 10.5) — distance ~0.707
        uav_far = StubUAV(id=2, x=10.5, y=10.5, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([target], [uav_near, uav_far])

        assert len(orders) >= 1
        assert orders[0].uav_id == uav_near.id

    def test_idle_guard_respected(self):
        """Given min_idle_count=2 and exactly 2 IDLE UAVs, coordinator returns
        no orders (would violate guard)."""
        coordinator = SwarmCoordinator(min_idle_count=2)
        target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        uav1 = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
        uav2 = StubUAV(id=2, x=10.02, y=10.02, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([target], [uav1, uav2])

        assert len(orders) == 0

    def test_no_assignment_when_fully_covered(self):
        """Given a target with EO_IR+SAR+SIGINT all contributing, coordinator
        returns no orders for that target."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        contribs = [
            make_contrib(uav_id=10, sensor_type="EO_IR"),
            make_contrib(uav_id=11, sensor_type="SAR"),
            make_contrib(uav_id=12, sensor_type="SIGINT"),
        ]
        target = StubTarget(
            id=1,
            x=10.0,
            y=10.0,
            type="SAM",
            fused_confidence=0.9,
            sensor_contributions=contribs,
        )
        uav = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR", "SAR", "SIGINT"])

        orders = coordinator.evaluate_and_assign([target], [uav])

        # No sensor gap — no orders
        assert len(orders) == 0

    def test_no_duplicate_sensor(self):
        """Given a target already covered by EO_IR, coordinator does not assign
        another EO_IR UAV even if one is available."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        contribs = [make_contrib(uav_id=99, sensor_type="EO_IR")]
        target = StubTarget(
            id=1,
            x=10.0,
            y=10.0,
            type="SAM",
            fused_confidence=0.3,
            sensor_contributions=contribs,
        )
        # Only EO_IR UAVs available — cannot cover SAR or SIGINT gaps
        uav1 = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
        uav2 = StubUAV(id=2, x=10.02, y=10.02, sensors=["EO_IR"])
        uav3 = StubUAV(id=3, x=10.03, y=10.03, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([target], [uav1, uav2, uav3])

        # EO_IR already covered; no UAV has SAR or SIGINT
        assert len(orders) == 0

    def test_priority_scoring(self):
        """Given two targets (SAM at 0.3 confidence, TRUCK at 0.3 confidence),
        SAM target gets assigned first (higher threat weight)."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        sam_target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        truck_target = StubTarget(id=2, x=10.0, y=10.0, type="TRUCK", fused_confidence=0.3)

        uav1 = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
        uav2 = StubUAV(id=2, x=10.02, y=10.02, sensors=["EO_IR"])
        uav3 = StubUAV(id=3, x=10.03, y=10.03, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([truck_target, sam_target], [uav1, uav2, uav3])

        # First order should be for the SAM target
        assert len(orders) >= 1
        assert orders[0].target_id == sam_target.id

    def test_skips_rtb_repositioning(self):
        """UAVs in RTB or REPOSITIONING mode are never assigned."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        uav_rtb = StubUAV(id=1, x=10.01, y=10.01, mode="RTB", sensors=["EO_IR"])
        uav_repo = StubUAV(id=2, x=10.02, y=10.02, mode="REPOSITIONING", sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([target], [uav_rtb, uav_repo])

        assert len(orders) == 0

    def test_multiple_gap_types(self):
        """Target missing both SAR and SIGINT gets two separate TaskingOrders
        if UAVs with those sensors are available."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        # Target already has EO_IR — missing SAR and SIGINT
        contribs = [make_contrib(uav_id=99, sensor_type="EO_IR")]
        target = StubTarget(
            id=1,
            x=10.0,
            y=10.0,
            type="SAM",
            fused_confidence=0.3,
            sensor_contributions=contribs,
        )
        uav_sar = StubUAV(id=1, x=10.01, y=10.01, sensors=["SAR"])
        uav_sigint = StubUAV(id=2, x=10.02, y=10.02, sensors=["SIGINT"])
        # Extra IDLE UAVs so idle guard is satisfied
        uav_idle1 = StubUAV(id=3, x=10.03, y=10.03, sensors=["EO_IR"])
        uav_idle2 = StubUAV(id=4, x=10.04, y=10.04, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign(
            [target],
            [uav_sar, uav_sigint, uav_idle1, uav_idle2],
        )

        assert len(orders) == 2
        # Both sensor gaps covered
        assigned_types = {o.reason for o in orders}
        assert len(assigned_types) == 2
        target_ids = {o.target_id for o in orders}
        assert target_ids == {target.id}

    def test_active_tasks_tracking(self):
        """After evaluate_and_assign produces orders, get_active_tasks returns
        corresponding SwarmTask entries."""
        coordinator = SwarmCoordinator(min_idle_count=1)
        target = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        uav = StubUAV(id=1, x=10.01, y=10.01, sensors=["EO_IR"])
        uav_idle = StubUAV(id=2, x=10.02, y=10.02, sensors=["SAR"])

        orders = coordinator.evaluate_and_assign([target], [uav, uav_idle])

        assert len(orders) >= 1
        tasks = coordinator.get_active_tasks()
        assert target.id in tasks


# ---------------------------------------------------------------------------
# TestImmutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_swarm_task_is_frozen(self):
        """SwarmTask must be a frozen dataclass (immutable)."""
        task = SwarmTask(
            target_id=1,
            assigned_uav_ids=(1, 2),
            sensor_coverage=("EO_IR",),
        )
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            task.target_id = 99  # type: ignore[misc]

    def test_tasking_order_is_frozen(self):
        """TaskingOrder must be a frozen dataclass (immutable)."""
        order = TaskingOrder(
            uav_id=1,
            target_id=1,
            mode="SUPPORT",
            reason="EO_IR",
            priority=1,
        )
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            order.uav_id = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_sensor_types_constant(self):
        """SENSOR_TYPES must contain EO_IR, SAR, SIGINT."""
        assert "EO_IR" in SENSOR_TYPES
        assert "SAR" in SENSOR_TYPES
        assert "SIGINT" in SENSOR_TYPES
        assert len(SENSOR_TYPES) == 3


# ---------------------------------------------------------------------------
# Integration tests (use real SimulationModel)
# ---------------------------------------------------------------------------


def test_request_release_swarm():
    """Integration: request_swarm force-assigns, release_swarm cancels."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from sim_engine import SimulationModel

    sim = SimulationModel()
    # Tick once to settle initial state
    sim.tick()
    detected = [t for t in sim.targets.values() if t.state != "UNDETECTED"]
    if not detected:
        # Force-detect first target for test
        first_target = next(iter(sim.targets.values()))
        first_target.state = "DETECTED"
        first_target.fused_confidence = 0.3
        detected = [first_target]
    target = detected[0]
    # Request swarm
    sim.request_swarm(target.id)
    # Release swarm
    sim.release_swarm(target.id)
    released = [u for u in sim.uavs.values() if u.mode == "SUPPORT" and target.id in u.tracked_target_ids]
    assert len(released) == 0


def test_swarm_state_in_broadcast():
    """Integration: swarm_tasks key exists in get_state() output."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from sim_engine import SimulationModel

    sim = SimulationModel()
    state = sim.get_state()
    assert "swarm_tasks" in state
    assert isinstance(state["swarm_tasks"], list)
    # Each task should have required keys (if any tasks exist)
    for task in state["swarm_tasks"]:
        assert "target_id" in task
        assert "assigned_uav_ids" in task
        assert "sensor_coverage" in task
        assert "formation_type" in task
