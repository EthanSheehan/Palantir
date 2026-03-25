# W4-004: Confidence-Gated Dynamic Authority

## Status: COMPLETE

## Files Created
- `src/python/confidence_gate.py` — ConfidenceThreshold (frozen dataclass) + ConfidenceGate class
- `src/python/tests/test_confidence_gate.py` — 36 tests across 7 test classes

## Files Modified
- `src/python/autopilot.py` — Two confidence gate integration points:
  1. Before nomination approval (Gate 1): checks AUTHORIZE_COA threshold
  2. Before COA authorization (Gate 2): checks ENGAGE threshold

## Implementation Details

### confidence_gate.py
- `ConfidenceThreshold` frozen dataclass: action, min_confidence, high_value_targets tuple, override_rate_limit
- `ConfidenceGate` class with:
  - `evaluate(action, confidence, target_type)` -> "PROCEED" | "ESCALATE" | "DENY"
  - `record_override()` — tracks operator override timestamps
  - `get_override_rate(window_seconds)` — rolling window override rate
  - `should_show_vigilance_prompt(seconds_since_last)` — 120s periodic check
- Override rate >30% in 5-min window escalates all actions
- High-value targets (CP, C2_NODE) always escalate regardless of confidence
- Unknown actions always escalate (safe default)

### Default Thresholds
| Action | Min Confidence |
|--------|---------------|
| AUTHORIZE_COA | 0.7 |
| ENGAGE | 0.85 |
| INTERCEPT | 0.6 |
| FOLLOW | 0.3 |
| PAINT | 0.3 |

### autopilot.py Integration
- Gate instantiated with defaults if none injected (dependency injection supported)
- Escalated entries skipped by autopilot, logged, and emitted to INTEL_FEED for operator pickup
- Two gate checkpoints: pre-approval and pre-COA-authorization

## Test Results
- 36 tests: 36 passed
- Full suite: 1013 passed
