"""Tests for AMCGridSettings magic constants — W6-037."""

import pytest
from config import AMCGridSettings

# Env vars that AMCGridSettings reads — must be cleaned before each test
# to prevent pollution from other tests running in random order.
_SETTINGS_ENV_VARS = [
    "AUTOPILOT_SCAN_DELAY",
    "AUTOPILOT_AUTHORIZE_DELAY",
    "AUTOPILOT_FOLLOW_DELAY",
    "AUTOPILOT_PAINT_DELAY",
    "DEMO_FAST_CLASSIFY_TIME",
    "DEMO_FAST_VERIFY_TIME",
    "UAV_SPEED_MPS",
    "DETECTION_RANGE_KM",
    "SWARM_TASK_EXPIRY_S",
    "TICK_RATE_HZ",
    "MAX_TURN_RATE_DPS",
    "IDLE_COUNT_THRESHOLD",
]


@pytest.fixture(autouse=True)
def _clean_settings_env(monkeypatch):
    """Remove all AMCGridSettings env vars so defaults are tested cleanly."""
    for var in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestAutopilotDelays:
    def test_scan_delay_default(self):
        s = AMCGridSettings()
        assert s.autopilot_scan_delay == 2.0

    def test_authorize_delay_default(self):
        s = AMCGridSettings()
        assert s.autopilot_authorize_delay == 5.0

    def test_follow_delay_default(self):
        s = AMCGridSettings()
        assert s.autopilot_follow_delay == 4.0

    def test_paint_delay_default(self):
        s = AMCGridSettings()
        assert s.autopilot_paint_delay == 5.0


class TestDemoFastThresholds:
    def test_classify_time_default(self):
        s = AMCGridSettings()
        assert s.demo_fast_classify_time == 5.0

    def test_verify_time_default(self):
        s = AMCGridSettings()
        assert s.demo_fast_verify_time == 8.0


class TestPhysicsConstants:
    def test_uav_speed_mps_default(self):
        s = AMCGridSettings()
        assert s.uav_speed_mps == 60.0

    def test_detection_range_km_default(self):
        s = AMCGridSettings()
        assert s.detection_range_km == 15.0

    def test_swarm_task_expiry_s_default(self):
        s = AMCGridSettings()
        assert s.swarm_task_expiry_s == 120.0

    def test_tick_rate_hz_default(self):
        s = AMCGridSettings()
        assert s.tick_rate_hz == 10.0

    def test_max_turn_rate_dps_default(self):
        s = AMCGridSettings()
        assert s.max_turn_rate_dps == 3.0

    def test_idle_count_threshold_default(self):
        s = AMCGridSettings()
        assert s.idle_count_threshold == 3


# ---------------------------------------------------------------------------
# Env-var overrides
# ---------------------------------------------------------------------------


class TestEnvVarOverrides:
    def test_autopilot_scan_delay_override(self, monkeypatch):
        monkeypatch.setenv("AUTOPILOT_SCAN_DELAY", "1.5")
        s = AMCGridSettings()
        assert s.autopilot_scan_delay == 1.5

    def test_autopilot_authorize_delay_override(self, monkeypatch):
        monkeypatch.setenv("AUTOPILOT_AUTHORIZE_DELAY", "3.0")
        s = AMCGridSettings()
        assert s.autopilot_authorize_delay == 3.0

    def test_demo_fast_classify_time_override(self, monkeypatch):
        monkeypatch.setenv("DEMO_FAST_CLASSIFY_TIME", "2.5")
        s = AMCGridSettings()
        assert s.demo_fast_classify_time == 2.5

    def test_demo_fast_verify_time_override(self, monkeypatch):
        monkeypatch.setenv("DEMO_FAST_VERIFY_TIME", "4.0")
        s = AMCGridSettings()
        assert s.demo_fast_verify_time == 4.0

    def test_uav_speed_mps_override(self, monkeypatch):
        monkeypatch.setenv("UAV_SPEED_MPS", "80.0")
        s = AMCGridSettings()
        assert s.uav_speed_mps == 80.0

    def test_detection_range_km_override(self, monkeypatch):
        monkeypatch.setenv("DETECTION_RANGE_KM", "20.0")
        s = AMCGridSettings()
        assert s.detection_range_km == 20.0

    def test_swarm_task_expiry_s_override(self, monkeypatch):
        monkeypatch.setenv("SWARM_TASK_EXPIRY_S", "60.0")
        s = AMCGridSettings()
        assert s.swarm_task_expiry_s == 60.0

    def test_tick_rate_hz_override(self, monkeypatch):
        monkeypatch.setenv("TICK_RATE_HZ", "20.0")
        s = AMCGridSettings()
        assert s.tick_rate_hz == 20.0

    def test_max_turn_rate_dps_override(self, monkeypatch):
        monkeypatch.setenv("MAX_TURN_RATE_DPS", "5.0")
        s = AMCGridSettings()
        assert s.max_turn_rate_dps == 5.0

    def test_idle_count_threshold_override(self, monkeypatch):
        monkeypatch.setenv("IDLE_COUNT_THRESHOLD", "5")
        s = AMCGridSettings()
        assert s.idle_count_threshold == 5


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


class TestFieldTypes:
    def test_autopilot_delays_are_float(self):
        s = AMCGridSettings()
        assert isinstance(s.autopilot_scan_delay, float)
        assert isinstance(s.autopilot_authorize_delay, float)
        assert isinstance(s.autopilot_follow_delay, float)
        assert isinstance(s.autopilot_paint_delay, float)

    def test_demo_fast_times_are_float(self):
        s = AMCGridSettings()
        assert isinstance(s.demo_fast_classify_time, float)
        assert isinstance(s.demo_fast_verify_time, float)

    def test_physics_floats(self):
        s = AMCGridSettings()
        assert isinstance(s.uav_speed_mps, float)
        assert isinstance(s.detection_range_km, float)
        assert isinstance(s.swarm_task_expiry_s, float)
        assert isinstance(s.tick_rate_hz, float)
        assert isinstance(s.max_turn_rate_dps, float)

    def test_idle_count_threshold_is_int(self):
        s = AMCGridSettings()
        assert isinstance(s.idle_count_threshold, int)
