# Phase 4: Enemy UAVs - Research

**Researched:** 2026-03-19
**Domain:** Adversary air simulation — enemy drone entities, detection mechanics, behaviors, intercept logic
**Confidence:** HIGH (all findings verified against the actual codebase)

---

## Summary

Phase 4 adds adversary UAV entities to the simulation. The codebase already has everything needed: a flight model (`UAV` class with `_turn_toward()`), a probabilistic detection pipeline (`sensor_model.py` + `sensor_fusion.py`), behavior patterns (stationary, patrol, shoot-and-scoot, ambush), and a WebSocket broadcast protocol. Enemy UAVs are a new entity type that reuses all of these — they are not targets (ground units) and not friendly UAVs, but a third category that participates in both roles simultaneously: they move like UAVs and are detected like targets.

The fundamental design question is whether to implement enemy UAVs as a new `EnemyUAV` class, or as a specialization of the existing `Target` class with UAV-like behavior, or as a separate parallel list in `SimulationModel`. The cleanest approach given the codebase is a **new `EnemyUAV` class** that reuses the `UAV` flight mechanics but is tracked in a separate `sim.enemy_uavs` list, detected by friendly sensors using the existing detection loop, and represented on the frontend as a distinct entity type with its own Cesium hook.

The detection system already handles any target type via `evaluate_detection()` — adding an RCS entry for `ENEMY_UAV` in `RCS_TABLE` is sufficient to make enemy UAVs detectable. The `sensor_model.py` uses duck-typed fields (`target_type`, position, heading), so detection evaluation will work without any changes to that module.

**Primary recommendation:** Build `EnemyUAV` as a separate class in `sim_engine.py` that reuses `UAV._turn_toward()` and the existing behavior patterns. Represent enemy UAVs as a `enemy_uavs` list in `SimulationModel`, with detection using the existing loop, and broadcast them in `get_state()` as a new `enemy_uavs` key.

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `math`, `random` | 3.x | Flight physics, probabilistic behavior | Already used throughout sim_engine.py |
| `structlog` | installed | Logging enemy UAV events | Already used for all sim logging |
| `pytest` | installed | TDD for new module | Project standard, all tests in `src/python/tests/` |
| CesiumJS (React hooks) | project version | Enemy UAV entities on globe | All entities are Cesium hook pattern |
| Blueprint (React) | 5.x | Enemy UAV cards in sidebar | Project standard for all UI components |
| Zustand | 4.5.0 | Enemy UAV state in frontend store | Locked decision: Zustand 4.5.0 |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sensor_model.evaluate_detection()` | local | Detection probability for enemy UAVs | Reuse directly — enemy UAVs are detectable targets |
| `sensor_fusion.fuse_detections()` | local | Multi-sensor fused confidence on enemy UAVs | Reuse if multiple friendly UAVs detect the same enemy drone |

**Installation:** No new packages needed. Everything reuses the existing stack.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
src/python/
├── sim_engine.py              # MODIFY: add EnemyUAV class, enemy_uavs list
├── tests/
│   └── test_enemy_uavs.py     # NEW: TDD tests for enemy UAV behaviors

src/frontend-react/src/
├── store/
│   └── types.ts               # MODIFY: add EnemyUAV interface
├── cesium/
│   └── useCesiumEnemyUAVs.ts  # NEW: Cesium hook for enemy UAV entities
├── panels/
│   └── enemies/
│       └── EnemyUAVCard.tsx   # NEW: Blueprint card for enemy UAV in ENEMIES tab
```

### Pattern 1: EnemyUAV as Separate Class (Reusing UAV Flight Model)

**What:** A new `EnemyUAV` class in `sim_engine.py` that contains the same flight mechanics as `UAV` but is tracked separately, has its own behaviors, and is detectable by friendly sensors.

**When to use:** This pattern keeps the friendly UAV list clean, avoids polluting `UAV` with adversarial fields, and makes it trivially clear in all loops which collection you're iterating.

**Key fields:**
```python
class EnemyUAV:
    id: int          # Prefixed e.g. 1000+ to avoid collision with friendly UAV IDs
    x: float
    y: float
    vx: float
    vy: float
    heading_deg: float
    mode: str        # RECON | ATTACK | JAMMING | EVADING | DESTROYED
    behavior: str    # patrol | loiter | direct_attack | evasion
    detected: bool   # Whether friendly sensors currently see it
    fused_confidence: float
    sensor_contributions: list
    threat_range_km: float   # For ATTACK mode engagement envelope
    # Reuses UAV._turn_toward() — copy the method or extract to module-level fn
```

**Source:** Direct inspection of `sim_engine.py` UAV class

### Pattern 2: Detection Loop Extension (Detect Enemy UAVs Like Ground Targets)

**What:** In `SimulationModel.tick()`, after the ground target detection loop, add a parallel loop that runs friendly UAV sensors against enemy UAV positions. Reuses `evaluate_detection()` with a new RCS entry `"ENEMY_UAV"`.

**Implementation points:**

1. Add to `sensor_model.py` RCS_TABLE:
```python
RCS_TABLE["ENEMY_UAV"] = 0.1   # Small radar cross-section (low-observable drone)
```

2. In `sim_engine.py` tick(), after target detection loop:
```python
for e in self.enemy_uavs:
    if e.mode == "DESTROYED":
        continue
    contributions = []
    for u in self.uavs:
        if u.mode in ("RTB", "REPOSITIONING"):
            continue
        for sensor_type in u.sensors:
            result = evaluate_detection(
                uav_lat=u.y, uav_lon=u.x,
                target_lat=e.y, target_lon=e.x,
                target_type="ENEMY_UAV",
                sensor_type=sensor_type,
                env=self.environment,
                aspect_deg=...,  # same aspect calculation as targets
                emitting=e.is_jamming,  # SIGINT detects jamming emissions
            )
            if result.detected:
                contributions.append(SensorContribution(...))
    if contributions:
        fused = fuse_detections(contributions)
        e.fused_confidence = fused.fused_confidence
        e.detected = True
    else:
        e.fused_confidence = max(0.0, e.fused_confidence * 0.95)
        e.detected = e.fused_confidence > 0.1
```

**Source:** Direct inspection of `sim_engine.py` target detection loop (lines 592–658)

### Pattern 3: Enemy UAV Behaviors

**What:** Three behaviors, defined analogously to ground target behaviors in `UNIT_BEHAVIOR`.

| Behavior | Movement | Description |
|----------|----------|-------------|
| `recon` | Loiter patrol over zone | Circular loiter like IDLE/SEARCH UAV. Detected = begins evasion. |
| `attack` | Direct approach to target coord | Flies toward a waypoint (friendly UAV base or high-value area) at speed |
| `jamming` | Station-keeping loiter | Holds position, `is_jamming=True` — SIGINT sensors detect it at range |

**Evasion behavior (EVADING mode):**
- Triggered when `fused_confidence > 0.5` (enemy drone detects it's being observed)
- Rapid direction change: pick random heading + speed boost (1.5x)
- After N seconds of low confidence, returns to original behavior
- Fixed-wing evasion is gradual (uses `_turn_toward()`) — not teleportation

### Pattern 4: Intercept Mechanic

**What:** Friendly UAV in INTERCEPT mode can target an enemy UAV. Reuse `command_intercept()` but accept enemy UAV IDs. The intercept range close (~300m) triggers "kill" — enemy UAV transitions to DESTROYED.

**ID namespace:** Enemy UAVs use IDs starting at 1000 (or negative) to avoid collision with target IDs (0–~30) and friendly UAV IDs (0–19). The frontend and backend must agree on this namespace convention.

**Alternative:** Add a `target_type` field to intercept commands (`"ground"` vs `"air"`). This is cleaner but requires frontend changes to the command buttons.

**Recommended:** Use ID namespace separation (simpler, no protocol change needed initially).

### Pattern 5: Cesium Hook for Enemy UAV Entities

**What:** `useCesiumEnemyUAVs.ts` following exactly the same pattern as `useCesiumDrones.ts`.

```typescript
// Source: src/frontend-react/src/cesium/useCesiumDrones.ts (existing pattern)
export function useCesiumEnemyUAVs(viewerRef: RefObject<Cesium.Viewer>) {
  const enemyUavs = useSimStore(state => state.enemyUavs);
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});
  useEffect(() => {
    // Create/update red-colored billboard entities per enemy UAV
    // Use different model/color than friendly drones (red vs blue)
  }, [enemyUavs]);
}
```

**Visual differentiation:**
- Friendly UAVs: blue/mode-colored labels
- Enemy UAVs: red labels, "ENM-{id}" prefix, threat ring if ATTACK mode

### Anti-Patterns to Avoid

- **Putting enemy UAVs in `self.targets`:** They would inherit ground-target behavior, get nominated for engagement through the existing kill chain, and appear in the wrong frontend tab. Keep them separate.
- **Using the same ID space as targets:** Will cause `_find_target()` to find enemy UAVs when the system looks for ground targets. Use IDs 1000+ for enemy UAVs.
- **Adding evasion as a mutation of the `Target.behavior` field:** Enemy UAVs need dynamic mode transitions (RECON → EVADING → RECON), not static behaviors. Model this as a state machine on `EnemyUAV.mode`, not as a behavior string.
- **Detecting enemy UAVs in the same loop as ground targets:** Keep loops separate for clarity and future extensibility (e.g., jamming effects on sensors only affect the enemy UAV detection loop, not ground target detection).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Flight physics | Custom turn/movement math | `UAV._turn_toward()` + loiter pattern already in sim_engine.py | Proven fixed-wing model with correct `MAX_TURN_RATE` |
| Detection probability | Custom range/RCS calculation | `sensor_model.evaluate_detection()` + add `ENEMY_UAV` to `RCS_TABLE` | Handles aspect angle, weather, sensor type, all edge cases |
| Sensor fusion | Custom confidence aggregation | `sensor_fusion.fuse_detections()` | Already handles multi-sensor fusion correctly |
| Patrol behavior | New waypoint logic | Copy the existing `"patrol"` behavior from `Target.update()` | Already handles bounds, waypoints, indices |
| Cesium entity management | New entity lifecycle | Follow `useCesiumDrones.ts` pattern exactly | Handles create/update/remove correctly with refs |
| Frontend state | Custom state management | Zustand `SimulationStore.ts` — add `enemyUavs` field | Locked project standard (v4.5.0) |

**Key insight:** This phase is almost entirely composition of existing code. The flight model, detection pipeline, fusion math, Cesium patterns, and frontend architecture all exist and work. The main new logic is: enemy behavior state machines (RECON/ATTACK/JAMMING/EVADING) and the intercept kill mechanic.

---

## Common Pitfalls

### Pitfall 1: Enemy UAV IDs Colliding with Target IDs

**What goes wrong:** `_find_target(enemy_uav_id)` returns an enemy UAV object, breaking the kill chain pipeline.

**Why it happens:** The intercept command sends `target_id` to the backend — if enemy UAVs share the same ID space as ground targets, any lookup function that iterates `self.targets` will fail silently or corrupt state.

**How to avoid:** Start enemy UAV IDs at 1000 (or use negative IDs). Add a separate `_find_enemy_uav(id)` method. Never add enemy UAVs to `self.targets`.

**Warning signs:** `command_paint()` or `_assign_target()` being called with an enemy UAV ID.

### Pitfall 2: Enemy UAVs Entering the HITL Nomination Pipeline

**What goes wrong:** `TacticalAssistant.update()` in `api_main.py` calls `_process_new_detection()` for every newly detected entity. If enemy UAVs appear in the target list, they'll get nominated for HITL approval and COA generation, which is wrong — enemy UAVs are intercepted, not struck with effectors.

**Why it happens:** `TacticalAssistant` reads from `sim_state["targets"]`. If enemy UAVs are broadcast in a separate key (`enemy_uavs`), this is automatic. If they appear in `targets`, it must filter by type.

**How to avoid:** Broadcast enemy UAVs under a separate `enemy_uavs` key in `get_state()`. The `TacticalAssistant` reads `targets` only.

**Warning signs:** Strike board showing enemy UAV entries.

### Pitfall 3: Detection Loop Performance at 10Hz

**What goes wrong:** Adding a double loop (N friendly UAVs × M enemy UAVs × K sensors) inside `tick()` causes the 10Hz loop to miss deadlines if N×M×K is large.

**Why it happens:** The existing target detection loop is already O(UAVs × Targets × Sensors). Enemy UAVs add another O(UAVs × EnemyUAVs × Sensors) pass.

**How to avoid:** Keep the number of enemy UAVs small (3–8 at most per theater config). The loop cost is cheap per pair (~microseconds). No spatial indexing needed at this scale.

**Warning signs:** Log messages showing `dt_sec` consistently capped at 0.1 (the safety clamp at sim_engine.py line 511).

### Pitfall 4: Frontend Type Errors from Missing `enemyUavs` Field

**What goes wrong:** `SimStatePayload` in `types.ts` doesn't include `enemy_uavs`, so the Zustand store ignores the new broadcast field. No enemy UAVs appear on the map.

**Why it happens:** TypeScript silently drops unknown fields on assignment if the interface doesn't declare them.

**How to avoid:** Add `enemyUavs: EnemyUAV[]` to both `SimStatePayload` (for the WS payload) and `SimulationStore` (for Zustand state) before wiring the Cesium hook.

**Warning signs:** `useCesiumEnemyUAVs` receives an empty array on every tick.

### Pitfall 5: Evasion Causing Thrash Between Modes

**What goes wrong:** An enemy UAV in RECON mode detects it's being watched (fused_confidence > threshold), switches to EVADING, briefly breaks sensor contact (confidence drops), immediately switches back to RECON, and oscillates every few ticks.

**Why it happens:** The evasion trigger and release use the same threshold without hysteresis.

**How to avoid:** Use a cooldown timer (`evasion_cooldown_sec`) that prevents transition back to RECON for at least 15 seconds after entering EVADING. Same pattern as `Target.flee_cooldown` (see sim_engine.py line 215).

**Warning signs:** Enemy UAV mode changing every 2–3 ticks in the log.

---

## Code Examples

Verified patterns from existing codebase:

### Reusing _turn_toward() (Fixed-Wing Flight)

```python
# Source: sim_engine.py UAV._turn_toward() (lines 263-277)
# Extract to module level or copy into EnemyUAV:
def _turn_toward(self, target_vx: float, target_vy: float, speed: float, dt_sec: float):
    curr_heading = math.atan2(self.vx, self.vy) if math.hypot(self.vx, self.vy) > 1e-9 else 0.0
    desired_heading = math.atan2(target_vx, target_vy)
    diff = desired_heading - curr_heading
    while diff > math.pi: diff -= 2 * math.pi
    while diff < -math.pi: diff += 2 * math.pi
    max_delta = MAX_TURN_RATE * dt_sec
    if abs(diff) > max_delta:
        diff = math.copysign(max_delta, diff)
    new_heading = curr_heading + diff
    self.vx = math.sin(new_heading) * speed
    self.vy = math.cos(new_heading) * speed
```

### Enemy UAV Loiter (RECON mode — reuse IDLE/SEARCH pattern)

```python
# Source: sim_engine.py UAV.update() lines 311-330
# Same circular loiter — just copy the IDLE/SEARCH branch for EnemyUAV.update()
loiter_speed = ENEMY_SPEED * 0.5
heading_rad = math.atan2(self.vx, self.vy)
turn = MAX_TURN_RATE * dt_sec
heading_rad += turn
self.vx = math.sin(heading_rad) * loiter_speed
self.vy = math.cos(heading_rad) * loiter_speed
self.x += self.vx * dt_sec
self.y += self.vy * dt_sec
```

### Detection of Enemy UAV in Tick Loop

```python
# Source: sim_engine.py lines 594-633 (ground target detection — mirror this)
for e in self.enemy_uavs:
    if e.mode == "DESTROYED":
        continue
    contributions = []
    for u in self.uavs:
        if u.mode in ("RTB", "REPOSITIONING"):
            continue
        dlat = e.y - u.y
        dlon = (e.x - u.x) * math.cos(math.radians((u.y + e.y) / 2.0))
        bearing_deg = (math.degrees(math.atan2(dlon, dlat)) + 360.0) % 360.0
        aspect_deg = (bearing_deg - e.heading_deg + 360.0) % 360.0
        for sensor_type in u.sensors:
            result = evaluate_detection(
                uav_lat=u.y, uav_lon=u.x,
                target_lat=e.y, target_lon=e.x,
                target_type="ENEMY_UAV",
                sensor_type=sensor_type,
                env=self.environment,
                aspect_deg=aspect_deg,
                emitting=e.is_jamming,
            )
            if result.detected:
                contributions.append(SensorContribution(
                    uav_id=u.id, sensor_type=sensor_type,
                    confidence=result.confidence, range_m=result.range_m,
                    bearing_deg=result.bearing_deg, timestamp=time.time(),
                ))
    if contributions:
        fused = fuse_detections(contributions)
        e.fused_confidence = fused.fused_confidence
        e.sensor_count = fused.sensor_count
        e.detected = True
    else:
        e.fused_confidence = max(0.0, e.fused_confidence * 0.95)
        e.detected = e.fused_confidence > 0.1
```

### Adding Enemy UAVs to get_state()

```python
# Source: sim_engine.py get_state() lines 786-851 (add after "targets" key)
"enemy_uavs": [
    {
        "id": e.id,
        "lon": e.x,
        "lat": e.y,
        "mode": e.mode,       # RECON | ATTACK | JAMMING | EVADING | DESTROYED
        "behavior": e.behavior,
        "heading_deg": round(e.heading_deg, 1),
        "detected": e.detected,
        "fused_confidence": round(e.fused_confidence, 3),
        "sensor_count": e.sensor_count,
        "is_jamming": e.is_jamming,
    } for e in self.enemy_uavs
],
```

### Cesium Hook Pattern (Enemy UAV)

```typescript
// Source: src/frontend-react/src/cesium/useCesiumDrones.ts (existing pattern)
export function useCesiumEnemyUAVs(viewerRef: RefObject<Cesium.Viewer | null>) {
  const enemyUavs = useSimStore(state => state.enemyUavs);
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const seen = new Set<number>();
    for (const e of enemyUavs) {
      seen.add(e.id);
      const pos = Cesium.Cartesian3.fromDegrees(e.lon, e.lat, 2000);
      if (!entitiesRef.current[e.id]) {
        entitiesRef.current[e.id] = viewer.entities.add({
          position: pos,
          label: {
            text: `ENM-${e.id}`,
            fillColor: Cesium.Color.RED,
          },
        });
      } else {
        (entitiesRef.current[e.id].position as any) =
          new Cesium.ConstantPositionProperty(pos);
      }
    }
    // Remove stale entities
    for (const id of Object.keys(entitiesRef.current).map(Number)) {
      if (!seen.has(id)) {
        viewer.entities.remove(entitiesRef.current[id]);
        delete entitiesRef.current[id];
      }
    }
  }, [enemyUavs, viewerRef]);
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `tracked_by_uav_id` | `tracked_by_uav_ids` list | Phase 1 | Enemy UAVs can be tracked by multiple friendly UAVs simultaneously — same pattern applies |
| Boolean `detected` | State machine + `fused_confidence` | Phase 1 | Enemy UAV detection should use same fused model |
| Hard-coded 0.5° proximity check | `sensor_model.evaluate_detection()` | Phase 1 | Enemy UAVs get realistic physics-based detection for free |

**Deprecated/outdated:**
- `target.detected_time`: removed in Phase 1 migration — do not add this to `EnemyUAV`
- `u.sensor_type` (singular): replaced by `u.sensors` list — use `u.sensors` in all new detection loops

---

## Open Questions

1. **Intercept kill mechanic: range-based or time-based?**
   - What we know: INTERCEPT mode brings friendly UAV within `INTERCEPT_CLOSE_DEG` (~300m) of target. No kill mechanic exists yet for any entity.
   - What's unclear: Should the kill be instant at 300m, or require a dwell time (e.g., 3 seconds in close range)? Should it consume the intercepting UAV (kamikaze) or return it to SEARCH?
   - Recommendation: Dwell-time kill (3 seconds at < `INTERCEPT_CLOSE_DEG`). Friendly UAV transitions to BDA mode after kill (when Phase 3 BDA mode is available) or back to SEARCH.

2. **Theater YAML: enemy UAV count configurable?**
   - What we know: `romania.yaml` has a `red_force.units` list. Enemy UAVs could be added there as `type: ENEMY_UAV`.
   - What's unclear: Theater YAML `behavior` field currently maps to `UNIT_BEHAVIOR` dict for ground targets. Enemy UAVs need a different behavior dispatch.
   - Recommendation: Add `enemy_uavs` as a separate YAML section in theater config (parallel to `red_force`, `blue_force`). Keeps ground target and air threat configuration separate.

3. **Demo autopilot: should enemy UAVs appear in demo mode?**
   - What we know: `demo_autopilot()` in `api_main.py` runs the full F2T2EA chain automatically. Enemy UAVs are a new threat type not currently handled.
   - What's unclear: Should demo mode auto-dispatch an INTERCEPT command when an enemy UAV is detected? Or just spawn them as ambient threats for visual effect?
   - Recommendation: Spawn 2–3 enemy UAVs at demo start (RECON behavior). If `fused_confidence > 0.7`, auto-dispatch nearest friendly UAV to INTERCEPT. This demonstrates the full air threat response chain without requiring manual operator input.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing, no new install needed) |
| Config file | none — discovered via `src/python/tests/` directory |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_enemy_uavs.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EUAV-01 | EnemyUAV spawns with RECON/ATTACK/JAMMING behavior | unit | `pytest tests/test_enemy_uavs.py::TestEnemyUAVSpawn -x` | Wave 0 |
| EUAV-02 | Friendly sensor detects enemy UAV (fused_confidence > 0) | unit | `pytest tests/test_enemy_uavs.py::TestEnemyUAVDetection -x` | Wave 0 |
| EUAV-03 | Enemy UAV enters EVADING mode when confidence > 0.5 | unit | `pytest tests/test_enemy_uavs.py::TestEvasion -x` | Wave 0 |
| EUAV-04 | INTERCEPT command within 300m transitions enemy UAV to DESTROYED | unit | `pytest tests/test_enemy_uavs.py::TestInterceptKill -x` | Wave 0 |
| EUAV-05 | get_state() includes enemy_uavs key | integration | `pytest tests/test_enemy_uavs.py::TestGetState -x` | Wave 0 |
| EUAV-06 | Enemy UAVs do NOT appear in sim.targets | integration | `pytest tests/test_enemy_uavs.py::TestSeparation -x` | Wave 0 |
| EUAV-07 | JAMMING enemy UAV detected at longer range by SIGINT | unit | `pytest tests/test_enemy_uavs.py::TestJammingDetection -x` | Wave 0 |
| EUAV-08 | 10Hz loop maintained with 8 enemy UAVs | performance | `pytest tests/test_enemy_uavs.py::TestPerformance -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_enemy_uavs.py -x`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work 4`

### Wave 0 Gaps
- [ ] `src/python/tests/test_enemy_uavs.py` — covers EUAV-01 through EUAV-08 (must be created in Wave 0 / Plan 1 before implementation)

---

## Sources

### Primary (HIGH confidence — verified against live codebase)

- `src/python/sim_engine.py` — UAV class, Target class, SimulationModel, detection loop, flight mechanics, get_state() shape
- `src/python/sensor_model.py` — `evaluate_detection()`, `RCS_TABLE`, `SENSOR_CONFIGS`, detection physics
- `src/python/sensor_fusion.py` — `fuse_detections()`, `SensorContribution` dataclass
- `src/frontend-react/src/store/types.ts` — TypeScript interfaces for all state entities
- `src/frontend-react/src/cesium/useCesiumDrones.ts` — Cesium entity hook pattern to follow
- `src/python/api_main.py` — WebSocket action schemas, TacticalAssistant, broadcast loop
- `theaters/romania.yaml` — Theater config structure for enemy UAV YAML section design

### Secondary (MEDIUM confidence)

- `.planning/ROADMAP.md` Phase 4 description — confirms: recon/attack/jamming behaviors, detection by friendly sensors, evasion/intercept mechanics
- `.planning/STATE.md` decisions log — confirms Zustand 4.5.0, no StrictMode, ViewerContext patterns

### Tertiary (LOW confidence)

- None — all findings come from the live codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against installed packages and existing code
- Architecture: HIGH — all patterns copied from existing working code in the same repo
- Pitfalls: HIGH — derived from direct code inspection of the specific functions that would be modified
- Behavior design (RECON/ATTACK/JAMMING): MEDIUM — based on phase goal description, not locked decisions (no CONTEXT.md for this phase)

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable codebase, no fast-moving external dependencies)
