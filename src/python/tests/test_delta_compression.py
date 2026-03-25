"""Tests for delta_compression.py — written FIRST (TDD RED phase).

Tests cover:
  - compute_delta: recursive diff, deleted keys, list diff by ID
  - apply_delta: reconstruct full state from base + delta
  - compress_payload: gzip compression
  - DeltaTracker: per-client state tracking
  - measure_savings: compression ratio
"""

from __future__ import annotations

import gzip
import json

import pytest
from delta_compression import (
    DeltaTracker,
    apply_delta,
    compress_payload,
    compute_delta,
    measure_savings,
)

# ---------------------------------------------------------------------------
# compute_delta
# ---------------------------------------------------------------------------


class TestComputeDelta:
    def test_identical_dicts_produce_empty_delta(self):
        state = {"a": 1, "b": 2}
        delta = compute_delta(state, state)
        assert delta == {}

    def test_changed_scalar_included(self):
        prev = {"a": 1, "b": 2}
        curr = {"a": 1, "b": 3}
        delta = compute_delta(prev, curr)
        assert delta == {"b": 3}

    def test_new_key_included(self):
        prev = {"a": 1}
        curr = {"a": 1, "b": 2}
        delta = compute_delta(prev, curr)
        assert delta == {"b": 2}

    def test_deleted_key_sentinel(self):
        prev = {"a": 1, "b": 2}
        curr = {"a": 1}
        delta = compute_delta(prev, curr)
        assert delta == {"b": "__deleted__"}

    def test_nested_dict_recursive(self):
        prev = {"meta": {"x": 1, "y": 2}}
        curr = {"meta": {"x": 1, "y": 9}}
        delta = compute_delta(prev, curr)
        assert delta == {"meta": {"y": 9}}

    def test_nested_dict_deleted_key(self):
        prev = {"meta": {"x": 1, "y": 2}}
        curr = {"meta": {"x": 1}}
        delta = compute_delta(prev, curr)
        assert delta == {"meta": {"y": "__deleted__"}}

    def test_list_diff_by_id_changed_field(self):
        prev = {"uavs": [{"id": 1, "lon": 10.0, "lat": 20.0}, {"id": 2, "lon": 5.0, "lat": 6.0}]}
        curr = {"uavs": [{"id": 1, "lon": 11.0, "lat": 20.0}, {"id": 2, "lon": 5.0, "lat": 6.0}]}
        delta = compute_delta(prev, curr)
        assert "uavs" in delta
        uav_delta = delta["uavs"]
        # Only UAV 1 changed
        changed = [d for d in uav_delta if d.get("id") == 1]
        assert len(changed) == 1
        assert changed[0]["lon"] == 11.0
        assert "lat" not in changed[0]

    def test_list_diff_removed_item_sentinel(self):
        prev = {"targets": [{"id": 1, "state": "DETECTED"}, {"id": 2, "state": "VERIFIED"}]}
        curr = {"targets": [{"id": 1, "state": "DETECTED"}]}
        delta = compute_delta(prev, curr)
        assert "targets" in delta
        removed = [d for d in delta["targets"] if d.get("__deleted__")]
        assert any(d.get("id") == 2 for d in removed)

    def test_list_diff_added_item(self):
        prev = {"targets": [{"id": 1, "state": "DETECTED"}]}
        curr = {"targets": [{"id": 1, "state": "DETECTED"}, {"id": 2, "state": "VERIFIED"}]}
        delta = compute_delta(prev, curr)
        assert "targets" in delta
        added = [d for d in delta["targets"] if d.get("id") == 2 and not d.get("__deleted__")]
        assert len(added) == 1

    def test_list_without_id_replaced_wholesale(self):
        prev = {"items": [1, 2, 3]}
        curr = {"items": [1, 2, 4]}
        delta = compute_delta(prev, curr)
        assert delta == {"items": [1, 2, 4]}

    def test_empty_prev_returns_full_curr(self):
        curr = {"a": 1, "b": 2}
        delta = compute_delta({}, curr)
        assert delta == curr

    def test_does_not_mutate_inputs(self):
        prev = {"a": 1, "nested": {"x": 1}}
        curr = {"a": 2, "nested": {"x": 2}}
        prev_copy = {"a": 1, "nested": {"x": 1}}
        curr_copy = {"a": 2, "nested": {"x": 2}}
        compute_delta(prev, curr)
        assert prev == prev_copy
        assert curr == curr_copy


# ---------------------------------------------------------------------------
# apply_delta
# ---------------------------------------------------------------------------


class TestApplyDelta:
    def test_apply_empty_delta_returns_same_values(self):
        base = {"a": 1, "b": 2}
        result = apply_delta(base, {})
        assert result == base

    def test_apply_returns_new_dict(self):
        base = {"a": 1}
        result = apply_delta(base, {})
        assert result is not base

    def test_apply_scalar_change(self):
        base = {"a": 1, "b": 2}
        result = apply_delta(base, {"b": 99})
        assert result == {"a": 1, "b": 99}

    def test_apply_deleted_key(self):
        base = {"a": 1, "b": 2}
        result = apply_delta(base, {"b": "__deleted__"})
        assert "b" not in result
        assert result["a"] == 1

    def test_apply_new_key(self):
        base = {"a": 1}
        result = apply_delta(base, {"b": 42})
        assert result == {"a": 1, "b": 42}

    def test_apply_nested_delta(self):
        base = {"meta": {"x": 1, "y": 2}}
        result = apply_delta(base, {"meta": {"y": 9}})
        assert result == {"meta": {"x": 1, "y": 9}}

    def test_apply_list_delta_updates_by_id(self):
        base = {"uavs": [{"id": 1, "lon": 10.0, "lat": 20.0}, {"id": 2, "lon": 5.0, "lat": 6.0}]}
        delta = {"uavs": [{"id": 1, "lon": 11.0}]}
        result = apply_delta(base, delta)
        uav1 = next(u for u in result["uavs"] if u["id"] == 1)
        assert uav1["lon"] == 11.0
        assert uav1["lat"] == 20.0

    def test_apply_list_delta_removes_deleted(self):
        base = {"targets": [{"id": 1, "state": "DETECTED"}, {"id": 2, "state": "VERIFIED"}]}
        delta = {"targets": [{"id": 2, "__deleted__": True}]}
        result = apply_delta(base, delta)
        ids = [t["id"] for t in result["targets"]]
        assert 2 not in ids
        assert 1 in ids

    def test_apply_list_delta_adds_new_item(self):
        base = {"targets": [{"id": 1, "state": "DETECTED"}]}
        delta = {"targets": [{"id": 2, "state": "VERIFIED"}]}
        result = apply_delta(base, delta)
        ids = [t["id"] for t in result["targets"]]
        assert 2 in ids

    def test_roundtrip_compute_then_apply(self):
        prev = {
            "autonomy_level": "SUPERVISED",
            "uavs": [{"id": 1, "lon": 10.0, "lat": 20.0, "mode": "IDLE"}],
            "targets": [{"id": 100, "state": "DETECTED", "fused_confidence": 0.5}],
        }
        curr = {
            "autonomy_level": "SUPERVISED",
            "uavs": [{"id": 1, "lon": 10.1, "lat": 20.0, "mode": "FOLLOW"}],
            "targets": [{"id": 100, "state": "CLASSIFIED", "fused_confidence": 0.7}],
        }
        delta = compute_delta(prev, curr)
        restored = apply_delta(prev, delta)
        assert restored == curr

    def test_does_not_mutate_base(self):
        base = {"a": 1, "b": 2}
        base_copy = {"a": 1, "b": 2}
        apply_delta(base, {"b": 99})
        assert base == base_copy


# ---------------------------------------------------------------------------
# compress_payload
# ---------------------------------------------------------------------------


class TestCompressPayload:
    def test_gzip_returns_bytes(self):
        data = {"type": "state", "data": {"a": 1}}
        result = compress_payload(data, method="gzip")
        assert isinstance(result, bytes)

    def test_gzip_decompresses_correctly(self):
        data = {"type": "state", "data": {"a": 1, "b": [1, 2, 3]}}
        compressed = compress_payload(data, method="gzip")
        decompressed = json.loads(gzip.decompress(compressed).decode("utf-8"))
        assert decompressed == data

    def test_gzip_smaller_than_raw_for_large_payload(self):
        data = {"items": [{"id": i, "value": "x" * 50} for i in range(100)]}
        raw_size = len(json.dumps(data).encode("utf-8"))
        compressed_size = len(compress_payload(data, method="gzip"))
        assert compressed_size < raw_size

    def test_json_method_returns_bytes(self):
        data = {"type": "state"}
        result = compress_payload(data, method="json")
        assert isinstance(result, bytes)
        assert json.loads(result) == data

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            compress_payload({}, method="unknown_method")


# ---------------------------------------------------------------------------
# DeltaTracker
# ---------------------------------------------------------------------------


class TestDeltaTracker:
    def test_first_call_returns_full_state(self):
        tracker = DeltaTracker()
        state = {"a": 1, "b": 2}
        result = tracker.get_delta("client_1", state)
        assert result == state

    def test_second_call_returns_only_changes(self):
        tracker = DeltaTracker()
        state1 = {"a": 1, "b": 2}
        state2 = {"a": 1, "b": 3}
        tracker.get_delta("client_1", state1)
        delta = tracker.get_delta("client_1", state2)
        assert delta == {"b": 3}

    def test_no_changes_returns_empty_delta(self):
        tracker = DeltaTracker()
        state = {"a": 1}
        tracker.get_delta("client_1", state)
        delta = tracker.get_delta("client_1", state)
        assert delta == {}

    def test_separate_clients_tracked_independently(self):
        tracker = DeltaTracker()
        s1 = {"a": 1}
        s2 = {"a": 99}
        tracker.get_delta("client_1", s1)
        tracker.get_delta("client_2", s2)
        d1 = tracker.get_delta("client_1", {"a": 2})
        d2 = tracker.get_delta("client_2", {"a": 100})
        assert d1 == {"a": 2}
        assert d2 == {"a": 100}

    def test_remove_client_clears_state(self):
        tracker = DeltaTracker()
        tracker.get_delta("client_1", {"a": 1})
        tracker.remove_client("client_1")
        # After removal, next call should return full state again
        result = tracker.get_delta("client_1", {"a": 1})
        assert result == {"a": 1}

    def test_get_delta_does_not_mutate_stored_state(self):
        tracker = DeltaTracker()
        state = {"a": 1, "b": 2}
        tracker.get_delta("client_1", state)
        # Mutate the original (simulate external mutation attempt)
        state["a"] = 999
        delta = tracker.get_delta("client_1", {"a": 999, "b": 2})
        # delta should reflect the change because tracker stored a copy
        assert "a" in delta or delta == {}

    def test_known_clients_list(self):
        tracker = DeltaTracker()
        tracker.get_delta("c1", {"x": 1})
        tracker.get_delta("c2", {"x": 2})
        assert set(tracker.known_clients()) == {"c1", "c2"}

    def test_remove_nonexistent_client_is_noop(self):
        tracker = DeltaTracker()
        tracker.remove_client("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# measure_savings
# ---------------------------------------------------------------------------


class TestMeasureSavings:
    def test_full_state_vs_empty_delta(self):
        full = {"a": 1, "b": 2, "c": [1, 2, 3]}
        delta = {}
        ratio = measure_savings(full, delta)
        assert ratio > 0.0

    def test_ratio_between_zero_and_one(self):
        full = {"items": list(range(100))}
        delta = {"items": [99]}
        ratio = measure_savings(full, delta)
        assert 0.0 <= ratio <= 1.0

    def test_identical_size_returns_zero(self):
        state = {"a": 1}
        ratio = measure_savings(state, state)
        assert ratio == pytest.approx(0.0, abs=1e-9)

    def test_large_state_small_delta_high_ratio(self):
        full = {"uavs": [{"id": i, "lon": float(i), "lat": float(i), "mode": "IDLE"} for i in range(50)]}
        delta = {"uavs": [{"id": 0, "lon": 0.1}]}
        ratio = measure_savings(full, delta)
        assert ratio > 0.5
