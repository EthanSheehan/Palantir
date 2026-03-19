import pytest
from verification_engine import (
    evaluate_target_state,
    VERIFICATION_THRESHOLDS,
    DEMO_FAST_THRESHOLDS,
    VerificationThreshold,
    _DEFAULT_THRESHOLD,
)


class TestEvaluateState:
    """Promotion and passthrough tests."""

    def test_detected_to_classified(self):
        result = evaluate_target_state(
            current_state="DETECTED", target_type="TRUCK",
            fused_confidence=0.65, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        assert result == "CLASSIFIED"

    def test_detected_stays_below_threshold(self):
        result = evaluate_target_state(
            current_state="DETECTED", target_type="TRUCK",
            fused_confidence=0.55, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        assert result == "DETECTED"

    def test_classified_to_verified_sensors(self):
        result = evaluate_target_state(
            current_state="CLASSIFIED", target_type="TRUCK",
            fused_confidence=0.85, sensor_type_count=2,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        assert result == "VERIFIED"

    def test_classified_to_verified_sustained(self):
        result = evaluate_target_state(
            current_state="CLASSIFIED", target_type="TRUCK",
            fused_confidence=0.85, sensor_type_count=1,
            time_in_current_state_sec=16.0, seconds_since_last_sensor=0.0,
        )
        assert result == "VERIFIED"

    def test_classified_stays_below_threshold(self):
        result = evaluate_target_state(
            current_state="CLASSIFIED", target_type="TRUCK",
            fused_confidence=0.7, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        assert result == "CLASSIFIED"

    def test_verified_no_auto_promote(self):
        result = evaluate_target_state(
            current_state="VERIFIED", target_type="SAM",
            fused_confidence=0.99, sensor_type_count=3,
            time_in_current_state_sec=100.0, seconds_since_last_sensor=0.0,
        )
        assert result == "VERIFIED"

    def test_undetected_passthrough(self):
        result = evaluate_target_state(
            current_state="UNDETECTED", target_type="TRUCK",
            fused_confidence=0.0, sensor_type_count=0,
            time_in_current_state_sec=0.0, seconds_since_last_sensor=100.0,
        )
        assert result == "UNDETECTED"

    @pytest.mark.parametrize("terminal_state", [
        "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED",
    ])
    def test_terminal_states_not_regressed(self, terminal_state):
        result = evaluate_target_state(
            current_state=terminal_state, target_type="SAM",
            fused_confidence=0.0, sensor_type_count=0,
            time_in_current_state_sec=0.0, seconds_since_last_sensor=999.0,
        )
        assert result == terminal_state


class TestRegression:
    def test_verified_to_classified(self):
        result = evaluate_target_state(
            current_state="VERIFIED", target_type="TRUCK",
            fused_confidence=0.9, sensor_type_count=2,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=20.0,
        )
        assert result == "CLASSIFIED"

    def test_classified_to_detected(self):
        result = evaluate_target_state(
            current_state="CLASSIFIED", target_type="TRUCK",
            fused_confidence=0.7, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=20.0,
        )
        assert result == "DETECTED"

    def test_detected_to_undetected(self):
        result = evaluate_target_state(
            current_state="DETECTED", target_type="TRUCK",
            fused_confidence=0.0, sensor_type_count=0,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=20.0,
        )
        assert result == "UNDETECTED"


class TestThresholds:
    def test_sam_thresholds_lower_than_default(self):
        sam = VERIFICATION_THRESHOLDS["SAM"]
        default = _DEFAULT_THRESHOLD
        assert sam.classify_confidence < default.classify_confidence
        assert sam.verify_confidence < default.verify_confidence

    def test_all_target_types_have_thresholds(self):
        expected = {"SAM", "TEL", "TRUCK", "CP", "MANPADS", "RADAR",
                    "C2_NODE", "LOGISTICS", "ARTILLERY", "APC"}
        assert expected == set(VERIFICATION_THRESHOLDS.keys())


class TestDemoFast:
    def test_demo_fast_halves_time(self):
        for key in VERIFICATION_THRESHOLDS:
            normal = VERIFICATION_THRESHOLDS[key]
            fast = DEMO_FAST_THRESHOLDS[key]
            assert fast.verify_sustained_sec == normal.verify_sustained_sec / 2.0
            assert fast.regression_timeout_sec == normal.regression_timeout_sec / 2.0

    def test_demo_fast_lowers_confidence(self):
        for key in VERIFICATION_THRESHOLDS:
            normal = VERIFICATION_THRESHOLDS[key]
            fast = DEMO_FAST_THRESHOLDS[key]
            assert fast.classify_confidence == max(0.3, normal.classify_confidence - 0.1)

    def test_demo_fast_promotes_easier(self):
        result = evaluate_target_state(
            current_state="DETECTED", target_type="SAM",
            fused_confidence=0.45, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
            demo_fast=True,
        )
        assert result == "CLASSIFIED"


class TestPurity:
    def test_returns_string(self):
        result = evaluate_target_state(
            current_state="DETECTED", target_type="TRUCK",
            fused_confidence=0.65, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        assert isinstance(result, str)

    def test_no_side_effects(self):
        args = dict(
            current_state="DETECTED", target_type="TRUCK",
            fused_confidence=0.65, sensor_type_count=1,
            time_in_current_state_sec=5.0, seconds_since_last_sensor=0.0,
        )
        r1 = evaluate_target_state(**args)
        r2 = evaluate_target_state(**args)
        assert r1 == r2
