# Phase 1: Multi-Sensor Target Fusion — Research

**Researched:** 2026-03-19
**Domain:** Python dataclasses, complementary sensor fusion math, Zustand TypeScript types, ECharts stacked bars, Cesium entity rings
**Confidence:** HIGH (verified against live codebase — sim_engine.py, sensor_model.py, api_main.py, and existing test patterns)

---

## Summary

Phase 1 adds multi-sensor target fusion: multiple UAVs with different sensor types contribute independent detections to the same target, and their confidences are fused using the complementary rule `1 - product(1 - ci)`. The fused confidence is higher than any single sensor's contribution.

The codebase is **ready** for this change. `sim_engine.py` already has:
- `UAV.sensors: list[str]` — populated by `_pick_sensors()` at spawn (50% EO_IR, 30% SAR, 20% SIGINT; 10% dual-sensor pairs)
- `UAV.sensor_type: str` — legacy single-sensor field, still used in `evaluate_detection()` calls
- `Target.tracked_by_uav_id: Optional[int]` — single-UAV assumption, needs migration to list
- `Target.detection_confidence: float` — best single-sensor confidence (no fusion today)
- `sensor_model.py` — already exports `evaluate_detection()` which takes `sensor_type: str` and returns `DetectionResult` with `.confidence` and `.sensor_type`

The detection loop in `sim_engine.py` tick step 9 currently picks the **best single detection** (`if result.confidence > best_detection.confidence`). Phase 1 changes this to **accumulate all detections per target** and call `fuse_detections()` from a new `sensor_fusion.py` module.

**Primary recommendation:** Author `src/python/sensor_fusion.py` as a pure function module (frozen dataclasses, no side effects). Migrate `Target` fields from singular to plural. Update the detection loop, tracking commands, and get_state() broadcast. Author React `FusionBar.tsx` + `SensorBadge.tsx` against the new payload fields.

**Phase dependency:** Phase 0 must deliver the React app shell, Zustand store, and `types.ts` before Phase 1's React components can be authored. The Python side (fusion module + sim_engine changes) is **independent** — it can be implemented before Phase 0 is complete.

---

## Standard Stack

### Python (verified against existing codebase)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| dataclasses (stdlib) | 3.9+ | `SensorContribution`, `FusedDetection` | Use `@dataclass(frozen=True)` — matches `sensor_model.py` pattern |
| typing (stdlib) | 3.9+ | type hints | `list[dict]`, `Optional[int]`, etc. |
| math (stdlib) | 3.9+ | complementary fusion arithmetic | `1 - product(1 - ci)` via loop |
| structlog | 21.5.0 | event logging | already used in sim_engine.py |
| pytest | 7.x | unit tests | existing suite; `conftest.py` adds `src/python` to sys.path |

### TypeScript / React (verified against package.json)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| react | 18.3.1 | FusionBar, SensorBadge components | already in project |
| @blueprintjs/core | 5.13.0 | ProgressBar, Tag, Card | existing design system |
| echarts | 5.5.0 | stacked bar chart for per-sensor contribution | already installed |
| echarts-for-react | 3.0.2 | React wrapper | already installed |
| zustand | 4.5.0 | store type extension | existing store |
| cesium | 1.114.0 | fusion ring around targets | existing entity hooks |

### No new dependencies required
All libraries needed for Phase 1 are already present. `sensor_fusion.py` uses only stdlib.

---

## Architecture Patterns

### Pattern 1: Pure Function Sensor Fusion Module

**What:** `src/python/sensor_fusion.py` — frozen dataclasses + a single pure function.
**When to use:** Called once per target per tick from `sim_engine.py` detection loop.
**Key insight:** The complementary fusion formula `1 - product(1 - ci)` requires that sensor confidences are statistically **independent**. Different sensor modalities (EO_IR vs SAR vs SIGINT) satisfy this — they exploit different physical phenomena. Multiple EO_IR sensors on the same target are **not** independent; the fused confidence must be capped using within-type averaging before cross-type fusion.

```python
# src/python/sensor_fusion.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True)
class SensorContribution:
    uav_id: int
    sensor_type: str        # "EO_IR" | "SAR" | "SIGINT"
    confidence: float       # 0.0–1.0 from evaluate_detection()
    range_m: float
    bearing_deg: float
    timestamp: float        # time.time() at detection


@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float         # complementary fusion result
    sensor_count: int               # number of UAVs contributing
    sensor_types: tuple[str, ...]   # unique sensor types observed
    contributing_uav_ids: tuple[int, ...]
    contributions: tuple[SensorContribution, ...]


def fuse_detections(contributions: list[SensorContribution]) -> FusedDetection:
    """
    Complementary sensor fusion: fused_confidence = 1 - product(1 - ci)
    for per-modality representatives.

    Within a sensor type, use the MAX confidence (best sensor of that type).
    Across sensor types, apply the complementary formula.

    Returns FusedDetection with fused_confidence in [0.0, 1.0].
    """
    if not contributions:
        return FusedDetection(
            fused_confidence=0.0,
            sensor_count=0,
            sensor_types=(),
            contributing_uav_ids=(),
            contributions=(),
        )

    # Group by sensor type — take max confidence per type
    per_type: dict[str, float] = {}
    for c in contributions:
        if c.sensor_type not in per_type or c.confidence > per_type[c.sensor_type]:
            per_type[c.sensor_type] = c.confidence

    # Complementary fusion across types
    complement = 1.0
    for ci in per_type.values():
        complement *= (1.0 - ci)
    fused = float(max(0.0, min(1.0, 1.0 - complement)))

    unique_types = tuple(sorted(per_type.keys()))
    uav_ids = tuple(sorted({c.uav_id for c in contributions}))

    return FusedDetection(
        fused_confidence=fused,
        sensor_count=len(uav_ids),
        sensor_types=unique_types,
        contributing_uav_ids=uav_ids,
        contributions=tuple(contributions),
    )
```

### Pattern 2: Target Field Migration (singular → plural)

**What:** `Target` class in `sim_engine.py` gets list-based tracking fields alongside the new fusion fields.
**Key insight:** `tracked_by_uav_id` is checked in `cancel_track()` (`if target.tracked_by_uav_id == uav_id`) and in `_assign_target()`. Both must be updated atomically. The existing state broadcast (`get_state()`) also serializes this field. All four locations must change together.

```python
# Before (sim_engine.py Target.__init__)
self.tracked_by_uav_id: Optional[int] = None

# After
self.tracked_by_uav_ids: list[int] = []       # all tracking UAVs
self.sensor_contributions: list[SensorContribution] = []
self.fused_confidence: float = 0.0
self.sensor_count: int = 0
```

**Backward compatibility note:** The legacy `tracked_by_uav_id` property should remain as a compatibility shim returning `tracked_by_uav_ids[0] if tracked_by_uav_ids else None`. This avoids breaking `_process_new_detection()` in api_main.py which reads `target["tracked_by_uav_id"]`.

```python
@property
def tracked_by_uav_id(self) -> Optional[int]:
    """Backward-compatible single tracker — returns primary tracker or None."""
    return self.tracked_by_uav_ids[0] if self.tracked_by_uav_ids else None
```

### Pattern 3: UAV Primary Target

**What:** `UAV` class gets `tracked_target_ids` list + `primary_target_id`.
**Key insight:** Most UAV behavior references `uav.tracked_target_id` (single target). Keep this as a property returning `primary_target_id` to avoid a cascade of changes in `_update_tracking_modes()`.

```python
# UAV.__init__ additions
self.tracked_target_ids: list[int] = []    # all targets this UAV tracks
self.primary_target_id: Optional[int] = None

@property
def tracked_target_id(self) -> Optional[int]:
    """Backward-compatible single-target ref — returns primary_target_id."""
    return self.primary_target_id

@tracked_target_id.setter
def tracked_target_id(self, value: Optional[int]):
    """Legacy setter — updates primary_target_id and tracked_target_ids."""
    self.primary_target_id = value
    if value is not None and value not in self.tracked_target_ids:
        self.tracked_target_ids.append(value)
    elif value is None:
        self.tracked_target_ids.clear()
        self.primary_target_id = None
```

### Pattern 4: Detection Loop Rewrite (accumulate all, then fuse)

**What:** Replace the "best single detection" loop in `tick()` step 9 with an accumulation loop that gathers all per-UAV detections per target, then calls `fuse_detections()`.
**Key insight:** Use all sensors in `u.sensors` (the list), not `u.sensor_type` (the legacy single field). Each sensor on a UAV contributes an independent `SensorContribution`.

```python
# In SimulationModel.tick() — step 9 rewrite
from sensor_fusion import SensorContribution, fuse_detections
import time

for t in self.targets:
    t.update(dt_sec, self.bounds, uav_positions)

    if t.state in ("DESTROYED", "ENGAGED"):
        continue

    contributions: list[SensorContribution] = []

    for u in self.uavs:
        if u.mode in ("RTB", "REPOSITIONING"):
            continue

        # Range gate using target's detection_range_km
        if t.detection_range_km is not None:
            dist_deg = math.hypot(u.x - t.x, u.y - t.y)
            dist_km = dist_deg / DEG_PER_KM
            if dist_km > t.detection_range_km:
                continue

        # Aspect angle computation (unchanged)
        dlat = t.y - u.y
        dlon = (t.x - u.x) * math.cos(math.radians((u.y + t.y) / 2.0))
        bearing_rad = math.atan2(dlon, dlat)
        bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
        aspect_deg = (bearing_deg - t.heading_deg + 360.0) % 360.0

        # Evaluate each sensor on this UAV
        for sensor_type in u.sensors:
            result = evaluate_detection(
                uav_lat=u.y,
                uav_lon=u.x,
                target_lat=t.y,
                target_lon=t.x,
                target_type=t.type,
                sensor_type=sensor_type,
                env=self.environment,
                aspect_deg=aspect_deg,
                emitting=t.is_emitting,
            )
            if result.detected:
                contributions.append(SensorContribution(
                    uav_id=u.id,
                    sensor_type=sensor_type,
                    confidence=result.confidence,
                    range_m=result.range_m,
                    bearing_deg=result.bearing_deg,
                    timestamp=time.time(),
                ))

    # Fuse all contributions
    fused = fuse_detections(contributions)
    t.sensor_contributions = list(fused.contributions)
    t.fused_confidence = fused.fused_confidence
    t.sensor_count = fused.sensor_count

    # Update tracked_by_uav_ids
    t.tracked_by_uav_ids = list(fused.contributing_uav_ids)

    if contributions:
        if t.state == "UNDETECTED":
            t.state = "DETECTED"
        # Legacy field for api_main.py backward compat
        t.detection_confidence = fused.fused_confidence
        # detected_by_sensor: use the highest-confidence sensor type
        best = max(contributions, key=lambda c: c.confidence)
        t.detected_by_sensor = best.sensor_type
    else:
        # Fade logic — unchanged
        if t.state == "DETECTED" and not t.tracked_by_uav_ids:
            t.detection_confidence *= 0.95
            t.fused_confidence *= 0.95
            if t.detection_confidence < 0.1:
                t.state = "UNDETECTED"
                t.detection_confidence = 0.0
                t.fused_confidence = 0.0
                t.sensor_contributions = []
                t.sensor_count = 0
                t.tracked_by_uav_ids = []
                t.detected_by_sensor = None
```

### Pattern 5: WebSocket State Broadcast Extension

**What:** `get_state()` in `sim_engine.py` adds new fusion fields to the target payload.
**When to use:** Called every tick in `api_main.py` broadcast loop.

```python
# In get_state() targets list comprehension — add new fields:
{
    "id": t.id,
    "lon": t.x,
    "lat": t.y,
    "type": t.type,
    "detected": t.detected,
    "state": t.state,
    "detection_confidence": round(t.detection_confidence, 3),
    "detected_by_sensor": t.detected_by_sensor,
    "is_emitting": t.is_emitting,
    "heading_deg": round(t.heading_deg, 1),
    "tracked_by_uav_id": t.tracked_by_uav_id,     # compat shim
    "threat_range_km": t.threat_range_km,
    "detection_range_km": t.detection_range_km,
    # NEW Phase 1 fields:
    "fused_confidence": round(t.fused_confidence, 3),
    "sensor_count": t.sensor_count,
    "tracked_by_uav_ids": t.tracked_by_uav_ids,
    "sensor_contributions": [
        {
            "uav_id": c.uav_id,
            "sensor_type": c.sensor_type,
            "confidence": round(c.confidence, 3),
        }
        for c in t.sensor_contributions
    ],
}
```

UAV payload gains:
```python
{
    "id": u.id,
    "lon": u.x,
    "lat": u.y,
    "mode": u.mode,
    "altitude_m": u.altitude_m,
    "sensor_type": u.sensor_type,   # compat
    "sensors": u.sensors,           # already serialized
    "heading_deg": round(u.heading_deg, 1),
    "tracked_target_id": u.tracked_target_id,    # compat shim
    "tracked_target_ids": u.tracked_target_ids,  # NEW
    "primary_target_id": u.primary_target_id,    # NEW
    "fuel_hours": round(u.fuel_hours, 2),
}
```

### Pattern 6: TypeScript Type Extensions (store/types.ts)

**What:** Extend the existing `UAV` and `Target` interfaces to include Phase 1 fields.
**Key insight:** The Phase 0 `types.ts` has `tracked_target_id: number | null` — keep it for compat, add new fields alongside.

```typescript
// store/types.ts extensions for Phase 1

export interface SensorContributionPayload {
  uav_id: number;
  sensor_type: 'EO_IR' | 'SAR' | 'SIGINT';
  confidence: number;
}

// Extend UAV
export interface UAV {
  id: number;
  lat: number;
  lon: number;
  altitude_m: number;
  mode: 'IDLE' | 'SEARCH' | 'FOLLOW' | 'PAINT' | 'INTERCEPT' | 'REPOSITIONING' | 'RTB';
  heading_deg: number;
  tracked_target_id: number | null;       // compat
  tracked_target_ids: number[];           // Phase 1 NEW
  primary_target_id: number | null;       // Phase 1 NEW
  sensor_type: string;                    // compat
  sensors: string[];                      // Phase 0 (already broadcast)
  fuel_hours: number;
}

// Extend Target
export interface Target {
  id: number;
  lat: number;
  lon: number;
  type: string;
  state: string;
  detected: boolean;
  detection_confidence: number;           // compat (= fused_confidence post-Phase 1)
  fused_confidence: number;              // Phase 1 NEW
  sensor_count: number;                  // Phase 1 NEW
  tracked_by_uav_id: number | null;      // compat shim
  tracked_by_uav_ids: number[];          // Phase 1 NEW
  sensor_contributions: SensorContributionPayload[];  // Phase 1 NEW
  detected_by_sensor: string | null;
  is_emitting: boolean;
  heading_deg: number;
  threat_range_km: number | null;
  detection_range_km: number | null;
}
```

### Pattern 7: FusionBar React Component

**What:** Stacked horizontal bar showing per-sensor confidence contribution.
**Sensor colors:** EO_IR = `#4A90E2` (blue), SAR = `#7ED321` (green), SIGINT = `#F5A623` (amber).
**Key insight:** Use ECharts `bar` series with `stack: 'fusion'` for a proper stacked bar. Each series gets only the contribution for that sensor type on that target. Use `echarts-for-react`.

```typescript
// panels/enemies/FusionBar.tsx
import ReactECharts from 'echarts-for-react';
import { SensorContributionPayload } from '../../store/types';

const SENSOR_COLORS = {
  EO_IR: '#4A90E2',
  SAR: '#7ED321',
  SIGINT: '#F5A623',
};

interface FusionBarProps {
  contributions: SensorContributionPayload[];
  fused_confidence: number;
}

export function FusionBar({ contributions, fused_confidence }: FusionBarProps) {
  // Group by sensor type, take max per type
  const perType: Record<string, number> = {};
  for (const c of contributions) {
    if (!perType[c.sensor_type] || c.confidence > perType[c.sensor_type]) {
      perType[c.sensor_type] = c.confidence;
    }
  }

  const SENSORS = ['EO_IR', 'SAR', 'SIGINT'] as const;
  const option = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', max: 1.0, show: false },
    yAxis: { type: 'category', data: ['FUSION'], show: false },
    grid: { top: 0, bottom: 0, left: 0, right: 0, containLabel: false },
    series: SENSORS.map(stype => ({
      name: stype,
      type: 'bar',
      stack: 'fusion',
      barMaxWidth: 12,
      itemStyle: { color: SENSOR_COLORS[stype] },
      data: [perType[stype] ?? 0],
    })),
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <ReactECharts option={option} style={{ height: 12, width: 120, flex: '0 0 120px' }} />
      <span style={{ color: '#aaa', fontSize: 11 }}>
        {(fused_confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}
```

### Pattern 8: SensorBadge React Component

**What:** Small badge showing sensor count.
**When to use:** EnemyCard header alongside the target type Tag.

```typescript
// panels/enemies/SensorBadge.tsx
import { Tag, Intent } from '@blueprintjs/core';

interface SensorBadgeProps {
  sensor_count: number;
}

export function SensorBadge({ sensor_count }: SensorBadgeProps) {
  if (sensor_count === 0) return null;
  const intent = sensor_count >= 3 ? Intent.SUCCESS
               : sensor_count === 2 ? Intent.WARNING
               : Intent.NONE;
  return (
    <Tag intent={intent} minimal style={{ fontSize: 10 }}>
      {sensor_count} SENSOR{sensor_count !== 1 ? 'S' : ''}
    </Tag>
  );
}
```

### Pattern 9: Cesium Fusion Ring

**What:** A ring around each target whose opacity and thickness scale with `sensor_count`.
**Key insight:** Use the existing `useCesiumTargets` hook in the `cesium/` directory (authored in Phase 0). Add a `fusionRingRef` alongside the existing `billboardRef`. Use `Cesium.EllipseGeometry` via a `Primitive` rather than an entity — it's more performant for per-tick updates.

Simpler approach for Phase 1: use `target.billboard.ellipse` property on the existing entity. CesiumJS entities support `ellipse` as a child description.

```typescript
// In useCesiumTargets.ts — add to entity creation/update:
entity.ellipse = new Cesium.EllipseGraphics({
  semiMajorAxis: new Cesium.CallbackProperty(() => {
    const target = targets.find(t => t.id === entity.id);
    return target ? 1000 + (target.sensor_count * 500) : 1000;
  }, false),
  semiMinorAxis: new Cesium.CallbackProperty(() => {
    const target = targets.find(t => t.id === entity.id);
    return target ? 1000 + (target.sensor_count * 500) : 1000;
  }, false),
  material: new Cesium.ColorMaterialProperty(
    new Cesium.CallbackProperty(() => {
      const target = targets.find(t => t.id === entity.id);
      const opacity = target ? Math.min(0.6, 0.2 * target.sensor_count) : 0.0;
      return Cesium.Color.CYAN.withAlpha(opacity);
    }, false)
  ),
  outline: true,
  outlineColor: Cesium.Color.CYAN,
  height: 0,
  heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
});
```

---

## Anti-Patterns to Avoid

- **Fusing same-type sensors additively:** Two EO_IR UAVs on one target do NOT give `1 - (1-0.6)*(1-0.5) = 0.8`. They share atmospheric attenuation and viewing geometry — use `max()` within type, then fuse across types.
- **Mutating `SensorContribution` or `FusedDetection`:** These are frozen dataclasses. Any post-creation modification will raise `FrozenInstanceError`. Build new instances instead.
- **Storing `contributions` list on `FusedDetection` as mutable:** `tuple` is used in `FusedDetection.contributions` — can safely store on a frozen dataclass. The `Target.sensor_contributions` field IS mutable (list) since Target itself is mutable.
- **Setting `tracked_by_uav_ids` in `cancel_track()` without removing from the list:** `cancel_track()` currently does `target.tracked_by_uav_id = None`. After migration, it must remove `uav_id` from `tracked_by_uav_ids` (not clear the whole list — other UAVs may still be tracking).
- **Breaking `_update_tracking_modes()` by changing `u.tracked_target_id`:** The property shim on UAV handles this automatically. Do NOT access `u.primary_target_id` directly in tracking mode logic — let the property shim manage it.
- **Sending the full `contributions` tuple over WebSocket every tick:** At 10Hz with 20 UAVs and 20 targets, this could be 4000 contribution records. Serialize only the active contributions (non-zero confidence) and limit to 10 per target.
- **Re-creating the Cesium ellipse entity every tick:** Use `CallbackProperty` for dynamic radius/opacity. Creating/destroying entities per tick causes GPU thrash.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fusion math | Custom weighted average | Complementary formula `1 - product(1-ci)` | Statistically correct for independent sensors |
| Per-type grouping | Sorting + indexing | `dict` by sensor_type, update on `>` comparison | O(n) single pass |
| ECharts stacked bar | Canvas draw calls | `echarts-for-react` with `stack: 'fusion'` | Framework handles bar layout and tooltips |
| Cesium ring radius | Direct `semiMajorAxis` updates | `CallbackProperty` with closure over store | Avoids entity recreate; reacts to store changes |
| TypeScript discriminated union for sensor types | `string` | `'EO_IR' \| 'SAR' \| 'SIGINT'` literal union | Compile-time safety on sensor type usage |

---

## Common Pitfalls

### Pitfall 1: `cancel_track()` Must Remove from List, Not Clear
**What goes wrong:** `cancel_track(uav_id=5)` clears `target.tracked_by_uav_ids = []` even if UAVs 3 and 7 are also tracking the target.
**Why it happens:** The old code set `target.tracked_by_uav_id = None` (singular). A naive translation clears the list.
**How to avoid:**
```python
def cancel_track(self, uav_id: int):
    uav = self._find_uav(uav_id)
    if not uav:
        return
    old_target_id = uav.primary_target_id
    uav.mode = "SEARCH"
    uav.tracked_target_ids = [tid for tid in uav.tracked_target_ids if tid != old_target_id]
    uav.primary_target_id = None
    if old_target_id is not None:
        target = self._find_target(old_target_id)
        if target:
            target.tracked_by_uav_ids = [uid for uid in target.tracked_by_uav_ids if uid != uav_id]
            # Only regress state if NO UAVs remain
            if not target.tracked_by_uav_ids and target.state in ("TRACKED", "LOCKED"):
                target.state = "DETECTED"
```
**Warning signs:** Target state regresses even though another UAV is still tracking it.

### Pitfall 2: Dual-Sensor UAV Counts as Two Contributions
**What goes wrong:** A UAV with `sensors: ["EO_IR", "SAR"]` is placed within range of a target. Both sensors fire, both detections are added as `SensorContribution`. The `contributing_uav_ids` set still has only 1 UAV ID, but `sensor_types` has 2 entries. This is **correct behavior** — one physical UAV CAN contribute two independent sensor modalities.
**Pitfall:** If `sensor_count` is derived from `len(contributing_uav_ids)`, it won't reflect dual-sensor UAVs contributing two types. Use `len(unique_sensor_types)` + `len(contributing_uav_ids)` separately, or just serialize both to the frontend and let the UI choose what to display.
**Recommendation:** `FusedDetection.sensor_count` = `len(contributing_uav_ids)` (UAV count). Add `sensor_type_count = len(sensor_types)` separately if needed by Phase 2.

### Pitfall 3: 10Hz Broadcast Serializing Large `contributions` Payloads
**What goes wrong:** With 20 UAVs and 20 targets and dual-sensor UAVs, the contributions list can have up to 80 entries per target. At 10Hz, this is 16,000 contribution records/sec over WebSocket.
**How to avoid:** In `get_state()`, limit `sensor_contributions` to active contributors with confidence > 0.05, and cap at 10 per target:
```python
"sensor_contributions": [
    {"uav_id": c.uav_id, "sensor_type": c.sensor_type, "confidence": round(c.confidence, 3)}
    for c in sorted(t.sensor_contributions, key=lambda c: c.confidence, reverse=True)[:10]
    if c.confidence > 0.05
],
```

### Pitfall 4: `FusedDetection.contributions` is a Tuple — Reassignment Fails
**What goes wrong:** Code tries `fused.contributions.append(...)` — raises `AttributeError: 'tuple' object has no attribute 'append'`.
**How to avoid:** `FusedDetection` is frozen. The `Target.sensor_contributions` field is a regular `list[SensorContribution]` — mutate that, not the frozen dataclass.

### Pitfall 5: SIGINT Fusion When Target Stops Emitting
**What goes wrong:** A target's `is_emitting` toggles False mid-tick. SIGINT contributions that were accumulated earlier in the same tick still include SIGINT confidence. The fused result is artificially high.
**How to avoid:** The `evaluate_detection()` function correctly returns `pd=0.0` when `requires_emitter=True` and `emitting=False`. Since detection is evaluated per-tick with the current `is_emitting` value, this is handled automatically — no SIGINT contribution will enter the list for a non-emitting tick.

### Pitfall 6: TypeScript `sensor_contributions` Optional vs Required
**What goes wrong:** Old sim state payloads (or reconnection on initial tick) don't have `sensor_contributions`. React component crashes with `Cannot read properties of undefined (reading 'length')`.
**How to avoid:** In `types.ts`, make it optional or default to empty array in the Zustand store:
```typescript
sensor_contributions: SensorContributionPayload[];  // always array (backend guarantees [])
```
Ensure `get_state()` always serializes `"sensor_contributions": []` even for UNDETECTED targets.

---

## Code Examples

### Verified codebase observations

**UAV.sensors already spawned correctly** (`sim_engine.py:235`):
```python
self.sensors: List[str] = _pick_sensors()
```
`_pick_sensors()` uses the `_SENSOR_DISTRIBUTION` table (lines 74–80) with the correct distribution. Already serialized in `get_state()` as `"sensors": u.sensors`.

**Detection loop "best single" pattern to replace** (`sim_engine.py:568–606`):
```python
best_detection = None
for u in self.uavs:
    ...
    result = evaluate_detection(... sensor_type=u.sensor_type ...)
    if result.detected:
        if best_detection is None or result.confidence > best_detection.confidence:
            best_detection = result
```
This pattern uses `u.sensor_type` (the legacy single field, always "EO_IR" unless theater overrides). Phase 1 replaces this with the accumulation loop using `u.sensors`.

**`_assign_target()` sets singular `target.tracked_by_uav_id`** (`sim_engine.py:452`):
```python
target.tracked_by_uav_id = uav_id
```
After migration, this becomes:
```python
if uav_id not in target.tracked_by_uav_ids:
    target.tracked_by_uav_ids.append(uav_id)
```

**`cancel_track()` reads singular** (`sim_engine.py:476`):
```python
if target and target.tracked_by_uav_id == uav_id:
    target.tracked_by_uav_id = None
```

**`_update_tracking_modes()` bump on detection confidence** (`sim_engine.py:693`):
```python
target.detection_confidence = min(1.0, target.detection_confidence + 0.1 * dt_sec)
target.detected_by_sensor = u.sensor_type
```
After migration: bump `target.fused_confidence` (and keep `detection_confidence` in sync as the compat alias).

**`get_state()` target serialization** (`sim_engine.py:771–787`): already serializes `tracked_by_uav_id`. Add new fields here.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, no config file — `conftest.py` adds sys.path) |
| Config file | `src/python/tests/conftest.py` (sys.path setup only) |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_sensor_fusion.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short` |
| Frontend tests | Manual smoke test via Vite dev server (no Playwright yet) |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_sensor_fusion.py -x`
- **After sim_engine changes:** `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short` (full suite must stay green)
- **Phase gate:** All Python tests green + manual demo of fused confidence climbing in frontend before moving to Phase 2

### Phase 1 Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| P1-FUSE-MATH | `fuse_detections([])` returns 0.0 confidence | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_empty_contributions -x` | Wave 1 |
| P1-FUSE-SINGLE | Single contribution fused_confidence equals that contribution's confidence | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_single_contribution -x` | Wave 1 |
| P1-FUSE-MULTI | Two independent sensors fuse higher than either alone | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_two_types_fuse_higher -x` | Wave 1 |
| P1-FUSE-SAME-TYPE | Two EO_IR sensors: within-type max, not complementary fusion | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_same_type_uses_max -x` | Wave 1 |
| P1-FUSE-BOUNDS | Fused confidence always in [0.0, 1.0] | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_confidence_bounded -x` | Wave 1 |
| P1-FUSE-FROZEN | `SensorContribution` and `FusedDetection` are immutable | unit | `pytest test_sensor_fusion.py::TestImmutability -x` | Wave 1 |
| P1-SIM-MULTI | Multiple UAVs near same target → `sensor_count` > 1 | integration | `pytest test_sim_integration.py::TestMultiSensorFusion -x` | Wave 2 |
| P1-SIM-CONFIDENCE | Fused confidence > any single UAV's contribution | integration | `pytest test_sim_integration.py::TestMultiSensorFusion::test_fused_higher_than_single -x` | Wave 2 |
| P1-SIM-DEGRADE | Removing UAVs from area → fused confidence degrades | integration | `pytest test_sim_integration.py::TestMultiSensorFusion::test_confidence_degrades_on_removal -x` | Wave 2 |
| P1-SIM-CANCEL | `cancel_track()` removes only the cancelled UAV, leaves others | integration | `pytest test_sim_integration.py::TestCancelTrackMulti -x` | Wave 2 |
| P1-STATE | `get_state()` target payload includes `fused_confidence`, `sensor_count`, `sensor_contributions` | integration | `pytest test_sim_integration.py::TestGetStatePhase1 -x` | Wave 2 |
| P1-COMPAT | `tracked_by_uav_id` (singular) still works as compat shim | integration | `pytest test_sim_integration.py::TestBackwardCompat -x` | Wave 2 |
| P1-UI | FusionBar renders with per-sensor colors | smoke | Manual / browser | — |
| P1-UI-BADGE | SensorBadge shows correct count | smoke | Manual / browser | — |
| P1-CESIUM | Fusion ring appears and scales with sensor_count | smoke | Manual / Cesium viewer | — |

### Test File Plan
- `src/python/tests/test_sensor_fusion.py` — **NEW** (~100 lines): pure function tests for `fuse_detections()`, immutability, edge cases
- `src/python/tests/test_sim_integration.py` — **EXTEND** (~50 lines): add `TestMultiSensorFusion`, `TestCancelTrackMulti`, `TestGetStatePhase1`, `TestBackwardCompat` test classes

### Wave 1 Gaps (must exist before coding)
- [ ] `src/python/tests/test_sensor_fusion.py` — covers P1-FUSE-* (write before `sensor_fusion.py`)
- [ ] `src/python/sensor_fusion.py` — implement to make tests green

### Wave 2 Gaps (after Python backend complete)
- [ ] `sim_engine.py` Target/UAV field migration (tracked_by_uav_id → tracked_by_uav_ids, compat property)
- [ ] `sim_engine.py` detection loop rewrite (accumulate → fuse)
- [ ] `sim_engine.py` get_state() extension (add fusion fields)
- [ ] `sim_engine.py` _assign_target() + cancel_track() migration
- [ ] extend `test_sim_integration.py` with new test classes

### Wave 3 Gaps (after Phase 0 React app exists)
- [ ] `src/frontend-react/src/store/types.ts` — extend UAV + Target interfaces
- [ ] `src/frontend-react/src/panels/enemies/FusionBar.tsx` — stacked bar component
- [ ] `src/frontend-react/src/panels/enemies/SensorBadge.tsx` — count badge
- [ ] `src/frontend-react/src/panels/enemies/EnemyCard.tsx` — integrate FusionBar + SensorBadge
- [ ] `src/frontend-react/src/panels/assets/DroneCard.tsx` — show tracked_target_ids, highlight primary
- [ ] `src/frontend-react/src/cesium/useCesiumTargets.ts` — add fusion ring via ellipse entity property

---

## Sources

### Primary (HIGH confidence — directly read from codebase)
- `src/python/sim_engine.py` — full content read; line-by-line analysis of Target class, UAV class, detection loop, get_state(), cancel_track(), _assign_target()
- `src/python/sensor_model.py` — full content read; evaluate_detection() signature, DetectionResult fields, SensorConfig structure
- `src/python/tests/test_sensor_model.py` — test pattern reference for new test file structure
- `src/python/tests/test_sim_integration.py` — integration test pattern reference
- `src/python/tests/conftest.py` — sys.path setup confirmed
- `.planning/ROADMAP.md` — Phase 1 spec (sections 1.1–1.8) read in full
- `.planning/REQUIREMENTS.md` — FR-1 Multi-Sensor Fusion requirements confirmed
- `.planning/phases/00-foundation-react-migration/00-RESEARCH.md` — Phase 0 research read; TypeScript types, store pattern, Cesium hook pattern

### Secondary (MEDIUM confidence — library docs, design inferences)
- Complementary fusion formula: standard sensor fusion literature — `1 - product(1 - ci)` is well-established for statistically independent detectors
- ECharts stacked bar pattern: `echarts-for-react` README + ECharts bar series docs — `stack: 'fusion'` confirmed pattern
- Blueprint Tag `intent` values: `Intent.SUCCESS` / `Intent.WARNING` / `Intent.NONE` — confirmed from Blueprint v5 API

---

## Metadata

**Confidence breakdown:**
- Python side (fusion math, sim_engine migration): HIGH — direct codebase analysis
- TypeScript types: HIGH — derived from Phase 0 research + existing get_state() output
- React component patterns (FusionBar, SensorBadge): HIGH — same Blueprint/ECharts stack as Phase 0
- Cesium fusion ring: MEDIUM — EllipseGraphics API verified, but CallbackProperty performance with 20 targets at 10Hz is an estimate

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable codebase; re-verify after Phase 0 delivery changes types.ts)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P1-FUSE-MODULE | Create `src/python/sensor_fusion.py` with `SensorContribution`, `FusedDetection` frozen dataclasses and pure `fuse_detections()` function | Pattern 1 documents full implementation; frozen dataclass pattern matches sensor_model.py |
| P1-TARGET-FIELDS | Migrate `Target.tracked_by_uav_id` (singular) → `tracked_by_uav_ids: list[int]`; add `sensor_contributions`, `fused_confidence`, `sensor_count` | Pattern 2; backward compat property shim in Pattern 2 |
| P1-UAV-FIELDS | Add `UAV.tracked_target_ids: list[int]` and `primary_target_id`; keep `tracked_target_id` as property shim | Pattern 3; must not break _update_tracking_modes() |
| P1-DETECT-LOOP | Rewrite tick() step 9 from "best single detection" to "accumulate all + fuse_detections()" | Pattern 4; uses u.sensors (list) not u.sensor_type (legacy) |
| P1-CANCEL | Update `cancel_track()` to remove from list (not clear list) | Pitfall 1 documents the exact fix |
| P1-ASSIGN | Update `_assign_target()` to append to tracked_by_uav_ids list | Code example in Pattern 2 section |
| P1-BROADCAST | Extend `get_state()` target payload with `fused_confidence`, `sensor_count`, `tracked_by_uav_ids`, `sensor_contributions` | Pattern 5; cap contributions at 10, confidence > 0.05 |
| P1-TESTS | New `test_sensor_fusion.py` + extend `test_sim_integration.py` | Validation Architecture section; test map documents all test cases |
| P1-TS-TYPES | Extend `types.ts` with Phase 1 fields on UAV and Target interfaces | Pattern 6 |
| P1-FUSIONBAR | `FusionBar.tsx` — stacked ECharts bar showing per-sensor confidence | Pattern 7; EO_IR blue, SAR green, SIGINT amber |
| P1-BADGE | `SensorBadge.tsx` — Blueprint Tag showing UAV count contributing to target | Pattern 8 |
| P1-ENEMYCARD | Update `EnemyCard.tsx` — embed FusionBar + SensorBadge + contributing UAV IDs | Integrates P1-FUSIONBAR + P1-BADGE |
| P1-DRONECARD | Update `DroneCard.tsx` — show `tracked_target_ids` list; highlight `primary_target_id` | Pattern 6 UAV type; show all tracked targets |
| P1-CESIUM-RING | Add fusion ring to `useCesiumTargets.ts` — EllipseGraphics scaling with sensor_count | Pattern 9 |
</phase_requirements>
