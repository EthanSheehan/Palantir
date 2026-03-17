"""
Centralised configuration loaded from environment variables.

Uses pydantic-settings to validate all required env vars at startup.
Import ``settings`` anywhere to access validated config values.
"""

from pydantic import Field
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def load_settings() -> PalantirSettings:
    """Load and validate settings. Raises ``ValidationError`` on missing required vars."""
    return PalantirSettings()
