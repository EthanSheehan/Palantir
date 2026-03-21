"""
Property-based tests for isr_priority.build_isr_queue().

Invariants tested:
1. Output is sorted descending by urgency_score.
2. All urgency_scores are >= 0.
3. Output length is <= max_requirements.
4. DESTROYED, ESCAPED, UNDETECTED targets never appear in the queue.
5. verification_gap is always in [0, 1].
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from isr_priority import build_isr_queue, THREAT_WEIGHTS, _EXCLUDED_STATES

TARGET_TYPES = list(THREAT_WEIGHTS.keys()) + ["UNKNOWN_TYPE"]
ALL_STATES = [
    "UNDETECTED", "DETECTED", "CLASSIFIED", "VERIFIED",
    "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED"
]
ACTIVE_STATES = [s for s in ALL_STATES if s not in _EXCLUDED_STATES]
SENSOR_TYPES = ["EO_IR", "SAR", "SIGINT"]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

sensor_contrib_strategy = st.fixed_dictionaries({
    "sensor_type": st.sampled_from(SENSOR_TYPES),
    "confidence": st.floats(0.0, 1.0, allow_nan=False),
})

target_strategy = st.fixed_dictionaries({
    "state": st.sampled_from(ALL_STATES),
    "type": st.sampled_from(TARGET_TYPES),
    "fused_confidence": st.floats(0.0, 1.0, allow_nan=False),
    "time_in_state_sec": st.floats(0.0, 120.0, allow_nan=False),
    "lat": st.floats(-90.0, 90.0, allow_nan=False),
    "lon": st.floats(-180.0, 180.0, allow_nan=False),
    "sensor_contributions": st.lists(sensor_contrib_strategy, min_size=0, max_size=4),
})

uav_strategy = st.fixed_dictionaries({
    "mode": st.sampled_from(["IDLE", "SEARCH", "FOLLOW", "SUPPORT"]),
    "sensors": st.lists(st.sampled_from(SENSOR_TYPES), min_size=0, max_size=3, unique=True),
    "lat": st.floats(-90.0, 90.0, allow_nan=False),
    "lon": st.floats(-180.0, 180.0, allow_nan=False),
})


def build_targets(dicts):
    return [dict(d, id=i) for i, d in enumerate(dicts)]


def build_uavs(dicts):
    return [dict(d, id=i) for i, d in enumerate(dicts)]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

@given(
    target_dicts=st.lists(target_strategy, min_size=0, max_size=15),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
    max_req=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=200)
def test_isr_queue_sorted_descending(target_dicts, uav_dicts, max_req):
    """ISR queue is always sorted by urgency_score descending."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs, max_requirements=max_req)

    scores = [r.urgency_score for r in queue]
    assert scores == sorted(scores, reverse=True), (
        f"Queue not sorted descending: {scores}"
    )


@given(
    target_dicts=st.lists(target_strategy, min_size=0, max_size=15),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_isr_scores_always_non_negative(target_dicts, uav_dicts):
    """All urgency scores in the ISR queue are >= 0."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs)

    for req in queue:
        assert req.urgency_score >= 0.0, (
            f"Negative urgency_score {req.urgency_score} for target {req.target_id}"
        )


@given(
    target_dicts=st.lists(target_strategy, min_size=0, max_size=15),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
    max_req=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=200)
def test_isr_queue_length_capped(target_dicts, uav_dicts, max_req):
    """Output length never exceeds max_requirements."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs, max_requirements=max_req)

    assert len(queue) <= max_req, (
        f"Queue length {len(queue)} exceeds max_requirements={max_req}"
    )


@given(
    target_dicts=st.lists(target_strategy, min_size=0, max_size=15),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_excluded_states_not_in_queue(target_dicts, uav_dicts):
    """DESTROYED, ESCAPED, UNDETECTED targets never appear in the ISR queue."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs)

    excluded_ids = {t["id"] for t in targets if t["state"] in _EXCLUDED_STATES}
    for req in queue:
        assert req.target_id not in excluded_ids, (
            f"Target {req.target_id} with excluded state appeared in ISR queue"
        )


@given(
    target_dicts=st.lists(target_strategy, min_size=0, max_size=15),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_verification_gap_in_0_1(target_dicts, uav_dicts):
    """Verification gap (1 - fused_confidence) is always in [0, 1]."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs)

    for req in queue:
        assert 0.0 <= req.verification_gap <= 1.0, (
            f"verification_gap {req.verification_gap} out of [0, 1] "
            f"for target {req.target_id}"
        )


@given(
    target_dicts=st.lists(
        target_strategy.filter(lambda t: t["state"] not in _EXCLUDED_STATES),
        min_size=1, max_size=10
    ),
    uav_dicts=st.lists(uav_strategy, min_size=0, max_size=5),
)
@settings(max_examples=200)
def test_active_targets_may_appear_in_queue(target_dicts, uav_dicts):
    """Targets with active states are eligible for the ISR queue."""
    targets = build_targets(target_dicts)
    uavs = build_uavs(uav_dicts)

    queue = build_isr_queue(targets, uavs, max_requirements=100)

    # All returned IDs should map to active (non-excluded) targets
    active_ids = {t["id"] for t in targets if t["state"] not in _EXCLUDED_STATES}
    for req in queue:
        assert req.target_id in active_ids, (
            f"Non-active target {req.target_id} in queue"
        )
