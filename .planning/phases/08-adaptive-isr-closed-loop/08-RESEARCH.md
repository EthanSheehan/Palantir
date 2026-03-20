# Phase 8: Adaptive ISR & Closed Loop - Research

**Researched:** 2026-03-20
**Domain:** Python priority queue design + UAV assignment logic + FastAPI WebSocket actions + Blueprint/React UI
**Confidence:** HIGH

## Summary

Phase 8 is the capstone: it closes the observe-orient-decide-act loop by wiring battlespace assessment output (from Phase 7) into autonomous UAV retasking. The two core deliverables are an `isr_priority.py` module that converts assessment data into a ranked ISR requirement queue, and a `coverage_mode` toggle in `sim_engine.py` that lets threat-adaptive coverage override the existing zone-imbalance dispatch logic.

The existing codebase is well-prepared. `AITaskingManagerAgent` already exists but uses an LLM-optional pattern and an empty asset list — Phase 8 replaces its heuristic with a deterministic scoring function (`_generate_response_heuristic`) that works without an LLM. `sim_engine.py` already has `REPOSITIONING` dispatch logic (the zone-imbalance path via `RomaniaMacroGrid.calculate_macro_flow`) that Phase 8 must gate behind a `coverage_mode` flag. The autonomy framework (Phase 3) and the `coverage_gap_detected` trigger (already in `AUTONOMOUS_TRANSITIONS`) are the integration hooks this phase activates.

The frontend is also ready: `DroneCard.tsx` already shows `mode_source` ('HUMAN'/'AUTO'). Phase 8 adds `tasking_source` attribution per UAV and a new `ISRQueue.tsx` component, plus a `SegmentedControl` coverage mode toggle — both patterns already exist in the project (`AutonomyToggle.tsx` uses `SegmentedControl`, `AssetsTab.tsx` lists drones).

The main risk is UAV starvation: threat-adaptive mode must preserve a minimum idle count to avoid draining all UAVs to a single high-threat zone. The existing `min_idle_count` constraint used by swarm coordination (Phase 5) is the right pattern to replicate.

**Primary recommendation:** Implement `isr_priority.py` as a pure-function module (matching `sensor_fusion.py` and `verification_engine.py` patterns), add `coverage_mode` as a string field on `SimulationModel` with a new `set_coverage_mode()` method, and gate the threat-adaptive dispatch in `tick()` before the existing `calculate_macro_flow` call.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-7 | ISR priority queue from assessment; threat-adaptive coverage mode; autonomous UAV retasking based on intelligence gaps | Covered by `isr_priority.py` (priority queue), `coverage_mode` flag in `sim_engine.py` (threat-adaptive dispatch), `ISRQueue.tsx` + coverage toggle (React UI) |
</phase_requirements>

## Standard Stack

### Core (all already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `dataclasses` (frozen) | 3.9+ | Immutable ISR requirement types | Matches sensor_fusion.py / verification_engine.py pattern |
| Python `heapq` or sorted list | stdlib | Priority queue ordering | No dependency, pure Python — sufficient at 20-30 UAV scale |
| `structlog` | in venv | Structured logging | Project standard |
| `@blueprintjs/core` | 5.13.0 | `HTMLTable`, `SegmentedControl`, `Tag`, `Intent` | All already imported in project |
| `zustand` | 4.5.0 | Store extension for ISR queue state | Locked at 4.5.0 (Decisions Log) |
| TypeScript `interface` | 5.x | ISR requirement types in store | Project standard |

### No New Dependencies
The entire phase can be implemented with existing project libraries. Do not add any scheduling or optimization libraries.

**Installation:** None required.

## Architecture Patterns

### Recommended Module Structure
```
src/python/
├── isr_priority.py             # NEW: ISRPriorityQueue + ISRRequirement dataclass
├── agents/
│   └── ai_tasking_manager.py   # MODIFY: add _generate_response_heuristic()
├── sim_engine.py               # MODIFY: coverage_mode field + threat-adaptive dispatch
├── api_main.py                 # MODIFY: wire isr_priority + set_coverage_mode WS action
└── tests/
    └── test_adaptive_isr.py    # NEW: ~120 lines

src/frontend-react/src/
├── panels/
│   └── assets/
│       ├── DroneCard.tsx       # MODIFY: add tasking_source badge
│       └── ISRQueue.tsx        # NEW: HTMLTable of ISR requirements
├── store/
│   ├── types.ts                # MODIFY: add ISRRequirement type + UAV.tasking_source
│   └── SimulationStore.ts      # MODIFY: add isr_queue field
```

### Pattern 1: Pure-Function ISR Priority Module
**What:** `isr_priority.py` takes assessment output (from Phase 7's `AssessmentResult`) and sim state (targets, UAVs) and returns an ordered list of `ISRRequirement` frozen dataclasses.
**When to use:** Called from `api_main.py`'s simulation loop on the same 5-second assessment cadence as `BattlespaceAssessor`.
**Key design:** No instance state — function takes snapshots, returns immutable results. Consistent with `sensor_fusion.py` pattern.

```python
# Source: project convention from sensor_fusion.py
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ISRRequirement:
    target_id: int
    target_type: str
    urgency_score: float        # 0.0-1.0, higher = more urgent
    verification_gap: float     # 1.0 - fused_confidence
    missing_sensor_types: tuple # sensors not yet contributing
    recommended_uav_ids: tuple  # nearest UAVs with matching sensors

def build_isr_queue(
    targets: list,
    uavs: list,
    assessment_result,          # AssessmentResult from Phase 7
    max_requirements: int = 10,
) -> List[ISRRequirement]:
    """
    Score targets by urgency = threat_weight * verification_gap * time_factor.
    Return top N requirements sorted descending by urgency_score.
    """
    ...
```

### Pattern 2: Coverage Mode Gating in tick()
**What:** `SimulationModel` gains a `coverage_mode: str = "balanced"` field. In `tick()`, before calling `self.grid.calculate_macro_flow(dt_sec)`, check the mode and optionally replace the dispatch with threat-adaptive logic.
**When to use:** Only when `coverage_mode == "threat_adaptive"` and assessment data is available.
**Key invariant:** Must preserve `min_idle_count` — threat-adaptive dispatch must not reassign UAVs already in FOLLOW/PAINT/INTERCEPT/SUPPORT modes.

```python
# In SimulationModel.tick() — gate the existing balanced path
if self.coverage_mode == "threat_adaptive" and self._last_assessment:
    dispatches = self._threat_adaptive_dispatches()
else:
    dispatches = self.grid.calculate_macro_flow(dt_sec)  # existing path unchanged
```

### Pattern 3: Heuristic Tasking Without LLM
**What:** `AITaskingManagerAgent._generate_response_heuristic()` is a pure scoring function that replaces the LLM call for sim mode.
**When to use:** Always in sim mode (LLM client is None). The existing `evaluate_and_retask()` already gates on `confidence_threshold` — the heuristic runs when confidence is below threshold.

```python
# In AITaskingManagerAgent
def _generate_response_heuristic(self, detection, available_assets) -> str:
    """
    Score assets: nearest with matching sensor type gets highest priority.
    Returns TaskingManagerOutput as JSON string (same contract as LLM path).
    """
    ...
```

### Pattern 4: WebSocket Action for Coverage Mode Toggle
**What:** New `set_coverage_mode` action on the WebSocket handler, validated via `_ACTION_SCHEMAS`.
**Key:** Follows the pattern of `set_autonomy_level` (string payload, fleet-wide flag, no per-UAV granularity needed).

```python
# In _ACTION_SCHEMAS
"set_coverage_mode": {"mode": "str"},

# In handle_payload
elif action == "set_coverage_mode":
    mode = payload["mode"]
    if mode in ("balanced", "threat_adaptive"):
        sim.set_coverage_mode(mode)
```

### Pattern 5: ISRQueue React Component
**What:** Blueprint `HTMLTable` listing ISR requirements in priority order. Follows the existing `StrikeBoard.tsx` pattern for tabular data.

```typescript
// Source: existing StrikeBoard.tsx pattern + Blueprint HTMLTable
import { HTMLTable, Tag, Intent } from '@blueprintjs/core';

export function ISRQueue() {
  const isr_queue = useSimStore(s => s.isr_queue);

  return (
    <HTMLTable striped condensed style={{ width: '100%' }}>
      <thead>
        <tr><th>Target</th><th>Type</th><th>Urgency</th><th>Gap</th><th>Sensors Needed</th></tr>
      </thead>
      <tbody>
        {isr_queue.map(req => (
          <tr key={req.target_id}>
            <td>TGT-{req.target_id}</td>
            <td><Tag minimal>{req.target_type}</Tag></td>
            <td><Tag intent={req.urgency_score > 0.7 ? Intent.DANGER : Intent.WARNING}>
              {(req.urgency_score * 100).toFixed(0)}%
            </Tag></td>
            <td>{(req.verification_gap * 100).toFixed(0)}%</td>
            <td>{req.missing_sensor_types.join(', ')}</td>
          </tr>
        ))}
      </tbody>
    </HTMLTable>
  );
}
```

### Pattern 6: Per-UAV Tasking Source Attribution
**What:** Each UAV in `get_state()` gains a `tasking_source` field: `"ZONE_BALANCE"`, `"ISR_PRIORITY"`, or `"OPERATOR"`. This is set when a UAV is assigned a REPOSITIONING task and cleared when it arrives.
**Key:** Only cosmetic/display data — does not change dispatch logic. Set as a string attribute on the `UAV` dataclass, serialized in `get_state()`.

```python
# UAV.__init__ addition
self.tasking_source: str = "ZONE_BALANCE"  # default

# In threat-adaptive dispatch
u.tasking_source = "ISR_PRIORITY"

# In balanced dispatch (existing calculate_macro_flow path)
u.tasking_source = "ZONE_BALANCE"

# When operator commands move_drone
uav.tasking_source = "OPERATOR"
```

### Anti-Patterns to Avoid
- **Calling the LLM in sim mode:** `AITaskingManagerAgent` is instantiated with `llm_client=None` — `_generate_response` raises `NotImplementedError`. The heuristic must be a fully separate code path.
- **Mutating assessment results:** `AssessmentResult` from Phase 7 is a frozen dataclass. Never modify it — pass it directly to `build_isr_queue`.
- **Calling `calculate_macro_flow` in both paths:** The coverage mode gate is exclusive — only one dispatch path runs per tick. Do not merge the results.
- **Draining all UAVs:** Threat-adaptive dispatch must check `len([u for u in self.uavs if u.mode == "IDLE"]) > MIN_IDLE_COUNT` before each assignment.
- **Blueprint `SegmentedControl` with `as const`:** Locked decision from Phase 3 — options array must be mutable (not `as const`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Priority queue ranking | Custom sort comparator | Python `sorted()` with `key=lambda r: -r.urgency_score` | Already O(n log n), 20-30 items max |
| ISR requirement deduplication | Custom set logic | Filter by `target_id` uniqueness before returning | Simple dict keyed by target_id |
| Coverage gap list | Recompute in Phase 8 | Read `assessment_result.coverage_gaps` from Phase 7 | Already computed by `BattlespaceAssessor` |
| Threat score for urgency | New clustering logic | Read `assessment_result.zone_threat_scores` | Already computed by `BattlespaceAssessor` |

**Key insight:** Phase 7's `BattlespaceAssessor` does all the spatial computation. Phase 8 only converts its already-serialized output into UAV tasking decisions.

## Common Pitfalls

### Pitfall 1: assessment_result Is None on First Ticks
**What goes wrong:** `_last_assessment` is None until the first 5-second interval fires. Threat-adaptive mode crashes if it tries to read coverage gaps.
**Why it happens:** The assessor only runs every 5 seconds; the coverage mode toggle might be sent before the first assessment completes.
**How to avoid:** Gate on `self._last_assessment is not None` before entering threat-adaptive dispatch. Fall back to balanced dispatch when None.
**Warning signs:** AttributeError on `_last_assessment.coverage_gaps` in the first 5 seconds after enabling threat-adaptive mode.

### Pitfall 2: Reassigning Active UAVs
**What goes wrong:** Threat-adaptive dispatch selects a UAV already in FOLLOW or PAINT mode, interrupting an active tracking operation.
**Why it happens:** The IDLE filter in the existing `calculate_macro_flow` path is only checked at the source zone level. The threat-adaptive path must independently filter to `mode == "IDLE"`.
**How to avoid:** Only candidate UAVs where `u.mode == "IDLE"` for threat-adaptive dispatch.
**Warning signs:** UAVs jumping from FOLLOW/PAINT to REPOSITIONING in the sim log.

### Pitfall 3: ISR Queue Stale Between Assessment Intervals
**What goes wrong:** `isr_queue` in the frontend shows outdated requirements for 5 seconds until the next assessment.
**Why it happens:** The queue is only rebuilt when assessment fires, not each tick.
**How to avoid:** Include the ISR queue in the same 5-second assessment payload update, not in the 10Hz tick broadcast. The frontend `SimulationStore` stores the queue as a separate field updated only on `ISR_QUEUE_UPDATE` or alongside the `assessment` key.
**Warning signs:** Frontend showing destroyed/verified targets still in the queue.

### Pitfall 4: Heuristic Tasking Conflicts with Autonomy System
**What goes wrong:** `_generate_response_heuristic()` issues tasking orders that conflict with the existing autonomy transition system (Phase 3 `AUTONOMOUS_TRANSITIONS`).
**Why it happens:** Both systems can independently tell a UAV to reposition.
**How to avoid:** Heuristic only targets IDLE UAVs. The autonomy transition system handles non-IDLE mode changes. These are non-overlapping — IDLE UAVs are not in `AUTONOMOUS_TRANSITIONS` paths except `("IDLE", "target_detected_in_zone") -> SEARCH`.
**Warning signs:** UAVs being assigned to two tasks simultaneously.

### Pitfall 5: Missing `mode_source` Update for ISR-Driven Moves
**What goes wrong:** UAVs repositioned by ISR priority still show `mode_source = "HUMAN"` in the frontend.
**Why it happens:** The existing `calculate_macro_flow` path doesn't set `mode_source`. The new threat-adaptive path must set `u.mode_source = "AUTO"`.
**Warning signs:** Operator confusion — ISR-driven UAVs appear as human-commanded.

## Code Examples

### ISRRequirement scoring formula
```python
# Source: derived from REQUIREMENTS.md FR-7 + project verification patterns
# urgency = threat_weight * (1 - fused_confidence) * recency_factor
THREAT_WEIGHTS = {
    "SAM": 1.0,
    "TEL": 0.9,
    "MANPADS": 0.8,
    "RADAR": 0.7,
    "CP": 0.6,
    "C2_NODE": 0.6,
    "TRUCK": 0.4,
    "LOGISTICS": 0.3,
}

def _score_target(target: dict) -> float:
    threat_w = THREAT_WEIGHTS.get(target["type"], 0.5)
    verification_gap = 1.0 - target.get("fused_confidence", 0.0)
    # Boost urgency for targets stuck in DETECTED/CLASSIFIED for a long time
    time_factor = min(1.0, target.get("time_in_state_sec", 0.0) / 60.0)
    return threat_w * verification_gap * (0.5 + 0.5 * time_factor)
```

### Coverage mode gate in tick()
```python
# Source: derived from existing sim_engine.py tick() structure at line ~753
MIN_IDLE_COUNT = 3  # never drop below 3 idle UAVs

# 4. Calculate imbalances and dispatches
if self.coverage_mode == "threat_adaptive" and self._last_assessment is not None:
    dispatches = self._threat_adaptive_dispatches()
else:
    dispatches = self.grid.calculate_macro_flow(dt_sec)
```

### Threat-adaptive dispatch (skeleton)
```python
def _threat_adaptive_dispatches(self) -> list:
    """
    Redistribute IDLE UAVs toward coverage gaps from assessment.
    Returns list of {source_id, count, target_coord} dicts (same format
    as calculate_macro_flow output — drop-in replacement).
    """
    dispatches = []
    idle_uavs = [u for u in self.uavs if u.mode == "IDLE"]
    if len(idle_uavs) <= MIN_IDLE_COUNT:
        return dispatches  # safety: never drain all idles

    gaps = sorted(
        self._last_assessment.coverage_gaps,
        key=lambda g: -g.threat_score  # highest threat gap first
    )
    assigned = 0
    for gap in gaps:
        if len(idle_uavs) - assigned <= MIN_IDLE_COUNT:
            break
        # Find nearest idle UAV to this gap
        nearest = min(
            idle_uavs,
            key=lambda u: (u.x - gap.lon) ** 2 + (u.y - gap.lat) ** 2
        )
        dispatches.append({
            "source_id": nearest.zone_id,
            "count": 1,
            "source_coord": (nearest.x, nearest.y),
            "target_coord": (gap.lon, gap.lat),
        })
        idle_uavs.remove(nearest)  # mark as assigned this tick
    return dispatches
```

### TypeScript type additions
```typescript
// Source: project types.ts pattern
export interface ISRRequirement {
  target_id: number;
  target_type: string;
  urgency_score: number;
  verification_gap: number;
  missing_sensor_types: string[];
  recommended_uav_ids: number[];
}

// Extend UAV interface (add to existing)
// tasking_source: 'ZONE_BALANCE' | 'ISR_PRIORITY' | 'OPERATOR';
```

### Blueprint SegmentedControl for coverage mode
```typescript
// Source: existing AutonomyToggle.tsx pattern (Phase 3)
// options array must be mutable — not as const (locked decision 2026-03-20)
const COVERAGE_OPTIONS = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Threat-Adaptive', value: 'threat_adaptive' },
];

<SegmentedControl
  options={COVERAGE_OPTIONS}
  value={coverageMode}
  onValueChange={val => sendMessage({ action: 'set_coverage_mode', mode: val })}
  small
/>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AITaskingManagerAgent calls LLM | Heuristic fallback when `llm_client=None` | Phase 8 (this phase) | LLM not required for sim operation |
| Zone-imbalance only dispatch | Two-mode: balanced vs threat-adaptive | Phase 8 (this phase) | Assessment-driven coverage without removing existing behavior |
| UAVs have no tasking attribution | `tasking_source` field on UAV | Phase 8 (this phase) | Operator visibility into auto vs human tasking |

**Deprecated/outdated:**
- `_generate_response()` raising `NotImplementedError`: still present but now bypassed via heuristic path when `llm_client is None`.

## Open Questions

1. **Should `isr_queue` be part of the 10Hz `get_state()` broadcast or a separate 5-second update?**
   - What we know: Phase 7 sends assessment data on a 5-second sub-loop.
   - What's unclear: Whether ISR queue needs to update at 10Hz (since verification state changes each tick) or if 5Hz staleness is acceptable.
   - Recommendation: Include in the same 5-second assessment payload. The UI doesn't need sub-second ISR queue updates. Avoids redundant computation in the hot 10Hz path.

2. **What is the Phase 7 `AssessmentResult` serialization format (exact field names in `get_state()`)?**
   - What we know: Phase 7 Plan 02 adds `assessment` key to get_state(). Phase 7 is PLANNED but not yet executed.
   - What's unclear: Exact field names for `coverage_gaps` list items (lat/lon/zone_id/threat_score).
   - Recommendation: Phase 8 Plan 01 must read Phase 7 artifacts first. The `ISRPriorityQueue` should accept dict input (not typed dataclasses) for robustness.

3. **Minimum idle count — is 3 the right floor?**
   - What we know: The existing zone imbalance logic doesn't have an explicit minimum. Phase 5 research mentions `min_idle_count` as a constraint.
   - What's unclear: Whether Phase 5 implemented this as a constant or a theater YAML value.
   - Recommendation: Hardcode `MIN_IDLE_COUNT = 3` for Phase 8. Make it a `SimulationModel` field so it can be overridden via theater YAML in a future phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (venv at `./venv/bin/python3 -m pytest`) |
| Config file | none — invoked directly |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_adaptive_isr.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-7 | ISR queue ranks targets by urgency score | unit | `pytest src/python/tests/test_adaptive_isr.py::test_isr_queue_ranking -x` | Wave 0 |
| FR-7 | High-threat targets (SAM, TEL) score higher than low-threat (TRUCK, LOGISTICS) | unit | `pytest src/python/tests/test_adaptive_isr.py::test_threat_weight_ordering -x` | Wave 0 |
| FR-7 | Empty target list returns empty ISR queue without exception | unit | `pytest src/python/tests/test_adaptive_isr.py::test_empty_state -x` | Wave 0 |
| FR-7 | Verified targets (fused_confidence >= 0.8) have near-zero verification gap and low urgency | unit | `pytest src/python/tests/test_adaptive_isr.py::test_verified_targets_low_urgency -x` | Wave 0 |
| FR-7 | Threat-adaptive dispatch does not reduce idle UAVs below MIN_IDLE_COUNT | unit | `pytest src/python/tests/test_adaptive_isr.py::test_min_idle_constraint -x` | Wave 0 |
| FR-7 | coverage_mode "threat_adaptive" dispatches toward coverage gaps not zone imbalance | integration | `pytest src/python/tests/test_adaptive_isr.py::test_threat_adaptive_dispatch -x` | Wave 0 |
| FR-7 | set_coverage_mode WS action toggles sim.coverage_mode | integration | `pytest src/python/tests/test_sim_integration.py::test_set_coverage_mode -x` | ❌ Wave 0 |
| FR-7 | AITaskingManagerAgent heuristic returns tasking orders for low-confidence detections | unit | `pytest src/python/tests/test_adaptive_isr.py::test_heuristic_tasking -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_adaptive_isr.py -x`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_adaptive_isr.py` — covers FR-7 (all unit tests above)
- [ ] Add `test_set_coverage_mode` to `src/python/tests/test_sim_integration.py`

## Sources

### Primary (HIGH confidence)
- Direct code reading of `src/python/agents/ai_tasking_manager.py` — current AITaskingManagerAgent contract and gap
- Direct code reading of `src/python/sim_engine.py` (lines 720-780) — tick() dispatch path and zone logic
- Direct code reading of `src/python/api_main.py` (lines 96-130) — action schemas, agent instantiation, simulation loop
- Direct code reading of `src/frontend-react/src/store/types.ts` — UAV type, existing fields
- Direct code reading of `src/frontend-react/src/panels/assets/DroneCard.tsx` — existing mode_source display pattern
- `.planning/REQUIREMENTS.md` FR-7 — requirement definition
- `.planning/phases/07-battlespace-assessment/07-RESEARCH.md` — Phase 7 output contract (AssessmentResult)
- `.planning/phases/07-battlespace-assessment/07-01-PLAN.md` and `07-02-PLAN.md` — exact artifacts Phase 8 depends on

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` Decisions Log — locked decisions re: Blueprint SegmentedControl as const, Zustand 4.5.0, mode_source field
- `.planning/ROADMAP.md` Phase 8 section — files changed list and risk assessment

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, versions locked by prior phases
- Architecture: HIGH — direct code reading; all integration points verified against actual sim_engine.py and api_main.py
- Pitfalls: HIGH — derived from direct code reading of existing tick() logic and AITaskingManagerAgent contracts
- Phase 7 output contract: MEDIUM — Phase 7 plans specify the interface but Phase 7 has not yet been executed; exact field names may shift

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable codebase — risk is Phase 7 execution changing assessment field names)
