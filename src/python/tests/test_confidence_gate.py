"""Tests for confidence_gate.py — W4-004 Confidence-Gated Dynamic Authority."""

import time

import pytest
from confidence_gate import DEFAULT_THRESHOLDS, ConfidenceGate, ConfidenceThreshold

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_gate():
    return ConfidenceGate(DEFAULT_THRESHOLDS)


@pytest.fixture
def custom_gate():
    thresholds = [
        ConfidenceThreshold(action="ENGAGE", min_confidence=0.85, high_value_targets=("CP", "C2_NODE")),
        ConfidenceThreshold(action="AUTHORIZE_COA", min_confidence=0.7, high_value_targets=("CP",)),
        ConfidenceThreshold(action="FOLLOW", min_confidence=0.3, high_value_targets=()),
    ]
    return ConfidenceGate(thresholds)


# ---------------------------------------------------------------------------
# PROCEED tests
# ---------------------------------------------------------------------------


class TestProceed:
    def test_proceed_when_above_threshold(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.9)
        assert result == "PROCEED"

    def test_proceed_at_exact_threshold(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.7)
        assert result == "PROCEED"

    def test_proceed_confidence_one(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 1.0)
        assert result == "PROCEED"

    def test_proceed_low_threshold_action(self, default_gate):
        result = default_gate.evaluate("FOLLOW", 0.35)
        assert result == "PROCEED"

    def test_proceed_paint_above_threshold(self, default_gate):
        result = default_gate.evaluate("PAINT", 0.5)
        assert result == "PROCEED"

    def test_proceed_non_high_value_target(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.9, target_type="SAM")
        assert result == "PROCEED"


# ---------------------------------------------------------------------------
# ESCALATE tests
# ---------------------------------------------------------------------------


class TestEscalate:
    def test_escalate_below_threshold(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.5)
        assert result == "ESCALATE"

    def test_escalate_engage_below_threshold(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.8)
        assert result == "ESCALATE"

    def test_escalate_confidence_zero(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.0)
        assert result == "ESCALATE"

    def test_escalate_high_value_target_always(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.99, target_type="CP")
        assert result == "ESCALATE"

    def test_escalate_high_value_c2_node(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.99, target_type="C2_NODE")
        assert result == "ESCALATE"

    def test_escalate_high_value_engage(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.99, target_type="CP")
        assert result == "ESCALATE"

    def test_escalate_unknown_action_always(self, default_gate):
        result = default_gate.evaluate("UNKNOWN_ACTION", 0.99)
        assert result == "ESCALATE"

    def test_escalate_just_below_threshold(self, default_gate):
        result = default_gate.evaluate("AUTHORIZE_COA", 0.699)
        assert result == "ESCALATE"


# ---------------------------------------------------------------------------
# Override rate tests
# ---------------------------------------------------------------------------


class TestOverrideRate:
    def test_override_rate_zero_initially(self, default_gate):
        assert default_gate.get_override_rate() == 0.0

    def test_override_rate_after_single_override(self, default_gate):
        default_gate.record_override()
        rate = default_gate.get_override_rate(window_seconds=300.0)
        assert rate > 0.0

    def test_override_rate_escalates_everything(self):
        gate = ConfidenceGate(DEFAULT_THRESHOLDS, override_rate_limit=0.3)
        # Record enough overrides to push rate above 30%
        # We need rate > 0.3 = overrides / (overrides + non_overrides)
        # With no non-overrides tracked, just overrides > 0 means rate is high
        for _ in range(5):
            gate.record_override()
        # With 5 overrides and 0 non-override evals, rate should be > 0.3
        result = gate.evaluate("FOLLOW", 0.99)
        assert result == "ESCALATE"

    def test_override_rate_calculation_with_window(self):
        gate = ConfidenceGate(DEFAULT_THRESHOLDS)
        gate.record_override()
        gate.record_override()
        rate = gate.get_override_rate(window_seconds=300.0)
        assert rate > 0.0

    def test_old_overrides_expire(self):
        gate = ConfidenceGate(DEFAULT_THRESHOLDS)
        # Inject an old override timestamp
        gate._override_timestamps.append(time.monotonic() - 600.0)
        rate = gate.get_override_rate(window_seconds=300.0)
        assert rate == 0.0


# ---------------------------------------------------------------------------
# Vigilance prompt tests
# ---------------------------------------------------------------------------


class TestVigilancePrompt:
    def test_vigilance_prompt_needed(self, default_gate):
        assert default_gate.should_show_vigilance_prompt(130.0) is True

    def test_vigilance_prompt_not_needed(self, default_gate):
        assert default_gate.should_show_vigilance_prompt(60.0) is False

    def test_vigilance_prompt_at_boundary(self, default_gate):
        assert default_gate.should_show_vigilance_prompt(120.0) is True

    def test_vigilance_prompt_zero_seconds(self, default_gate):
        assert default_gate.should_show_vigilance_prompt(0.0) is False


# ---------------------------------------------------------------------------
# Default thresholds tests
# ---------------------------------------------------------------------------


class TestDefaultThresholds:
    def test_default_authorize_coa_threshold(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert thresholds["AUTHORIZE_COA"].min_confidence == 0.7

    def test_default_engage_threshold(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert thresholds["ENGAGE"].min_confidence == 0.85

    def test_default_intercept_threshold(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert thresholds["INTERCEPT"].min_confidence == 0.6

    def test_default_follow_threshold(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert thresholds["FOLLOW"].min_confidence == 0.3

    def test_default_paint_threshold(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert thresholds["PAINT"].min_confidence == 0.3

    def test_default_high_value_targets(self):
        thresholds = {t.action: t for t in DEFAULT_THRESHOLDS}
        assert "CP" in thresholds["AUTHORIZE_COA"].high_value_targets
        assert "C2_NODE" in thresholds["AUTHORIZE_COA"].high_value_targets


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_target_type(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.9, target_type="")
        assert result == "PROCEED"

    def test_none_target_type_above_threshold(self, default_gate):
        result = default_gate.evaluate("ENGAGE", 0.9, target_type=None)
        assert result == "PROCEED"

    def test_confidence_exactly_zero(self, default_gate):
        result = default_gate.evaluate("FOLLOW", 0.0)
        assert result == "ESCALATE"

    def test_confidence_exactly_one(self, default_gate):
        result = default_gate.evaluate("FOLLOW", 1.0)
        assert result == "PROCEED"

    def test_empty_thresholds(self):
        gate = ConfidenceGate([])
        result = gate.evaluate("ENGAGE", 0.9)
        assert result == "ESCALATE"

    def test_custom_override_rate_limit(self):
        gate = ConfidenceGate(DEFAULT_THRESHOLDS, override_rate_limit=0.5)
        assert gate._override_rate_limit == 0.5

    def test_multiple_high_value_targets_per_action(self, custom_gate):
        # CP is high-value for ENGAGE
        result = custom_gate.evaluate("ENGAGE", 0.99, target_type="CP")
        assert result == "ESCALATE"
        # C2_NODE is also high-value for ENGAGE
        result = custom_gate.evaluate("ENGAGE", 0.99, target_type="C2_NODE")
        assert result == "ESCALATE"
