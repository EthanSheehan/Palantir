"""
Tests for Hungarian algorithm swarm assignment upgrade (W3-004).

TDD RED phase — tests written BEFORE implementation.
Tests the optimal assignment, drone loss promotion, and Byzantine detection.
"""

import time

from sensor_fusion import SensorContribution
from swarm_coordinator import SwarmCoordinator, SwarmTask

# ---------------------------------------------------------------------------
# Stub classes (same as test_swarm_coordinator.py)
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
# TestHungarianAssignment
# ---------------------------------------------------------------------------


class TestHungarianAssignment:
    """Tests for optimal assignment via Hungarian algorithm."""

    def test_optimal_assignment_3x3(self):
        """3 UAVs, 3 targets — verify assignments minimize total distance.
        Each target already has SAR+SIGINT, only missing EO_IR."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        # Pre-cover SAR and SIGINT so only EO_IR gap remains per target
        covered = [
            make_contrib(uav_id=90, sensor_type="SAR"),
            make_contrib(uav_id=91, sensor_type="SIGINT"),
        ]
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3, sensor_contributions=list(covered))
        t2 = StubTarget(id=2, x=10.0, y=0.0, type="SAM", fused_confidence=0.3, sensor_contributions=list(covered))
        t3 = StubTarget(id=3, x=5.0, y=10.0, type="SAM", fused_confidence=0.3, sensor_contributions=list(covered))

        u1 = StubUAV(id=1, x=0.1, y=0.1, sensors=["EO_IR"])
        u2 = StubUAV(id=2, x=9.9, y=0.1, sensors=["EO_IR"])
        u3 = StubUAV(id=3, x=5.1, y=9.9, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([t1, t2, t3], [u1, u2, u3])

        assert len(orders) == 3
        assignment = {o.target_id: o.uav_id for o in orders}
        # Optimal: u1→t1, u2→t2, u3→t3 (each UAV closest to its target)
        assert assignment[1] == 1
        assert assignment[2] == 2
        assert assignment[3] == 3

    def test_more_uavs_than_targets(self):
        """5 UAVs, 2 targets — only 2 UAVs assigned, 3 remain idle."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)
        t2 = StubTarget(id=2, x=10.0, y=0.0, type="SAM", fused_confidence=0.3)

        uavs = [StubUAV(id=i, x=i * 2.0, y=0.0, sensors=["EO_IR"]) for i in range(1, 6)]

        orders = coordinator.evaluate_and_assign([t1, t2], uavs)

        assigned_uav_ids = {o.uav_id for o in orders}
        # Should assign exactly one UAV per target's EO_IR gap
        assert len(orders) == 2
        assert len(assigned_uav_ids) == 2

    def test_more_targets_than_uavs(self):
        """1 UAV, 3 targets — highest priority target gets the UAV."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        # SAM has weight 1.0, TRUCK 0.5, LOGISTICS 0.3
        t_sam = StubTarget(id=1, x=5.0, y=5.0, type="SAM", fused_confidence=0.3)
        t_truck = StubTarget(id=2, x=5.0, y=5.0, type="TRUCK", fused_confidence=0.3)
        t_log = StubTarget(id=3, x=5.0, y=5.0, type="LOGISTICS", fused_confidence=0.3)

        u1 = StubUAV(id=1, x=5.1, y=5.1, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([t_truck, t_log, t_sam], [u1])

        assert len(orders) == 1
        # SAM has highest priority score, should be assigned
        assert orders[0].target_id == t_sam.id

    def test_empty_uav_list(self):
        """No UAVs available — returns empty orders."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)

        orders = coordinator.evaluate_and_assign([t1], [])

        assert orders == []

    def test_empty_target_list(self):
        """No targets — returns empty orders."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        u1 = StubUAV(id=1, x=0.0, y=0.0, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([], [u1])

        assert orders == []

    def test_single_uav_single_target(self):
        """1 UAV, 1 target — straightforward assignment."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=10.0, y=10.0, type="SAM", fused_confidence=0.3)
        u1 = StubUAV(id=1, x=10.1, y=10.1, sensors=["EO_IR"])

        orders = coordinator.evaluate_and_assign([t1], [u1])

        assert len(orders) == 1
        assert orders[0].uav_id == 1
        assert orders[0].target_id == 1

    def test_priority_scoring_unchanged(self):
        """Priority scoring formula (threat_weight * (1 - confidence)) still works."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        # SAM weight=1.0, conf=0.3 → score=0.7
        # TEL weight=0.9, conf=0.1 → score=0.81
        t_sam = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)
        t_tel = StubTarget(id=2, x=0.0, y=0.0, type="TEL", fused_confidence=0.1)

        u1 = StubUAV(id=1, x=0.1, y=0.1, sensors=["EO_IR"])

        # TEL has higher score (0.81 > 0.7), should be assigned first
        orders = coordinator.evaluate_and_assign([t_sam, t_tel], [u1])

        assert len(orders) == 1
        assert orders[0].target_id == t_tel.id

    def test_task_expiry_still_works(self):
        """Tasks older than 120s are expired and UAVs released."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)
        u1 = StubUAV(id=1, x=0.1, y=0.1, sensors=["EO_IR"])
        u2 = StubUAV(id=2, x=0.2, y=0.2, sensors=["EO_IR"])

        # First assignment
        coordinator.evaluate_and_assign([t1], [u1, u2])
        assert 1 in coordinator.get_active_tasks()

        # Manually backdate the task
        old_task = coordinator._active_tasks[1]
        coordinator._active_tasks[1] = SwarmTask(
            target_id=old_task.target_id,
            assigned_uav_ids=old_task.assigned_uav_ids,
            sensor_coverage=old_task.sensor_coverage,
            created_at=time.time() - 130,
        )

        # Next call should expire the task
        coordinator.evaluate_and_assign([t1], [u1, u2])
        # Task was expired and then re-created (target still has gap)
        tasks = coordinator.get_active_tasks()
        if 1 in tasks:
            # Re-created task should have recent timestamp
            assert time.time() - tasks[1].created_at < 5


class TestDroneLossPromotion:
    """Tests for automatic task re-queuing when a UAV is lost."""

    def test_lost_uav_task_reprioritized(self):
        """When a UAV on a task disappears from the UAV list,
        the task should be re-queued with elevated priority."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)
        u1 = StubUAV(id=1, x=0.1, y=0.1, sensors=["EO_IR"])
        u2 = StubUAV(id=2, x=0.2, y=0.2, sensors=["EO_IR"])
        u3 = StubUAV(id=3, x=0.3, y=0.3, sensors=["EO_IR"])

        # Initial assignment — u1 gets the task
        orders = coordinator.evaluate_and_assign([t1], [u1, u2, u3])
        assert len(orders) >= 1

        # Now u1 is lost (not in UAV list) — only u2, u3 remain
        orders2 = coordinator.evaluate_and_assign([t1], [u2, u3])

        # The lost UAV's task should be reassigned
        active = coordinator.get_active_tasks()
        if 1 in active:
            assert u1.id not in active[1].assigned_uav_ids


class TestByzantineDetection:
    """Tests for Byzantine position anomaly detection."""

    def test_teleporting_uav_flagged(self):
        """A UAV whose position jumps >50km in one tick is skipped."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)

        # Normal UAV
        u_normal = StubUAV(id=2, x=0.1, y=0.1, sensors=["EO_IR"])
        # Teleporting UAV — position will be flagged as anomalous
        u_teleport = StubUAV(id=1, x=0.05, y=0.05, sensors=["EO_IR"])

        # First tick: record positions
        coordinator.evaluate_and_assign([t1], [u_normal, u_teleport])

        # Second tick: u_teleport jumps >50km (0.5 degrees ≈ 55km)
        u_teleport_moved = StubUAV(id=1, x=10.0, y=10.0, sensors=["EO_IR"])
        t2 = StubTarget(id=2, x=0.0, y=0.0, type="TEL", fused_confidence=0.3)

        orders = coordinator.evaluate_and_assign([t2], [u_normal, u_teleport_moved])

        # Teleporting UAV should NOT be assigned
        assigned_ids = {o.uav_id for o in orders}
        assert u_teleport_moved.id not in assigned_ids

    def test_normal_movement_not_flagged(self):
        """A UAV moving at normal speed is NOT flagged."""
        coordinator = SwarmCoordinator(min_idle_count=0)
        t1 = StubTarget(id=1, x=0.0, y=0.0, type="SAM", fused_confidence=0.3)
        u1 = StubUAV(id=1, x=0.0, y=0.0, sensors=["EO_IR"])
        u2 = StubUAV(id=2, x=1.0, y=1.0, sensors=["EO_IR"])

        # First tick
        coordinator.evaluate_and_assign([t1], [u1, u2])

        # Second tick — small movement (normal)
        u1_moved = StubUAV(id=1, x=0.01, y=0.01, sensors=["EO_IR"])
        t2 = StubTarget(id=2, x=0.0, y=0.0, type="TEL", fused_confidence=0.3)

        orders = coordinator.evaluate_and_assign([t2], [u1_moved, u2])

        # Normal UAV should be assignable
        assigned_ids = {o.uav_id for o in orders}
        assert 1 in assigned_ids or 2 in assigned_ids
