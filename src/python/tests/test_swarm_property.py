"""
Property-based tests for SwarmCoordinator.evaluate_and_assign().

Invariants tested:
1. No drone is assigned to two different targets in the same call.
2. Number of assignments <= number of available (IDLE/SEARCH) drones.
3. All assigned UAV IDs exist in the input drone list.
4. All assigned target IDs exist in the input target list.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings
from hypothesis import strategies as st
from types import SimpleNamespace

from swarm_coordinator import SwarmCoordinator, SENSOR_TYPES


# ---------------------------------------------------------------------------
# Strategies to build mock UAV and Target objects
# ---------------------------------------------------------------------------

UAV_MODES = ["IDLE", "SEARCH", "FOLLOW", "PAINT", "SUPPORT"]
TARGET_STATES = ["DETECTED", "CLASSIFIED", "VERIFIED", "NOMINATED"]
TARGET_TYPES = ["SAM", "TEL", "TRUCK", "MANPADS", "RADAR", "CP", "LOGISTICS"]


def make_uav(uav_id, mode, x, y, sensors):
    return SimpleNamespace(
        id=uav_id,
        mode=mode,
        x=x,
        y=y,
        sensors=sensors,
        tracked_target_ids=[],
    )


def make_target(target_id, state, ttype, x, y, sensor_contribs):
    return SimpleNamespace(
        id=target_id,
        state=state,
        type=ttype,
        x=x,
        y=y,
        fused_confidence=0.3,
        sensor_contributions=sensor_contribs,
    )


# Strategy for a single UAV
uav_strategy = st.fixed_dictionaries({
    "mode": st.sampled_from(UAV_MODES),
    "x": st.floats(-100.0, 100.0, allow_nan=False),
    "y": st.floats(-100.0, 100.0, allow_nan=False),
    "sensors": st.lists(
        st.sampled_from(list(SENSOR_TYPES)), min_size=0, max_size=3, unique=True
    ),
})

# Strategy for a single target
target_strategy = st.fixed_dictionaries({
    "state": st.sampled_from(TARGET_STATES),
    "type": st.sampled_from(TARGET_TYPES),
    "x": st.floats(-100.0, 100.0, allow_nan=False),
    "y": st.floats(-100.0, 100.0, allow_nan=False),
})


def build_uavs(uav_dicts):
    """Assign unique IDs and build UAV objects."""
    return [
        make_uav(i, d["mode"], d["x"], d["y"], d["sensors"])
        for i, d in enumerate(uav_dicts)
    ]


def build_targets(target_dicts):
    """Assign unique IDs and build target objects with no sensor contributions."""
    return [
        make_target(100 + i, d["state"], d["type"], d["x"], d["y"], [])
        for i, d in enumerate(target_dicts)
    ]


@given(
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=10),
    target_dicts=st.lists(target_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_no_dual_assignment(uav_dicts, target_dicts):
    """No drone is assigned to more than one target in the same call."""
    coord = SwarmCoordinator(min_idle_count=1)
    uavs = build_uavs(uav_dicts)
    targets = build_targets(target_dicts)

    orders = coord.evaluate_and_assign(targets, uavs)

    assigned_uav_ids = [o.uav_id for o in orders]
    assert len(assigned_uav_ids) == len(set(assigned_uav_ids)), (
        f"Dual assignment detected: {assigned_uav_ids}"
    )


@given(
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=10),
    target_dicts=st.lists(target_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_assignment_count_respects_available_drones(uav_dicts, target_dicts):
    """Number of assignments never exceeds number of assignable drones."""
    coord = SwarmCoordinator(min_idle_count=0)
    uavs = build_uavs(uav_dicts)
    targets = build_targets(target_dicts)

    assignable_count = sum(1 for u in uavs if u.mode in ("IDLE", "SEARCH"))
    orders = coord.evaluate_and_assign(targets, uavs)

    assert len(orders) <= assignable_count, (
        f"Assigned {len(orders)} drones but only {assignable_count} are assignable"
    )


@given(
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=10),
    target_dicts=st.lists(target_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_assigned_uav_ids_exist_in_input(uav_dicts, target_dicts):
    """All UAV IDs in orders must exist in the input UAV list."""
    coord = SwarmCoordinator(min_idle_count=0)
    uavs = build_uavs(uav_dicts)
    targets = build_targets(target_dicts)

    orders = coord.evaluate_and_assign(targets, uavs)

    valid_uav_ids = {u.id for u in uavs}
    for order in orders:
        assert order.uav_id in valid_uav_ids, (
            f"Order references non-existent UAV id {order.uav_id}"
        )


@given(
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=10),
    target_dicts=st.lists(target_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_assigned_target_ids_exist_in_input(uav_dicts, target_dicts):
    """All target IDs in orders must exist in the input target list."""
    coord = SwarmCoordinator(min_idle_count=0)
    uavs = build_uavs(uav_dicts)
    targets = build_targets(target_dicts)

    orders = coord.evaluate_and_assign(targets, uavs)

    valid_target_ids = {t.id for t in targets}
    for order in orders:
        assert order.target_id in valid_target_ids, (
            f"Order references non-existent target id {order.target_id}"
        )


@given(
    uav_dicts=st.lists(uav_strategy, min_size=3, max_size=10),
    target_dicts=st.lists(target_strategy, min_size=1, max_size=5),
)
@settings(max_examples=200)
def test_force_flag_still_no_dual_assignment(uav_dicts, target_dicts):
    """No dual assignment even when force=True (operator override path)."""
    coord = SwarmCoordinator(min_idle_count=0)
    uavs = build_uavs(uav_dicts)
    targets = build_targets(target_dicts)

    orders = coord.evaluate_and_assign(targets, uavs, force=True)

    assigned_uav_ids = [o.uav_id for o in orders]
    assert len(assigned_uav_ids) == len(set(assigned_uav_ids)), (
        f"Dual assignment on force=True: {assigned_uav_ids}"
    )
