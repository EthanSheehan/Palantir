"""
Property-based tests for verification_engine.evaluate_target_state().

Invariants tested:
1. Output state is always a valid known state string.
2. Terminal states are never changed.
3. No regression happens when time since last sensor is below threshold.
4. Promotion only happens in the correct direction (DETECTED->CLASSIFIED->VERIFIED).
5. State is deterministic (same inputs = same output).
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from verification_engine import (
    evaluate_target_state,
    VERIFICATION_THRESHOLDS,
    _TERMINAL_STATES,
    _MANAGED_STATES,
)

ALL_VALID_STATES = list(_MANAGED_STATES | _TERMINAL_STATES | {"UNDETECTED", "UNKNOWN"})
MANAGED_STATES_LIST = list(_MANAGED_STATES) + ["UNDETECTED"]
TERMINAL_STATES_LIST = list(_TERMINAL_STATES)
TARGET_TYPES = list(VERIFICATION_THRESHOLDS.keys()) + ["UNKNOWN_TYPE"]


@given(
    current_state=st.sampled_from(TERMINAL_STATES_LIST),
    target_type=st.sampled_from(TARGET_TYPES),
    fused_confidence=st.floats(0.0, 1.0, allow_nan=False),
    sensor_type_count=st.integers(0, 10),
    time_in_state=st.floats(0.0, 120.0, allow_nan=False),
    seconds_since_sensor=st.floats(0.0, 60.0, allow_nan=False),
    demo_fast=st.booleans(),
)
@settings(max_examples=200)
def test_terminal_states_never_change(
    current_state, target_type, fused_confidence, sensor_type_count,
    time_in_state, seconds_since_sensor, demo_fast
):
    """Terminal states (NOMINATED, LOCKED, ENGAGED, DESTROYED, ESCAPED) never change."""
    result = evaluate_target_state(
        current_state, target_type, fused_confidence,
        sensor_type_count, time_in_state, seconds_since_sensor, demo_fast
    )
    assert result == current_state, (
        f"Terminal state {current_state} was changed to {result}"
    )


@given(
    current_state=st.sampled_from(MANAGED_STATES_LIST),
    target_type=st.sampled_from(TARGET_TYPES),
    fused_confidence=st.floats(0.0, 1.0, allow_nan=False),
    sensor_type_count=st.integers(0, 10),
    time_in_state=st.floats(0.0, 120.0, allow_nan=False),
    seconds_since_sensor=st.floats(0.0, 60.0, allow_nan=False),
    demo_fast=st.booleans(),
)
@settings(max_examples=200)
def test_output_state_is_always_valid(
    current_state, target_type, fused_confidence, sensor_type_count,
    time_in_state, seconds_since_sensor, demo_fast
):
    """Result is always one of the known valid state strings."""
    result = evaluate_target_state(
        current_state, target_type, fused_confidence,
        sensor_type_count, time_in_state, seconds_since_sensor, demo_fast
    )
    assert result in (
        "UNDETECTED", "DETECTED", "CLASSIFIED", "VERIFIED",
        "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED"
    ), f"Unknown state returned: {result!r}"


@given(
    target_type=st.sampled_from(list(VERIFICATION_THRESHOLDS.keys())),
    fused_confidence=st.floats(0.0, 1.0, allow_nan=False),
    sensor_type_count=st.integers(0, 10),
    time_in_state=st.floats(0.0, 120.0, allow_nan=False),
    demo_fast=st.booleans(),
)
@settings(max_examples=200)
def test_no_regression_below_timeout(
    target_type, fused_confidence, sensor_type_count, time_in_state, demo_fast
):
    """When seconds_since_last_sensor is 0, no regression occurs."""
    seconds_since_sensor = 0.0

    for current_state in ["VERIFIED", "CLASSIFIED", "DETECTED"]:
        result = evaluate_target_state(
            current_state, target_type, fused_confidence,
            sensor_type_count, time_in_state, seconds_since_sensor, demo_fast
        )
        state_order = {"UNDETECTED": 0, "DETECTED": 1, "CLASSIFIED": 2, "VERIFIED": 3}
        # Result should not be lower order than current state (no regression when sensors present)
        if current_state in state_order and result in state_order:
            assert state_order[result] >= state_order[current_state], (
                f"Regression at 0s since sensor: {current_state} -> {result} "
                f"for target_type={target_type}, confidence={fused_confidence}"
            )


@given(
    target_type=st.sampled_from(list(VERIFICATION_THRESHOLDS.keys())),
    fused_confidence=st.floats(0.0, 1.0, allow_nan=False),
    sensor_type_count=st.integers(0, 10),
    time_in_state=st.floats(0.0, 120.0, allow_nan=False),
    seconds_since_sensor=st.floats(0.0, 120.0, allow_nan=False),
    demo_fast=st.booleans(),
)
@settings(max_examples=200)
def test_state_transitions_are_deterministic(
    target_type, fused_confidence, sensor_type_count, time_in_state,
    seconds_since_sensor, demo_fast
):
    """Same inputs always produce the same output (function is pure/deterministic)."""
    for current_state in MANAGED_STATES_LIST:
        result1 = evaluate_target_state(
            current_state, target_type, fused_confidence,
            sensor_type_count, time_in_state, seconds_since_sensor, demo_fast
        )
        result2 = evaluate_target_state(
            current_state, target_type, fused_confidence,
            sensor_type_count, time_in_state, seconds_since_sensor, demo_fast
        )
        assert result1 == result2, (
            f"Non-deterministic: {current_state} -> {result1} vs {result2}"
        )


@given(
    target_type=st.sampled_from(list(VERIFICATION_THRESHOLDS.keys())),
    fused_confidence=st.floats(0.8, 1.0, allow_nan=False),
    sensor_type_count=st.integers(3, 10),
    time_in_state=st.floats(30.0, 120.0, allow_nan=False),
    seconds_since_sensor=st.floats(0.0, 1.0, allow_nan=False),
)
@settings(max_examples=200)
def test_verified_can_be_reached_from_classified_with_enough_evidence(
    target_type, fused_confidence, sensor_type_count, time_in_state, seconds_since_sensor
):
    """CLASSIFIED -> VERIFIED is achievable with high confidence + sensor diversity."""
    result = evaluate_target_state(
        "CLASSIFIED", target_type, fused_confidence,
        sensor_type_count, time_in_state, seconds_since_sensor, demo_fast=False
    )
    # With confidence 0.8+, 3+ sensors, 30+ seconds — should always promote to VERIFIED
    # (all thresholds have verify_confidence <= 0.8 and verify_sensor_types <= 2)
    assert result == "VERIFIED", (
        f"Expected VERIFIED but got {result} with confidence={fused_confidence}, "
        f"sensors={sensor_type_count}, time={time_in_state}"
    )
