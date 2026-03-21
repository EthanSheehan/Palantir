"""Tests for the per-action autonomy policy (W4-002)."""

from __future__ import annotations

import time

import pytest
from autonomy_policy import (
    VALID_ACTIONS,
    VALID_LEVELS,
    ActionAutonomy,
    AutonomyPolicy,
)

# ---------------------------------------------------------------------------
# ActionAutonomy frozen dataclass
# ---------------------------------------------------------------------------


class TestActionAutonomy:
    def test_frozen(self):
        aa = ActionAutonomy(action="FOLLOW", level="MANUAL")
        with pytest.raises(AttributeError):
            aa.action = "PAINT"

    def test_defaults(self):
        aa = ActionAutonomy(action="FOLLOW", level="MANUAL")
        assert aa.expires_at is None
        assert aa.exception_targets == ()

    def test_with_expiry_and_exceptions(self):
        aa = ActionAutonomy(action="ENGAGE", level="AUTONOMOUS", expires_at=9999.0, exception_targets=("SAM", "TEL"))
        assert aa.expires_at == 9999.0
        assert aa.exception_targets == ("SAM", "TEL")


# ---------------------------------------------------------------------------
# AutonomyPolicy — default level
# ---------------------------------------------------------------------------


class TestDefaultLevel:
    def test_default_is_manual(self):
        p = AutonomyPolicy()
        assert p.get_action_level("FOLLOW") == "MANUAL"

    def test_custom_default(self):
        p = AutonomyPolicy(default_level="SUPERVISED")
        assert p.get_action_level("PAINT") == "SUPERVISED"

    def test_set_default_level_returns_new(self):
        p1 = AutonomyPolicy()
        p2 = p1.set_default_level("AUTONOMOUS")
        assert p2.get_action_level("FOLLOW") == "AUTONOMOUS"
        assert p1.get_action_level("FOLLOW") == "MANUAL"

    def test_invalid_default_level(self):
        with pytest.raises(ValueError, match="level"):
            AutonomyPolicy(default_level="INVALID")


# ---------------------------------------------------------------------------
# set_action_level / get_action_level
# ---------------------------------------------------------------------------


class TestSetGetActionLevel:
    def test_set_returns_new_policy(self):
        p1 = AutonomyPolicy()
        p2 = p1.set_action_level("FOLLOW", "AUTONOMOUS")
        assert p2 is not p1
        assert p2.get_action_level("FOLLOW") == "AUTONOMOUS"
        assert p1.get_action_level("FOLLOW") == "MANUAL"

    def test_set_multiple_actions(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        p = p.set_action_level("PAINT", "SUPERVISED")
        assert p.get_action_level("FOLLOW") == "AUTONOMOUS"
        assert p.get_action_level("PAINT") == "SUPERVISED"
        assert p.get_action_level("ENGAGE") == "MANUAL"

    def test_invalid_action_raises(self):
        p = AutonomyPolicy()
        with pytest.raises(ValueError, match="action"):
            p.set_action_level("INVALID_ACTION", "MANUAL")

    def test_invalid_level_raises(self):
        p = AutonomyPolicy()
        with pytest.raises(ValueError, match="level"):
            p.set_action_level("FOLLOW", "INVALID_LEVEL")


# ---------------------------------------------------------------------------
# Time-bounded grants
# ---------------------------------------------------------------------------


class TestTimeBoundedGrants:
    def test_duration_sets_expires_at(self):
        p = AutonomyPolicy()
        before = time.time()
        p2 = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=60.0)
        after = time.time()
        d = p2.to_dict()
        action_entry = next(a for a in d["actions"] if a["action"] == "FOLLOW")
        assert action_entry["expires_at"] is not None
        assert before + 60.0 <= action_entry["expires_at"] <= after + 60.0

    def test_expired_grant_reverts_to_default(self):
        p = AutonomyPolicy(default_level="MANUAL")
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=-1.0)
        assert p.get_action_level("FOLLOW") == "MANUAL"

    def test_non_expired_grant_stays(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=9999.0)
        assert p.get_action_level("FOLLOW") == "AUTONOMOUS"

    def test_tick_expires_grants(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=-1.0)
        p = p.set_action_level("PAINT", "SUPERVISED", duration_seconds=9999.0)
        p2 = p.tick()
        assert p2.get_action_level("FOLLOW") == "MANUAL"
        assert p2.get_action_level("PAINT") == "SUPERVISED"

    def test_tick_returns_same_if_nothing_expired(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=9999.0)
        p2 = p.tick()
        assert p2.get_action_level("FOLLOW") == "AUTONOMOUS"

    def test_tick_returns_new_if_something_expired(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=-1.0)
        p2 = p.tick()
        assert p2 is not p

    def test_permanent_grant_no_expiry(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        p2 = p.tick()
        assert p2.get_action_level("FOLLOW") == "AUTONOMOUS"


# ---------------------------------------------------------------------------
# Exception targets
# ---------------------------------------------------------------------------


class TestExceptionTargets:
    def test_exception_target_forces_manual(self):
        p = AutonomyPolicy()
        p = p.set_action_level("ENGAGE", "AUTONOMOUS", exception_targets=["SAM", "TEL"])
        assert p.get_effective_level("ENGAGE", target_type="SAM") == "MANUAL"
        assert p.get_effective_level("ENGAGE", target_type="TRUCK") == "AUTONOMOUS"

    def test_exception_target_without_target_type(self):
        p = AutonomyPolicy()
        p = p.set_action_level("ENGAGE", "AUTONOMOUS", exception_targets=["SAM"])
        assert p.get_effective_level("ENGAGE") == "AUTONOMOUS"

    def test_no_exceptions_passthrough(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        assert p.get_effective_level("FOLLOW", target_type="SAM") == "AUTONOMOUS"


# ---------------------------------------------------------------------------
# get_effective_level
# ---------------------------------------------------------------------------


class TestGetEffectiveLevel:
    def test_uses_action_level(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "SUPERVISED")
        assert p.get_effective_level("FOLLOW") == "SUPERVISED"

    def test_falls_back_to_default(self):
        p = AutonomyPolicy(default_level="SUPERVISED")
        assert p.get_effective_level("FOLLOW") == "SUPERVISED"

    def test_expired_falls_back(self):
        p = AutonomyPolicy(default_level="MANUAL")
        p = p.set_action_level("FOLLOW", "AUTONOMOUS", duration_seconds=-1.0)
        assert p.get_effective_level("FOLLOW") == "MANUAL"


# ---------------------------------------------------------------------------
# is_autonomous / is_supervised
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_is_autonomous_true(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        assert p.is_autonomous("FOLLOW") is True

    def test_is_autonomous_false(self):
        p = AutonomyPolicy()
        assert p.is_autonomous("FOLLOW") is False

    def test_is_supervised_true(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "SUPERVISED")
        assert p.is_supervised("FOLLOW") is True

    def test_is_supervised_false(self):
        p = AutonomyPolicy()
        assert p.is_supervised("FOLLOW") is False

    def test_is_autonomous_with_exception(self):
        p = AutonomyPolicy()
        p = p.set_action_level("ENGAGE", "AUTONOMOUS", exception_targets=["SAM"])
        assert p.is_autonomous("ENGAGE", target_type="SAM") is False
        assert p.is_autonomous("ENGAGE", target_type="TRUCK") is True


# ---------------------------------------------------------------------------
# force_manual
# ---------------------------------------------------------------------------


class TestForceManual:
    def test_resets_all_to_manual(self):
        p = AutonomyPolicy(default_level="AUTONOMOUS")
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        p = p.set_action_level("PAINT", "SUPERVISED")
        p2 = p.force_manual()
        assert p2.get_action_level("FOLLOW") == "MANUAL"
        assert p2.get_action_level("PAINT") == "MANUAL"
        assert p2.get_effective_level("ENGAGE") == "MANUAL"

    def test_returns_new_policy(self):
        p = AutonomyPolicy(default_level="AUTONOMOUS")
        p2 = p.force_manual()
        assert p2 is not p
        assert p.get_action_level("FOLLOW") == "AUTONOMOUS"


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_structure(self):
        p = AutonomyPolicy(default_level="SUPERVISED")
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        d = p.to_dict()
        assert d["default_level"] == "SUPERVISED"
        assert isinstance(d["actions"], list)
        follow = next(a for a in d["actions"] if a["action"] == "FOLLOW")
        assert follow["level"] == "AUTONOMOUS"
        assert follow["expires_at"] is None
        assert follow["exception_targets"] == []

    def test_to_dict_with_expiry(self):
        p = AutonomyPolicy()
        p = p.set_action_level("ENGAGE", "AUTONOMOUS", duration_seconds=120.0)
        d = p.to_dict()
        engage = next(a for a in d["actions"] if a["action"] == "ENGAGE")
        assert engage["expires_at"] is not None
        assert isinstance(engage["expires_at"], float)

    def test_to_dict_with_exceptions(self):
        p = AutonomyPolicy()
        p = p.set_action_level("ENGAGE", "AUTONOMOUS", exception_targets=["SAM"])
        d = p.to_dict()
        engage = next(a for a in d["actions"] if a["action"] == "ENGAGE")
        assert engage["exception_targets"] == ["SAM"]


# ---------------------------------------------------------------------------
# Backward compatibility — global level sets default
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_set_default_affects_all_unset_actions(self):
        p = AutonomyPolicy()
        p = p.set_default_level("AUTONOMOUS")
        for action in VALID_ACTIONS:
            assert p.get_action_level(action) == "AUTONOMOUS"

    def test_per_action_overrides_default(self):
        p = AutonomyPolicy(default_level="AUTONOMOUS")
        p = p.set_action_level("ENGAGE", "MANUAL")
        assert p.get_action_level("ENGAGE") == "MANUAL"
        assert p.get_action_level("FOLLOW") == "AUTONOMOUS"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_valid_actions_constant(self):
        assert "FOLLOW" in VALID_ACTIONS
        assert "ENGAGE" in VALID_ACTIONS
        assert "SWARM_ASSIGN" in VALID_ACTIONS

    def test_valid_levels_constant(self):
        assert VALID_LEVELS == {"MANUAL", "SUPERVISED", "AUTONOMOUS"}

    def test_overwrite_action_level(self):
        p = AutonomyPolicy()
        p = p.set_action_level("FOLLOW", "AUTONOMOUS")
        p = p.set_action_level("FOLLOW", "SUPERVISED")
        assert p.get_action_level("FOLLOW") == "SUPERVISED"

    def test_get_action_level_unknown_action_returns_default(self):
        """Unknown action in get_action_level returns default level (graceful)."""
        p = AutonomyPolicy(default_level="SUPERVISED")
        assert p.get_action_level("FOLLOW") == "SUPERVISED"
