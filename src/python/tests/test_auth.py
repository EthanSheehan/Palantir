"""Tests for WebSocket token authentication (W3-006)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from auth import (
    ADMIN_ACTIONS,
    DASHBOARD_ACTIONS,
    SIMULATOR_ACTIONS,
    AuthConfig,
    AuthManager,
    TokenTier,
)

# ---------------------------------------------------------------------------
# TokenTier enum
# ---------------------------------------------------------------------------


def test_token_tier_values():
    assert TokenTier.SIMULATOR.value == "SIMULATOR"
    assert TokenTier.DASHBOARD.value == "DASHBOARD"
    assert TokenTier.ADMIN.value == "ADMIN"


# ---------------------------------------------------------------------------
# AuthConfig frozen dataclass
# ---------------------------------------------------------------------------


def test_auth_config_defaults():
    cfg = AuthConfig()
    assert cfg.enabled is True
    assert cfg.tokens == {}
    assert cfg.demo_token == "dev"


def test_auth_config_is_frozen():
    cfg = AuthConfig()
    with pytest.raises(AttributeError):
        cfg.enabled = False


def test_auth_config_custom():
    tokens = {"tok1": TokenTier.DASHBOARD, "tok2": TokenTier.SIMULATOR}
    cfg = AuthConfig(enabled=False, tokens=tokens, demo_token="mydev")
    assert cfg.enabled is False
    assert cfg.tokens == tokens
    assert cfg.demo_token == "mydev"


# ---------------------------------------------------------------------------
# AuthManager.authenticate
# ---------------------------------------------------------------------------


def test_authenticate_valid_dashboard_token():
    cfg = AuthConfig(tokens={"dash-key": TokenTier.DASHBOARD})
    mgr = AuthManager(cfg)
    assert mgr.authenticate("dash-key") == TokenTier.DASHBOARD


def test_authenticate_valid_simulator_token():
    cfg = AuthConfig(tokens={"sim-key": TokenTier.SIMULATOR})
    mgr = AuthManager(cfg)
    assert mgr.authenticate("sim-key") == TokenTier.SIMULATOR


def test_authenticate_valid_admin_token():
    cfg = AuthConfig(tokens={"admin-key": TokenTier.ADMIN})
    mgr = AuthManager(cfg)
    assert mgr.authenticate("admin-key") == TokenTier.ADMIN


def test_authenticate_invalid_token():
    cfg = AuthConfig(tokens={"real-key": TokenTier.DASHBOARD})
    mgr = AuthManager(cfg)
    assert mgr.authenticate("wrong-key") is None


def test_authenticate_empty_token():
    cfg = AuthConfig(tokens={"key": TokenTier.DASHBOARD})
    mgr = AuthManager(cfg)
    assert mgr.authenticate("") is None


def test_authenticate_none_token():
    cfg = AuthConfig(tokens={"key": TokenTier.DASHBOARD})
    mgr = AuthManager(cfg)
    assert mgr.authenticate(None) is None


def test_authenticate_demo_token_returns_dashboard():
    cfg = AuthConfig(demo_token="dev")
    mgr = AuthManager(cfg)
    assert mgr.authenticate("dev") == TokenTier.DASHBOARD


def test_authenticate_custom_demo_token():
    cfg = AuthConfig(demo_token="test-bypass")
    mgr = AuthManager(cfg)
    assert mgr.authenticate("test-bypass") == TokenTier.DASHBOARD


def test_authenticate_demo_token_overridden_by_explicit_token():
    """If a token exists in the token map AND is the demo token, the explicit tier wins."""
    cfg = AuthConfig(tokens={"dev": TokenTier.ADMIN}, demo_token="dev")
    mgr = AuthManager(cfg)
    assert mgr.authenticate("dev") == TokenTier.ADMIN


# ---------------------------------------------------------------------------
# AuthManager.is_authorized
# ---------------------------------------------------------------------------


def test_simulator_can_send_drone_feed():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.SIMULATOR, "DRONE_FEED") is True


def test_simulator_can_send_track_update():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.SIMULATOR, "TRACK_UPDATE") is True


def test_simulator_cannot_approve_nomination():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.SIMULATOR, "approve_nomination") is False


def test_simulator_cannot_authorize_coa():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.SIMULATOR, "authorize_coa") is False


def test_dashboard_can_approve_nomination():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.DASHBOARD, "approve_nomination") is True


def test_dashboard_can_move_drone():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.DASHBOARD, "move_drone") is True


def test_dashboard_cannot_do_admin_actions():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    for action in ADMIN_ACTIONS:
        assert mgr.is_authorized(TokenTier.DASHBOARD, action) is False, f"DASHBOARD should not have {action}"


def test_admin_can_do_everything():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    all_actions = SIMULATOR_ACTIONS | DASHBOARD_ACTIONS | ADMIN_ACTIONS
    for action in all_actions:
        assert mgr.is_authorized(TokenTier.ADMIN, action) is True, f"ADMIN should have {action}"


def test_unknown_action_denied_for_simulator():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.SIMULATOR, "nonexistent_action") is False


def test_unknown_action_allowed_for_dashboard():
    """DASHBOARD gets all non-admin actions; unknown actions are allowed."""
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.DASHBOARD, "some_future_action") is True


def test_unknown_action_allowed_for_admin():
    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    assert mgr.is_authorized(TokenTier.ADMIN, "some_future_action") is True


# ---------------------------------------------------------------------------
# AuthManager.from_env
# ---------------------------------------------------------------------------


def test_from_env_disabled():
    env = {"AUTH_DISABLED": "true"}
    with patch.dict(os.environ, env, clear=False):
        mgr = AuthManager.from_env()
    assert mgr.config.enabled is False


def test_from_env_enabled_with_tokens():
    env = {
        "AUTH_DISABLED": "false",
        "DEMO_TOKEN": "mydev",
        "DASHBOARD_TOKENS": "tok-a,tok-b",
        "SIMULATOR_TOKENS": "sim-1,sim-2",
        "ADMIN_TOKENS": "adm-1",
    }
    with patch.dict(os.environ, env, clear=False):
        mgr = AuthManager.from_env()
    assert mgr.config.enabled is True
    assert mgr.config.demo_token == "mydev"
    assert mgr.authenticate("tok-a") == TokenTier.DASHBOARD
    assert mgr.authenticate("tok-b") == TokenTier.DASHBOARD
    assert mgr.authenticate("sim-1") == TokenTier.SIMULATOR
    assert mgr.authenticate("sim-2") == TokenTier.SIMULATOR
    assert mgr.authenticate("adm-1") == TokenTier.ADMIN


def test_from_env_empty_tokens():
    env = {"AUTH_DISABLED": "false", "DASHBOARD_TOKENS": "", "SIMULATOR_TOKENS": ""}
    with patch.dict(os.environ, env, clear=False):
        mgr = AuthManager.from_env()
    assert mgr.config.tokens == {}


def test_from_env_default_demo_token():
    env = {"AUTH_DISABLED": "false"}
    with patch.dict(os.environ, env, clear=False):
        mgr = AuthManager.from_env()
    assert mgr.config.demo_token == "dev"


# ---------------------------------------------------------------------------
# Permission matrix completeness
# ---------------------------------------------------------------------------


def test_all_dispatch_actions_covered():
    """Every action in the WS dispatch table should be authorized for at least one tier."""
    from websocket_handlers import _DISPATCH_TABLE

    cfg = AuthConfig()
    mgr = AuthManager(cfg)
    for action in _DISPATCH_TABLE:
        authorized_by_any = any(mgr.is_authorized(tier, action) for tier in TokenTier)
        assert authorized_by_any, f"Action '{action}' is not authorized for any tier"


def test_simulator_actions_are_minimal():
    """SIMULATOR tier should have a very small allowlist."""
    assert len(SIMULATOR_ACTIONS) <= 5


# ---------------------------------------------------------------------------
# Auth disabled mode
# ---------------------------------------------------------------------------


def test_auth_disabled_authenticate_any_token():
    cfg = AuthConfig(enabled=False)
    mgr = AuthManager(cfg)
    assert mgr.authenticate("anything") == TokenTier.DASHBOARD
    assert mgr.authenticate("") == TokenTier.DASHBOARD
    assert mgr.authenticate(None) == TokenTier.DASHBOARD
