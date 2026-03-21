"""Tests for override_tracker.py — W4-006 Override Capture with Reason Codes."""

from __future__ import annotations

import time

import pytest
from override_tracker import OverrideReason, OverrideRecord, OverrideTracker


class TestOverrideReason:
    def test_all_reason_codes_exist(self):
        assert OverrideReason.WRONG_TARGET.value == "WRONG_TARGET"
        assert OverrideReason.WRONG_TIMING.value == "WRONG_TIMING"
        assert OverrideReason.ROE_VIOLATION.value == "ROE_VIOLATION"
        assert OverrideReason.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
        assert OverrideReason.OTHER.value == "OTHER"

    def test_reason_count(self):
        assert len(OverrideReason) == 5


class TestOverrideRecord:
    def test_record_is_frozen(self):
        record = OverrideRecord(
            timestamp="2026-03-21T00:00:00Z",
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="Strike TEL at grid 1234",
        )
        with pytest.raises(AttributeError):
            record.reason = OverrideReason.OTHER  # type: ignore[misc]

    def test_record_fields(self):
        record = OverrideRecord(
            timestamp="2026-03-21T12:00:00Z",
            action_type="REJECT_COA",
            target_id=42,
            reason=OverrideReason.ROE_VIOLATION,
            free_text="Too close to civilian area",
            ai_recommendation="Engage with JDAM",
        )
        assert record.action_type == "REJECT_COA"
        assert record.target_id == 42
        assert record.reason == OverrideReason.ROE_VIOLATION
        assert record.free_text == "Too close to civilian area"
        assert record.ai_recommendation == "Engage with JDAM"


class TestOverrideTrackerRecord:
    def test_record_creates_override_record(self):
        tracker = OverrideTracker()
        record = tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="Strike SAM at grid 5678",
        )
        assert isinstance(record, OverrideRecord)
        assert record.action_type == "REJECT_NOMINATION"
        assert record.target_id == 1
        assert record.reason == OverrideReason.WRONG_TARGET

    def test_record_with_all_reason_codes(self):
        tracker = OverrideTracker()
        for reason in OverrideReason:
            record = tracker.record(
                action_type="REJECT_NOMINATION",
                target_id=1,
                reason=reason,
                free_text=None,
                ai_recommendation="test",
            )
            assert record.reason == reason

    def test_record_timestamp_is_iso(self):
        tracker = OverrideTracker()
        record = tracker.record(
            action_type="REJECT_COA",
            target_id=2,
            reason=OverrideReason.WRONG_TIMING,
            free_text=None,
            ai_recommendation="test",
        )
        assert "T" in record.timestamp
        assert record.timestamp.endswith("+00:00") or record.timestamp.endswith("Z")

    def test_free_text_truncation_at_200_chars(self):
        tracker = OverrideTracker()
        long_text = "x" * 300
        record = tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.OTHER,
            free_text=long_text,
            ai_recommendation="test",
        )
        assert record.free_text is not None
        assert len(record.free_text) == 200

    def test_free_text_none_preserved(self):
        tracker = OverrideTracker()
        record = tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="test",
        )
        assert record.free_text is None

    def test_target_id_none_allowed(self):
        tracker = OverrideTracker()
        record = tracker.record(
            action_type="REJECT_COA",
            target_id=None,
            reason=OverrideReason.WRONG_TIMING,
            free_text=None,
            ai_recommendation="test",
        )
        assert record.target_id is None


class TestOverrideTrackerGetRecent:
    def test_get_recent_returns_chronological_order(self):
        tracker = OverrideTracker()
        for i in range(5):
            tracker.record(
                action_type="REJECT_NOMINATION",
                target_id=i,
                reason=OverrideReason.WRONG_TARGET,
                free_text=None,
                ai_recommendation=f"rec-{i}",
            )
        recent = tracker.get_recent(3)
        assert len(recent) == 3
        assert recent[0].target_id == 2
        assert recent[1].target_id == 3
        assert recent[2].target_id == 4

    def test_get_recent_default_count(self):
        tracker = OverrideTracker()
        for i in range(15):
            tracker.record(
                action_type="REJECT_NOMINATION",
                target_id=i,
                reason=OverrideReason.WRONG_TARGET,
                free_text=None,
                ai_recommendation="test",
            )
        recent = tracker.get_recent()
        assert len(recent) == 10

    def test_get_recent_empty_tracker(self):
        tracker = OverrideTracker()
        assert tracker.get_recent() == []


class TestOverrideTrackerAcceptanceRate:
    def test_acceptance_rate_all_rejected(self):
        tracker = OverrideTracker()
        tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="test",
        )
        assert tracker.get_acceptance_rate() == 0.0

    def test_acceptance_rate_all_accepted(self):
        tracker = OverrideTracker()
        tracker.record_acceptance()
        tracker.record_acceptance()
        assert tracker.get_acceptance_rate() == 1.0

    def test_acceptance_rate_mixed(self):
        tracker = OverrideTracker()
        tracker.record_acceptance()
        tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="test",
        )
        rate = tracker.get_acceptance_rate()
        assert rate == pytest.approx(0.5)

    def test_acceptance_rate_empty_tracker(self):
        tracker = OverrideTracker()
        assert tracker.get_acceptance_rate() == 1.0

    def test_acceptance_rate_respects_window(self):
        tracker = OverrideTracker()
        # Inject old timestamps by manipulating internal state
        tracker._acceptances.append(time.time() - 600)  # 10 min ago, outside 5min window
        tracker.record_acceptance()  # recent
        tracker.record(
            action_type="REJECT_NOMINATION",
            target_id=1,
            reason=OverrideReason.WRONG_TARGET,
            free_text=None,
            ai_recommendation="test",
        )
        # Window=300s: 1 accept + 1 reject = 0.5
        rate = tracker.get_acceptance_rate(window_seconds=300.0)
        assert rate == pytest.approx(0.5)


class TestOverrideTrackerReasonDistribution:
    def test_reason_distribution(self):
        tracker = OverrideTracker()
        tracker.record("REJECT_NOMINATION", 1, OverrideReason.WRONG_TARGET, None, "test")
        tracker.record("REJECT_NOMINATION", 2, OverrideReason.WRONG_TARGET, None, "test")
        tracker.record("REJECT_COA", 3, OverrideReason.ROE_VIOLATION, None, "test")
        dist = tracker.get_reason_distribution()
        assert dist == {"WRONG_TARGET": 2, "ROE_VIOLATION": 1}

    def test_reason_distribution_empty(self):
        tracker = OverrideTracker()
        assert tracker.get_reason_distribution() == {}


class TestOverrideTrackerPromptContext:
    def test_prompt_context_empty(self):
        tracker = OverrideTracker()
        ctx = tracker.get_prompt_context()
        assert "100%" in ctx or "no overrides" in ctx.lower() or "acceptance" in ctx.lower()

    def test_prompt_context_with_overrides(self):
        tracker = OverrideTracker()
        tracker.record("REJECT_NOMINATION", 1, OverrideReason.WRONG_TARGET, None, "Strike SAM")
        tracker.record("REJECT_COA", 2, OverrideReason.ROE_VIOLATION, "Too close", "Use JDAM")
        ctx = tracker.get_prompt_context()
        assert "WRONG_TARGET" in ctx
        assert "ROE_VIOLATION" in ctx
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_prompt_context_includes_acceptance_rate(self):
        tracker = OverrideTracker()
        tracker.record_acceptance()
        tracker.record("REJECT_NOMINATION", 1, OverrideReason.WRONG_TARGET, None, "test")
        ctx = tracker.get_prompt_context()
        assert "50%" in ctx or "0.5" in ctx


class TestOverrideTrackerAcceptanceTracking:
    def test_record_acceptance(self):
        tracker = OverrideTracker()
        tracker.record_acceptance()
        tracker.record_acceptance()
        assert tracker.get_acceptance_rate() == 1.0

    def test_acceptance_does_not_appear_in_overrides(self):
        tracker = OverrideTracker()
        tracker.record_acceptance()
        assert tracker.get_recent() == []
        assert tracker.get_reason_distribution() == {}
