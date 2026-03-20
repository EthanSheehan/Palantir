# Phase 10: Upgraded Drone Feeds - Research

**Researched:** 2026-03-20
**Domain:** Canvas 2D rendering, ECharts waterfall/heatmap, React multi-canvas layout, Blueprint UI
**Confidence:** HIGH

---

## Summary

Phase 10 is a pure frontend phase with a small Python backend shim. The dominant challenge is the multi-canvas layout system: DroneCamPIP.tsx currently renders a single 400x300 canvas through `useDroneCam`. The rewrite must support SINGLE/PIP/SPLIT/QUAD layouts, each composing up to 4 independent canvas instances driven by different drones and sensor render pipelines (EO/IR, SAR, SIGINT, FUSION).

Canvas 2D is the right rendering primitive — it is already in use, well-understood in this codebase, and avoids adding WebGL/Three.js complexity. Sensor modes are purely visual effects applied on top of the existing scene graph: color grading, noise textures, and overlay elements. The only genuinely new rendering domain is the SIGINT waterfall display, which is better done with ECharts (already installed at 5.5.0) than with raw canvas due to the complexity of a scrolling time-frequency heatmap.

The backend changes are minimal: expose `fov_targets` (targets currently in a UAV's FOV), `sensor_quality` per UAV, and nothing else. The frontend already receives all the data it needs (fuel_hours, sensors[], fused_confidence, sensor_contributions, heading_deg) from the existing WebSocket payload.

**Primary recommendation:** Extract `useDroneCam` into a parameterized `useSensorCanvas(droneId, sensorMode, canvasRef)` hook, compose layouts in the rewritten `DroneCamPIP.tsx`, and use ECharts `heatmap` series for the SIGINT waterfall with a sliding time window.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FR-9 | EO/IR, SAR, SIGINT sensor displays; SIGINT waterfall; PIP/SPLIT/QUAD layouts; Enhanced HUD with compass tape, fuel, multi-target bounding boxes | Canvas 2D color grading for EO/SAR modes, ECharts heatmap series for SIGINT waterfall, CSS flexbox/grid for layout composition, existing UAV data model has all required fields |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Canvas 2D API | browser native | EO/IR and SAR synthetic sensor rendering | Already used in useDroneCam; no deps; predictable 60fps rAF loop |
| ECharts | 5.5.0 (already installed) | SIGINT waterfall heatmap display | Already in project; palantir theme registered; heatmap series fits time-frequency display |
| echarts-for-react | 3.0.2 (already installed) | React wrapper for ECharts | Consistent with FusionBar.tsx pattern already in codebase |
| @blueprintjs/core | 5.13.0 (already installed) | CamLayoutSelector ButtonGroup, HUD overlays | Project standard; SegmentedControl/ButtonGroup used everywhere |
| React 18 | 18.3.1 (already installed) | Component architecture for layout system | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Zustand 4.5.0 | already installed | New UI state: camLayout, sensorMode per slot | Must extend SimulationStore with new fields |
| requestAnimationFrame | browser native | 60fps render loop for each canvas | One rAF loop per active canvas; cancel on unmount |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ECharts heatmap for SIGINT | Canvas 2D custom waterfall | ECharts is easier and already in project; custom canvas saves no deps but costs 200+ lines |
| CSS flexbox/grid for layout | ResizeObserver + absolute px | Flexbox is simpler and sufficient; pixel-perfect layout not required |
| Separate hooks per sensor | Single hook with sensorMode param | Parameterized hook avoids 4x code duplication; tradeoff is slight complexity in the switch |

**Installation:** No new packages required. All dependencies are already in `package.json`.

---

## Architecture Patterns

### Recommended Project Structure

```
src/frontend-react/src/
  hooks/
    useSensorCanvas.ts        # Replaces useDroneCam — parameterized by droneId + sensorMode
  overlays/
    DroneCamPIP.tsx           # MAJOR REWRITE — layout orchestrator, composes slots
  components/
    SigintDisplay.tsx         # NEW — ECharts waterfall chart
    CamLayoutSelector.tsx     # NEW — Blueprint ButtonGroup SINGLE/PIP/SPLIT/QUAD
    SensorHUD.tsx             # NEW — compass tape, fuel bar, sensor status overlay (Canvas or DOM)
```

### Pattern 1: Parameterized Canvas Hook

The existing `useDroneCam` is not parameterized — it always reads `selectedDroneId` from the store. For multi-slot layouts we need each slot to target a specific drone and sensor mode.

**What:** Extract and parameterize into `useSensorCanvas(droneId: number | null, sensorMode: SensorMode, canvasRef)`
**When to use:** One call per canvas slot

```typescript
// Source: existing useDroneCam.ts pattern, extended
export type SensorMode = 'EO_IR' | 'SAR' | 'SIGINT' | 'FUSION';

export function useSensorCanvas(
  droneId: number | null,
  sensorMode: SensorMode,
  canvasRef: React.RefObject<HTMLCanvasElement | null>
) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number | null = null;

    function render() {
      animId = requestAnimationFrame(render);
      const { uavs, targets } = useSimStore.getState();
      const drone = droneId != null ? uavs.find(u => u.id === droneId) ?? null : null;
      if (!drone) { drawNoFeed(ctx!, canvas!); return; }
      drawSensorFrame(ctx!, canvas!, drone, targets, sensorMode);
    }

    animId = requestAnimationFrame(render);
    return () => { if (animId != null) cancelAnimationFrame(animId); };
  }, [droneId, sensorMode, canvasRef]);
}
```

**Key decision:** Keep `useSimStore.getState()` inside the rAF loop (same pattern as existing hook) — avoids React re-renders on every tick.

### Pattern 2: Sensor Mode Visual Rendering

Each mode is a draw-function variant called from `drawSensorFrame`:

**EO/IR** — thermal green palette:
```typescript
function applyEoIrFilter(ctx: CanvasRenderingContext2D, w: number, h: number) {
  // Dark green background already established
  // Hot targets: fill semi-transparent green glow around detected positions
  // Terrain noise: draw subtle noise texture using fillRect with random alpha
  // Color palette: background #0a1a0a, grid #0f2010, targets glow '#00ff88' with radial gradient
}
```

**SAR** — amber radar returns:
```typescript
function applySarFilter(ctx: CanvasRenderingContext2D, w: number, h: number) {
  // Background: near-black #0d0800
  // Scan-line effect: horizontal amber stripe moving top-to-bottom each frame
  // Target echoes: amber '#ffb300' with sharp bright center and fast falloff
  // Velocity vectors: short lines from target position in heading direction
  // Noise: scattered amber dots with low alpha
}
```

**SIGINT** — handled by SigintDisplay component (ECharts), not canvas.

**FUSION** — split-screen: two side-by-side sub-canvases (EO_IR left, SAR right) with a center divider line. Reuse the EO_IR and SAR draw functions on each half via `ctx.save()/ctx.restore()` + `ctx.translate()` + `ctx.scale(0.5, 1)` clip regions.

### Pattern 3: Layout Composition

```typescript
// DroneCamPIP.tsx — layout slots
type CamLayout = 'SINGLE' | 'PIP' | 'SPLIT' | 'QUAD';

// SINGLE: one canvas, full frame
// PIP: large canvas (main drone) + small canvas (second drone, top-right corner overlay)
// SPLIT: two equal canvases side by side in a flex row
// QUAD: 2x2 CSS grid of four canvases

// Each slot = { droneId: number | null; sensorMode: SensorMode }
// Slot assignment: SINGLE=[primary], PIP=[primary, secondary], SPLIT=[primary, secondary], QUAD=[0,1,2,3 from fleet]
```

Layout is pure CSS — `display: flex` for SPLIT, `display: grid; grid-template-columns: 1fr 1fr` for QUAD, absolute positioning for PIP overlay.

### Pattern 4: SigintDisplay ECharts Waterfall

The SIGINT display is not a camera view — it shows emitter frequency vs time as a scrolling heatmap. This is a separate component alongside the canvas feed, rendered when the selected drone has `sensors` including `'SIGINT'`.

```typescript
// Source: ECharts heatmap series docs + existing FusionBar.tsx pattern
// echarts-for-react ReactECharts with option object, animation: false, notMerge: false

const SIGINT_FREQ_BINS = 64;  // y-axis: frequency bands 0-63
const SIGINT_TIME_SLOTS = 60; // x-axis: last 60 ticks (~6s at 10Hz or 30s at 2Hz)

// Data: Float32Array ring buffer [time_slot][freq_bin] = intensity
// Each tick: shift left, insert new column of per-freq intensities
// Emitter at known frequency bin: inject high-intensity value
// Background: thermal noise floor ~0.1 + random jitter

option = {
  animation: false,
  xAxis: { type: 'category', data: timeLabels, show: false },
  yAxis: { type: 'category', data: freqLabels, show: false },
  visualMap: {
    min: 0, max: 1,
    inRange: { color: ['#000814', '#001d3d', '#003566', '#ffd60a', '#ffffff'] },
    show: false,
  },
  series: [{
    type: 'heatmap',
    data: flattenedData,   // [[time, freq, intensity], ...]
    emphasis: { disabled: true },
  }],
  grid: { top: 0, bottom: 0, left: 0, right: 0 },
};
```

**Critical:** `animation: false` and `notMerge: false` — matches FusionBar pattern. The color scale uses a dark-blue-to-white ramp for the "SIGINT dark blue" aesthetic.

### Pattern 5: SensorHUD — DOM overlay, not canvas

The HUD elements (compass tape, fuel gauge, sensor status) are easier and more maintainable as absolutely-positioned DOM elements over the canvas, rather than drawn into the canvas itself. The existing HUD in `useDroneCam` uses canvas — this was fine for one simple HUD but the new HUD is more complex.

```typescript
// SensorHUD.tsx — positioned absolute over the canvas container
// compass tape: horizontal div with tick marks, current heading highlighted
// fuel gauge: Blueprint ProgressBar (intent changes: green > 50%, warning 20-50%, danger < 20%)
// sensor status: small text badge showing active sensor type + fused count
// threat warning: red flash overlay div when target.threat_range_km within range
```

DOM HUD avoids the complexity of text rendering, clipping, and animation in canvas. Blueprint ProgressBar handles fuel with zero custom code.

### Anti-Patterns to Avoid
- **One hook instance shared across slots:** Each canvas slot needs its own `useSensorCanvas` call with its own rAF loop. Sharing one loop that writes to multiple canvases is error-prone.
- **Re-creating canvas context on every render:** Keep `ctx` in the `useEffect` closure, not in component state.
- **ECharts for sensor frame rendering:** ECharts is only for SIGINT waterfall. EO/IR and SAR use canvas — ECharts is too heavy for 60fps frame-by-frame synthetic imagery.
- **Keeping `tracked_target_id` (singular):** The UAV type already has `tracked_target_ids` (plural) from Phase 1. The existing `useDroneCam` uses the legacy `tracked_target_id` field. Phase 10 should use `primary_target_id` for the primary reticle and loop `tracked_target_ids` for secondary bounding boxes.
- **Blocking layout change on drone selection:** Layout and drone-slot assignment should be independent state — user picks layout first, then assigns drones to slots (or auto-assign from current fleet).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SIGINT frequency heatmap | Custom canvas 2D heatmap | ECharts heatmap series | Interpolation, tooltip, color mapping already solved; ~50 lines vs ~200 |
| Fuel progress indicator | Canvas arc or custom bar | Blueprint ProgressBar | Intent-based color changes for free; accessible |
| Layout resize handling | ResizeObserver + JS calculations | CSS flexbox/grid | Simpler, handles parent resize automatically |

**Key insight:** The visual effects for EO/IR and SAR are simple color grading + noise — they don't require a shader pipeline or WebGL. Canvas 2D `fillRect` with varying alpha and color is sufficient for the "synthetic sensor" aesthetic.

---

## Common Pitfalls

### Pitfall 1: Canvas Size vs CSS Size Mismatch
**What goes wrong:** Canvas renders blurry or wrong size — element sized by CSS but canvas internal resolution (width/height attributes) not updated.
**Why it happens:** Setting `canvas.style.width = '100%'` doesn't change `canvas.width`. The canvas rasterizes at its attribute dimensions, then scales up via CSS.
**How to avoid:** In `useSensorCanvas`, on mount read the canvas's `clientWidth`/`clientHeight` and set `canvas.width = canvas.clientWidth * window.devicePixelRatio` (or use a fixed size matching the container). QUAD layout slots will be ~200x150 each — pre-compute per layout.
**Warning signs:** Blurry text/lines, targets appearing at wrong positions.

### Pitfall 2: Multiple rAF Loops Creating Canvas Contention
**What goes wrong:** QUAD layout spawns 4 `useSensorCanvas` hooks, each running `requestAnimationFrame`. If canvas refs overlap or the drone list changes, you get stale closures drawing to wrong canvases.
**Why it happens:** The `useEffect` dependency array needs `[droneId, sensorMode]` — if these change, the old effect's cleanup must cancel the old rAF before the new one starts.
**How to avoid:** Strictly follow the cleanup pattern: `return () => { if (animId != null) cancelAnimationFrame(animId); }`. The `animId` must be declared with `let` inside the effect, not `useRef`.

### Pitfall 3: ECharts Waterfall Performance at 10Hz
**What goes wrong:** SIGINT waterfall lags or freezes if updated every WebSocket tick (10Hz = 100ms).
**Why it happens:** `echarts-for-react` triggers a full React re-render + ECharts setOption on every `option` prop change. At 10Hz with 64x60=3840 data points this is significant.
**How to avoid:** Throttle SIGINT data updates to 2Hz (match SENSOR_FEED rate). Use `notMerge: false` so ECharts does incremental updates. Keep the data array stable with a ring buffer — shift the oldest column, push the new column.

### Pitfall 4: FUSION Mode Canvas Clipping
**What goes wrong:** In FUSION mode (split-screen two sensors), the target projection coordinates overflow into the wrong half.
**Why it happens:** The `projectTarget()` function returns coordinates in [0..WIDTH, 0..HEIGHT] space. If you just draw both pipelines to the full canvas, they overlap.
**How to avoid:** Use `ctx.save(); ctx.beginPath(); ctx.rect(0, 0, WIDTH/2, HEIGHT); ctx.clip(); drawEoIrFrame(...); ctx.restore()` for left half, then the same for right half with `ctx.rect(WIDTH/2, 0, WIDTH/2, HEIGHT)`. Adjust `projectTarget` to accept a width parameter so it projects into the clipped region.

### Pitfall 5: Blueprint SegmentedControl vs ButtonGroup for Layout Selector
**What goes wrong:** Using `SegmentedControl` breaks with `as const` typed options arrays (known issue from Phase 3 decisions log).
**Why it happens:** Blueprint SegmentedControl requires a mutable options array — the `as const` modifier makes it readonly.
**How to avoid:** Use `ButtonGroup` with individual `Button` components (as done in AutonomyToggle.tsx pattern) OR use `SegmentedControl` with a non-const array.

### Pitfall 6: Stale primary_target_id vs tracked_target_id
**What goes wrong:** Reticle or bounding boxes don't render on the correct target.
**Why it happens:** The existing `useDroneCam` uses `drone.tracked_target_id` (the legacy Phase 0 field). After Phase 1, the authoritative field is `drone.primary_target_id`.
**How to avoid:** In `useSensorCanvas`, use `drone.primary_target_id` for the primary reticle/lock box, and loop `drone.tracked_target_ids` for all secondary dashed bounding boxes.

---

## Code Examples

Verified patterns from existing codebase:

### ECharts Usage Pattern (from FusionBar.tsx)
```typescript
// Source: src/frontend-react/src/panels/enemies/FusionBar.tsx
import ReactECharts from 'echarts-for-react';
import { useMemo } from 'react';

// Key: animation: false, notMerge: false, opts.renderer: 'canvas'
const option = useMemo(() => ({
  animation: false,
  // ... chart config
}), [stableKey]); // stableKey = serialized data fingerprint to avoid unnecessary re-renders

<ReactECharts
  option={option}
  style={{ height: 12, width: 120 }}
  opts={{ renderer: 'canvas' }}
  notMerge={false}
/>
```

### rAF Loop Pattern (from useDroneCam.ts)
```typescript
// Source: src/frontend-react/src/hooks/useDroneCam.ts
useEffect(() => {
  const canvas = canvasRef.current;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let animId: number | null = null;

  function renderLoop() {
    animId = requestAnimationFrame(renderLoop);
    const { selectedDroneId, droneCamVisible, uavs, targets } = useSimStore.getState();
    // ... draw
  }

  animId = requestAnimationFrame(renderLoop);
  return () => {
    if (animId != null) cancelAnimationFrame(animId);
  };
}, [canvasRef]); // dependency: only canvasRef (stable ref)
```

### Blueprint ButtonGroup Pattern for Selectors
```typescript
// Source: pattern from DroneModeButtons.tsx / AutonomyToggle.tsx
import { Button, ButtonGroup, Intent } from '@blueprintjs/core';

// Use ButtonGroup + Button (not SegmentedControl) to avoid as const issues
<ButtonGroup small>
  {LAYOUTS.map(l => (
    <Button
      key={l.key}
      active={layout === l.key}
      intent={layout === l.key ? Intent.PRIMARY : Intent.NONE}
      onClick={() => setLayout(l.key)}
    >
      {l.label}
    </Button>
  ))}
</ButtonGroup>
```

### Blueprint ProgressBar for Fuel Gauge
```typescript
// Source: Blueprint docs pattern, consistent with project usage
import { ProgressBar, Intent } from '@blueprintjs/core';

const fuelFraction = Math.min(drone.fuel_hours / 24, 1);  // 24h max endurance
const fuelIntent = fuelFraction > 0.5 ? Intent.SUCCESS
  : fuelFraction > 0.2 ? Intent.WARNING
  : Intent.DANGER;

<ProgressBar value={fuelFraction} intent={fuelIntent} animate={false} stripes={false} />
```

### Canvas Clipping for FUSION Split-Screen
```typescript
// Pattern for splitting canvas into two half-width render regions
function drawFusionFrame(ctx: CanvasRenderingContext2D, w: number, h: number, drone: UAV, targets: Target[]) {
  // Left half: EO/IR
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, w / 2, h);
  ctx.clip();
  drawEoIrFrame(ctx, w / 2, h, drone, targets);
  ctx.restore();

  // Divider line
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(w / 2, 0);
  ctx.lineTo(w / 2, h);
  ctx.stroke();

  // Right half: SAR
  ctx.save();
  ctx.translate(w / 2, 0);
  ctx.beginPath();
  ctx.rect(0, 0, w / 2, h);
  ctx.clip();
  drawSarFrame(ctx, w / 2, h, drone, targets);
  ctx.restore();
}
```

---

## Backend Changes (Minimal)

The roadmap specifies ~30 lines in `sim_engine.py` and ~20 lines in `api_main.py`. Based on what data is already in the payload:

**Already present in get_state():**
- `fuel_hours` — UAV field, already serialized (line 1351 in sim_engine.py)
- `sensors` — UAV sensors list, already serialized
- `heading_deg`, `lat`, `lon`, `altitude_m` — all present
- `fused_confidence`, `sensor_contributions`, `sensor_count` — target fields, already serialized
- `threat_range_km` — target field, already serialized

**What needs to be added (the ~30 lines):**
1. `fov_targets: list[int]` per UAV — IDs of targets currently within FOV. Computed in `get_state()` using the same `_in_fov()` logic from detection, saves the frontend from re-doing geometry. This enables accurate multi-target bounding boxes without duplicate projection math.
2. `sensor_quality: float` per UAV — simple proxy: `min(1.0, fused_confidence of primary target)` or a fixed quality based on mode (PAINT=1.0, FOLLOW=0.8, others=0.6). Used by the HUD sensor status panel.

These are read-only computed fields added to the get_state serialization — no sim logic changes, no new state.

---

## State Additions Needed in Zustand Store

```typescript
// Add to SimulationStore.ts / types.ts:

// UAV type addition:
export interface UAV {
  // ... existing fields ...
  fov_targets: number[];      // IDs of targets currently in FOV (new from backend)
  sensor_quality: number;     // 0-1 sensor quality metric (new from backend)
}

// New UI state:
export type CamLayout = 'SINGLE' | 'PIP' | 'SPLIT' | 'QUAD';
export type SensorMode = 'EO_IR' | 'SAR' | 'SIGINT' | 'FUSION';

// SimulationStore additions:
camLayout: CamLayout;           // selected layout
setCamLayout: (l: CamLayout) => void;
// Note: sensor mode per slot is local to DroneCamPIP component state, not global store
// (no other component needs to know which sensor mode slot 3 is in)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single canvas, single drone | Multi-slot canvas layout | Phase 10 | Architecture change to DroneCamPIP |
| Green EO-only rendering | Sensor-typed rendering (EO/SAR/SIGINT) | Phase 10 | useDroneCam → useSensorCanvas |
| tracked_target_id (singular) | primary_target_id + tracked_target_ids | Phase 1 | Existing useDroneCam uses legacy field; must migrate |
| Simple HUD (text overlay in canvas) | DOM overlay SensorHUD with Blueprint components | Phase 10 | Separates HUD concerns from canvas draw loop |

**Deprecated/outdated in this phase:**
- `useDroneCam.ts`: Replaced by `useSensorCanvas.ts`. Keep the file until migration is verified, then delete.
- `drone.tracked_target_id` usage in canvas hook: Replace with `drone.primary_target_id`.

---

## Open Questions

1. **SIGINT waterfall data source**
   - What we know: The backend generates SIGINT detections when an enemy UAV is JAMMING or a target is `is_emitting=True`. The SENSOR_FEED (Phase 6) sends per-UAV detection results at 2Hz.
   - What's unclear: Phase 6 (Information Feeds) may not be complete before Phase 10. If SENSOR_FEED isn't available, SIGINT waterfall data must be synthesized from `sensor_contributions` in the STATE_FEED.
   - Recommendation: Synthesize SIGINT waterfall from `sensor_contributions` where `sensor_type === 'SIGINT'`. Use confidence as intensity, assign a pseudo-frequency bin per target ID (deterministic mapping). This avoids SENSOR_FEED dependency.

2. **QUAD layout drone slot assignment**
   - What we know: QUAD shows 4 slots. There are up to 20 UAVs.
   - What's unclear: Which 4 drones populate the QUAD slots? Options: (a) first 4 from fleet, (b) 4 most recently active, (c) user manually assigns.
   - Recommendation: Auto-assign QUAD slots to the 4 drones with non-IDLE modes (or first 4 if all idle). This is deterministic, no UI needed, sufficient for demo.

3. **SensorHUD compass tape implementation**
   - What we know: Compass tape is a horizontal strip with bearing markings, current heading highlighted. It's a known HUD pattern.
   - What's unclear: Whether to implement as canvas (consistent with existing HUD style) or DOM (easier with CSS).
   - Recommendation: DOM implementation. A fixed-width div with overflow hidden, containing an inner div of ~1080px wide with tick marks drawn via CSS border-top, translated left/right based on `heading_deg`. This is simpler than canvas text measurement and avoids canvas context sharing.

---

## Validation Architecture

No `nyquist_validation` key in `.planning/config.json` — treat as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + TypeScript compile check (frontend) |
| Config file | pytest.ini or default discovery at src/python/tests/ |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/ && cd src/frontend-react && npx tsc --noEmit` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-9 | Backend serializes fov_targets and sensor_quality per UAV | unit | `pytest src/python/tests/test_sim_engine.py -k "sensor_quality or fov_targets" -x` | ❌ Wave 0 (add test) |
| FR-9 | Canvas sensor modes render without throwing (EO/SAR/FUSION) | smoke | `cd src/frontend-react && npx tsc --noEmit` | existing |
| FR-9 | SIGINT ECharts option object structure is valid | unit | TypeScript compile | existing |
| FR-9 | CamLayout Zustand actions update state correctly | unit | TypeScript compile + manual | existing |

### Sampling Rate
- **Per task commit:** `cd /Users/Rocklord/Documents/GitHub/Palantir/src/frontend-react && npx tsc --noEmit`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/ -q && cd src/frontend-react && npx tsc --noEmit`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_sim_engine.py` — add assertions for `fov_targets` and `sensor_quality` in `get_state()` output

---

## Sources

### Primary (HIGH confidence)
- Codebase: `src/frontend-react/src/hooks/useDroneCam.ts` — existing canvas hook, rAF pattern
- Codebase: `src/frontend-react/src/panels/enemies/FusionBar.tsx` — ECharts usage pattern
- Codebase: `src/frontend-react/src/store/types.ts` — full UAV/Target data model
- Codebase: `src/frontend-react/src/store/SimulationStore.ts` — Zustand store patterns
- Codebase: `src/frontend-react/src/theme/palantir.ts` — ECharts theme registration
- Codebase: `src/frontend-react/package.json` — confirmed library versions
- Codebase: `src/python/sim_engine.py` — confirmed fuel_hours and sensors[] already serialized
- Project STATE.md decisions — Blueprint SegmentedControl mutable array constraint, as const incompatibility

### Secondary (MEDIUM confidence)
- ECharts heatmap series documentation — heatmap type used for waterfall via time×frequency data
- Canvas 2D clip region pattern — standard MDN API, well-known

### Tertiary (LOW confidence)
- None — all findings verified against existing codebase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, versions confirmed from package.json
- Architecture: HIGH — useSensorCanvas hook pattern derived directly from existing useDroneCam code
- Pitfalls: HIGH — canvas size mismatch, rAF cleanup, and SegmentedControl issues are all directly observed in the codebase (tracked_target_id vs primary_target_id, Phase 3 SegmentedControl decision)
- ECharts SIGINT waterfall: MEDIUM — ECharts heatmap series is correct approach but specific sliding-window update pattern should be validated during implementation

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable libraries, no breaking changes expected)
