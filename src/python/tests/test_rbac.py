"""Tests for RBAC JWT authentication (W5-006).

Covers:
  - JWT token creation and validation
  - Role extraction from token
  - Role-based permission matrix
  - OBSERVER / OPERATOR / COMMANDER / ADMIN access rules
  - AUTH_DISABLED dev mode bypass
  - Expired and invalid token rejection
  - HITL actions include operator identity in audit
"""

from __future__ import annotations

import time

import pytest
from rbac import (
    PERMISSION_MATRIX,
    Role,
    UserSession,
    check_permission,
    create_token,
    validate_token,
)

# Use a ≥32-byte secret for all test JWT calls to avoid InsecureKeyLengthWarning
TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long!"

# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------


def test_role_values():
    assert Role.OBSERVER.value == "OBSERVER"
    assert Role.OPERATOR.value == "OPERATOR"
    assert Role.COMMANDER.value == "COMMANDER"
    assert Role.ADMIN.value == "ADMIN"


def test_role_ordering():
    roles = [Role.OBSERVER, Role.OPERATOR, Role.COMMANDER, Role.ADMIN]
    assert len(roles) == 4


# ---------------------------------------------------------------------------
# UserSession frozen dataclass
# ---------------------------------------------------------------------------


def test_user_session_frozen():
    session = UserSession(user_id="u1", role=Role.OPERATOR, token_exp=9999999999)
    with pytest.raises((AttributeError, TypeError)):
        session.user_id = "changed"


def test_user_session_fields():
    session = UserSession(user_id="alice", role=Role.COMMANDER, token_exp=1234567890)
    assert session.user_id == "alice"
    assert session.role == Role.COMMANDER
    assert session.token_exp == 1234567890


# ---------------------------------------------------------------------------
# create_token / validate_token
# ---------------------------------------------------------------------------


def test_create_token_returns_string():
    token = create_token("user1", Role.OPERATOR, secret=TEST_JWT_SECRET)
    assert isinstance(token, str)
    assert len(token) > 20


@pytest.fixture(autouse=False)
def auth_enabled(monkeypatch):
    """Disable AUTH_DISABLED so real JWT validation runs."""
    import rbac as rbac_mod

    monkeypatch.setattr(rbac_mod, "AUTH_DISABLED", False)


def test_validate_token_returns_user_session(auth_enabled):
    token = create_token("user42", Role.COMMANDER, secret=TEST_JWT_SECRET)
    session = validate_token(token, secret=TEST_JWT_SECRET)
    assert isinstance(session, UserSession)
    assert session.user_id == "user42"
    assert session.role == Role.COMMANDER


def test_validate_token_wrong_secret_raises(auth_enabled):
    token = create_token("u1", Role.ADMIN, secret=TEST_JWT_SECRET)
    with pytest.raises(Exception):
        validate_token(token, secret="wrong-secret-that-is-at-least-32-bytes-!")


def test_validate_token_invalid_token_raises(auth_enabled):
    with pytest.raises(Exception):
        validate_token("not.a.jwt.token", secret=TEST_JWT_SECRET)


def test_validate_token_expired_raises(auth_enabled):
    # Create a token already expired (exp = 1 second in the past)
    token = create_token("u1", Role.OPERATOR, secret=TEST_JWT_SECRET, expires_in_seconds=-10)
    with pytest.raises(Exception):
        validate_token(token, secret=TEST_JWT_SECRET)


def test_validate_token_exp_field_set(auth_enabled):
    token = create_token("u1", Role.OBSERVER, secret=TEST_JWT_SECRET, expires_in_seconds=3600)
    session = validate_token(token, secret=TEST_JWT_SECRET)
    # exp should be in the future
    assert session.token_exp > int(time.time())


def test_token_role_round_trip(auth_enabled):
    for role in Role:
        token = create_token("test", role, secret=TEST_JWT_SECRET)
        session = validate_token(token, secret=TEST_JWT_SECRET)
        assert session.role == role


# ---------------------------------------------------------------------------
# Permission matrix — OBSERVER (view only)
# ---------------------------------------------------------------------------


def test_observer_can_subscribe(auth_enabled):
    assert check_permission(Role.OBSERVER, "subscribe") is True


def test_observer_can_subscribe_sensor_feed(auth_enabled):
    assert check_permission(Role.OBSERVER, "subscribe_sensor_feed") is True


def test_observer_cannot_approve_nomination(auth_enabled):
    assert check_permission(Role.OBSERVER, "approve_nomination") is False


def test_observer_cannot_reject_nomination(auth_enabled):
    assert check_permission(Role.OBSERVER, "reject_nomination") is False


def test_observer_cannot_authorize_coa(auth_enabled):
    assert check_permission(Role.OBSERVER, "authorize_coa") is False


def test_observer_cannot_move_drone(auth_enabled):
    assert check_permission(Role.OBSERVER, "move_drone") is False


def test_observer_cannot_request_swarm(auth_enabled):
    assert check_permission(Role.OBSERVER, "request_swarm") is False


# ---------------------------------------------------------------------------
# Permission matrix — OPERATOR (assign drones, no strike auth)
# ---------------------------------------------------------------------------


def test_operator_can_move_drone(auth_enabled):
    assert check_permission(Role.OPERATOR, "move_drone") is True


def test_operator_can_follow_target(auth_enabled):
    assert check_permission(Role.OPERATOR, "follow_target") is True


def test_operator_can_request_swarm(auth_enabled):
    assert check_permission(Role.OPERATOR, "request_swarm") is True


def test_operator_can_scan_area(auth_enabled):
    assert check_permission(Role.OPERATOR, "scan_area") is True


def test_operator_cannot_authorize_coa(auth_enabled):
    assert check_permission(Role.OPERATOR, "authorize_coa") is False


def test_operator_cannot_approve_nomination(auth_enabled):
    assert check_permission(Role.OPERATOR, "approve_nomination") is False


# ---------------------------------------------------------------------------
# Permission matrix — COMMANDER (approve/authorize strikes)
# ---------------------------------------------------------------------------


def test_commander_can_approve_nomination(auth_enabled):
    assert check_permission(Role.COMMANDER, "approve_nomination") is True


def test_commander_can_reject_nomination(auth_enabled):
    assert check_permission(Role.COMMANDER, "reject_nomination") is True


def test_commander_can_authorize_coa(auth_enabled):
    assert check_permission(Role.COMMANDER, "authorize_coa") is True


def test_commander_can_reject_coa(auth_enabled):
    assert check_permission(Role.COMMANDER, "reject_coa") is True


def test_commander_can_move_drone(auth_enabled):
    assert check_permission(Role.COMMANDER, "move_drone") is True


def test_commander_cannot_do_admin_actions(auth_enabled):
    assert check_permission(Role.COMMANDER, "config_update") is False
    assert check_permission(Role.COMMANDER, "admin_reset") is False


# ---------------------------------------------------------------------------
# Permission matrix — ADMIN (all access)
# ---------------------------------------------------------------------------


def test_admin_can_do_all_actions(auth_enabled):
    all_actions = set(PERMISSION_MATRIX.keys())
    for action in all_actions:
        assert check_permission(Role.ADMIN, action) is True, f"ADMIN denied: {action}"


def test_admin_can_config_update(auth_enabled):
    assert check_permission(Role.ADMIN, "config_update") is True


def test_admin_can_admin_reset(auth_enabled):
    assert check_permission(Role.ADMIN, "admin_reset") is True


# ---------------------------------------------------------------------------
# AUTH_DISABLED dev mode
# ---------------------------------------------------------------------------


def test_auth_disabled_validate_returns_admin_session(monkeypatch):
    import rbac as rbac_mod

    monkeypatch.setattr(rbac_mod, "AUTH_DISABLED", True)
    session = validate_token("any-token-or-garbage", secret="ignored")
    assert isinstance(session, UserSession)
    assert session.role == Role.ADMIN
    assert session.user_id == "dev"


def test_auth_disabled_check_permission_allows_all(monkeypatch):
    import rbac as rbac_mod

    monkeypatch.setattr(rbac_mod, "AUTH_DISABLED", True)
    assert check_permission(Role.OBSERVER, "authorize_coa") is True


def test_auth_disabled_false_enforces_checks(monkeypatch):
    import rbac as rbac_mod

    monkeypatch.setattr(rbac_mod, "AUTH_DISABLED", False)
    assert check_permission(Role.OBSERVER, "authorize_coa") is False


# ---------------------------------------------------------------------------
# HITL operator identity audit
# ---------------------------------------------------------------------------


def test_hitl_manager_approve_records_operator_id():
    from hitl_manager import HITLManager

    mgr = HITLManager()
    entry = mgr.nominate_target(
        target_data={
            "target_id": 1,
            "target_type": "SAM",
            "target_location": [45.0, 25.0],
            "detection_confidence": 0.9,
        },
        evaluation={
            "priority_score": 0.8,
            "roe_evaluation": "AUTHORIZED",
            "reasoning_trace": "test",
        },
    )
    updated = mgr.approve_nomination(entry.id, rationale="clear target", operator_id="alice")
    assert updated.decision is not None
    assert updated.decision.get("operator_id") == "alice"


def test_hitl_manager_reject_records_operator_id():
    from hitl_manager import HITLManager

    mgr = HITLManager()
    entry = mgr.nominate_target(
        target_data={
            "target_id": 2,
            "target_type": "TEL",
            "target_location": [46.0, 26.0],
            "detection_confidence": 0.85,
        },
        evaluation={
            "priority_score": 0.7,
            "roe_evaluation": "AUTHORIZED",
            "reasoning_trace": "test",
        },
    )
    updated = mgr.reject_nomination(entry.id, rationale="civilian risk", operator_id="bob")
    assert updated.decision is not None
    assert updated.decision.get("operator_id") == "bob"


def test_hitl_manager_backward_compat_no_operator_id():
    """Calling without operator_id should not raise (backward compat)."""
    from hitl_manager import HITLManager

    mgr = HITLManager()
    entry = mgr.nominate_target(
        target_data={
            "target_id": 3,
            "target_type": "CP",
            "target_location": [47.0, 27.0],
            "detection_confidence": 0.75,
        },
        evaluation={
            "priority_score": 0.6,
            "roe_evaluation": "AUTHORIZED",
            "reasoning_trace": "test",
        },
    )
    # Should not raise even without operator_id
    updated = mgr.approve_nomination(entry.id, rationale="ok")
    assert updated.status == "APPROVED"
