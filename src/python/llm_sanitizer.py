"""
llm_sanitizer.py
================
LLM prompt injection defense and output validation utilities.

Pure functions — no side effects, no global state mutation.

Public API:
  sanitize_prompt_input(text)         -> cleaned string (raises InjectionDetected if attack found)
  validate_llm_output(response, schema) -> validated dict (raises OutputValidationError on failure)
  check_hallucination(ai_targets, sensor_targets) -> list of hallucinated items
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class InjectionDetected(ValueError):
    """Raised when a prompt injection pattern is detected in input text."""


class OutputValidationError(ValueError):
    """Raised when an LLM output fails schema or structural validation."""


# ---------------------------------------------------------------------------
# Injection pattern blocklist
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+|previous\s+|prior\s+)?(instructions|directives|rules|prompts)", re.IGNORECASE),
    re.compile(r"disregard\s+(your|all|previous|prior)?\s*(training|instructions|rules|directives)", re.IGNORECASE),
    re.compile(r"\bsystem\s*:", re.IGNORECASE),
    re.compile(r"\bact\s+as\b.{0,50}\b(unrestricted|uncensored|without|no\s+limits?)", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\s+(a\s+)?(different|new|another|unrestricted)", re.IGNORECASE),
    re.compile(r"\bforget\s+(all\s+)?(previous|prior|your)\s*(instructions|rules|training)", re.IGNORECASE),
    re.compile(r"\bnew\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"\boverride\s+(all\s+)?(previous|prior|your)\s*(instructions|rules|constraints)", re.IGNORECASE),
]

# Control characters to strip (keep printable ASCII + unicode letters/numbers/punctuation)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Normalize line endings to a single space (strip \n, \r)
_NEWLINE_RE = re.compile(r"[\r\n]+")


# ---------------------------------------------------------------------------
# sanitize_prompt_input
# ---------------------------------------------------------------------------


def sanitize_prompt_input(text: Any) -> str:
    """
    Sanitize user-controlled text before it enters an LLM prompt.

    Steps:
    1. Coerce None/non-string to empty string
    2. Normalize unicode (NFC)
    3. Strip control characters
    4. Collapse newlines to spaces
    5. Detect and raise on injection patterns

    Returns a cleaned string safe for inclusion in an LLM prompt.
    Raises InjectionDetected if an injection attack pattern is found.
    """
    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    # Normalize unicode to NFC (preserves accents, special chars)
    normalized = unicodedata.normalize("NFC", text)

    # Strip control characters (keep tabs as space equivalent)
    without_ctrl = _CONTROL_CHAR_RE.sub("", normalized)

    # Collapse newlines to single space
    cleaned = _NEWLINE_RE.sub(" ", without_ctrl).strip()

    # Check for injection patterns — raise if found
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise InjectionDetected(f"Prompt injection pattern detected: {pattern.pattern!r}")

    return cleaned


# ---------------------------------------------------------------------------
# validate_llm_output
# ---------------------------------------------------------------------------


def validate_llm_output(response: str, schema: dict[str, Any]) -> dict[str, Any]:
    """
    Validate an LLM text response as structured JSON.

    - Strips markdown code fences if present
    - Parses JSON (raises OutputValidationError with 'malformed' if invalid)
    - Verifies the result is a JSON object (raises with 'object' if array/scalar)
    - Checks all required fields are present (raises with 'missing' if not)

    Returns the validated dict.
    """
    if not response or not response.strip():
        raise OutputValidationError("malformed: empty response from LLM")

    text = response.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OutputValidationError(f"malformed: JSON parse error — {exc}") from exc

    if not isinstance(parsed, dict):
        raise OutputValidationError(f"Expected a JSON object but got {type(parsed).__name__}")

    required_fields: list[str] = schema.get("required", [])
    missing = [field for field in required_fields if field not in parsed]
    if missing:
        raise OutputValidationError(f"missing required fields: {', '.join(missing)}")

    return parsed


# ---------------------------------------------------------------------------
# check_hallucination
# ---------------------------------------------------------------------------


def check_hallucination(
    ai_targets: list[dict[str, Any]],
    sensor_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Cross-check AI-reported targets against verified sensor fusion data.

    Returns a new list of AI target entries whose 'id' field does not appear
    in the sensor_targets list. These are potential hallucinations.

    Pure function — does not modify input lists.
    """
    sensor_ids: frozenset[str] = frozenset(t.get("id", "") for t in sensor_targets if t.get("id"))

    return [target for target in ai_targets if target.get("id") not in sensor_ids]
