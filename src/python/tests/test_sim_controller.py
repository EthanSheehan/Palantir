"""Tests for SimController — simulation fidelity controls (W5-001)."""

from __future__ import annotations

import pytest
from sim_controller import (
    VALID_SPEEDS,
    SimController,
    SimControlState,
)

# ---------------------------------------------------------------------------
# SimControlState frozen dataclass
# ---------------------------------------------------------------------------


class TestSimControlState:
    def test_frozen(self):
        s = SimControlState(paused=False, speed_multiplier=1, step_requested=False)
        with pytest.raises((AttributeError, TypeError)):
            s.paused = True

    def test_defaults(self):
        s = SimControlState()
        assert s.paused is False
        assert s.speed_multiplier == 1
        assert s.step_requested is False


# ---------------------------------------------------------------------------
# SimController.pause / resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    def test_pause_sets_paused(self):
        ctrl = SimController()
        ctrl2 = ctrl.pause()
        assert ctrl2.state.paused is True

    def test_resume_clears_paused(self):
        ctrl = SimController()
        ctrl2 = ctrl.pause().resume()
        assert ctrl2.state.paused is False

    def test_pause_is_idempotent(self):
        ctrl = SimController()
        s1 = ctrl.pause().state
        s2 = ctrl.pause().pause().state
        assert s1.paused == s2.paused

    def test_resume_on_running_is_idempotent(self):
        ctrl = SimController()
        assert ctrl.resume().state.paused is False

    def test_pause_returns_new_controller(self):
        ctrl = SimController()
        ctrl2 = ctrl.pause()
        assert ctrl is not ctrl2

    def test_resume_returns_new_controller(self):
        ctrl = SimController().pause()
        ctrl2 = ctrl.resume()
        assert ctrl is not ctrl2

    def test_original_unchanged_after_pause(self):
        ctrl = SimController()
        _ = ctrl.pause()
        assert ctrl.state.paused is False


# ---------------------------------------------------------------------------
# SimController.set_speed
# ---------------------------------------------------------------------------


class TestSetSpeed:
    def test_valid_speeds(self):
        ctrl = SimController()
        for speed in VALID_SPEEDS:
            c = ctrl.set_speed(speed)
            assert c.state.speed_multiplier == speed

    def test_invalid_speed_raises(self):
        ctrl = SimController()
        with pytest.raises(ValueError, match="speed"):
            ctrl.set_speed(3)

    def test_invalid_speed_zero_raises(self):
        ctrl = SimController()
        with pytest.raises(ValueError, match="speed"):
            ctrl.set_speed(0)

    def test_invalid_speed_negative_raises(self):
        ctrl = SimController()
        with pytest.raises(ValueError, match="speed"):
            ctrl.set_speed(-1)

    def test_set_speed_returns_new_controller(self):
        ctrl = SimController()
        ctrl2 = ctrl.set_speed(5)
        assert ctrl is not ctrl2

    def test_original_speed_unchanged(self):
        ctrl = SimController()
        _ = ctrl.set_speed(10)
        assert ctrl.state.speed_multiplier == 1


# ---------------------------------------------------------------------------
# SimController.step (single-step mode)
# ---------------------------------------------------------------------------


class TestSingleStep:
    def test_step_sets_step_requested(self):
        ctrl = SimController()
        ctrl2 = ctrl.step()
        assert ctrl2.state.step_requested is True

    def test_step_on_paused_sets_flag(self):
        ctrl = SimController().pause()
        ctrl2 = ctrl.step()
        assert ctrl2.state.step_requested is True
        assert ctrl2.state.paused is True

    def test_step_returns_new_controller(self):
        ctrl = SimController()
        ctrl2 = ctrl.step()
        assert ctrl is not ctrl2


# ---------------------------------------------------------------------------
# SimController.should_tick
# ---------------------------------------------------------------------------


class TestShouldTick:
    def test_running_returns_true(self):
        ctrl = SimController()
        should_run, effective_dt = ctrl.should_tick(0.1)
        assert should_run is True

    def test_paused_returns_false(self):
        ctrl = SimController().pause()
        should_run, effective_dt = ctrl.should_tick(0.1)
        assert should_run is False

    def test_paused_effective_dt_zero(self):
        ctrl = SimController().pause()
        _, effective_dt = ctrl.should_tick(0.1)
        assert effective_dt == 0.0

    def test_speed_multiplier_scales_dt(self):
        ctrl = SimController().set_speed(10)
        should_run, effective_dt = ctrl.should_tick(0.1)
        assert should_run is True
        assert pytest.approx(effective_dt) == 1.0

    def test_speed_1x_dt_unchanged(self):
        ctrl = SimController()
        _, effective_dt = ctrl.should_tick(0.1)
        assert pytest.approx(effective_dt) == 0.1

    def test_paused_with_step_returns_true(self):
        ctrl = SimController().pause().step()
        should_run, effective_dt = ctrl.should_tick(0.1)
        assert should_run is True

    def test_paused_with_step_uses_base_dt(self):
        ctrl = SimController().pause().step()
        _, effective_dt = ctrl.should_tick(0.1)
        assert pytest.approx(effective_dt) == 0.1

    def test_step_consumed_after_should_tick(self):
        ctrl = SimController().pause().step()
        ctrl2 = ctrl.consume_step()
        assert ctrl2.state.step_requested is False
        assert ctrl2.state.paused is True


# ---------------------------------------------------------------------------
# SimController.get_state (serialization)
# ---------------------------------------------------------------------------


class TestGetState:
    def test_get_state_includes_paused(self):
        ctrl = SimController().pause()
        s = ctrl.get_state()
        assert s["paused"] is True

    def test_get_state_includes_speed(self):
        ctrl = SimController().set_speed(50)
        s = ctrl.get_state()
        assert s["speed_multiplier"] == 50

    def test_get_state_includes_step_requested(self):
        ctrl = SimController().step()
        s = ctrl.get_state()
        assert s["step_requested"] is True

    def test_get_state_includes_valid_speeds(self):
        ctrl = SimController()
        s = ctrl.get_state()
        assert "valid_speeds" in s
        assert set(s["valid_speeds"]) == set(VALID_SPEEDS)


# ---------------------------------------------------------------------------
# Paused state blocks tick advancement (integration-style)
# ---------------------------------------------------------------------------


class TestPausedBlocksTick:
    def test_paused_should_tick_false_across_calls(self):
        ctrl = SimController().pause()
        for _ in range(5):
            should_run, _ = ctrl.should_tick(0.1)
            assert should_run is False

    def test_step_advances_exactly_one_tick(self):
        ctrl = SimController().pause()
        tick_count = 0

        ctrl_step = ctrl.step()
        should_run, _ = ctrl_step.should_tick(0.1)
        if should_run:
            tick_count += 1
        ctrl_after = ctrl_step.consume_step()

        # After consuming the step, subsequent should_tick returns False
        should_run_2, _ = ctrl_after.should_tick(0.1)
        assert should_run_2 is False
        assert tick_count == 1
