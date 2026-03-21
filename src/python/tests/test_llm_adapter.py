"""
Tests for llm_adapter.py
=========================
Covers initialization, fallback behaviour, model hint mapping,
and structured output parsing — all without running providers.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")

from llm_adapter import (
    LLMAdapter,
    LLMResponse,
    _parse_json_permissive,
    _resolve_ollama_model,
)

# ---------------------------------------------------------------------------
# Helper: patch all probes to disable real provider detection
# ---------------------------------------------------------------------------


def _no_providers():
    """Context manager stack that disables all provider auto-detection."""
    return (
        patch("llm_adapter._probe_gemini", return_value=(False, "")),
        patch("llm_adapter._probe_anthropic", return_value=(False, "")),
        patch("llm_adapter._probe_ollama", return_value=(False, [])),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter_no_ollama():
    """LLMAdapter created when all providers are unreachable."""
    p1, p2, p3 = _no_providers()
    with p1, p2, p3:
        return LLMAdapter()


@pytest.fixture()
def adapter_with_ollama():
    """LLMAdapter created with a mocked Ollama that has two models."""
    models = ["llama3.2:8b", "llama3.3:70b"]
    p1, p2, _ = _no_providers()
    with p1, p2, patch("llm_adapter._probe_ollama", return_value=(True, models)):
        return LLMAdapter()


@pytest.fixture()
def adapter_with_gemini():
    """LLMAdapter created with a mocked Gemini provider."""
    _, p2, p3 = _no_providers()
    with (
        patch("llm_adapter._probe_gemini", return_value=(True, "fake-key")),
        p2,
        p3,
        patch.dict("sys.modules", {"google": MagicMock(), "google.genai": MagicMock()}),
    ):
        return LLMAdapter(gemini_api_key="fake-key")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    def test_no_crash_when_no_providers(self, adapter_no_ollama: LLMAdapter):
        assert adapter_no_ollama is not None

    def test_fallback_only_when_no_providers(self, adapter_no_ollama: LLMAdapter):
        assert adapter_no_ollama._fallback_only is True
        assert adapter_no_ollama.is_available() is False

    def test_available_when_ollama_connected(self, adapter_with_ollama: LLMAdapter):
        assert adapter_with_ollama._fallback_only is False
        assert adapter_with_ollama.is_available() is True

    def test_no_crash_when_ollama_has_no_models(self):
        p1, p2, _ = _no_providers()
        with p1, p2, patch("llm_adapter._probe_ollama", return_value=(True, [])):
            adapter = LLMAdapter()
        assert adapter._fallback_only is True
        assert adapter.is_available() is False

    def test_gemini_available(self, adapter_with_gemini: LLMAdapter):
        assert adapter_with_gemini._gemini_available is True
        assert adapter_with_gemini.is_available() is True


# ---------------------------------------------------------------------------
# Fallback responses
# ---------------------------------------------------------------------------


class TestFallback:
    @pytest.mark.asyncio
    async def test_complete_returns_heuristic_when_no_provider(self, adapter_no_ollama: LLMAdapter):
        resp = await adapter_no_ollama.complete([{"role": "user", "content": "hello"}])
        assert resp.provider == "fallback"
        assert resp.model == "heuristic"
        assert resp.tokens_used == 0
        assert "[HEURISTIC]" in resp.content

    @pytest.mark.asyncio
    async def test_structured_returns_empty_dict_when_no_provider(self, adapter_no_ollama: LLMAdapter):
        result = await adapter_no_ollama.complete_structured(
            [{"role": "user", "content": "hello"}],
            response_schema={"type": "object"},
        )
        assert result == {}


# ---------------------------------------------------------------------------
# Model hint mapping
# ---------------------------------------------------------------------------


class TestModelHints:
    def test_fast_resolves_to_small_model(self):
        available = ["llama3.2:8b", "llama3.3:70b"]
        assert _resolve_ollama_model("fast", available) == "llama3.2:8b"

    def test_reasoning_resolves_to_large_model(self):
        available = ["llama3.2:8b", "llama3.3:70b"]
        assert _resolve_ollama_model("reasoning", available) == "llama3.3:70b"

    def test_default_resolves_to_small_model(self):
        available = ["llama3.2:8b", "llama3.3:70b"]
        assert _resolve_ollama_model("default", available) == "llama3.2:8b"

    def test_falls_back_to_first_available(self):
        available = ["mistral:7b"]
        assert _resolve_ollama_model("fast", available) == "mistral:7b"

    def test_returns_preferred_when_nothing_available(self):
        assert _resolve_ollama_model("fast", []) == "llama3.2:8b"


# ---------------------------------------------------------------------------
# Provider status
# ---------------------------------------------------------------------------


class TestProviderStatus:
    def test_status_when_no_providers(self, adapter_no_ollama: LLMAdapter):
        status = adapter_no_ollama.get_provider_status()
        assert status["fallback_only"] is True
        assert status["ollama"]["available"] is False
        assert status["gemini"]["available"] is False

    def test_status_when_ollama_available(self, adapter_with_ollama: LLMAdapter):
        status = adapter_with_ollama.get_provider_status()
        assert status["fallback_only"] is False
        assert status["ollama"]["available"] is True
        assert "llama3.2:8b" in status["ollama"]["models"]


# ---------------------------------------------------------------------------
# Mocked Ollama completion
# ---------------------------------------------------------------------------


class TestOllamaCompletion:
    @pytest.mark.asyncio
    async def test_complete_calls_ollama_chat(self, adapter_with_ollama: LLMAdapter):
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_response = MagicMock()
        mock_response.message = mock_message
        mock_response.eval_count = 10
        mock_response.prompt_eval_count = 5

        with patch("ollama.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.chat = AsyncMock(return_value=mock_response)

            resp = await adapter_with_ollama.complete(
                [{"role": "user", "content": "test"}],
                model_hint="fast",
            )

        assert resp.content == "Test response"
        assert resp.provider == "ollama"
        assert resp.model == "llama3.2:8b"
        assert resp.tokens_used == 15

    @pytest.mark.asyncio
    async def test_complete_returns_fallback_on_exception(self, adapter_with_ollama: LLMAdapter):
        with patch("ollama.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.chat = AsyncMock(side_effect=RuntimeError("connection refused"))

            resp = await adapter_with_ollama.complete(
                [{"role": "user", "content": "test"}],
            )

        assert resp.provider == "fallback"


# ---------------------------------------------------------------------------
# Mocked Gemini completion
# ---------------------------------------------------------------------------


class TestGeminiCompletion:
    @pytest.mark.asyncio
    async def test_complete_calls_gemini(self, adapter_with_gemini: LLMAdapter):
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 10
        mock_usage.candidates_token_count = 20

        mock_response = MagicMock()
        mock_response.text = "Gemini response"
        mock_response.usage_metadata = mock_usage

        with patch("google.genai.Client") as MockClient:
            instance = MockClient.return_value
            instance.aio.models.generate_content = AsyncMock(return_value=mock_response)

            resp = await adapter_with_gemini.complete(
                [{"role": "user", "content": "test"}],
                model_hint="fast",
            )

        assert resp.content == "Gemini response"
        assert resp.provider == "gemini"
        assert resp.model == "gemini-2.0-flash"
        assert resp.tokens_used == 30

    @pytest.mark.asyncio
    async def test_gemini_falls_back_on_exception(self, adapter_with_gemini: LLMAdapter):
        with patch("google.genai.Client") as MockClient:
            instance = MockClient.return_value
            instance.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("quota exceeded"))

            resp = await adapter_with_gemini.complete(
                [{"role": "user", "content": "test"}],
            )

        assert resp.provider == "fallback"


# ---------------------------------------------------------------------------
# Structured output parsing
# ---------------------------------------------------------------------------


class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_structured_output_parses_json(self, adapter_with_ollama: LLMAdapter):
        payload = {"priority": 8, "action": "engage"}
        mock_message = MagicMock()
        mock_message.content = json.dumps(payload)
        mock_response = MagicMock()
        mock_response.message = mock_message
        mock_response.eval_count = 10
        mock_response.prompt_eval_count = 5

        with patch("ollama.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.chat = AsyncMock(return_value=mock_response)

            result = await adapter_with_ollama.complete_structured(
                [{"role": "user", "content": "evaluate target"}],
                response_schema={"type": "object"},
            )

        assert result == payload


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


class TestJsonParsing:
    def test_parses_clean_json(self):
        assert _parse_json_permissive('{"a": 1}') == {"a": 1}

    def test_strips_markdown_fences(self):
        text = '```json\n{"a": 1}\n```'
        assert _parse_json_permissive(text) == {"a": 1}

    def test_returns_empty_on_invalid(self):
        assert _parse_json_permissive("not json at all") == {}

    def test_handles_whitespace(self):
        assert _parse_json_permissive('  \n{"b": 2}\n  ') == {"b": 2}


# ---------------------------------------------------------------------------
# LLMResponse immutability
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_frozen_dataclass(self):
        resp = LLMResponse(content="x", model="m", provider="p", tokens_used=0)
        with pytest.raises(AttributeError):
            resp.content = "y"
