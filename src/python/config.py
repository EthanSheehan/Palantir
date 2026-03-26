"""
Centralised configuration loaded from environment variables.

Uses pydantic-settings to validate all required env vars at startup.
Import ``settings`` anywhere to access validated config values.
"""

import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class PalantirSettings(BaseSettings):
    """All environment variables consumed by the Palantir C2 system."""

    # -- Required for LangChain / OpenAI agent features --
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key for LLM agent features (optional when using Ollama)",
    )

    # -- Optional: Anthropic Claude --
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key (optional, for Claude-based agents)",
    )

    # -- Optional: Google Gemini --
    gemini_api_key: str = Field(
        default="",
        description="Gemini API key (optional, for Gemini-based agents)",
    )

    # -- Server --
    host: str = Field(default="0.0.0.0", description="Bind address for the API server")
    port: int = Field(default=8000, description="Port for the API server")
    log_level: str = Field(default="INFO", description="Logging level")

    # -- Simulation --
    simulation_hz: int = Field(default=10, description="Simulation tick rate in Hz")
    default_theater: str = Field(default="romania", description="Default theater to load")

    # -- WebSocket --
    ws_backend_url: str = Field(
        default="ws://localhost:8000/ws",
        description="Backend WebSocket URL for simulator clients",
    )

    # -- Demo mode --
    demo_mode: bool = Field(
        default=False,
        description="Enable demo auto-pilot: auto-approve, auto-COA, auto-engage",
    )

    # -- Autopilot timing (seconds) --
    autopilot_scan_delay: float = Field(
        default=2.0,
        description="Seconds between main autopilot scan loop iterations",
    )
    autopilot_authorize_delay: float = Field(
        default=5.0,
        description="Seconds autopilot waits before auto-approving a PENDING nomination",
    )
    autopilot_follow_delay: float = Field(
        default=4.0,
        description="Seconds autopilot waits before dispatching a UAV to follow a target",
    )
    autopilot_paint_delay: float = Field(
        default=5.0,
        description="Seconds autopilot waits before issuing a paint/lock command",
    )

    # -- Demo FAST verification thresholds --
    demo_fast_classify_time: float = Field(
        default=5.0,
        description="Sustained-detect seconds threshold for DETECTED->CLASSIFIED in demo-fast mode",
    )
    demo_fast_verify_time: float = Field(
        default=8.0,
        description="Sustained-detect seconds threshold for CLASSIFIED->VERIFIED in demo-fast mode",
    )

    # -- Simulation physics constants --
    uav_speed_mps: float = Field(
        default=60.0,
        description="Default UAV airspeed in metres per second",
    )
    detection_range_km: float = Field(
        default=15.0,
        description="Maximum sensor detection range in kilometres",
    )
    swarm_task_expiry_s: float = Field(
        default=120.0,
        description="Seconds before an unexecuted swarm task is discarded",
    )
    tick_rate_hz: float = Field(
        default=10.0,
        description="Simulation tick rate in Hz",
    )
    max_turn_rate_dps: float = Field(
        default=3.0,
        description="Maximum UAV turn rate in degrees per second (fixed-wing standard rate turn)",
    )
    idle_count_threshold: int = Field(
        default=3,
        description="Minimum number of idle UAVs to maintain before threat-adaptive swarm dispatch",
    )

    # -- TLS / SSL --
    ssl_enabled: bool = Field(
        default=False,
        description="Enable TLS/SSL for the uvicorn server",
    )
    ssl_certfile: str | None = Field(
        default=None,
        description="Path to SSL certificate file (PEM format)",
    )
    ssl_keyfile: str | None = Field(
        default=None,
        description="Path to SSL private key file (PEM format)",
    )
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed WebSocket connection origins; localhost always allowed in dev",
    )

    # -- Auth (W3-006) --
    auth_enabled: bool = Field(
        default=False,
        description="Enable WebSocket token authentication (default disabled for backward compat)",
    )
    demo_token: str = Field(
        default="dev",
        description="Dev bypass token (always authenticates as DASHBOARD)",
    )
    dashboard_tokens: str = Field(
        default="",
        description="Comma-separated DASHBOARD-tier API keys",
    )
    simulator_tokens: str = Field(
        default="",
        description="Comma-separated SIMULATOR-tier API keys",
    )
    admin_tokens: str = Field(
        default="",
        description="Comma-separated ADMIN-tier API keys",
    )

    @model_validator(mode="after")
    def _validate_ssl(self) -> "PalantirSettings":
        if self.ssl_enabled:
            if not self.ssl_certfile:
                raise ValueError("ssl_certfile must be set when ssl_enabled is True")
            if not self.ssl_keyfile:
                raise ValueError("ssl_keyfile must be set when ssl_enabled is True")
            if not os.path.isfile(self.ssl_certfile):
                raise ValueError(f"ssl_certfile does not exist: {self.ssl_certfile}")
            if not os.path.isfile(self.ssl_keyfile):
                raise ValueError(f"ssl_keyfile does not exist: {self.ssl_keyfile}")
        return self

    @model_validator(mode="after")
    def _validate_demo_token(self) -> "PalantirSettings":
        if self.auth_enabled and self.demo_token == "dev":
            import warnings
            warnings.warn(
                "auth_enabled=True but demo_token is still 'dev' — "
                "rotate demo_token for production",
                UserWarning,
                stacklevel=2,
            )
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def load_settings() -> PalantirSettings:
    """Load and validate settings. Raises ``ValidationError`` on missing required vars."""
    return PalantirSettings()
