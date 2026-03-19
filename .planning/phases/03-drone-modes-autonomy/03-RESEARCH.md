# Phase 3: Drone Modes & Autonomy - Research

**Researched:** 2026-03-19
**Domain:** Python simulation state machine, asyncio event loop, React/Blueprint UI
**Confidence:** HIGH

---

## Summary

Phase 3 adds four new UAV behavioral modes (SUPPORT, VERIFY, OVERWATCH, BDA) and a 3-tier autonomy
system (MANUAL / SUPERVISED / AUTONOMOUS) to the existing simulation engine. The Python work is
straightforward: the sim already has a clean mode dispatch pattern in `_update_tracking_modes()` and
`UAV.update()`. Adding new modes follows the same orbit-math patterns already used for FOLLOW/PAINT.

The 3-tier autonomy system requires two new pieces of state on `SimulationModel`: a fleet-wide
`autonomy_level` and a per-UAV `autonomy_override`. In SUPERVISED mode, the engine queues a pending
transition and holds it until the operator approves or a countdown expires — this is the only
significantly new architectural concept. Pending transitions are best stored as a dict on the sim,
keyed by `uav_id`, and broadcast to the dashboard each tick so the frontend can render countdowns.

The React side needs a global `AutonomyToggle` component and per-pending-transition `TransitionToast`
components. Blueprint's `Toast2`/`Toaster` API (v5+) is async and requires a ref rather than a static
`create()` call — this is the main pitfall. All new mode colors must be added to `constants.ts` so
Cesium and UI components stay consistent.

**Primary recommendation:** Add autonomy fields to `SimulationModel` directly (not a separate
module); keep autonomy logic inside `sim_engine.py` since it is tightly coupled to the tick loop.
Add new mode behaviors as cases in `_update_tracking_modes()`. Isolate the pending-transition queue
as a plain dict, not a separate class, to avoid circular imports.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-3 | New modes: SUPPORT, VERIFY, OVERWATCH, BDA; 3-tier autonomy: MANUAL/SUPERVISED/AUTONOMOUS; SUPERVISED has approve/reject with auto-approve timeout; per-drone autonomy override | Orbit-math patterns verified from existing FOLLOW/PAINT code; Blueprint Toast2 API verified for countdown UI; pending-transition dict pattern identified |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python (stdlib) | 3.11+ | State machine logic, dataclasses, asyncio | Already in use |
| FastAPI / WebSocket | 0.115.x | New WS actions for autonomy | Already in use |
| pytest | 8.x | Unit tests for new mode behaviors | Already in use — `./venv/bin/python3 -m pytest src/python/tests/` |
| @blueprintjs/core | 5.x | AutonomyToggle (SegmentedControl), TransitionToast (Toast2) | Already installed in React stack |
| Zustand | 4.5.0 | Frontend state for autonomy level, pending transitions | Locked at 4.5.0 per STATE.md |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog | latest | Logging mode transitions, autonomy decisions | Already in use — follow existing pattern |
| event_logger | internal | JSONL audit trail for mode changes | Already wired in api_main.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dict-based pending transitions on SimulationModel | Separate AutonomyManager class | Dict is simpler, avoids coupling. Separate class warranted only if autonomy logic grows beyond Phase 3 scope |
| Blueprint Toast2 | Custom notification component | Toast2 already in Blueprint; hand-rolling loses keyboard nav and accessible markup |

---

## Architecture Patterns

### Recommended Project Structure

No new top-level Python modules for this phase. All sim-side logic goes into `sim_engine.py`. New
test file follows existing pattern:

```
src/python/
  sim_engine.py          # MODIFY — new modes + autonomy fields
  api_main.py            # MODIFY — 4 new WS action handlers
  tests/
    test_drone_modes.py  # NEW — unit + integration tests

src/frontend-react/src/
  panels/assets/
    DroneModeButtons.tsx  # MODIFY — add SUPPORT, VERIFY buttons
    DroneCard.tsx         # MODIFY — mode source indicator (HUMAN/AUTO)
  components/             # or panels/overlays/ — TBD based on P0 output
    AutonomyToggle.tsx    # NEW
    TransitionToast.tsx   # NEW
  shared/
    constants.ts          # MODIFY — add new mode colors
  cesium/
    useCesiumDrones.ts    # MODIFY — new mode colors for entity material
```

### Pattern 1: New Mode Orbit Behavior in `_update_tracking_modes()`

**What:** Each new mode is a `elif u.mode == "..."` block inside `_update_tracking_modes()`. This
exactly mirrors FOLLOW/PAINT/INTERCEPT.

**When to use:** All four new modes that require per-tick position updates.

**Verified from existing code (`sim_engine.py` lines 620-690):**
```python
# Existing pattern — replicate for SUPPORT, VERIFY, OVERWATCH, BDA
elif u.mode == "PAINT":
    orbit_r = PAINT_ORBIT_RADIUS_DEG
    # ... orbit math using _turn_toward() ...
    u._turn_toward(dvx, dvy, speed, dt_sec)
    u.x += u.vx * dt_sec
    u.y += u.vy * dt_sec
```

For `tick()`, add new modes to the exclusion set on line 550 so `UAV.update()` does not run on them:
```python
# CURRENT (line 550):
if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT"):
# MUST BECOME:
if u.mode not in ("FOLLOW", "PAINT", "INTERCEPT", "SUPPORT", "VERIFY", "OVERWATCH", "BDA"):
```

**This is the known bug pattern** — the STATE.md lists `sim_engine.py:509` as already having this
double-update bug for INTERCEPT. The same fix is needed for all new modes.

### Pattern 2: Autonomy State on SimulationModel

**What:** Two new fields on `SimulationModel.__init__()`:
```python
self.autonomy_level: str = "MANUAL"          # fleet-wide: MANUAL / SUPERVISED / AUTONOMOUS
self.pending_transitions: dict = {}           # uav_id -> {mode, reason, expires_at}
```

Per-UAV override field on `UAV.__init__()`:
```python
self.autonomy_override: str | None = None    # None = use fleet level
```

Helper to resolve effective autonomy for a given UAV:
```python
def _effective_autonomy(self, uav: UAV) -> str:
    return uav.autonomy_override or self.autonomy_level
```

### Pattern 3: Autonomous Transition Evaluation

**What:** Called once per tick, after kinematics, checks AUTONOMOUS_TRANSITIONS table and either
fires immediately (AUTONOMOUS) or queues a pending transition (SUPERVISED).

```python
AUTONOMOUS_TRANSITIONS = {
    ("IDLE", "target_detected_in_zone"): "SEARCH",
    ("SEARCH", "high_confidence_detection"): "FOLLOW",
    ("FOLLOW", "verification_gap"): "VERIFY",
    ("FOLLOW", "target_verified_nominated"): "PAINT",
    ("PAINT", "engagement_complete"): "BDA",
    ("BDA", "assessment_complete"): "SEARCH",
    ("IDLE", "swarm_support_requested"): "SUPPORT",
    ("IDLE", "coverage_gap_detected"): "OVERWATCH",
    # ("ANY", "fuel_below_threshold") handled separately — already in UAV.update()
}

def _evaluate_autonomy(self, dt_sec: float):
    """Evaluate autonomous transitions for all UAVs."""
    import time
    now = time.monotonic()

    # Expire timed-out pending transitions (auto-approve in SUPERVISED)
    for uav_id, pending in list(self.pending_transitions.items()):
        if now >= pending["expires_at"]:
            uav = self._find_uav(uav_id)
            if uav:
                uav.mode = pending["mode"]
            del self.pending_transitions[uav_id]

    for u in self.uavs:
        effective = self._effective_autonomy(u)
        if effective == "MANUAL":
            continue
        if u.id in self.pending_transitions:
            continue  # already has a pending transition

        trigger = self._detect_trigger(u)
        if trigger is None:
            continue
        key = (u.mode, trigger)
        new_mode = AUTONOMOUS_TRANSITIONS.get(key)
        if new_mode is None:
            continue

        if effective == "AUTONOMOUS":
            u.mode = new_mode
        elif effective == "SUPERVISED":
            TIMEOUT_SEC = 10.0  # configurable
            self.pending_transitions[u.id] = {
                "mode": new_mode,
                "reason": trigger,
                "expires_at": now + TIMEOUT_SEC,
            }
```

### Pattern 4: New WebSocket Actions

Follow the existing handler pattern in `handle_payload()`:

```python
elif action == "set_autonomy_level":
    level = payload.get("level")
    if level not in ("MANUAL", "SUPERVISED", "AUTONOMOUS"):
        await _send_error(websocket, "Invalid autonomy level", action)
        return
    sim.autonomy_level = level
    log_event("command", {"action": action, "level": level})

elif action == "set_drone_autonomy":
    # payload: {drone_id: int, level: str | None}
    uav = sim._find_uav(payload["drone_id"])
    if uav:
        uav.autonomy_override = payload.get("level")  # None clears override

elif action == "approve_transition":
    # payload: {drone_id: int}
    pending = sim.pending_transitions.pop(payload["drone_id"], None)
    if pending:
        uav = sim._find_uav(payload["drone_id"])
        if uav:
            uav.mode = pending["mode"]

elif action == "reject_transition":
    # payload: {drone_id: int}
    sim.pending_transitions.pop(payload["drone_id"], None)
```

Add these four actions to `_ACTION_SCHEMAS` for validation:
```python
"set_autonomy_level": {"level": "str"},
"set_drone_autonomy": {"drone_id": "int"},
"approve_transition": {"drone_id": "int"},
"reject_transition": {"drone_id": "int"},
```

### Pattern 5: Pending Transitions in get_state()

The state broadcast must include pending transitions so the frontend can render countdowns:

```python
# In get_state() UAV dict:
{
    "id": u.id,
    ...existing fields...,
    "autonomy_override": u.autonomy_override,
    "pending_transition": self.pending_transitions.get(u.id),  # or None
}
# Top-level:
"autonomy_level": self.autonomy_level,
```

### Pattern 6: Blueprint Toast2 (SUPERVISED countdown UI)

**Critical pitfall:** Blueprint v5 `Toast2` requires using `OverlayToaster.createAsync()` (async),
not the old `Toaster.create()` static method. Use a ref pattern:

```typescript
// TransitionToast.tsx
import { OverlayToaster, Toast2 } from "@blueprintjs/core";
import { useRef, useEffect } from "react";

const toasterRef = useRef<OverlayToaster>(null);

// Render toaster once:
<OverlayToaster ref={toasterRef} position="top-right" />

// Show per-transition:
toasterRef.current?.show({
  message: <TransitionToastBody uavId={uavId} mode={mode} reason={reason} expiresAt={expiresAt} />,
  intent: "warning",
  timeout: timeoutMs,
  action: { text: "Approve", onClick: () => sendApprove(uavId) },
  onDismiss: () => sendReject(uavId),
});
```

**Alternative confirmed working:** render `<Toast2>` inside the component tree when a pending
transition exists; use a `useInterval` hook to update countdown display. This avoids the async
`createAsync()` complexity and is simpler to test.

### Pattern 7: SegmentedControl for AutonomyToggle

Blueprint `SegmentedControl` (v5) is the correct component for MANUAL / SUPERVISED / AUTONOMOUS:

```typescript
// AutonomyToggle.tsx
import { SegmentedControl } from "@blueprintjs/core";

<SegmentedControl
  options={[
    { label: "MANUAL", value: "MANUAL" },
    { label: "SUPERVISED", value: "SUPERVISED" },
    { label: "AUTONOMOUS", value: "AUTONOMOUS" },
  ]}
  value={autonomyLevel}
  onValueChange={(val) => {
    setAutonomyLevel(val);
    sendWsAction({ action: "set_autonomy_level", level: val });
  }}
  intent="primary"
  small
/>
```

### Mode Physics Reference

New modes — orbit radii follow existing naming convention (`DEG_PER_KM = 1/111`):

```python
# Add to sim_engine.py constants:
SUPPORT_ORBIT_RADIUS_DEG = 0.027      # ~3km (same as LOITER_RADIUS_DEG)
VERIFY_CROSS_DISTANCE_DEG = 0.009     # ~1km perpendicular offset
OVERWATCH_RACETRACK_LENGTH_DEG = 0.045  # ~5km straight legs
BDA_ORBIT_RADIUS_DEG = 0.009          # ~1km tight (same as PAINT)
BDA_DURATION_SEC = 30.0               # auto-transitions to SEARCH after 30s
```

**BDA auto-transition:** Add a `bda_timer` field to UAV (set when entering BDA, decremented per
tick). When timer expires, set mode to SEARCH. This avoids relying on the autonomy layer for a
time-triggered transition.

### Anti-Patterns to Avoid

- **Putting BDA auto-transition in autonomy evaluation:** BDA→SEARCH is always time-triggered (30s),
  not conditional. Bake it into the BDA mode behavior block directly. Autonomy only gates transitions
  driven by external events (detections, zone conditions).
- **Adding `autonomy_level` to the `UAV` class as primary storage:** Keep fleet-wide on
  `SimulationModel`; per-UAV is an override only.
- **Putting pending transitions in `UAV` class:** Storing them on `SimulationModel` keeps the
  approval/reject logic in one place (the sim's command interface), not scattered.
- **Calling `Toaster.create()` (Blueprint v4 static API):** Does not work in Blueprint v5. Use
  `OverlayToaster` ref or render inline `Toast2` components.
- **Forgetting to update `_update_tracking_modes()` guard:** The mode exclusion list on `tick()`
  line 550 must include all four new modes or they will receive a double physics update.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fixed-wing turn physics | Custom trigonometry | Existing `_turn_toward()` method | Already handles heading wrap, max turn rate, fixed-wing arc |
| Circular orbit math | Custom orbit loop | Existing FOLLOW/PAINT orbit block | Proven, tested, same radial logic works for SUPPORT/BDA |
| Toast notifications | Custom notification div | Blueprint `Toast2` / `OverlayToaster` | Accessible, positioned, auto-dismiss, action buttons built in |
| Countdown timer display | `setTimeout` chain | `useInterval` hook (or `setInterval` in useEffect cleanup) | Avoids stale closure bugs |
| WebSocket action validation | Ad-hoc checks | Existing `_validate_payload()` + `_ACTION_SCHEMAS` | Already tested, consistent error format |

---

## Common Pitfalls

### Pitfall 1: Double Physics Update on New Modes

**What goes wrong:** New modes added to `_update_tracking_modes()` but not excluded from
`UAV.update()` on tick line 550. UAV position updates twice per tick — jitters or teleports.

**Why it happens:** `UAV.update()` handles IDLE/SEARCH/RTB/REPOSITIONING. FOLLOW/PAINT/INTERCEPT are
already in the exclusion list. Any new mode handled in `_update_tracking_modes()` must be added too.

**How to avoid:** Always update the exclusion tuple at the same time as adding the new mode case.

**Warning signs:** Drone moves 2x expected distance per tick; erratic orbits.

### Pitfall 2: Pending Transition Race — Approve After Expiry

**What goes wrong:** Frontend sends `approve_transition` after the server has already auto-approved
and cleared the entry. Causes a no-op (fine) but frontend countdown timer shows "approved" when
nothing happened.

**How to avoid:** `approve_transition` handler pops from dict and checks the result:
```python
pending = sim.pending_transitions.pop(payload["drone_id"], None)
if pending is None:
    # Already expired/approved — silently ignore
    return
```
Frontend should treat absence of `pending_transition` in state as "resolved" regardless of who acted.

### Pitfall 3: Blueprint Toast2 vs Toaster API

**What goes wrong:** Using `Toaster.create()` (Blueprint v4 static factory) in Blueprint v5 project
causes a runtime error. The API changed.

**How to avoid:** Use `OverlayToaster` with a ref, or render inline `Toast2` keyed by UAV id.

### Pitfall 4: `autonomy_level` Not in get_state() Broadcast

**What goes wrong:** Frontend AutonomyToggle initializes to "MANUAL" but cannot reflect server-side
state on reconnect or page refresh.

**How to avoid:** Add `autonomy_level` to the top-level `get_state()` dict. Frontend reads initial
value from first state packet.

### Pitfall 5: VERIFY Mode — Sensor-Type-Specific Behavior Without Phase 1 Data

**What goes wrong:** VERIFY mode is supposed to do sensor-specific passes (EO_IR = perpendicular
cross, SAR = parallel track, SIGINT = loiter). Phase 1 adds `sensors: list[str]` to UAV. If Phase 1
is not yet merged, `u.sensors` exists on the UAV class already (added in Phase 0.6 — confirmed in
`sim_engine.py` line 235: `self.sensors: List[str] = _pick_sensors()`). Safe to use.

**Resolution:** `u.sensors[0]` or `"EO_IR" in u.sensors` is safe now. VERIFY can use this
immediately without waiting for Phase 1.

### Pitfall 6: OVERWATCH Racetrack Pattern Off-Map

**What goes wrong:** Racetrack legs extend beyond theater bounds, UAV teleports to center (existing
boundary clamp logic in `UAV.update()` for SEARCH).

**How to avoid:** Clamp racetrack waypoints to `self.bounds` when generating them. Store racetrack
state (waypoint index, direction) on the UAV — add `overwatch_waypoints: list` and
`overwatch_wp_idx: int` to `UAV.__init__()`.

---

## Code Examples

### SUPPORT Mode Orbit (wide orbit around tracked target)

```python
# Source: derived from existing FOLLOW orbit (sim_engine.py:635-654)
elif u.mode == "SUPPORT":
    # Wide orbit at ~3km — provides secondary sensor coverage
    orbit_r = SUPPORT_ORBIT_RADIUS_DEG
    if dist < 0.001:
        u.x -= orbit_r
        dist = orbit_r
        dx, dy = target.x - u.x, target.y - u.y
    nx, ny = dx / dist, dy / dist
    tx, ty = -ny, nx  # tangent direction
    if dist < orbit_r * 0.8:
        dvx = (-nx * 0.2 + tx * 0.8) * speed
        dvy = (-ny * 0.2 + ty * 0.8) * speed
    elif dist > orbit_r * 1.2:
        dvx = (nx * 0.2 + tx * 0.8) * speed
        dvy = (ny * 0.2 + ty * 0.8) * speed
    else:
        dvx, dvy = tx * speed, ty * speed
    u._turn_toward(dvx, dvy, speed, dt_sec)
    u.x += u.vx * dt_sec
    u.y += u.vy * dt_sec
```

### BDA Mode with Auto-Transition Timer

```python
# UAV.__init__() addition:
self.bda_timer: float = 0.0

# In _update_tracking_modes():
elif u.mode == "BDA":
    # Tight orbit (same as PAINT) for damage assessment
    orbit_r = BDA_ORBIT_RADIUS_DEG
    # ... same orbit math as PAINT ...
    u.bda_timer -= dt_sec
    if u.bda_timer <= 0:
        u.mode = "SEARCH"
        u.tracked_target_id = None
        continue

# When entering BDA mode (in command_bda() or autonomy evaluator):
uav.bda_timer = BDA_DURATION_SEC
```

### OVERWATCH Racetrack

```python
# UAV.__init__() additions:
self.overwatch_waypoints: list = []  # list of (x, y)
self.overwatch_wp_idx: int = 0

# In _update_tracking_modes():
elif u.mode == "OVERWATCH":
    if not u.overwatch_waypoints:
        # Generate a 2-leg racetrack centered on UAV's current zone center
        cx, cy = u.x, u.y
        half = OVERWATCH_RACETRACK_LENGTH_DEG / 2
        u.overwatch_waypoints = [
            (max(self.bounds['min_lon'], cx - half), cy),
            (min(self.bounds['max_lon'], cx + half), cy),
        ]
        u.overwatch_wp_idx = 0
    wp = u.overwatch_waypoints[u.overwatch_wp_idx]
    dx, dy = wp[0] - u.x, wp[1] - u.y
    dist = math.hypot(dx, dy)
    if dist < 0.005:
        u.overwatch_wp_idx = (u.overwatch_wp_idx + 1) % len(u.overwatch_waypoints)
    else:
        u._turn_toward((dx/dist)*speed, (dy/dist)*speed, speed, dt_sec)
    u.x += u.vx * dt_sec
    u.y += u.vy * dt_sec
```

### Zustand Store Addition for Autonomy

```typescript
// In SimulationStore.ts — add to store state:
autonomyLevel: "MANUAL" as "MANUAL" | "SUPERVISED" | "AUTONOMOUS",
pendingTransitions: {} as Record<number, { mode: string; reason: string; expires_at: number }>,

// In useWebSocket dispatch (when state message arrives):
const level = data.autonomy_level;
if (level) set({ autonomyLevel: level });
const pending: Record<number, ...> = {};
for (const uav of data.uavs) {
  if (uav.pending_transition) pending[uav.id] = uav.pending_transition;
}
set({ pendingTransitions: pending });
```

### Mode Colors in constants.ts

```typescript
// Add to MODE_STYLES or equivalent in shared/constants.ts:
export const MODE_COLORS: Record<string, string> = {
  IDLE:          "#6e7f8c",
  SEARCH:        "#2d72d2",  // Blueprint blue
  FOLLOW:        "#1c7f4e",  // green
  PAINT:         "#cd4246",  // red
  INTERCEPT:     "#f76d00",  // orange
  RTB:           "#5c7080",  // gray
  REPOSITIONING: "#a854a8",  // purple
  // Phase 3 additions:
  SUPPORT:       "#00b3a4",  // teal
  VERIFY:        "#d97008",  // amber
  OVERWATCH:     "#5c5fd6",  // indigo
  BDA:           "#7f8fa4",  // gray-blue
};
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `tracked_by_uav_id` on Target | Still single in current engine (Phase 1 migrates to list) | Phase 1 pending | SUPPORT mode needs a target to orbit around — use `u.tracked_target_id` set before entering SUPPORT |
| Toaster.create() static factory | OverlayToaster ref + createAsync | Blueprint v5 | Must use ref pattern |

**Deprecated/outdated:**
- `UAV.sensor_type: str` (single string): Still present at `sim_engine.py:238` as `self.sensor_type = "EO_IR"`. Phase 1 adds `sensors: list[str]`. VERIFY mode uses `u.sensors[0]` (already available from `_pick_sensors()` at line 235).

---

## Open Questions

1. **VERIFY mode — does it need a target to orbit, or just a grid zone?**
   - What we know: Spec says "sensor-specific pass" (perpendicular cross, parallel track, loiter) — these imply flying a pattern *over* a target location, not an arbitrary zone.
   - What's unclear: VERIFY is triggered by `("FOLLOW", "verification_gap")`. At that point the UAV already has `tracked_target_id` set. Safe to assume VERIFY orbits the same target.
   - Recommendation: VERIFY requires `tracked_target_id` set (same as FOLLOW). Copy target reference from FOLLOW when transitioning.

2. **SUPERVISED timeout duration — hardcoded or configurable?**
   - What we know: Spec says "auto-approve after N seconds" without specifying N.
   - Recommendation: Use `10` seconds as default; add `supervised_timeout_sec: float = 10.0` to `SimulationModel.__init__()` so tests can override it.

3. **SUPPORT and OVERWATCH — do they require a target or a zone?**
   - SUPPORT: spec says "provides secondary sensor data to target" — requires `tracked_target_id`.
   - OVERWATCH: spec says "area denial, persistent coverage" — does NOT require a target. Racetrack over current zone position.
   - Recommendation: SUPPORT sets `tracked_target_id` before entering. OVERWATCH clears `tracked_target_id`.

4. **Mode source indicator (HUMAN/AUTO) on DroneCard — how is it stored?**
   - What we know: The spec calls for a mode source indicator. Not mentioned in current UAV state.
   - Recommendation: Add `mode_source: str = "HUMAN"` field to UAV (set to "AUTO" when autonomy system initiates a transition, "HUMAN" on operator command). Include in `get_state()` broadcast.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest in venv) |
| Config file | none — uses conftest.py at `src/python/tests/conftest.py` |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_drone_modes.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-3 | SUPPORT mode orbits target at ~3km | unit | `pytest tests/test_drone_modes.py::TestSupportMode -x` | Wave 0 |
| FR-3 | VERIFY mode runs sensor-specific pass pattern | unit | `pytest tests/test_drone_modes.py::TestVerifyMode -x` | Wave 0 |
| FR-3 | OVERWATCH mode runs racetrack within bounds | unit | `pytest tests/test_drone_modes.py::TestOverwatchMode -x` | Wave 0 |
| FR-3 | BDA mode auto-transitions to SEARCH after 30s | unit | `pytest tests/test_drone_modes.py::TestBdaMode -x` | Wave 0 |
| FR-3 | MANUAL: autonomous transitions do not fire | unit | `pytest tests/test_drone_modes.py::TestAutonomyManual -x` | Wave 0 |
| FR-3 | AUTONOMOUS: transitions fire without approval | unit | `pytest tests/test_drone_modes.py::TestAutonomyAutonomous -x` | Wave 0 |
| FR-3 | SUPERVISED: transition queued, auto-approved on timeout | unit | `pytest tests/test_drone_modes.py::TestAutonomySupervised -x` | Wave 0 |
| FR-3 | Per-drone autonomy override takes precedence | unit | `pytest tests/test_drone_modes.py::TestPerDroneOverride -x` | Wave 0 |
| FR-3 | approve_transition applies pending mode | unit | `pytest tests/test_drone_modes.py::TestApproveTransition -x` | Wave 0 |
| FR-3 | reject_transition clears pending without mode change | unit | `pytest tests/test_drone_modes.py::TestRejectTransition -x` | Wave 0 |
| FR-3 | New modes not double-updated (excluded from UAV.update) | integration | `pytest tests/test_drone_modes.py::TestModeExclusion -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_drone_modes.py -x`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_drone_modes.py` — covers all FR-3 behaviors above

*(conftest.py and framework already exist — no additional setup needed)*

---

## Sources

### Primary (HIGH confidence)
- Direct code reading of `sim_engine.py` — verified all orbit patterns, mode exclusion list, UAV fields
- Direct code reading of `api_main.py` — verified action schema pattern, validate_payload, handle_payload dispatch
- Direct code reading of `src/python/tests/conftest.py` and `test_sim_integration.py` — verified test patterns
- `.planning/STATE.md` — verified known bug (double-update), locked decisions (Zustand 4.5.0, Blueprint 5)
- `.planning/ROADMAP.md` — verified Phase 3 spec, mode constants, autonomy transition table

### Secondary (MEDIUM confidence)
- Blueprint v5 SegmentedControl API: confirmed from project's existing Blueprint usage and Blueprint v5 docs pattern. `OverlayToaster` ref pattern is the current v5 approach.
- Blueprint Toast2 API change (v4 → v5): verified conceptually — Blueprint v5 introduced `Toast2` and deprecated `Toast`. The `Toaster.create()` static method was the v4 API; v5 uses `OverlayToaster` ref.

### Tertiary (LOW confidence)
- None — all critical claims verified from source code or confirmed project decisions.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use, versions locked
- Architecture: HIGH — all patterns derived directly from existing sim_engine.py code
- Pitfalls: HIGH — double-update bug is documented in STATE.md; others derived from code analysis
- Test map: HIGH — follows exact pattern of existing test_sim_integration.py

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable codebase, no external dependencies changing)
