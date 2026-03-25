# W4-001: AI Explainability Layer — Results

## Status: COMPLETE

## Files Created
- `src/python/explainability.py` — ExplainabilityEngine + DecisionExplanation frozen dataclass + format_source_label helper

## Files Modified
- `src/python/hitl_manager.py` — Added `explanation: Optional[dict]` field to StrikeBoardEntry, included in get_strike_board() output
- `src/python/llm_adapter.py` — Added `source_label` property to LLMResponse (uses format_source_label)
- `src/python/autopilot.py` — Generates DecisionExplanation for nomination approvals and COA authorizations, includes in audit log

## Tests
- `src/python/tests/test_explainability.py` — 26 tests covering:
  - DecisionExplanation creation, immutability, confidence bounds, top_factors limit, optional fields, to_dict
  - Source label formatting (Gemini, Anthropic, Ollama, Heuristic, unknown)
  - explain_nomination with various inputs (target types, ROE decisions, low confidence)
  - explain_coa with alternatives and effector factors
  - explain_intercept with threat levels and counterfactuals
  - HITL integration (serialization, field attachment)
  - ROE rule reference (PERMITTED, ESCALATE)

## Test Results
- 26/26 explainability tests pass
- 1021/1021 full suite tests pass (excluding pre-existing test_kill_chain_tracker import error)

## Design Decisions
- DecisionExplanation is a frozen dataclass with __post_init__ validation (confidence 0-1, top_factors max 3)
- ExplainabilityEngine is stateless — pure functions wrapped in a class for organization
- Source labels use a lookup map with fallback to raw provider string
- Threat weights per target type drive nomination confidence scoring
- COA confidence combines Pk, time, and risk with weighted formula
- Explanations attached to audit log `details` dict (not a separate field) for backward compatibility
