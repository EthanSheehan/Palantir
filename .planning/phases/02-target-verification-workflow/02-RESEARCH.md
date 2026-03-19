# Phase 2: Target Verification Workflow — Research

**Researched:** 2026-03-19
**Domain:** Python state machine, time-decay regression, WebSocket action gating, Blueprint ProgressBar, pure-function engine
**Confidence:** HIGH (verified against live codebase — sim_engine.py, api_main.py, event_logger.py, existing test patterns)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-2 | State machine: UNDETECTED→DETECTED→CLASSIFIED→VERIFIED→NOMINATED; promotion by fused_confidence + sensor diversity + time; configurable thresholds per target type; regression on sensor loss; manual operator fast-track | All patterns below address this directly |
| NFR-4 | All new Python modules have pytest tests; pure functions for verification (no side effects); 80%+ coverage on new code | Validation Architecture section; pure function design in Pattern 1 |
</phase_requirements>

---

## Summary

Phase 2 adds a verification state machine that gates ISR/nomination pipeline access behind confidence and sensor-diversity evidence. Targets must now climb from DETECTED → CLASSIFIED (fused_confidence >= 0.6) → VERIFIED (fused_confidence >= 0.8 AND multi-sensor OR sustained) before `_process_new_detection()` fires.

The existing `TARGET_STATES` tuple in `sim_engine.py` currently reads `("UNDETECTED", "DETECTED", "TRACKED", "IDENTIFIED", "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED")`. Phase 2 introduces `CLASSIFIED` and `VERIFIED` as new promotion states between `DETECTED` and `NOMINATED`. The states `TRACKED` and `IDENTIFIED` are **not removed** — they are still used by `_assign_target()` (`TRACKED` when FOLLOW, `LOCKED` via PAINT/INTERCEPT). The new states sit alongside the existing command-driven ones, gating the pipeline without breaking `command_follow/paint/intercept`.

Phase 2 depends on Phase 1 delivering `fused_confidence`, `sensor_count`, and `sensor_contributions` on each target. The `verification_engine.py` reads those fields and is therefore a pure consumer — no sim_engine mutation until Phase 1 fields exist. Critically, Phase 0 React files are still empty (directory scaffolding only), which means Phase 2's React components must be authored alongside or after Phase 0 execution.

**Primary recommendation:** Implement `verification_engine.py` as a pure-function module with frozen dataclasses and a `VERIFICATION_THRESHOLDS` dict. Wire it into `sim_engine.py`'s tick loop as a post-fusion step. Gate `TacticalAssistant.update()` on `state == "VERIFIED"`. Author `VerificationStepper.tsx` as a Blueprint ProgressBar + Step dots composite component.

---

## Standard Stack

### Python (verified against existing codebase)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| dataclasses (stdlib) | 3.9+ | `VerificationThreshold` frozen dataclass | matches sensor_model.py / Phase 1 pattern |
| typing (stdlib) | 3.9+ | type hints | `Optional[float]`, `dict[str, VerificationThreshold]` |
| time (stdlib) | 3.9+ | `time.time()` for regression timer | already used in sim_engine.py tick loop |
| structlog | 21.5.0 | state transition logging | already used throughout |
| event_logger | project | `log_event("target_state_transition", ...)` | already in api_main.py import |
| pytest | 7.x | unit tests | existing suite; conftest.py adds sys.path |

### TypeScript / React (verified against package.json)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| react | 18.3.1 | VerificationStepper component | already in project |
| @blueprintjs/core | 5.13.0 | ProgressBar, Tag, Button (Intent.WARNING) | existing design system |
| zustand | 4.5.0 | Target interface extension | existing store |

### No new dependencies required
All libraries needed for Phase 2 are already present. `verification_engine.py` uses only stdlib.

---

## Architecture Patterns

### Recommended Project Structure
```
src/python/
  verification_engine.py     # NEW — pure function module (~120 lines)
  sim_engine.py              # MODIFY — add verification step to tick(), wire timers
  api_main.py                # MODIFY — gate _process_new_detection(), add verify_target action

src/frontend-react/src/panels/enemies/
  VerificationStepper.tsx    # NEW — Blueprint ProgressBar + step dots
  EnemyCard.tsx              # MODIFY — integrate VerificationStepper

src/python/tests/
  test_verification.py       # NEW — pure function + integration tests
```

### Pattern 1: Pure Function Verification Engine

**What:** `src/python/verification_engine.py` — frozen dataclasses + pure `evaluate_target_state()` function.
**When to use:** Called once per target per tick from `sim_engine.py`, after fusion is computed.
**Key insight:** The function takes current state + evidence (fused_confidence, sensor_type_count, time_in_state, last_sensor_contact_time) and returns a new state. It never modifies the target directly — `sim_engine.py` applies the returned state. This keeps the engine testable in isolation.

```python
# src/python/verification_engine.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time


@dataclass(frozen=True)
class VerificationThreshold:
    classify_confidence: float     # fused_confidence needed for DETECTED→CLASSIFIED
    verify_confidence: float       # fused_confidence needed for CLASSIFIED→VERIFIED
    verify_sensor_types: int       # min distinct sensor types OR...
    verify_sustained_sec: float    # ...sustained detect time threshold (whichever lower)
    regression_timeout_sec: float  # seconds with no sensors before regressing one state


# Per-target-type thresholds (SAMs verify faster — high threat)
VERIFICATION_THRESHOLDS: dict[str, VerificationThreshold] = {
    "SAM":      VerificationThreshold(0.5, 0.7, 2, 10.0, 8.0),
    "TEL":      VerificationThreshold(0.5, 0.7, 2, 10.0, 10.0),
    "RADAR":    VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "C2_NODE":  VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "MANPADS":  VerificationThreshold(0.5, 0.7, 2, 10.0, 8.0),
    "CP":       VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "TRUCK":    VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "LOGISTICS":VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
    "ARTILLERY":VerificationThreshold(0.55, 0.75, 2, 12.0, 10.0),
    "APC":      VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0),
}

# Default threshold for unknown target types
_DEFAULT_THRESHOLD = VerificationThreshold(0.6, 0.8, 2, 15.0, 15.0)

# DEMO_FAST preset: halves all time thresholds, lowers confidence by 0.1
DEMO_FAST_THRESHOLDS: dict[str, VerificationThreshold] = {
    k: VerificationThreshold(
        max(0.3, v.classify_confidence - 0.1),
        max(0.4, v.verify_confidence - 0.1),
        v.verify_sensor_types,
        v.verify_sustained_sec / 2.0,
        v.regression_timeout_sec / 2.0,
    )
    for k, v in VERIFICATION_THRESHOLDS.items()
}


# States that the verification engine manages (subset of full TARGET_STATES)
_MANAGED_STATES = frozenset({"DETECTED", "CLASSIFIED", "VERIFIED"})

# States that are terminal or managed by other systems (do not regress)
_TERMINAL_STATES = frozenset({"NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED"})


def evaluate_target_state(
    current_state: str,
    target_type: str,
    fused_confidence: float,
    sensor_type_count: int,
    time_in_current_state_sec: float,
    seconds_since_last_sensor: float,
    demo_fast: bool = False,
) -> str:
    """
    Pure function: given current evidence, return the new target state.

    Does not modify any object. Returns the same state if no transition occurs.

    Rules:
    - DETECTED → CLASSIFIED: confidence >= classify_confidence AND 1+ sensor active
    - CLASSIFIED → VERIFIED: confidence >= verify_confidence AND
                              (sensor_type_count >= verify_sensor_types OR
                               time_in_current_state_sec >= verify_sustained_sec)
    - VERIFIED → NOMINATED:  handled externally by ISR/Strategy pipeline
    - Regression: seconds_since_last_sensor >= regression_timeout_sec → regress one state
    - Terminal states (NOMINATED, LOCKED, ENGAGED, DESTROYED, ESCAPED): no-op
    """
    # Never touch terminal states
    if current_state in _TERMINAL_STATES:
        return current_state

    # Only manage our target states
    if current_state not in _MANAGED_STATES and current_state != "UNDETECTED":
        return current_state

    thresholds = (
        DEMO_FAST_THRESHOLDS if demo_fast else VERIFICATION_THRESHOLDS
    ).get(target_type, _DEFAULT_THRESHOLD)

    has_sensor_contact = seconds_since_last_sensor < thresholds.regression_timeout_sec

    # Regression: no sensor contact → step back one state
    if not has_sensor_contact:
        if current_state == "VERIFIED":
            return "CLASSIFIED"
        if current_state == "CLASSIFIED":
            return "DETECTED"
        if current_state == "DETECTED":
            return "UNDETECTED"
        return current_state

    # Promotion rules (bottom-up: check highest first, fall through)
    if current_state == "CLASSIFIED":
        meets_sensor_diversity = sensor_type_count >= thresholds.verify_sensor_types
        meets_sustained = time_in_current_state_sec >= thresholds.verify_sustained_sec
        if (fused_confidence >= thresholds.verify_confidence and
                (meets_sensor_diversity or meets_sustained)):
            return "VERIFIED"

    elif current_state == "DETECTED":
        if fused_confidence >= thresholds.classify_confidence:
            return "CLASSIFIED"

    return current_state
```

### Pattern 2: Target State Timer Fields

**What:** `Target` in `sim_engine.py` needs timer fields to support time-based promotion and regression.
**Key insight:** `time_in_state_sec` and `last_sensor_contact_time` must be reset on each state transition. They are managed in `sim_engine.py` where state transitions happen, not in `verification_engine.py` (which is pure).

```python
# Target.__init__ additions (sim_engine.py)
self.time_in_state_sec: float = 0.0        # seconds in current state (reset on transition)
self.last_sensor_contact_time: float = time.time()  # updated each tick with sensor contact
```

**Reset on state transition** (in `sim_engine.py` tick loop, after calling `evaluate_target_state()`):
```python
new_state = evaluate_target_state(
    current_state=t.state,
    target_type=t.type,
    fused_confidence=t.fused_confidence,
    sensor_type_count=len(set(c.sensor_type for c in t.sensor_contributions)),
    time_in_current_state_sec=t.time_in_state_sec,
    seconds_since_last_sensor=now - t.last_sensor_contact_time,
    demo_fast=self.demo_fast,
)
if new_state != t.state:
    old_state = t.state
    t.state = new_state
    t.time_in_state_sec = 0.0  # reset timer on any transition
    log_event("target_state_transition", {
        "target_id": t.id,
        "target_type": t.type,
        "from": old_state,
        "to": new_state,
        "fused_confidence": t.fused_confidence,
    })
else:
    t.time_in_state_sec += dt_sec

# Update last sensor contact time if contributions exist this tick
if t.sensor_contributions:
    t.last_sensor_contact_time = now
```

**Important:** `TARGET_STATES` tuple must be extended to include `"CLASSIFIED"` and `"VERIFIED"`. The existing `set_target_state()` method validates against this tuple, and the demo autopilot uses it.

```python
# sim_engine.py line 14 — MODIFY
TARGET_STATES = (
    "UNDETECTED", "DETECTED", "CLASSIFIED", "VERIFIED",
    "TRACKED", "IDENTIFIED", "NOMINATED", "LOCKED",
    "ENGAGED", "DESTROYED", "ESCAPED",
)
```

### Pattern 3: Pipeline Gate in TacticalAssistant

**What:** `TacticalAssistant.update()` in `api_main.py` currently fires `_process_new_detection()` on ANY state transition away from UNDETECTED. Phase 2 gates this to `state == "VERIFIED"` only.
**Key insight:** The existing `is_detected` variable tests `state != "UNDETECTED"`. This must become two separate concepts: "newly visible to UI" (any detected state) vs. "newly verified for nomination". The assistant message "NEW CONTACT" should still fire on first detection — only the ISR/nomination pipeline should be gated.

```python
# api_main.py — TacticalAssistant.update() modification
def update(self, sim_state):
    new_messages = []
    for target in sim_state.get("targets", []):
        tid = target["id"]
        current_state = target.get("state", "UNDETECTED")
        is_any_detected = current_state != "UNDETECTED"
        is_verified = current_state == "VERIFIED"
        t_type = target["type"]

        # UI visibility: fire "NEW CONTACT" on first detection (any state)
        if is_any_detected and not self.last_detected.get(tid, False):
            msg = {
                "type": "ASSISTANT_MESSAGE",
                "text": f"NEW CONTACT: {t_type} localized at {target['lon']:.4f}, {target['lat']:.4f}",
                "severity": "INFO",
                "timestamp": time.strftime("%H:%M:%S")
            }
            new_messages.append(msg)

        # ISR pipeline gate: only fire on VERIFIED (was not verified last tick)
        was_verified = self._last_verified.get(tid, False)
        if is_verified and not was_verified:
            hitl_msg = _process_new_detection(target, self._nominated)
            if hitl_msg:
                new_messages.append(hitl_msg)

        self.last_detected[tid] = is_any_detected
        self._last_verified[tid] = is_verified

    return new_messages
```

**Add `_last_verified` dict to `TacticalAssistant.__init__`:**
```python
self._last_verified: dict = {}  # target_id -> bool
```

### Pattern 4: Manual Verify WebSocket Action

**What:** New `verify_target` WebSocket action allows operator to fast-track a CLASSIFIED target to VERIFIED.
**When to use:** Operator clicks "VERIFY" button on a CLASSIFIED target card in the UI.

```python
# api_main.py — add to _ACTION_SCHEMAS:
"verify_target": {"target_id": "int"},

# api_main.py — add to WebSocket action handler:
elif action == "verify_target":
    target_id = payload["target_id"]
    target = sim._find_target(target_id)
    if target and target.state == "CLASSIFIED":
        old_state = target.state
        target.state = "VERIFIED"
        target.time_in_state_sec = 0.0
        log_event("target_state_transition", {
            "target_id": target_id,
            "target_type": target.type,
            "from": old_state,
            "to": "VERIFIED",
            "source": "manual_operator",
        })
        logger.info("manual_verify", target_id=target_id)
```

### Pattern 5: get_state() Broadcast Extension

**What:** `get_state()` must include `time_in_state_sec` and the next-threshold confidence for the UI progress bar.
**Key insight:** The UI ProgressBar needs to know both current confidence and the threshold for the NEXT state. Rather than hard-coding thresholds in TypeScript, serialize them as part of the target payload.

```python
# In get_state() targets list comprehension — add new fields:
{
    # ... existing fields ...
    "verification_state": t.state,        # same as "state" but explicit
    "time_in_state_sec": round(t.time_in_state_sec, 1),
    "next_threshold": _get_next_threshold(t),   # float: confidence needed for next state
}

# Helper (add to sim_engine.py):
def _get_next_threshold(target) -> Optional[float]:
    """Return the confidence threshold for the next verification promotion."""
    from verification_engine import VERIFICATION_THRESHOLDS, _DEFAULT_THRESHOLD
    thresh = VERIFICATION_THRESHOLDS.get(target.type, _DEFAULT_THRESHOLD)
    if target.state == "DETECTED":
        return thresh.classify_confidence
    if target.state == "CLASSIFIED":
        return thresh.verify_confidence
    return None
```

### Pattern 6: VerificationStepper React Component

**What:** Blueprint `ProgressBar` + styled step dots showing DETECTED→CLASSIFIED→VERIFIED→NOMINATED.
**Key insight:** Blueprint v5 does NOT have a `Steps` component like AntDesign. Use a custom row of colored dots (Blueprint `Icon` or simple `div`) + a `ProgressBar`. The stepper is a thin presentation component receiving props from `EnemyCard`.

```typescript
// src/frontend-react/src/panels/enemies/VerificationStepper.tsx
import { ProgressBar, Intent, Button } from '@blueprintjs/core';

const STEPS = ['DETECTED', 'CLASSIFIED', 'VERIFIED', 'NOMINATED'] as const;
type VerificationState = typeof STEPS[number] | 'UNDETECTED' | 'LOCKED' | 'ENGAGED' | 'DESTROYED' | 'ESCAPED';

// Dot color: gray=pending, amber=current, green=passed
const dotColor = (step: string, currentState: VerificationState): string => {
  const stepIdx = STEPS.indexOf(step as any);
  const currIdx = STEPS.indexOf(currentState as any);
  if (currIdx === -1) return '#5C7080';  // terminal states — all gray
  if (stepIdx < currIdx) return '#0F9960'; // green — passed
  if (stepIdx === currIdx) return '#D9822B'; // amber — current
  return '#5C7080'; // gray — pending
};

interface VerificationStepperProps {
  state: string;
  fused_confidence: number;
  next_threshold: number | null;
  time_in_state_sec: number;
  onManualVerify?: () => void;  // undefined when not CLASSIFIED
}

export function VerificationStepper({
  state,
  fused_confidence,
  next_threshold,
  time_in_state_sec,
  onManualVerify,
}: VerificationStepperProps) {
  const progressValue = next_threshold ? Math.min(1.0, fused_confidence / next_threshold) : 1.0;
  const isClassified = state === 'CLASSIFIED';

  return (
    <div style={{ padding: '4px 0' }}>
      {/* Step dots row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {STEPS.map((step, i) => (
          <div key={step} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: dotColor(step, state as VerificationState),
              flexShrink: 0,
            }} />
            <span style={{ fontSize: 10, color: '#A7B6C2' }}>{step}</span>
            {i < STEPS.length - 1 && (
              <div style={{ width: 12, height: 1, backgroundColor: '#394B59' }} />
            )}
          </div>
        ))}
      </div>

      {/* Progress bar toward next threshold */}
      {next_threshold !== null && (
        <ProgressBar
          value={progressValue}
          intent={isClassified ? Intent.WARNING : Intent.PRIMARY}
          animate={false}
          stripes={false}
          style={{ height: 4 }}
        />
      )}

      {/* Manual VERIFY button — only on CLASSIFIED targets */}
      {isClassified && onManualVerify && (
        <Button
          small
          intent={Intent.WARNING}
          text="VERIFY"
          onClick={onManualVerify}
          style={{ marginTop: 4 }}
        />
      )}
    </div>
  );
}
```

### Pattern 7: TypeScript Type Extensions

**What:** Extend `Target` interface in `store/types.ts` with Phase 2 fields.
**Key insight:** Phase 0 `types.ts` is still empty (not yet executed). Phase 2 executor must add these fields to whichever `types.ts` Phase 0 leaves. Document what to add.

```typescript
// store/types.ts — additions to Target interface for Phase 2
export interface Target {
  // ... existing Phase 0 + Phase 1 fields ...
  time_in_state_sec: number;          // Phase 2 NEW
  next_threshold: number | null;      // Phase 2 NEW — confidence for next state
}
```

### Anti-Patterns to Avoid

- **Modifying state in `evaluate_target_state()`:** The function is pure — it returns a string. All mutation happens in `sim_engine.py` after the call.
- **Regressing NOMINATED/LOCKED/ENGAGED targets:** `_TERMINAL_STATES` guard prevents regression on targets already in the pipeline.
- **Resetting `time_in_state_sec` without logging:** Always call `log_event("target_state_transition", ...)` alongside any state change.
- **Blueprint Steps component:** Blueprint v5 has no `Steps` stepper. Use custom dots + ProgressBar (see Pattern 6).
- **Firing ISR pipeline on DETECTED:** `TacticalAssistant.update()` must use `_last_verified` (not `last_detected`) to gate `_process_new_detection()`.
- **Checking `sensor_type_count` from Phase 1 before Phase 1 is wired:** If Phase 1 hasn't run yet, `sensor_contributions` will be empty. Use `len(set(c['sensor_type'] for c in t.get('sensor_contributions', [])))` with a safe default.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State transition logging | Custom logger | `event_logger.log_event()` | Already wired in api_main.py; async, non-blocking |
| Progress bar visualization | Canvas draw | Blueprint `ProgressBar` with `value=` prop | Handles animation, theming, accessibility |
| Confidence-to-threshold ratio | Custom math | `min(1.0, fused_confidence / next_threshold)` | One-liner; threshold already serialized from backend |
| Per-type threshold config | YAML file | `VERIFICATION_THRESHOLDS` dict in verification_engine.py | Same pattern as `_SENSOR_DISTRIBUTION` in sim_engine.py |
| Regression timer | asyncio task | `time_in_state_sec` field + delta in tick() | Stays synchronous with the sim loop |

**Key insight:** The sim loop already calls `time.time()` at the top of each tick (`now = time.time()`). Reuse this `now` value for all timer comparisons — don't call `time.time()` again inside the verification step.

---

## Common Pitfalls

### Pitfall 1: `TRACKED` and `IDENTIFIED` States Still Used by `_assign_target()`

**What goes wrong:** Executor removes `TRACKED`/`IDENTIFIED` from `TARGET_STATES` when adding `CLASSIFIED`/`VERIFIED`. This breaks `command_follow()` which calls `_assign_target(..., "TRACKED")`.
**Why it happens:** The old state machine is `DETECTED → TRACKED → IDENTIFIED → NOMINATED`. Phase 2 adds new states but the FOLLOW/PAINT/INTERCEPT command flow uses `TRACKED` as a side effect, not a verification state.
**How to avoid:** Keep `TRACKED` and `IDENTIFIED` in `TARGET_STATES`. The new states `CLASSIFIED` and `VERIFIED` are **additive** — they sit between `DETECTED` and the command-driven states. A target can be `VERIFIED` AND `TRACKED` if an operator is actively following it. Do not conflate them.
**Warning signs:** `command_follow()` silently fails because `target_state="TRACKED"` fails the `if new_state in TARGET_STATES` check.

### Pitfall 2: `TacticalAssistant` Fires ISR on Every DETECTED→CLASSIFIED Transition

**What goes wrong:** Current `is_detected = state != "UNDETECTED"` fires `_process_new_detection()` on first DETECTED state. After Phase 2, this check fires three times (DETECTED, CLASSIFIED, VERIFIED) for the same target.
**Why it happens:** `last_detected` is a simple bool — it becomes `True` on first non-UNDETECTED and stays True.
**How to avoid:** Separate `last_detected` (for "NEW CONTACT" UI message) from `_last_verified` (for ISR pipeline trigger). See Pattern 3.

### Pitfall 3: `time_in_state_sec` Not Reset on Manual Verify

**What goes wrong:** Operator manually verifies a target. The backend sets `state = "VERIFIED"` but forgets to reset `time_in_state_sec = 0.0`. On the next tick, `evaluate_target_state()` sees a large `time_in_current_state_sec` value for VERIFIED state — this is harmless but misleading in the UI.
**How to avoid:** Always pair `target.state = new_state` with `target.time_in_state_sec = 0.0` in both the automated tick AND the manual `verify_target` handler.

### Pitfall 4: `sensor_type_count` Derived from Stale `sensor_contributions`

**What goes wrong:** `sensor_contributions` on the target is the list from the LAST TICK. If a UAV left range between ticks, the contributions list may still have old entries. The verification engine sees 2 sensor types but only 1 is actually active.
**Why it happens:** Phase 1 clears `sensor_contributions` only when confidence drops below 0.05. A UAV that just left range may still have `confidence = 0.08` (above threshold).
**How to avoid:** In `evaluate_target_state()`, pass `sensor_type_count` derived from the **current tick's fused result** (computed in the fusion step), not from the stale contributions list. In `sim_engine.py`, compute `sensor_type_count` from the fresh `FusedDetection.sensor_types` tuple before calling `evaluate_target_state()`.

### Pitfall 5: `DEMO_FAST` Flag Not Propagated to `SimulationModel`

**What goes wrong:** `verification_engine.py` exports `DEMO_FAST_THRESHOLDS` but `sim_engine.py` calls `evaluate_target_state(..., demo_fast=False)` unconditionally.
**Why it happens:** The `SimulationModel` class has no `demo_fast` field yet.
**How to avoid:** Add `self.demo_fast: bool = False` to `SimulationModel.__init__`. Wire it to the `DEMO_MODE` env var (already used by `api_main.py` settings). Pass `demo_fast=self.demo_fast` when calling `evaluate_target_state()`.

### Pitfall 6: `next_threshold` Serialized as `None` for All Non-Verification States

**What goes wrong:** Targets in `NOMINATED`, `LOCKED`, `ENGAGED` states get `next_threshold: None`. `VerificationStepper` receives `null` — it should render no progress bar, which is correct. But if the TypeScript code does `fused_confidence / next_threshold` without null-checking, it divides by null.
**How to avoid:** Pattern 6's `VerificationStepper` has `{next_threshold !== null && <ProgressBar ...>}` guard. In TypeScript types: `next_threshold: number | null`.

### Pitfall 7: `TacticalAssistant._last_verified` Missing from `demo_autopilot()` Reset

**What goes wrong:** `demo_autopilot()` runs a loop that re-uses the same `TacticalAssistant` instance. After a target is DESTROYED and a new one spawns with the same ID (not possible in current sim, but during demo restarts), `_last_verified` will incorrectly suppress the ISR pipeline fire.
**How to avoid:** Keep as-is for now (target IDs do not recycle in the current sim). Document as a known limitation. No fix required for Phase 2 scope.

---

## Code Examples

### Verified codebase state

**Current `TARGET_STATES` (sim_engine.py:14):**
```python
TARGET_STATES = (
    "UNDETECTED", "DETECTED", "TRACKED", "IDENTIFIED",
    "NOMINATED", "LOCKED", "ENGAGED", "DESTROYED", "ESCAPED",
)
```
Phase 2 adds `"CLASSIFIED"` and `"VERIFIED"` between `"DETECTED"` and `"TRACKED"`.

**Current `_assign_target()` state logic (sim_engine.py:453):**
```python
if target_state == "LOCKED" or target.state in ("DETECTED", "UNDETECTED"):
    target.state = target_state
```
This logic only overrides state if the target is currently DETECTED or UNDETECTED. After Phase 2, CLASSIFIED and VERIFIED targets can also be commanded (FOLLOW → TRACKED). Change to:
```python
if target_state == "LOCKED" or target.state in ("DETECTED", "CLASSIFIED", "VERIFIED", "UNDETECTED"):
    target.state = target_state
```

**Current cancel_track() regression (sim_engine.py:478):**
```python
if target.state in ("TRACKED", "LOCKED"):
    target.state = "DETECTED"
```
After Phase 2: keep the TRACKED→DETECTED regression, but also handle VERIFIED→CLASSIFIED regressions through the timer path (don't regress on cancel_track alone — only via sensor timeout).

**Current `TacticalAssistant.update()` detection trigger (api_main.py:136):**
```python
is_detected = target.get("state", "UNDETECTED") != "UNDETECTED"
if is_detected and not self.last_detected.get(tid, False):
    hitl_msg = _process_new_detection(target, self._nominated)
```
Phase 2 splits this into two guards as shown in Pattern 3.

**`event_logger.log_event()` usage pattern (already wired in api_main.py):**
```python
from event_logger import log_event
log_event("target_state_transition", {
    "target_id": t.id,
    "target_type": t.type,
    "from": old_state,
    "to": new_state,
    "fused_confidence": t.fused_confidence,
})
```

**Blueprint ProgressBar import (verified in node_modules):**
```typescript
import { ProgressBar, Intent, Button, Tag } from '@blueprintjs/core';
// ProgressBar props: value (0-1), intent, animate (bool), stripes (bool)
// Intent values: Intent.PRIMARY (blue), Intent.WARNING (amber), Intent.SUCCESS (green)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Binary detected/undetected | Multi-state with DETECTED/CLASSIFIED/VERIFIED | Phase 2 | ISR pipeline gated on evidence quality |
| Single sensor confidence | Fused multi-sensor confidence | Phase 1 | Confidence values are now composite |
| Any detection fires nomination | Only VERIFIED fires nomination | Phase 2 | Reduces false nominations |
| No time-in-state tracking | `time_in_state_sec` field on Target | Phase 2 | Enables sustained-contact verification path |

**Deprecated/outdated in Phase 2 scope:**
- `TRACKED` as first detected state: remains valid as a command-driven state, but no longer the first auto-promoted state after DETECTED
- `IDENTIFIED` state: was between TRACKED and NOMINATED in the old flow; becomes largely unused after Phase 2 but is kept for backward compatibility

---

## Open Questions

1. **How does Phase 2 interact with Phase 1 not yet being executed?**
   - What we know: Phase 1 adds `fused_confidence`, `sensor_type_count`, `sensor_contributions` to `Target`. Phase 2 `evaluate_target_state()` reads these fields.
   - What's unclear: If Phase 2 is planned before Phase 1 is executed, the fields won't exist yet in `sim_engine.py`.
   - Recommendation: Phase 2 plan must explicitly state it depends on Phase 1 fields being present. Plans should check for `fused_confidence` attribute existence in `sim_engine.py` before beginning Phase 2 work.

2. **Should VERIFIED→NOMINATED be explicit in sim_engine or only via ISR pipeline?**
   - What we know: The roadmap says "VERIFIED → NOMINATED: ISR + Strategy pipeline (existing)". The ISR pipeline in `_process_new_detection()` calls `hitl.nominate_target()` which sets state to NOMINATED externally via `set_target_state()`.
   - What's unclear: The `set_target_state()` flow in `api_main.py` vs `sim_engine.py` — need to confirm NOMINATED is set correctly after hitl pipeline runs.
   - Recommendation: Leave NOMINATED transition to the existing HITL pipeline. Do not set it explicitly in `evaluate_target_state()` — this is already how it worked before Phase 2.

3. **Demo autopilot timing with verification added?**
   - What we know: `demo_autopilot()` currently auto-approves nominations. With Phase 2, a target must reach VERIFIED before it's nominated at all.
   - What's unclear: Will demo autopilot timing feel natural with default thresholds, or is DEMO_FAST required by default?
   - Recommendation: Wire `DEMO_FAST` to `settings.demo_mode` so `--demo` flag automatically uses halved thresholds.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, conftest.py adds sys.path) |
| Config file | `src/python/tests/conftest.py` (sys.path setup only) |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_verification.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short` |
| Frontend tests | Manual smoke test via Vite dev server (no Playwright yet) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-2-PROMOTE-CLASSIFY | DETECTED + conf>=0.6 → CLASSIFIED | unit | `pytest test_verification.py::TestEvaluateState::test_detected_to_classified -x` | Wave 1 |
| FR-2-PROMOTE-VERIFY-SENSOR | CLASSIFIED + conf>=0.8 + 2+ types → VERIFIED | unit | `pytest test_verification.py::TestEvaluateState::test_classified_to_verified_sensors -x` | Wave 1 |
| FR-2-PROMOTE-VERIFY-TIME | CLASSIFIED + conf>=0.8 + sustained>=15s → VERIFIED | unit | `pytest test_verification.py::TestEvaluateState::test_classified_to_verified_sustained -x` | Wave 1 |
| FR-2-REGRESS | No sensor contact for timeout_sec → regress one state | unit | `pytest test_verification.py::TestEvaluateState::test_regression -x` | Wave 1 |
| FR-2-TERMINAL | NOMINATED/LOCKED/ENGAGED/DESTROYED not regressed | unit | `pytest test_verification.py::TestEvaluateState::test_terminal_states_not_regressed -x` | Wave 1 |
| FR-2-SAM-FAST | SAM thresholds lower than default | unit | `pytest test_verification.py::TestThresholds::test_sam_thresholds_lower_than_default -x` | Wave 1 |
| FR-2-DEMO-FAST | DEMO_FAST thresholds halve time thresholds | unit | `pytest test_verification.py::TestDemoFast::test_demo_fast_halves_time -x` | Wave 1 |
| FR-2-PURE | evaluate_target_state returns string, never mutates | unit | `pytest test_verification.py::TestPurity -x` | Wave 1 |
| FR-2-SIM-TIMER | time_in_state_sec increments each tick, resets on transition | integration | `pytest test_verification.py::TestSimIntegration::test_timer_increments -x` | Wave 2 |
| FR-2-SIM-PROMOTE | Sim tick auto-promotes after enough ticks with high confidence | integration | `pytest test_verification.py::TestSimIntegration::test_auto_promotion -x` | Wave 2 |
| FR-2-SIM-GATE | _process_new_detection only fires on VERIFIED targets | integration | `pytest test_verification.py::TestPipelineGate::test_gate_fires_on_verified_only -x` | Wave 2 |
| FR-2-MANUAL | verify_target WebSocket action fast-tracks CLASSIFIED→VERIFIED | integration | `pytest test_verification.py::TestManualVerify -x` | Wave 2 |
| FR-2-STATE-BROADCAST | get_state() includes time_in_state_sec and next_threshold | integration | `pytest test_verification.py::TestBroadcast -x` | Wave 2 |
| FR-2-UI-STEPPER | VerificationStepper renders step dots and progress bar | smoke | Manual browser test | — |
| FR-2-UI-VERIFY-BTN | VERIFY button visible on CLASSIFIED, absent on VERIFIED | smoke | Manual browser test | — |
| NFR-4-COVERAGE | 80%+ coverage on verification_engine.py | coverage | `pytest test_verification.py --cov=verification_engine --cov-report=term-missing` | Wave 1 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_verification.py -x`
- **After sim_engine changes:** `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short`
- **Phase gate:** All Python tests green + manual demo of DETECTED→CLASSIFIED→VERIFIED stepper in UI before moving to Phase 3

### Wave 0 Gaps
- [ ] `src/python/tests/test_verification.py` — covers FR-2-PROMOTE-*, FR-2-REGRESS, FR-2-TERMINAL, FR-2-SAM-FAST, FR-2-DEMO-FAST, FR-2-PURE (write before `verification_engine.py`)
- [ ] `src/python/verification_engine.py` — implement to make tests green

---

## Sources

### Primary (HIGH confidence — directly read from codebase)
- `src/python/sim_engine.py` — Target class fields (lines 94-130), UAV class (lines 219-239), detection loop (lines 560-616), `_assign_target()` (lines 445-480), `cancel_track()` (lines 466-480), `get_state()` (lines 770-797), `TARGET_STATES` (lines 14-17)
- `src/python/api_main.py` — `TacticalAssistant.update()` (lines 132-154), `_process_new_detection()` (lines 157-230), `_ACTION_SCHEMAS` (lines 95-107), event_logger import (line 16)
- `src/python/event_logger.py` — `log_event()` signature confirmed; async queue pattern
- `src/python/tests/conftest.py` — sys.path pattern confirmed
- `src/python/tests/test_sim_integration.py` — integration test structure reference
- `src/python/tests/test_sensor_spawn.py` — test class structure reference
- `.planning/ROADMAP.md` — Phase 2 spec (sections 2.1–2.6) read in full
- `.planning/REQUIREMENTS.md` — FR-2, NFR-4 confirmed
- `.planning/phases/01-multi-sensor-target-fusion/01-RESEARCH.md` — Phase 1 data model (fused_confidence, sensor_contributions, sensor_type_count) confirmed as dependency

### Secondary (MEDIUM confidence — library verification)
- Blueprint v5 ProgressBar API: verified from `node_modules/@blueprintjs/core/src/components/progress-bar/progressBar.tsx` — `value`, `intent`, `animate`, `stripes` props confirmed
- Blueprint v5 Button `intent=` API: `Intent.WARNING` = amber, confirmed from button component source
- Blueprint v5 has NO built-in Steps/Stepper component: confirmed by directory scan of `node_modules/@blueprintjs/core/src/components/` — no `steps/` subdirectory

---

## Metadata

**Confidence breakdown:**
- Python verification engine: HIGH — direct codebase analysis; pure function design matches Phase 1 pattern
- Target state machine changes: HIGH — `TARGET_STATES`, `_assign_target()`, `cancel_track()` all verified line-by-line
- `TacticalAssistant` gate change: HIGH — exact code read; modification is surgical (add `_last_verified` dict + change condition)
- Blueprint ProgressBar/Button: HIGH — verified against installed node_modules source
- Blueprint Steps availability: HIGH — confirmed ABSENT by directory scan; custom dots required

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable stack; re-verify `types.ts` contents after Phase 0 execution delivers actual file)
