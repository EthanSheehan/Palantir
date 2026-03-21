"""
Property-based tests for sensor_fusion.fuse_detections().

Invariants tested:
1. Fused confidence always in [0, 1].
2. Fusion is monotonic: adding a sensor never decreases confidence.
3. Empty contributions returns confidence 0.0.
4. Single contribution returns that contribution's confidence.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from sensor_fusion import SensorContribution, fuse_detections

SENSOR_TYPES = ["EO_IR", "SAR", "SIGINT", "OPTICAL", "RADAR"]

sensor_contribution_strategy = st.builds(
    SensorContribution,
    uav_id=st.integers(min_value=0, max_value=100),
    sensor_type=st.sampled_from(SENSOR_TYPES),
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    range_m=st.floats(min_value=0.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    bearing_deg=st.floats(min_value=0.0, max_value=360.0, allow_nan=False, allow_infinity=False),
    timestamp=st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
)


@given(st.lists(sensor_contribution_strategy, min_size=0, max_size=20))
@settings(max_examples=200)
def test_fusion_confidence_always_in_0_1(contributions):
    """Fused confidence is always within [0, 1] for any valid inputs."""
    result = fuse_detections(contributions)
    assert 0.0 <= result.fused_confidence <= 1.0, (
        f"Fused confidence {result.fused_confidence} out of [0, 1]"
    )


@given(
    st.lists(sensor_contribution_strategy, min_size=0, max_size=10),
    sensor_contribution_strategy,
)
@settings(max_examples=200)
def test_fusion_monotonic_with_more_sensors(base_contributions, extra):
    """Adding a sensor contribution never decreases fused confidence."""
    base_result = fuse_detections(base_contributions)
    extended_result = fuse_detections(base_contributions + [extra])
    # Confidence can only stay the same or increase when adding sensors
    # (because complementary fusion: 1 - prod(1-ci) is monotonically non-decreasing)
    assert extended_result.fused_confidence >= base_result.fused_confidence - 1e-9, (
        f"Monotonicity violated: base={base_result.fused_confidence}, "
        f"extended={extended_result.fused_confidence}"
    )


def test_fusion_empty_contributions_returns_zero():
    """Empty contributions must return fused_confidence == 0.0."""
    result = fuse_detections([])
    assert result.fused_confidence == 0.0
    assert result.sensor_count == 0
    assert result.sensor_types == ()
    assert result.contributing_uav_ids == ()


@given(sensor_contribution_strategy)
@settings(max_examples=200)
def test_fusion_single_contribution(contrib):
    """Single contribution fused_confidence matches that contribution's confidence."""
    result = fuse_detections([contrib])
    # With one sensor type: fused = 1 - (1 - max_in_type) = max_in_type = contrib.confidence
    assert abs(result.fused_confidence - contrib.confidence) < 1e-9, (
        f"Expected {contrib.confidence}, got {result.fused_confidence}"
    )


@given(st.lists(sensor_contribution_strategy, min_size=1, max_size=20))
@settings(max_examples=200)
def test_fusion_sensor_types_in_result(contributions):
    """All sensor types in result are from the input contributions."""
    result = fuse_detections(contributions)
    input_types = {c.sensor_type for c in contributions}
    for st_name in result.sensor_types:
        assert st_name in input_types, f"Unknown sensor type {st_name} in result"


@given(st.lists(sensor_contribution_strategy, min_size=1, max_size=20))
@settings(max_examples=200)
def test_fusion_uav_ids_subset_of_input(contributions):
    """Contributing UAV IDs in result are a subset of input UAV IDs."""
    result = fuse_detections(contributions)
    input_ids = {c.uav_id for c in contributions}
    for uid in result.contributing_uav_ids:
        assert uid in input_ids, f"UAV id {uid} not in input set"
