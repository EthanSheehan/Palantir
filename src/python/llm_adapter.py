"""
llm_adapter.py
==============
Unified LLM interface with provider chain:
  1. Google Gemini (API key required — primary)
  2. Anthropic Claude (API key required)
  3. Ollama (local, free)
  4. Heuristic fallback (always available)

Supports model hints ("fast", "reasoning", "default") mapped to provider-
specific models. When no LLM is reachable, every call returns a deterministic
heuristic response so the rest of the pipeline keeps running.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Immutable response container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: int


# ---------------------------------------------------------------------------
# Model-hint mappings per provider
# ---------------------------------------------------------------------------

_GEMINI_MODEL_MAP: dict[str, str] = {
    "fast": "gemini-2.0-flash",
    "default": "gemini-2.0-flash",
    "reasoning": "gemini-2.5-pro-preview-06-05",
}

_ANTHROPIC_MODEL_MAP: dict[str, str] = {
    "fast": "claude-haiku-4-5-20251001",
    "default": "claude-sonnet-4-6",
    "reasoning": "claude-sonnet-4-6",
}

_OLLAMA_MODEL_MAP: dict[str, str] = {
    "fast": "llama3.2:8b",
    "default": "llama3.2:8b",
    "reasoning": "llama3.3:70b",
}

_HEURISTIC_RESPONSE = LLMResponse(
    content="[HEURISTIC] No LLM available. Using rule-based logic.",
    model="heuristic",
    provider="fallback",
    tokens_used=0,
)


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------


def _probe_gemini() -> tuple[bool, str]:
    """Check if Gemini API key is set and the SDK is installed."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return (False, "")
    try:
        from google import genai  # noqa: F401

        return (True, api_key)
    except ImportError:
        logger.warning("google_genai_sdk_not_installed", hint="pip install google-genai")
        return (False, "")


def _probe_anthropic() -> tuple[bool, str]:
    """Check if Anthropic API key is set and the SDK is installed."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return (False, "")
    try:
        import anthropic  # noqa: F401

        return (True, api_key)
    except ImportError:
        logger.warning("anthropic_sdk_not_installed", hint="pip install anthropic")
        return (False, "")


def _probe_ollama(base_url: str) -> tuple[bool, list[str]]:
    """Check whether Ollama is reachable and return (ok, model_names)."""
    try:
        import ollama as _ollama_pkg

        client = _ollama_pkg.Client(host=base_url)
        response = client.list()
        models = [m.model for m in getattr(response, "models", [])]
        return (True, models)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ollama_probe_failed", error=str(exc))
        return (False, [])


def _resolve_ollama_model(hint: str, available: list[str]) -> str:
    """Pick the best available Ollama model for a given hint."""
    preferred = _OLLAMA_MODEL_MAP.get(hint, _OLLAMA_MODEL_MAP["default"])
    if preferred in available:
        return preferred
    if available:
        return available[0]
    return preferred


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------


class LLMAdapter:
    """Unified LLM interface with provider chain and fallback."""

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        anthropic_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ) -> None:
        self._ollama_base_url = ollama_base_url
        self._anthropic_api_key = anthropic_api_key or ""
        self._gemini_api_key = gemini_api_key or ""

        # Provider state
        self._gemini_available = False
        self._anthropic_available = False
        self._ollama_available = False
        self._ollama_models: list[str] = []
        self._fallback_only = True

        self._detect_providers()

    # -- Provider detection --------------------------------------------------

    def _detect_providers(self) -> None:
        # Try Gemini first (preferred — user's primary provider)
        if self._gemini_api_key:
            try:
                from google import genai  # noqa: F401

                self._gemini_available = True
                self._fallback_only = False
                logger.info("gemini_connected", model_map=_GEMINI_MODEL_MAP)
            except ImportError:
                logger.warning("google_genai_sdk_not_installed")
        else:
            ok, key = _probe_gemini()
            if ok:
                self._gemini_api_key = key
                self._gemini_available = True
                self._fallback_only = False
                logger.info("gemini_connected", model_map=_GEMINI_MODEL_MAP)

        # Try Anthropic as secondary
        if self._anthropic_api_key:
            try:
                import anthropic  # noqa: F401

                self._anthropic_available = True
                self._fallback_only = False
                logger.info("anthropic_connected", model_map=_ANTHROPIC_MODEL_MAP)
            except ImportError:
                logger.warning("anthropic_sdk_not_installed")
        else:
            ok, key = _probe_anthropic()
            if ok:
                self._anthropic_api_key = key
                self._anthropic_available = True
                self._fallback_only = False
                logger.info("anthropic_connected", model_map=_ANTHROPIC_MODEL_MAP)

        # Try Ollama as tertiary
        ok, models = _probe_ollama(self._ollama_base_url)
        self._ollama_available = ok
        self._ollama_models = models

        if ok and models:
            self._fallback_only = False
            logger.info("ollama_connected", models=models)

        if self._fallback_only:
            logger.warning(
                "no_llm_providers",
                hint="Set GEMINI_API_KEY, ANTHROPIC_API_KEY, or start Ollama with `ollama serve`",
            )

    # -- Public API ----------------------------------------------------------

    async def complete(
        self,
        messages: list[dict[str, str]],
        model_hint: str = "default",
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send a completion request to the best available provider."""
        if self._fallback_only:
            return _HEURISTIC_RESPONSE

        # Prefer Gemini (primary)
        if self._gemini_available:
            return await self._gemini_complete(messages, model_hint, temperature, max_tokens)

        # Anthropic (secondary)
        if self._anthropic_available:
            return await self._anthropic_complete(messages, model_hint, temperature, max_tokens)

        # Ollama (tertiary)
        if self._ollama_available:
            model = _resolve_ollama_model(model_hint, self._ollama_models)
            return await self._ollama_complete(messages, model, temperature, max_tokens)

        return _HEURISTIC_RESPONSE

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],
        model_hint: str = "default",
    ) -> dict[str, Any]:
        """Get a structured JSON response matching *response_schema*."""
        schema_instruction = (
            "You MUST respond with valid JSON that conforms to the following "
            f"JSON schema:\n```json\n{json.dumps(response_schema, indent=2)}\n```\n"
            "Return ONLY the JSON object, no markdown fences, no commentary."
        )

        augmented: list[dict[str, str]] = [
            {"role": "system", "content": schema_instruction},
            *messages,
        ]

        response = await self.complete(augmented, model_hint=model_hint, temperature=0.1)

        if response.provider == "fallback":
            return {}

        return _parse_json_permissive(response.content)

    def is_available(self) -> bool:
        """Return True if at least one LLM provider is reachable."""
        return not self._fallback_only

    def get_provider_status(self) -> dict[str, Any]:
        """Return status of all providers."""
        return {
            "gemini": {
                "available": self._gemini_available,
                "models": _GEMINI_MODEL_MAP,
            },
            "anthropic": {
                "available": self._anthropic_available,
                "models": _ANTHROPIC_MODEL_MAP,
            },
            "ollama": {
                "available": self._ollama_available,
                "base_url": self._ollama_base_url,
                "models": list(self._ollama_models),
            },
            "fallback_only": self._fallback_only,
        }

    # -- Gemini backend ------------------------------------------------------

    async def _gemini_complete(
        self,
        messages: list[dict[str, str]],
        model_hint: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Call Google Gemini API and return an immutable LLMResponse."""
        try:
            from google import genai
            from google.genai import types

            model = _GEMINI_MODEL_MAP.get(model_hint, _GEMINI_MODEL_MAP["default"])
            client = genai.Client(api_key=self._gemini_api_key)

            # Separate system message from user/assistant messages
            system_instruction = ""
            contents: list[types.Content] = []
            for msg in messages:
                role = msg.get("role", "user")
                text = msg.get("content", "")
                if role == "system":
                    system_instruction += text + "\n"
                else:
                    # Gemini uses "user" and "model" roles
                    gemini_role = "model" if role == "assistant" else "user"
                    contents.append(
                        types.Content(
                            role=gemini_role,
                            parts=[types.Part.from_text(text=text)],
                        )
                    )

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            if system_instruction.strip():
                config.system_instruction = system_instruction.strip()

            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            content = response.text or ""
            tokens = 0
            if response.usage_metadata:
                tokens = (response.usage_metadata.prompt_token_count or 0) + (
                    response.usage_metadata.candidates_token_count or 0
                )

            return LLMResponse(
                content=content,
                model=model,
                provider="gemini",
                tokens_used=tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("gemini_completion_failed", error=str(exc))
            # Try Anthropic as fallback
            if self._anthropic_available:
                return await self._anthropic_complete(messages, model_hint, temperature, max_tokens)
            # Try Ollama as fallback
            if self._ollama_available:
                ollama_model = _resolve_ollama_model(model_hint, self._ollama_models)
                return await self._ollama_complete(messages, ollama_model, temperature, max_tokens)
            return _HEURISTIC_RESPONSE

    # -- Anthropic backend ---------------------------------------------------

    async def _anthropic_complete(
        self,
        messages: list[dict[str, str]],
        model_hint: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Call Anthropic Claude API and return an immutable LLMResponse."""
        try:
            import anthropic

            model = _ANTHROPIC_MODEL_MAP.get(model_hint, _ANTHROPIC_MODEL_MAP["default"])
            client = anthropic.AsyncAnthropic(api_key=self._anthropic_api_key)

            # Separate system message from user messages
            system_msg = ""
            chat_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    system_msg += msg.get("content", "") + "\n"
                else:
                    chat_messages.append(msg)

            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": chat_messages,
            }
            if system_msg.strip():
                kwargs["system"] = system_msg.strip()

            response = await client.messages.create(**kwargs)

            content = response.content[0].text if response.content else ""
            tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

            return LLMResponse(
                content=content,
                model=model,
                provider="anthropic",
                tokens_used=tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("anthropic_completion_failed", error=str(exc))
            # Try Ollama as fallback
            if self._ollama_available:
                ollama_model = _resolve_ollama_model(model_hint, self._ollama_models)
                return await self._ollama_complete(messages, ollama_model, temperature, max_tokens)
            return _HEURISTIC_RESPONSE

    # -- Ollama backend ------------------------------------------------------

    async def _ollama_complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Call Ollama chat endpoint and return an immutable LLMResponse."""
        try:
            import ollama as _ollama_pkg

            client = _ollama_pkg.AsyncClient(host=self._ollama_base_url)
            response = await client.chat(
                model=model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            content = response.message.content or ""
            tokens = (getattr(response, "eval_count", 0) or 0) + (getattr(response, "prompt_eval_count", 0) or 0)

            return LLMResponse(
                content=content,
                model=model,
                provider="ollama",
                tokens_used=tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ollama_completion_failed", model=model, error=str(exc))
            return _HEURISTIC_RESPONSE


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def _parse_json_permissive(text: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from LLM output."""
    stripped = text.strip()

    # Strip markdown code fences if present
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("json_parse_failed", text_preview=stripped[:200])
        return {}
