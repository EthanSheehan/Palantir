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


class TestSimIntegration:
    """Integration: verify timer fields exist on Target and increment."""

    def test_timer_fields_exist(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from sim_engine import SimulationModel
        model = SimulationModel()
        assert len(model.targets) > 0
        t = model.targets[0]
        assert hasattr(t, 'time_in_state_sec')
        assert hasattr(t, 'last_sensor_contact_time')
        assert t.time_in_state_sec == 0.0

    def test_target_states_extended(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from sim_engine import TARGET_STATES
        assert "CLASSIFIED" in TARGET_STATES
        assert "VERIFIED" in TARGET_STATES
        # Existing states preserved
        assert "TRACKED" in TARGET_STATES
        assert "IDENTIFIED" in TARGET_STATES

    def test_get_state_includes_verification_fields(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from sim_engine import SimulationModel
        model = SimulationModel()
        state = model.get_state()
        for t in state["targets"]:
            assert "time_in_state_sec" in t
            assert "next_threshold" in t


class TestPipelineGate:
    """Integration: _process_new_detection only fires on VERIFIED."""

    def test_tactical_assistant_has_last_verified(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import api_main
        assistant = api_main.TacticalAssistant()
        assert hasattr(assistant, '_last_verified')

    def test_gate_does_not_fire_on_detected(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import api_main
        assistant = api_main.TacticalAssistant()
        sim_state = {"targets": [
            {"id": 1, "type": "SAM", "state": "DETECTED", "lon": 26.0, "lat": 44.0}
        ]}
        msgs = assistant.update(sim_state)
        # Should get NEW CONTACT message but NOT a nomination/HITL message
        assert any("NEW CONTACT" in m.get("text", "") for m in msgs)
        # Should not have triggered _process_new_detection (no HITL nomination)
        assert 1 not in assistant._nominated

    def test_gate_fires_on_verified(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import api_main
        assistant = api_main.TacticalAssistant()
        # First tick: DETECTED (triggers NEW CONTACT only)
        sim_state_1 = {"targets": [
            {"id": 1, "type": "SAM", "state": "DETECTED", "lon": 26.0, "lat": 44.0}
        ]}
        assistant.update(sim_state_1)
        # Second tick: VERIFIED (should trigger ISR pipeline)
        sim_state_2 = {"targets": [
            {"id": 1, "type": "SAM", "state": "VERIFIED", "lon": 26.0, "lat": 44.0,
             "detection_confidence": 0.9}
        ]}
        assistant.update(sim_state_2)
        # The pipeline should have fired (even if it returns None due to heuristic path)
        assert assistant._last_verified.get(1) is True


class TestManualVerify:
    """Integration: verify_target action schema exists."""

    def test_verify_target_in_action_schemas(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import api_main
        assert "verify_target" in api_main._ACTION_SCHEMAS
        assert api_main._ACTION_SCHEMAS["verify_target"] == {"target_id": "int"}


class TestBroadcast:
    """Integration: get_state includes verification fields."""

    def test_next_threshold_for_detected_target(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from sim_engine import SimulationModel
        model = SimulationModel()
        # Force a target to DETECTED state
        if model.targets:
            model.targets[0].state = "DETECTED"
            model.targets[0].detection_confidence = 0.3
            state = model.get_state()
            t = next(t for t in state["targets"] if t["id"] == model.targets[0].id)
            assert t["next_threshold"] is not None
            assert isinstance(t["next_threshold"], float)

    def test_next_threshold_none_for_nominated(self):
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from sim_engine import SimulationModel
        model = SimulationModel()
        if model.targets:
            model.targets[0].state = "NOMINATED"
            state = model.get_state()
            t = next(t for t in state["targets"] if t["id"] == model.targets[0].id)
            assert t["next_threshold"] is None
