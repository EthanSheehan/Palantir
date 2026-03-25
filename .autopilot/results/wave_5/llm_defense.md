# W5-007: LLM Prompt Injection Defense + Output Validation

**Status: PASS**

## Files Created

- `src/python/llm_sanitizer.py` — pure-function sanitization/validation module
- `src/python/tests/test_llm_sanitizer.py` — 32 tests (TDD, all green)

## Test Results

```
32 passed in 0.38s   (test_llm_sanitizer.py)
24 passed in 1.13s   (test_llm_adapter.py — no regressions)
```

## Implementation

### sanitize_prompt_input(text)
- Accepts None/non-string (returns "")
- Strips control characters (\x00-\x08, \x0e-\x1f, \x7f)
- Collapses \r\n to single space
- NFC unicode normalization (preserves accents, military unicode)
- Raises InjectionDetected on blocklisted patterns:
  - "ignore previous/all instructions"
  - "disregard your training/instructions"
  - "system:" prefix
  - "act as unrestricted model"
  - "jailbreak"
  - "you are now a different AI"
  - "forget previous instructions"
  - "override previous instructions"
  - Case-insensitive matching

### validate_llm_output(response, schema)
- Strips markdown code fences
- Raises OutputValidationError("malformed") on invalid JSON
- Raises OutputValidationError on non-object JSON (arrays, scalars)
- Raises OutputValidationError("missing") when required fields absent
- Returns validated dict on success

### check_hallucination(ai_targets, sensor_targets)
- Cross-checks AI target IDs against sensor fusion data
- Returns list of AI targets whose ID not in sensor_targets
- Pure function — does not mutate inputs
- Returns new list (not reference to input)

## Acceptance Criteria Checklist

- [x] Strip newlines, control characters from target fields before LLM prompt
- [x] Instruction patterns stripped (raises on detection)
- [x] All LLM responses required as structured JSON with schema validation
- [x] Cross-check AI targeting data against verified sensor fusion (hallucination detection)
- [x] Sanitize all reflected text
- [x] No existing tests broken
