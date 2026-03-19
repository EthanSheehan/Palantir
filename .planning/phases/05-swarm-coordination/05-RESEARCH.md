# Phase 5: Swarm Coordination - Research

**Researched:** 2026-03-19
**Domain:** Multi-UAV greedy assignment, Python dataclasses, React/Blueprint UI, Cesium polylines
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-4 | Automatic dispatch of complementary sensors to targets; greedy nearest-available assignment with sensor-type match; minimum idle count constraint; Request/release swarm via operator command | Algorithm pattern documented below; idle-count guard logic mapped; two WS actions identified; SwarmPanel + Cesium hook patterns derived from existing code |

</phase_requirements>

---

## Summary

Phase 5 adds a `SwarmCoordinator` class that runs per-tick after the detection/fusion loop and issues `TaskingOrder`s to IDLE/SEARCH UAVs that have sensor gaps relative to detected targets. The algorithm is a simple greedy assignment: score targets by `threat × (1 - confidence) × elapsed_time`, sort highest-first, find the nearest available UAV with the needed sensor type, and skip if assigning would drop the IDLE count below `min_idle_count`. No external solver library is needed — the greedy approach is intentional (fast, predictable, debuggable at 10 Hz).

The codebase patterns are already mature. `sensor_fusion.py` shows the frozen-dataclass style for domain types. `sim_engine.py` shows how `_assign_target()` wires a UAV to a target while keeping `tracked_by_uav_ids` and `primary_target_id` consistent. The React side follows the pattern established by `FusionBar.tsx` and `EnemyCard.tsx`: pull from Zustand, render inline styles matching Blueprint dark theme. The Cesium side follows `useCesiumFlowLines.ts`: subscribe to the Zustand store, tear down and rebuild entities on each state update using `viewer.entities`.

**Primary recommendation:** Implement `SwarmCoordinator` as a pure-logic class (no I/O, no async) invoked synchronously inside `SimulationModel.tick()` after the fusion block. Expose swarm state (`swarm_tasks`) in `get_state()` so the frontend can render without any new WS message types.

---

## Standard Stack

### Core (all already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python dataclasses (stdlib) | 3.11+ | `SwarmTask`, `TaskingOrder` value types | Already used: `SensorContribution`, `FusedDetection` follow this pattern |
| `math` (stdlib) | 3.11+ | Distance calculations (`math.hypot`) | Already used throughout `sim_engine.py` |
| `typing` (stdlib) | 3.11+ | Type hints, `Optional`, `List` | Project convention |
| React + Zustand 4.5.0 | locked | State management, component rendering | Locked decision |
| Blueprint 5.x | installed | UI components (Button, Icon, Tag) | Project UI standard |
| CesiumJS (vite-plugin-cesium) | installed | Dashed polyline formation lines | Pattern in `useCesiumFlowLines.ts` |

### No New Dependencies Required

The entire phase uses only what is already installed. This is a HIGH confidence finding from direct codebase inspection.

---

## Architecture Patterns

### Recommended Project Structure

```
src/python/
  swarm_coordinator.py         # NEW — SwarmCoordinator class + dataclasses
  sim_engine.py                # MODIFY — call coordinator.evaluate_and_assign() in tick()
  api_main.py                  # MODIFY — add request_swarm / release_swarm WS actions

src/python/tests/
  test_swarm_coordinator.py    # NEW — pytest unit tests

src/frontend-react/src/
  panels/enemies/
    SwarmPanel.tsx             # NEW — per-target sensor coverage indicator
  cesium/
    useCesiumSwarmLines.ts     # NEW — dashed cyan polylines between swarm members
```

### Pattern 1: Frozen Dataclass Domain Types

The project uses `@dataclass(frozen=True)` for value types to enforce immutability (see `sensor_fusion.py`). Follow the same pattern for swarm types.

```python
# Source: src/python/sensor_fusion.py — established project pattern
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SwarmTask:
    target_id: int
    assigned_uav_ids: tuple[int, ...]   # tuple, not list — frozen-compatible
    sensor_coverage: tuple[str, ...]    # sensor types currently covered
    formation_type: str                  # "SUPPORT_RING" | "SENSOR_CLUSTER"

@dataclass(frozen=True)
class TaskingOrder:
    uav_id: int
    target_id: int
    mode: str           # always "SUPPORT" for Phase 5
    reason: str         # human-readable, shown in assistant log
    priority: int       # higher = more urgent
```

### Pattern 2: SwarmCoordinator Class Structure

```python
# src/python/swarm_coordinator.py
import math
from typing import List, Dict, Optional

SENSOR_TYPES = ("EO_IR", "SAR", "SIGINT")

class SwarmCoordinator:
    def __init__(self, min_idle_count: int = 3):
        self.min_idle_count = min_idle_count
        # target_id -> SwarmTask (mutable across ticks — coordinator owns this state)
        self._active_tasks: Dict[int, SwarmTask] = {}

    def evaluate_and_assign(
        self,
        targets: list,  # sim_engine.Target objects
        uavs: list,     # sim_engine.UAV objects
    ) -> List[TaskingOrder]:
        """
        Greedy assignment pass. Returns list of TaskingOrders to execute.
        Called by SimulationModel.tick() — must be fast (O(T*U) where T=targets, U=UAVs).
        """
        orders = []

        # 1. Score each detectable target
        scored = []
        for t in targets:
            if t.state not in ("DETECTED", "CLASSIFIED"):
                continue
            gap_types = self._sensor_gap(t)
            if not gap_types:
                continue
            score = self._priority_score(t)
            scored.append((score, t, gap_types))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 2. Greedy assignment with idle guard
        idle_count = sum(1 for u in uavs if u.mode in ("IDLE", "SEARCH"))

        for _score, target, gap_types in scored:
            for needed_sensor in gap_types:
                if idle_count <= self.min_idle_count:
                    break
                candidate = self._find_nearest(uavs, target, needed_sensor)
                if candidate is None:
                    continue
                orders.append(TaskingOrder(
                    uav_id=candidate.id,
                    target_id=target.id,
                    mode="SUPPORT",
                    reason=f"Sensor gap: {needed_sensor} needed for TARGET-{target.id}",
                    priority=int(_score * 100),
                ))
                idle_count -= 1

        return orders

    def _sensor_gap(self, target) -> List[str]:
        """Return sensor types not yet contributing to this target."""
        covered = {c.sensor_type for c in target.sensor_contributions}
        return [s for s in SENSOR_TYPES if s not in covered]

    def _priority_score(self, target) -> float:
        """threat_weight * (1 - confidence) — higher = more urgent."""
        THREAT_WEIGHTS = {"SAM": 1.0, "TEL": 0.9, "CP": 0.7, "TRUCK": 0.5}
        threat = THREAT_WEIGHTS.get(target.type, 0.5)
        gap = 1.0 - target.fused_confidence
        return threat * gap

    def _find_nearest(self, uavs, target, sensor_type: str):
        """Find nearest IDLE/SEARCH UAV with the required sensor type."""
        candidates = [
            u for u in uavs
            if u.mode in ("IDLE", "SEARCH")
            and sensor_type in u.sensors
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda u: math.hypot(u.x - target.x, u.y - target.y))

    def get_active_tasks(self) -> Dict[int, SwarmTask]:
        return dict(self._active_tasks)
```

### Pattern 3: sim_engine.tick() Integration

The coordinator runs after Step 9 (fusion/detection) in the existing tick flow. This is the same position where any future battlespace assessment hook would also run.

```python
# src/python/sim_engine.py — inside tick() after the fusion block
# Step 10 (NEW): Swarm coordination
swarm_orders = self.swarm_coordinator.evaluate_and_assign(self.targets, self.uavs)
for order in swarm_orders:
    self._assign_target(order.uav_id, order.target_id, "SUPPORT", "DETECTED")
    # SUPPORT mode: wide ~3km orbit, contributes sensor data (Phase 3 definition)
```

**Critical constraint:** `_assign_target()` must NOT be called when a UAV's mode is already "SUPPORT" for the same target. Add a guard: skip if `uav.mode == "SUPPORT" and order.target_id in uav.tracked_target_ids`.

### Pattern 4: get_state() Extension

Swarm task data travels via the existing STATE broadcast — no new WS message type needed.

```python
# src/python/sim_engine.py — in get_state()
"swarm_tasks": [
    {
        "target_id": task.target_id,
        "assigned_uav_ids": list(task.assigned_uav_ids),
        "sensor_coverage": list(task.sensor_coverage),
        "formation_type": task.formation_type,
    }
    for task in self.swarm_coordinator.get_active_tasks().values()
],
```

### Pattern 5: WebSocket Actions

Two new WS actions following the existing `_ACTION_SCHEMAS` pattern:

```python
# src/python/api_main.py — add to _ACTION_SCHEMAS
"request_swarm": {"target_id": "int"},
"release_swarm": {"target_id": "int"},
```

Handler logic:
- `request_swarm`: force-assign the nearest matching UAV for each sensor gap on that target immediately (bypasses score ordering)
- `release_swarm`: cancel SUPPORT mode for all UAVs tracking that target, set them to "SEARCH"

### Pattern 6: React SwarmPanel Component

Follows `FusionBar.tsx` (src/frontend-react/src/panels/enemies/FusionBar.tsx) inline-style pattern — no new CSS files.

```typescript
// src/frontend-react/src/panels/enemies/SwarmPanel.tsx
interface SwarmPanelProps {
  target: Target;
  swarmTasks: SwarmTask[];  // filtered to this target
}

// Sensor icons: filled (contributing) vs hollow (gap)
const SENSOR_COLORS = {
  EO_IR:  '#4A90E2',  // blue — matches FusionBar
  SAR:    '#7ED321',  // green
  SIGINT: '#F5A623',  // amber
};
```

### Pattern 7: Cesium Swarm Lines Hook

Follows `useCesiumFlowLines.ts` exactly — subscribe to store, rebuild on change.

```typescript
// src/frontend-react/src/cesium/useCesiumSwarmLines.ts
// Dashed polyline: use PolylineDashMaterialProperty instead of PolylineGlowMaterialProperty
material: new Cesium.PolylineDashMaterialProperty({
  color: Cesium.Color.CYAN.withAlpha(0.7),
  dashLength: 16.0,
})
```

**Key difference from flow lines:** swarm lines connect UAV positions to target positions, not zone centers to zone centers. The hook must read from `state.uavs` and `state.swarmTasks` jointly.

### Anti-Patterns to Avoid

- **Mutating SwarmTask in place:** Use immutable dataclasses. When a task changes, create a new `SwarmTask` and replace `_active_tasks[target_id]`.
- **Running coordinator before fusion:** The coordinator reads `target.sensor_contributions` and `target.fused_confidence` — these are only valid after the fusion block in step 9.
- **Assigning SUPPORT to RTB/REPOSITIONING UAVs:** The `_find_nearest()` filter must exclude `RTB` and `REPOSITIONING` modes.
- **Draining all IDLEs:** The `idle_count <= min_idle_count` guard must be checked BEFORE each assignment, not after.
- **New WS message types for swarm data:** Piggybacking on the existing state broadcast avoids frontend subscription complexity.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Distance calculation | Custom Euclidean lat/lon | `math.hypot(u.x - t.x, u.y - t.y)` | Already used throughout sim_engine.py; degree-space distance is fine at theater scale |
| Dashed polylines | Custom canvas overlay | `Cesium.PolylineDashMaterialProperty` | Built-in Cesium material, zero extra code |
| Optimal assignment | Hungarian algorithm / OR-Tools | Greedy nearest-available | Roadmap explicitly specifies greedy; Hungarian is overkill at 10-20 UAVs |
| Swarm state persistence | Redis / database | In-memory `_active_tasks` dict on `SwarmCoordinator` | Single process, reset on restart is acceptable |

**Key insight:** The greedy algorithm is O(T × U) per tick where T ≤ 20 targets and U ≤ 20 UAVs — that is ≤ 400 comparisons at 10 Hz, negligible cost. Do not introduce a solver.

---

## Common Pitfalls

### Pitfall 1: Re-assigning Already-Assigned UAVs
**What goes wrong:** `evaluate_and_assign()` runs every tick. It will keep issuing `TaskingOrder`s for UAVs already in SUPPORT mode, causing redundant `_assign_target()` calls and log spam.
**Why it happens:** The coordinator sees the UAV as "IDLE" before `_assign_target()` updates the mode, or doesn't check existing SUPPORT assignments.
**How to avoid:** At the start of `_find_nearest()`, exclude UAVs already in SUPPORT mode for any tracked target. Also, after issuing a `TaskingOrder`, optimistically update the local `idle_count` down by 1.
**Warning signs:** Log shows repeated "command_assign" for the same UAV-target pair.

### Pitfall 2: Zone Balancing Conflict
**What goes wrong:** `SimulationModel.tick()` step 3 assigns IDLE UAVs to SEARCH for zones with demand. Step 5 dispatches them to REPOSITIONING. If swarm coordinator runs after these, it may find no IDLE UAVs.
**Why it happens:** Zone balancing greedily consumes IDLEs before swarm gets a turn.
**How to avoid:** Run swarm coordinator AFTER zone balancing (Step 5) but check `u.mode in ("IDLE", "SEARCH")` — UAVs in SEARCH are eligible for swarm assignment. The SEARCH→SUPPORT transition is valid (no orbit commitment yet).
**Warning signs:** `evaluate_and_assign()` returns orders but `idle_count` check always blocks them.

### Pitfall 3: SUPPORT Mode Not Defined in sim_engine
**What goes wrong:** Phase 5 calls `_assign_target(uav_id, target_id, "SUPPORT", ...)` but `UAV_MODES` tuple does not include "SUPPORT" yet (that's Phase 3's job). If Phase 3 is not yet implemented, the mode string is unrecognized by `_update_tracking_modes()` and the UAV will drift.
**Why it happens:** Phase ordering — Phases 1-4 must be complete before Phase 5.
**How to avoid:** Confirm `UAV_MODES` contains `"SUPPORT"` before running. Add a runtime assertion in `SwarmCoordinator.__init__` if needed. If Phase 3 is still pending, stub SUPPORT as FOLLOW for Phase 5 dev.
**Warning signs:** UAVs assigned SUPPORT mode but `_update_tracking_modes()` skips them (the `if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT")` guard).

### Pitfall 4: Cesium Swarm Lines Position Source
**What goes wrong:** Swarm lines connect wrong positions because UAV positions in the store are `{lat, lon}` but target positions are also `{lat, lon}` — but Cesium `fromDegreesArray` expects `[lon, lat]` order.
**Why it happens:** Lat/lon vs lon/lat confusion common in geo code.
**How to avoid:** Follow the exact pattern in `useCesiumFlowLines.ts` — it uses `flow.source[0], flow.source[1]` where source is `[lon, lat]`. Match the ordering from `get_state()` which serializes as `"lon": u.x, "lat": u.y`.
**Warning signs:** Lines appear but point to wrong continent / off-screen.

### Pitfall 5: Zustand Types Not Updated
**What goes wrong:** Backend broadcasts `swarm_tasks` in state but TypeScript types in `types.ts` don't include it, causing implicit `any` and potential runtime errors.
**How to avoid:** Add `SwarmTask` interface and `swarm_tasks: SwarmTask[]` to `SimStatePayload` and `SimState` at the start of the frontend plan.

---

## Code Examples

### Existing Pattern: assign_target (do not break)

```python
# Source: src/python/sim_engine.py:465-478
def _assign_target(self, uav_id: int, target_id: int, mode: str, target_state: str):
    uav = self._find_uav(uav_id)
    target = self._find_target(target_id)
    if not uav or not target:
        logger.warning("command_failed", mode=mode, uav_id=uav_id, target_id=target_id)
        return
    uav.mode = mode
    uav.tracked_target_id = target_id
    uav.commanded_target = None
    if uav_id not in target.tracked_by_uav_ids:
        target.tracked_by_uav_ids.append(uav_id)
    if target_state == "LOCKED" or target.state in ("DETECTED", "UNDETECTED"):
        target.state = target_state
```

### Existing Pattern: Cesium Dashed Lines Material

```typescript
// Source: Cesium API — PolylineDashMaterialProperty (verified against Cesium docs)
new Cesium.PolylineDashMaterialProperty({
  color: Cesium.Color.CYAN.withAlpha(0.7),
  gapColor: Cesium.Color.TRANSPARENT,
  dashLength: 16.0,
  dashPattern: 255,
})
```

### Existing Pattern: Blueprint Button with intent

```typescript
// Source: src/frontend-react/src/panels/mission/StrikeBoard.tsx (existing component)
import { Button, Intent } from '@blueprintjs/core';
<Button intent={Intent.PRIMARY} small onClick={handleRequestSwarm}>
  REQUEST SWARM
</Button>
```

### Existing Pattern: React.memo with custom comparator

```typescript
// Source: src/frontend-react/src/panels/enemies/EnemyCard.tsx:187-189
export const EnemyCard = React.memo(EnemyCardInner, (prev, next) => {
  return targetsShallowEqual(prev.target, next.target) && trackersEqual(prev.trackers, next.trackers);
});
```

SwarmPanel should follow this pattern — compare `swarmTasks` by `assigned_uav_ids` length and sensor coverage, not reference equality.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single UAV per target tracking | `tracked_by_uav_ids: list` per target | Phase 1 (complete) | Swarm can assign multiple UAVs without breaking existing tracking |
| Boolean `detected` field | Full state machine (`DETECTED`/`CLASSIFIED`/etc.) | Phase 1 (complete) | Coordinator can score by state in Phase 5 |
| Single sensor per UAV | `sensors: list[str]` per UAV | Phase 1 (complete) | Sensor-type matching in `_find_nearest()` is already possible |
| `_assign_target()` as command-only | Used by both commands and swarm | Phase 5 (this phase) | Coordinator reuses existing wiring |

---

## Open Questions

1. **SUPPORT mode orbit behavior**
   - What we know: Phase 3 defines SUPPORT as "wide orbit ~3km, provides secondary sensor data"
   - What's unclear: If Phase 3 is not yet implemented when Phase 5 is planned, `_update_tracking_modes()` won't have SUPPORT handling
   - Recommendation: Planner should check Phase 3 completion status before writing Phase 5 plans. If Phase 3 pending, stub SUPPORT as FOLLOW in `_update_tracking_modes()` with a TODO comment.

2. **Swarm task persistence across ticks**
   - What we know: `evaluate_and_assign()` runs every tick; UAVs can be re-tasked by operator commands
   - What's unclear: Should the coordinator track which tasks it issued and not re-issue them if the UAV is already in SUPPORT mode?
   - Recommendation: Yes — maintain `_active_tasks: Dict[int, SwarmTask]` on the coordinator. Update it from the UAV/target state at the top of each `evaluate_and_assign()` call rather than re-issuing orders blindly.

3. **Demo autopilot integration**
   - What we know: `demo_autopilot()` in `api_main.py` auto-fires follow/paint. Swarm runs automatically per tick.
   - What's unclear: Will demo mode produce observable swarm behavior without explicit demo_autopilot changes?
   - Recommendation: Swarm coordinator runs regardless of demo mode — it should activate naturally as targets become DETECTED. No demo_autopilot changes needed for Phase 5.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed at `./venv/bin/python3 -m pytest`) |
| Config file | none — tests discovered by pattern |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_swarm_coordinator.py -x -q` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| FR-4 | Greedy assignment dispatches nearest UAV with matching sensor | unit | `pytest tests/test_swarm_coordinator.py::test_assigns_nearest_matching_uav -x` | Wave 0 |
| FR-4 | Idle count guard prevents draining all UAVs | unit | `pytest tests/test_swarm_coordinator.py::test_idle_guard_respected -x` | Wave 0 |
| FR-4 | No assignment when confidence already 1.0 (no gap) | unit | `pytest tests/test_swarm_coordinator.py::test_no_assignment_when_fully_covered -x` | Wave 0 |
| FR-4 | Same-sensor UAV not re-assigned if already contributing | unit | `pytest tests/test_swarm_coordinator.py::test_no_duplicate_sensor -x` | Wave 0 |
| FR-4 | Request/release swarm WS actions accepted without error | integration | `pytest tests/test_swarm_coordinator.py::test_request_release_swarm -x` | Wave 0 |
| FR-4 | Swarm tasks appear in get_state() broadcast | integration | `pytest tests/test_sim_integration.py::test_swarm_state_in_broadcast -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_swarm_coordinator.py -x -q`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_swarm_coordinator.py` — covers FR-4 (all rows above)
- [ ] `SwarmTask` and `TaskingOrder` types in `src/frontend-react/src/store/types.ts`

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `src/python/sim_engine.py`, `src/python/sensor_fusion.py`, `src/python/api_main.py`, `src/frontend-react/src/store/SimulationStore.ts`, `src/frontend-react/src/store/types.ts`, `src/frontend-react/src/cesium/useCesiumFlowLines.ts`, `src/frontend-react/src/panels/enemies/EnemyCard.tsx` — all patterns derived from live code
- `.planning/ROADMAP.md` — algorithm spec, file list, risk assessment
- `.planning/REQUIREMENTS.md` — FR-4 specification

### Secondary (MEDIUM confidence)
- Cesium `PolylineDashMaterialProperty` — standard Cesium API, confirmed present in project's Cesium install via `vite-plugin-cesium`

### Tertiary (LOW confidence)
- None — all findings based on primary source inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies confirmed present in codebase
- Architecture: HIGH — patterns derived directly from existing working code
- Pitfalls: HIGH — derived from reading actual sim_engine.tick() flow and known Phase 3 dependency
- Algorithm: HIGH — roadmap specifies greedy explicitly; no research needed on alternatives

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable codebase, no external API dependencies)
