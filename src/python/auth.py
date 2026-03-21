"""WebSocket token authentication (W3-006).

Provides tiered API-key authentication for WebSocket connections.
Token tiers: SIMULATOR (data ingest only), DASHBOARD (full operator), ADMIN (config).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class TokenTier(str, Enum):
    SIMULATOR = "SIMULATOR"
    DASHBOARD = "DASHBOARD"
    ADMIN = "ADMIN"


# ---------------------------------------------------------------------------
# Permission sets
# ---------------------------------------------------------------------------

SIMULATOR_ACTIONS: frozenset[str] = frozenset(
    {
        "DRONE_FEED",
        "TRACK_UPDATE",
        "TRACK_UPDATE_BATCH",
    }
)

ADMIN_ACTIONS: frozenset[str] = frozenset(
    {
        "set_roe",
        "config_update",
        "admin_reset",
    }
)

# DASHBOARD gets everything that isn't admin-only.
# We define it explicitly for the actions that exist in the dispatch table,
# but the authorization logic uses a deny-list approach: DASHBOARD can do
# anything except ADMIN_ACTIONS.
DASHBOARD_ACTIONS: frozenset[str] = frozenset(
    {
        "spike",
        "move_drone",
        "SET_SCENARIO",
        "follow_target",
        "paint_target",
        "intercept_target",
        "intercept_enemy",
        "cancel_track",
        "scan_area",
        "approve_nomination",
        "reject_nomination",
        "retask_nomination",
        "authorize_coa",
        "reject_coa",
        "verify_target",
        "sitrep_query",
        "generate_sitrep",
        "retask_sensors",
        "reset",
        "set_autonomy_level",
        "set_drone_autonomy",
        "approve_transition",
        "reject_transition",
        "request_swarm",
        "release_swarm",
        "set_coverage_mode",
        "subscribe",
        "subscribe_sensor_feed",
        "DRONE_FEED",
        "TRACK_UPDATE",
        "TRACK_UPDATE_BATCH",
    }
)


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool = True
    tokens: dict[str, TokenTier] = field(default_factory=dict)
    demo_token: str = "dev"


class AuthManager:
    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    @property
    def config(self) -> AuthConfig:
        return self._config

    def authenticate(self, token: str | None) -> TokenTier | None:
        if not self._config.enabled:
            return TokenTier.DASHBOARD

        if not token:
            return None

        # Explicit token map takes priority
        tier = self._config.tokens.get(token)
        if tier is not None:
            return tier

        # Demo token bypass
        if token == self._config.demo_token:
            return TokenTier.DASHBOARD

        return None

    def is_authorized(self, tier: TokenTier, action: str) -> bool:
        if tier == TokenTier.ADMIN:
            return True
        if tier == TokenTier.DASHBOARD:
            return action not in ADMIN_ACTIONS
        if tier == TokenTier.SIMULATOR:
            return action in SIMULATOR_ACTIONS
        return False

    @classmethod
    def from_env(cls) -> AuthManager:
        disabled = os.environ.get("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")
        demo_token = os.environ.get("DEMO_TOKEN", "dev")

        tokens: dict[str, TokenTier] = {}
        for raw in _split_csv(os.environ.get("DASHBOARD_TOKENS", "")):
            tokens[raw] = TokenTier.DASHBOARD
        for raw in _split_csv(os.environ.get("SIMULATOR_TOKENS", "")):
            tokens[raw] = TokenTier.SIMULATOR
        for raw in _split_csv(os.environ.get("ADMIN_TOKENS", "")):
            tokens[raw] = TokenTier.ADMIN

        return cls(
            AuthConfig(
                enabled=not disabled,
                tokens=tokens,
                demo_token=demo_token,
            )
        )


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]
