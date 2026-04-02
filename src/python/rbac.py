"""Role-Based Access Control with JWT authentication (W5-006).

Roles (ascending privilege):
  OBSERVER  — view only (subscribe, read state)
  OPERATOR  — drone assignment and ISR tasking
  COMMANDER — HITL approvals and strike authorization
  ADMIN     — full access including config

AUTH_DISABLED=true (env var) bypasses all checks — returns ADMIN dev session.
JWT_SECRET env var sets the signing secret (required when auth is enabled).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import Enum

import jwt

# ---------------------------------------------------------------------------
# Module-level flag — read from environment; tests can monkeypatch.
# NOTE: These are intentionally read once at import time. Changing the env
# vars after process start has no effect; a restart is required.
# JWT_SECRET validation is intentionally lazy (checked in validate_token)
# so that importing this module never raises, even during tests.
# ---------------------------------------------------------------------------
AUTH_DISABLED: bool = os.environ.get("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")

_raw_secret: str | None = os.environ.get("JWT_SECRET")
# Dev/test mode: allow short or missing secret (fallback to dev placeholder).
# When AUTH_DISABLED is False the secret is validated lazily in validate_token().
JWT_SECRET: str = _raw_secret if _raw_secret else "amc-grid-dev-secret"

_DEFAULT_EXPIRY = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------


class Role(str, Enum):
    OBSERVER = "OBSERVER"
    OPERATOR = "OPERATOR"
    COMMANDER = "COMMANDER"
    ADMIN = "ADMIN"


# Numeric level — used for "at least" comparisons in the matrix
_ROLE_LEVEL: dict[Role, int] = {
    Role.OBSERVER: 0,
    Role.OPERATOR: 1,
    Role.COMMANDER: 2,
    Role.ADMIN: 3,
}


# ---------------------------------------------------------------------------
# UserSession
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserSession:
    user_id: str
    role: Role
    token_exp: int  # Unix timestamp


# ---------------------------------------------------------------------------
# Permission matrix
# Action → minimum Role required
# ---------------------------------------------------------------------------

PERMISSION_MATRIX: dict[str, Role] = {
    # Read / subscribe — OBSERVER and above
    "subscribe": Role.OBSERVER,
    "subscribe_sensor_feed": Role.OBSERVER,
    "sitrep_query": Role.OBSERVER,
    "generate_sitrep": Role.OBSERVER,
    # Drone & ISR operations — OPERATOR and above
    "move_drone": Role.OPERATOR,
    "follow_target": Role.OPERATOR,
    "paint_target": Role.OPERATOR,
    "intercept_target": Role.OPERATOR,
    "intercept_enemy": Role.OPERATOR,
    "cancel_track": Role.OPERATOR,
    "scan_area": Role.OPERATOR,
    "spike": Role.OPERATOR,
    "retask_sensors": Role.OPERATOR,
    "retask_nomination": Role.OPERATOR,
    "verify_target": Role.OPERATOR,
    "set_drone_autonomy": Role.OPERATOR,
    "approve_transition": Role.OPERATOR,
    "reject_transition": Role.OPERATOR,
    "request_swarm": Role.OPERATOR,
    "release_swarm": Role.OPERATOR,
    "set_coverage_mode": Role.OPERATOR,
    "launch_drone": Role.OPERATOR,
    # HITL / strike authorization — COMMANDER and above
    "approve_nomination": Role.COMMANDER,
    "reject_nomination": Role.COMMANDER,
    "authorize_coa": Role.COMMANDER,
    "reject_coa": Role.COMMANDER,
    "set_autonomy_level": Role.COMMANDER,
    # Admin / config — ADMIN only
    "config_update": Role.ADMIN,
    "admin_reset": Role.ADMIN,
    "set_roe": Role.ADMIN,
    "reset": Role.ADMIN,
    "SET_SCENARIO": Role.ADMIN,
    # Simulator data ingest — OPERATOR and above (simulator clients)
    "DRONE_FEED": Role.OPERATOR,
    "TRACK_UPDATE": Role.OPERATOR,
    "TRACK_UPDATE_BATCH": Role.OPERATOR,
}


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_token(
    user_id: str,
    role: Role,
    secret: str,
    expires_in_seconds: int = _DEFAULT_EXPIRY,
) -> str:
    """Create a signed JWT encoding user_id, role, and expiry."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role.value,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def validate_token(token: str, secret: str) -> UserSession:
    """Decode and validate a JWT.

    Returns a UserSession on success.
    When AUTH_DISABLED is True, skips all checks and returns a dev ADMIN session.
    Raises jwt.PyJWTError (or subclass) on any failure.
    """
    if AUTH_DISABLED:
        return UserSession(
            user_id="dev",
            role=Role.ADMIN,
            token_exp=int(time.time()) + _DEFAULT_EXPIRY,
        )

    if len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters when AUTH_DISABLED is false. "
            "Set AUTH_DISABLED=true for local development."
        )

    payload = jwt.decode(token, secret, algorithms=["HS256"])
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or len(sub) > 128:
        raise jwt.InvalidTokenError("JWT 'sub' field must be a non-empty string of at most 128 characters")
    role = Role(payload["role"])
    return UserSession(
        user_id=sub,
        role=role,
        token_exp=int(payload["exp"]),
    )


# ---------------------------------------------------------------------------
# Permission check
# ---------------------------------------------------------------------------


def check_permission(role: Role, action: str) -> bool:
    """Return True if *role* is allowed to perform *action*.

    When AUTH_DISABLED is True, all checks pass.
    Unknown actions default to ADMIN-only.
    """
    if AUTH_DISABLED:
        return True

    min_role = PERMISSION_MATRIX.get(action, Role.ADMIN)
    return _ROLE_LEVEL[role] >= _ROLE_LEVEL[min_role]
