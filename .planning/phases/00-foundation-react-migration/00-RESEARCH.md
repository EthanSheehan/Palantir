# Phase 0: Foundation & React Migration - Research

**Researched:** 2026-03-19
**Domain:** React 18 + TypeScript + Vite + CesiumJS + Blueprint.js v5 + Zustand v4
**Confidence:** HIGH (verified against npm registry, official docs, and live codebase)

## Summary

The project already has a scaffold at `src/frontend-react/` with all dependencies defined in `package.json` (React 18.3.1, Blueprint v5.13, CesiumJS 1.114, Vite 5.4, Zustand 4.5, ECharts 5.5, vite-plugin-cesium 1.2.23). The directories in `src/` are stubbed but empty — no `.tsx`/`.ts` files exist yet. This means Phase 0 is a pure authoring task, not a migration of partial code.

The existing vanilla JS frontend (`src/frontend/`) has well-understood patterns that map directly to React hooks. The state object (`state.js`) maps cleanly to a single Zustand store. The WebSocket handler (`websocket.js`) maps to a `useWebSocket` hook. All Cesium entity management uses imperative patterns (SampledPositionProperty, GroundPrimitive, CallbackProperty) that must stay imperative inside `useEffect` bodies — this is the right approach given the decision to avoid resium.

The `palantir.sh` launcher currently starts `src/frontend/serve.py`. It must be updated to run `vite` (or `vite build && serve dist`) for the React frontend. The bug in `sim_engine.py:509` already has the correct tuple `("FOLLOW", "PAINT", "INTERCEPT")` in the current codebase — the stated bug at line 509 appears to be a previously fixed issue. The STATE.md entry may be stale, but verify before including a "fix" task.

**Primary recommendation:** Author files in dependency order — store + types → hooks → CesiumContainer + Cesium hooks → panels — then update `palantir.sh`. Keep React.StrictMode disabled (or guard Viewer creation with a ref flag) to prevent double-mount Viewer corruption.

## Standard Stack

### Core (verified against npm registry 2026-03-19)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 18.3.1 | UI framework | Current LTS, concurrent features |
| react-dom | 18.3.1 | DOM renderer | Paired with react |
| typescript | 5.5.0 | Type safety | Catches payload shape errors early |
| vite | 5.4.0 (dev) | Build tool + HMR | Replaces `serve.py`, instant refresh |
| @vitejs/plugin-react | 4.3.0 (dev) | JSX transform | Official React plugin for Vite |
| vite-plugin-cesium | 1.2.23 (dev) | CesiumJS asset handling | Handles CESIUM_BASE_URL and static assets |
| cesium | 1.114.0 | 3D globe | Already in use; 1.114+ removes need for node externals |
| @blueprintjs/core | 5.13.0 | UI components | Dark theme, enterprise look |
| @blueprintjs/icons | 5.14.0 | Icon set | Paired with core |
| @blueprintjs/select | 5.3.0 | Dropdown components | Theater selector |
| zustand | 4.5.0 | State management | Zero-boilerplate, subscribes outside React |
| echarts | 5.5.0 | Charts | Palantir-dark theme support |
| echarts-for-react | 3.0.2 | ECharts React wrapper | Standard for React+ECharts |

**Note:** Zustand 5.x was released after project dependency lock — project is on v4. The v4 API (`create` + `immer` middleware pattern) is what must be used.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @blueprintjs/select | 5.3.0 | Select/Suggest | Theater dropdown picker |
| immer (optional) | — | Immutable updates in Zustand | If store updates grow complex |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| vite-plugin-cesium | Manual CESIUM_BASE_URL config | Plugin automates all asset copying; manual is ~20 lines of extra config |
| Zustand v4 | Jotai, Redux | Zustand is already locked in project decision |
| echarts-for-react | recharts, victory | ECharts was decided for Palantir dark theme |

**Installation (already in package.json — run once):**
```bash
cd src/frontend-react && npm install
```

## Architecture Patterns

### Validated Project Structure (already scaffolded)
```
src/frontend-react/
  index.html                          # <body class="bp5-dark"> already set
  vite.config.ts                      # cesium() + react() plugins, proxy to :8000
  tsconfig.json                       # strict mode, bundler resolution
  src/
    main.tsx                          # React root, FocusStyleManager.onlyShowFocusOnTabs()
    App.tsx                           # Layout: Sidebar (left) + CesiumContainer (fill)
    store/                            # EMPTY — must author
    hooks/                            # EMPTY — must author
    cesium/                           # EMPTY — must author
    panels/                           # EMPTY — must author (4 subdirs already exist)
    overlays/                         # EMPTY — must author
    shared/                           # EMPTY — must author
    theme/                            # EMPTY — must author
```

### Pattern 1: Zustand Store (SimulationStore)
**What:** Single store holds all sim state. WebSocket hook calls `setState` directly.
**When to use:** Any component that needs sim data subscribes with a selector.
**Key insight:** At 10Hz, avoid selecting entire `uavs` array if component only needs one field — use per-field selectors or shallow equality to prevent unnecessary re-renders.

```typescript
// Source: Zustand v4 docs
import { create } from 'zustand';

interface SimState {
  uavs: UAV[];
  targets: Target[];
  zones: Zone[];
  strikeBoard: StrikeEntry[];
  theater: TheaterInfo | null;
  demoMode: boolean;
  // UI state
  selectedDroneId: number | null;
  selectedTargetId: number | null;
  trackedDroneId: number | null;
  gridVisState: 0 | 1 | 2;
  showAllWaypoints: boolean;
  droneCamVisible: boolean;
  // Actions
  setSimState: (data: Partial<SimState>) => void;
  selectDrone: (id: number | null) => void;
  selectTarget: (id: number | null) => void;
}

export const useSimStore = create<SimState>((set) => ({
  uavs: [],
  targets: [],
  zones: [],
  strikeBoard: [],
  theater: null,
  demoMode: false,
  selectedDroneId: null,
  selectedTargetId: null,
  trackedDroneId: null,
  gridVisState: 2,
  showAllWaypoints: false,
  droneCamVisible: false,
  setSimState: (data) => set(data),
  selectDrone: (id) => set({ selectedDroneId: id }),
  selectTarget: (id) => set({ selectedTargetId: id }),
}));
```

### Pattern 2: WebSocket Hook
**What:** Single hook manages the WS connection, dispatches messages to the Zustand store.
**When to use:** Mount once at App level, pass `sendMessage` down or expose via store.
**Key insight:** The existing `websocket.js` uses `document.dispatchEvent` as a bus. In React, replace this with direct Zustand `setState` calls — no custom events needed.

```typescript
// Translates websocket.js pattern to React hook
export function useWebSocket() {
  const setSimState = useSimStore(s => s.setSimState);
  const wsRef = useRef<WebSocket | null>(null);

  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'IDENTIFY', client_type: 'DASHBOARD' }));
      };
      ws.onclose = () => setTimeout(connect, 1000);
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'state') {
          setSimState(payload.data);
        }
        // ASSISTANT_MESSAGE, HITL_UPDATE handled via store fields
      };
    }
    connect();
    return () => wsRef.current?.close();
  }, [setSimState]);

  return { sendMessage };
}
```

### Pattern 3: Cesium Viewer Lifecycle (CRITICAL)
**What:** Create Viewer once, destroy on unmount. Ref-based, not state-based.
**When to use:** `CesiumContainer.tsx` mounts the Viewer and passes `viewerRef` to all Cesium hooks.
**Critical issue:** React 18 StrictMode double-mounts components in dev. A guard flag prevents double Viewer creation. Alternatively, disable StrictMode for this project (acceptable for a C2 app that needs stable refs).

```typescript
// CesiumContainer.tsx — imperative Viewer lifecycle
export function CesiumContainer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;

    // Set token before creating Viewer
    Cesium.Ion.defaultAccessToken = CESIUM_TOKEN;

    viewerRef.current = new Cesium.Viewer(containerRef.current, {
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      terrain: Cesium.Terrain.fromWorldTerrain(),
    });

    // CARTO dark tiles (no key required — same as map.js)
    const viewer = viewerRef.current;
    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
      })
    );

    return () => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, []);

  // Pass viewerRef to all Cesium sub-hooks
  useCesiumDrones(viewerRef);
  useCesiumTargets(viewerRef);
  useCesiumZones(viewerRef);
  useCesiumFlowLines(viewerRef);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

### Pattern 4: Cesium Entity Hook (useCesiumDrones)
**What:** Translates `updateDrones()` from `drones.js` into a hook that subscribes to Zustand.
**When to use:** Called inside `CesiumContainer.tsx` after viewer is initialized.
**Key insight:** Use a `useRef<Record<number, Cesium.Entity>>({})` to store entity refs — never React state. Only create/update entities imperatively in `useEffect`.

```typescript
export function useCesiumDrones(viewerRef: RefObject<Cesium.Viewer | null>) {
  const uavs = useSimStore(s => s.uavs);
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    const currentIds = new Set(uavs.map(u => u.id));

    uavs.forEach(uav => {
      if (!entitiesRef.current[uav.id]) {
        // _createDroneEntity logic from drones.js
        const positionProperty = new Cesium.SampledPositionProperty();
        positionProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
        positionProperty.setInterpolationOptions({
          interpolationDegree: 2,
          interpolationAlgorithm: Cesium.HermitePolynomialApproximation,
        });
        // ... rest of entity creation
      } else {
        // _updateExistingDrone logic from drones.js
      }
    });

    // Cleanup removed UAVs
    Object.keys(entitiesRef.current).forEach(idStr => {
      const id = parseInt(idStr);
      if (!currentIds.has(id)) {
        viewer.entities.remove(entitiesRef.current[id]);
        delete entitiesRef.current[id];
      }
    });
  }, [uavs, viewerRef]);
}
```

### Pattern 5: Blueprint.js Dark Theme Setup
**What:** Apply dark theme globally via `bp5-dark` class and CSS imports.
**When to use:** `main.tsx` and `index.html`.

```typescript
// main.tsx
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import { FocusStyleManager } from '@blueprintjs/core';

FocusStyleManager.onlyShowFocusOnTabs();

// index.html already has: <body class="bp5-dark">
// That single class enables dark theme for all Blueprint components
```

### Pattern 6: Zustand Subscribe Outside React (for Cesium hooks)
**What:** Cesium hooks can subscribe to Zustand store directly without React render cycle.
**When to use:** When Cesium entity updates should not trigger React re-renders.

```typescript
// Subscribe to store changes in a non-React context
const unsubscribe = useSimStore.subscribe(
  (state) => state.uavs,
  (uavs) => { /* update Cesium entities */ }
);
```

### Pattern 7: TypeScript Interfaces for WebSocket Payload
**What:** `store/types.ts` defines all shapes broadcast from the backend.
**Key fields from examining `api_main.py` and `sim_engine.py`:**

```typescript
// store/types.ts
export interface UAV {
  id: number;
  lat: number;
  lon: number;
  altitude_m: number;
  mode: 'IDLE' | 'SEARCH' | 'FOLLOW' | 'PAINT' | 'INTERCEPT' | 'REPOSITIONING' | 'RTB';
  heading_deg: number;
  tracked_target_id: number | null;
  sensor_type: string;      // currently "EO_IR" for all
  fuel_hours: number;
}

export interface Target {
  id: number;
  lat: number;
  lon: number;
  type: string;             // SAM, TEL, TRUCK, CP, MANPADS, RADAR, C2_NODE, LOGISTICS, ARTILLERY, APC
  state: string;            // UNDETECTED, DETECTED, IDENTIFIED, TRACKED, NOMINATED, ENGAGED, NEUTRALIZED
  detected: boolean;
  detection_confidence: number;
  concealed?: boolean;
}

export interface Zone {
  x_idx: number;
  y_idx: number;
  lat: number;
  lon: number;
  width: number;
  height: number;
  imbalance: number;
}

export interface StrikeEntry {
  id: string;
  target_type: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'RETASKED';
  detection_confidence: number;
  priority_score: number;
  roe_evaluation: string;
}

export interface COA {
  id: string;
  effector_name: string;
  effector_type: string;
  pk_estimate: number;
  time_to_effect_min: number;
  risk_score: number;
  composite_score: number;
  status: string;
}

export interface SimStatePayload {
  uavs: UAV[];
  targets: Target[];
  zones: Zone[];
  flows: Array<{ source: [number, number]; target: [number, number] }>;
  strike_board: StrikeEntry[];
  theater: { name: string; bounds: TheaterBounds } | null;
  demo_mode: boolean;
  sitrep_response?: string;
  hitl_update?: { text: string; severity: string } | string;
}
```

### Pattern 8: JSONL Event Logger
**What:** Async append-only JSONL log using asyncio queue + aiofiles pattern.
**When to use:** `src/python/event_logger.py` — called from sim tick and WS handlers.
**Key insight:** FastAPI runs on asyncio. Use an asyncio queue with a background writer task to avoid blocking the sim loop with I/O. The existing codebase already uses `aiofiles`-compatible patterns via `asyncio`.

```python
# src/python/event_logger.py
import asyncio
import json
import os
from datetime import date, datetime
from pathlib import Path

LOG_DIR = Path("logs")
_queue: asyncio.Queue = asyncio.Queue()

async def _writer_task():
    LOG_DIR.mkdir(exist_ok=True)
    while True:
        event = await _queue.get()
        log_path = LOG_DIR / f"events-{date.today().isoformat()}.jsonl"
        line = json.dumps(event) + "\n"
        with open(log_path, "a") as f:  # sync OK — queue buffers
            f.write(line)

def log_event(event_type: str, data: dict) -> None:
    """Non-blocking enqueue. Call from sync or async contexts."""
    event = {"timestamp": datetime.utcnow().isoformat() + "Z",
             "event_type": event_type, "data": data}
    _queue.put_nowait(event)

async def start_logger():
    asyncio.create_task(_writer_task())
```

### Pattern 9: Multi-Sensor UAV Spawn
**What:** Assign `sensors: list[str]` at spawn time using weighted random distribution.
**Where:** `sim_engine.py` UAV spawn loop (lines ~360-370).

```python
import random

SENSOR_DIST = [
    (["EO_IR"], 0.50),
    (["SAR"], 0.20),
    (["SIGINT"], 0.10),
    (["EO_IR", "SAR"], 0.10),
    (["EO_IR", "SIGINT"], 0.10),
]

def _pick_sensors():
    r = random.random()
    cumulative = 0.0
    for sensors, prob in SENSOR_DIST:
        cumulative += prob
        if r < cumulative:
            return sensors
    return ["EO_IR"]
```

### Pattern 10: Theater YAML Wiring
**What:** `speed_kmh`, `threat_range_km`, `detection_range_km` are parsed but not consumed.
**Where:** Theater YAML `red_force.units[]` has per-unit `speed_kmh` and `threat_range_km`.

The fix is to wire these in `_build_target_pool()` and `Target.__init__`. The targets need a `speed_kmh` attribute read from the unit config, converted to `speed_deg_per_sec` at spawn. The threat ring radius in `targets.js` hardcodes `THREAT_RING_RADIUS = 5000` — this should come from the theater config.

### Anti-Patterns to Avoid
- **Creating Cesium Viewer in React state:** Viewer is not serializable, will cause render loop. Always use `useRef`.
- **Calling `viewer.entities.add` in render:** Must be in `useEffect`. Cesium mutations are side effects.
- **Selecting entire store in Cesium hooks:** `const state = useSimStore()` subscribes to every change. Always use field selectors.
- **Using resium:** Project decision is explicit — imperative hooks only. Resium wraps SampledPositionProperty poorly.
- **React StrictMode with Viewer:** StrictMode double-mounts cause Viewer to be created twice. Guard with `if (viewerRef.current) return` or disable StrictMode.
- **Sync file I/O in event logger:** Blocks the asyncio event loop during the 10Hz sim tick. Use queue pattern above.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sidebar resize drag | Custom ResizeObserver | `useResizable` hook using `mousedown/mousemove` (already in `sidebar.js`) | Simple enough to port — exact logic is 20 lines |
| Blueprint dark theme | Custom CSS variables | `bp5-dark` class on body | Blueprint handles all dark variants automatically |
| CesiumJS + Vite asset pipeline | Copying `Build/Cesium/` manually | `vite-plugin-cesium` | Plugin handles CESIUM_BASE_URL, worker copies, and WASM modules |
| WS reconnect logic | Exponential backoff library | setTimeout(connect, 1000) | The existing pattern works; simple 1s reconnect is sufficient |
| TypeScript strict null checks on Cesium | Type assertions everywhere | `viewer.isDestroyed()` guard before any Cesium call | Viewer can be destroyed between renders |

**Key insight:** The existing vanilla JS frontend is the reference implementation. Don't redesign — port the logic 1:1 into hooks, then wrap with React components. The Cesium entity management is battle-tested; preserve it exactly.

## Common Pitfalls

### Pitfall 1: React StrictMode Double Viewer
**What goes wrong:** In dev mode, `CesiumContainer` mounts twice. Two Viewers are created in the same DOM element. The second throws an error or produces a blank canvas.
**Why it happens:** React 18 StrictMode intentionally double-invokes effects in development.
**How to avoid:** Either (a) disable StrictMode in `main.tsx` (simplest), or (b) add `if (viewerRef.current) return;` as the first line of the Viewer creation effect.
**Warning signs:** Blank Cesium canvas in dev; works in production build.

### Pitfall 2: vite-plugin-cesium CESIUM_BASE_URL
**What goes wrong:** Cesium loads but workers fail; terrain or imagery tiles show errors in console.
**Why it happens:** CesiumJS requires static assets (workers, WASM) at a specific URL path. Without the plugin, these paths are wrong.
**How to avoid:** Confirm `cesium()` is listed in `plugins` array of `vite.config.ts` before `react()`. The existing `vite.config.ts` has this correct.
**Warning signs:** Console errors about `CESIUM_BASE_URL`, failed worker fetches, broken terrain.

### Pitfall 3: CesiumJS 1.114 vs older CSS import
**What goes wrong:** CSS import path for widgets fails at compile time.
**Why it happens:** Before 1.114, the import was `cesium/Build/Cesium/Widgets/widgets.css`. From 1.114+ it changed.
**How to avoid:** For CesiumJS 1.114 (project version), if explicit CSS import is needed: `import 'cesium/Build/Cesium/Widgets/widgets.css'`. However, vite-plugin-cesium handles this automatically — no manual import needed.
**Warning signs:** TypeScript or Vite build error on CSS import.

### Pitfall 4: Blueprint v5 CSS Order
**What goes wrong:** Blueprint styles partially applied; icons missing; dark theme not active.
**Why it happens:** Blueprint CSS must be imported before any custom CSS. Icons CSS must be imported separately.
**How to avoid:** In `main.tsx`, import order must be:
```typescript
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
// custom CSS after
```
**Warning signs:** Missing icons, wrong colors, `bp5-dark` class having no effect.

### Pitfall 5: Zustand Selector Re-Render at 10Hz
**What goes wrong:** The entire sidebar re-renders 10 times per second because components subscribe to the full UAV array.
**Why it happens:** `useSimStore(s => s.uavs)` triggers re-render on every tick even if the specific UAV a component cares about didn't change.
**How to avoid:** Use `useShallow` from Zustand for arrays, or select only the fields needed. For DroneCard, use `useSimStore(s => s.uavs.find(u => u.id === droneId))` per card.
**Warning signs:** DevTools profiler shows every panel re-rendering 10x/sec.

### Pitfall 6: GroundPrimitive Zone Recreation
**What goes wrong:** Zones flicker or performance degrades because the primitive is recreated every tick.
**Why it happens:** If `useCesiumZones` destroys and recreates the GroundPrimitive on every state update, it causes GPU pipeline thrash.
**How to avoid:** Mirror `map.js` pattern exactly: create the primitive ONCE (first call), then use `getGeometryInstanceAttributes(id)` + dirty-check (`_lastColor`) for updates. Store the primitive in a ref, not state.
**Warning signs:** Zone grid flickers; GPU memory climbs steadily.

### Pitfall 7: Canvas animationFrame in DroneCam
**What goes wrong:** `requestAnimationFrame` loop persists after component unmount; memory leak.
**Why it happens:** The `animFrame` reference is captured in closure; cleanup function doesn't cancel it.
**How to avoid:** Return cleanup in `useEffect` that calls `cancelAnimationFrame(animFrame.current)`. Use `useRef` for the frame ID.
**Warning signs:** Console warnings about setState on unmounted component; memory grows.

### Pitfall 8: sim_engine.py:509 Bug Assessment
**What goes wrong:** The STATE.md bug report says `("FOLLOW", "FOLLOW", "PAINT")` should be `("FOLLOW", "PAINT", "INTERCEPT")`.
**Current state:** The code at line 509 already reads `("FOLLOW", "PAINT", "INTERCEPT")` — this appears to have been fixed in commit `ce539b8` (mode rework). Verify before writing a "fix" task — the task should audit rather than blindly apply.
**Warning signs:** If a "fix" task changes already-correct code, it introduces a regression.

## Code Examples

Verified patterns from live codebase:

### Cesium Ion Token (from map.js)
```typescript
// The token is hardcoded in map.js line 2
// Move to environment variable or constants.ts
const CESIUM_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
// In production: use import.meta.env.VITE_CESIUM_TOKEN
```

### Blueprint Card Pattern (replaces drone-card div)
```typescript
import { Card, Elevation, Tag, Intent } from '@blueprintjs/core';

// Replaces _renderDroneCard() in dronelist.js
function DroneCard({ uav, isTracked }: { uav: UAV; isTracked: boolean }) {
  const modeIntent = {
    IDLE: Intent.PRIMARY,
    SEARCH: Intent.SUCCESS,
    FOLLOW: Intent.WARNING,
    PAINT: Intent.DANGER,
    INTERCEPT: 'none' as const,
  };

  return (
    <Card elevation={Elevation.TWO} interactive>
      <div className="drone-card-header">
        <span style={{ color: isTracked ? '#facc15' : undefined }}>
          UAV-{uav.id}
        </span>
        <Tag intent={modeIntent[uav.mode] ?? Intent.NONE}>
          {uav.mode}
        </Tag>
      </div>
    </Card>
  );
}
```

### WebSocket Actions (from websocket.js + dronelist.js)
```typescript
// All existing actions are plain JSON — no protocol changes needed
const WS_ACTIONS = {
  scanArea: (droneId: number) => ({ action: 'scan_area', drone_id: droneId }),
  followTarget: (droneId: number, targetId: number) =>
    ({ action: 'follow_target', drone_id: droneId, target_id: targetId }),
  paintTarget: (droneId: number, targetId: number) =>
    ({ action: 'paint_target', drone_id: droneId, target_id: targetId }),
  interceptTarget: (droneId: number, targetId: number) =>
    ({ action: 'intercept_target', drone_id: droneId, target_id: targetId }),
  approveNomination: (entryId: string) =>
    ({ action: 'approve_nomination', entry_id: entryId, rationale: 'Commander approved' }),
  rejectNomination: (entryId: string) =>
    ({ action: 'reject_nomination', entry_id: entryId, rationale: 'Commander rejected' }),
  authorizeCoa: (entryId: string, coaId: string) =>
    ({ action: 'authorize_coa', entry_id: entryId, coa_id: coaId, rationale: 'COA authorized' }),
};
```

### palantir.sh Update Pattern
```bash
# Replace: (cd src/frontend && python3 serve.py 3000) &
# With: (cd src/frontend-react && npm run dev -- --port 3000) &
# Or for production: (cd src/frontend-react && npm run build && npx serve dist -p 3000) &
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| webpack + CesiumJS | Vite + vite-plugin-cesium | 2022 | Zero-config setup |
| Redux for React state | Zustand | 2021+ | 10x less boilerplate |
| CesiumJS <1.114 extern declarations | CesiumJS 1.114+ no-extern | 2024 | Simpler Vite config |
| Blueprint v4 (migrate Popover) | Blueprint v5 | 2023 | v2 Select/Suggest now default |
| resium (declarative Cesium) | Imperative hooks | Project decision | Required for SampledPositionProperty |

**Deprecated/outdated:**
- `cesium/Build/Cesium/Widgets/widgets.css` import path: Use vite-plugin-cesium, which handles this.
- Blueprint `Popover` (v4): Use `Popover2` or v5-native Popover.
- `document.dispatchEvent` custom events: Replace with Zustand `setState` calls.
- `state.viewer` global: Replace with `viewerRef` passed through hook props.
- `window._uavEntities` global: Replace with `entitiesRef.current` inside hook.

## Open Questions

1. **Cesium Ion token exposure**
   - What we know: The token is hardcoded in `map.js` line 2, readable in browser source
   - What's unclear: Whether the project intends to keep it hardcoded or move to an env var
   - Recommendation: Move to `import.meta.env.VITE_CESIUM_TOKEN` in `constants.ts`; add to `.env` file

2. **sim_engine.py:509 bug status**
   - What we know: Current code at line 509 already has `("FOLLOW", "PAINT", "INTERCEPT")` — the correct tuple
   - What's unclear: Whether STATE.md is stale or there's a different occurrence
   - Recommendation: Planner should add an audit task, not a blind-fix task; grep for all tuples containing these modes before writing the fix

3. **React.StrictMode decision**
   - What we know: StrictMode causes double-mount which corrupts Viewer creation without a guard
   - What's unclear: Whether the team wants StrictMode for its benefits (catches side effects)
   - Recommendation: Disable StrictMode in `main.tsx` for this project; the Cesium imperative pattern is fundamentally side-effect-based

4. **palantir.sh Vite dev vs prod**
   - What we know: Vite dev server supports HMR but requires Node.js; the existing `serve.py` is a simple Python static server
   - What's unclear: Whether CI/production should use `vite build` + static serve or always run dev server
   - Recommendation: Update `palantir.sh` to use `npm run dev` for local development; add a `--prod` flag for built output

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, no config file — conftest.py adds sys.path) |
| Config file | `src/python/tests/conftest.py` (sys.path setup only) |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_event_logger.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |
| Frontend tests | None currently — Playwright setup is a Wave 0 gap |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P0-BUG | sim_engine mode exclusion audit | unit | `pytest src/python/tests/test_sim_integration.py -x` | ✅ |
| P0-LOG | JSONL event logger writes events | unit | `pytest src/python/tests/test_event_logger.py -x` | ❌ Wave 0 |
| P0-SENSOR | UAV multi-sensor spawn distribution | unit | `pytest src/python/tests/test_sensor_spawn.py -x` | ❌ Wave 0 |
| P0-THEATER | Theater YAML speed/range wiring | unit | `pytest src/python/tests/test_theater_loader.py -x` | ✅ (partial) |
| P0-UI | React app renders in browser | smoke | Manual / Playwright | ❌ Wave 0 |
| P0-WS | WebSocket state payload received by React | integration | Manual / Playwright | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** All Python tests green + manual smoke test of Vite dev server before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_event_logger.py` — covers P0-LOG (JSONL append, queue drain, daily rotation)
- [ ] `src/python/tests/test_sensor_spawn.py` — covers P0-SENSOR (distribution probabilities, list[str] field)
- [ ] `src/frontend-react/playwright.config.ts` — E2E framework for smoke tests (optional — mark manual if omitted)
- [ ] `src/frontend-react/src/main.tsx` — entry point needed before any tests can run

## Sources

### Primary (HIGH confidence)
- npm registry live query — all package versions verified 2026-03-19
- `src/frontend-react/package.json` — confirmed dependency versions
- `src/frontend-react/vite.config.ts` — confirmed plugin configuration
- `src/frontend/map.js`, `drones.js`, `targets.js`, `websocket.js`, `state.js` — source-of-truth for port
- `src/python/sim_engine.py` — line 509 bug status verified in codebase
- `theaters/romania.yaml` — confirmed theater YAML structure and unused fields
- `palantir.sh` — confirmed how frontend is launched today

### Secondary (MEDIUM confidence)
- [Cesium blog: Configuring Vite or Webpack for CesiumJS](https://cesium.com/blog/2024/02/13/configuring-vite-or-webpack-for-cesiumjs/) — CesiumJS 1.114 extern notes verified
- [vite-plugin-cesium README](https://github.com/nshen/vite-plugin-cesium/blob/main/README.md) — minimal config confirmed
- [Blueprint docs](https://blueprintjs.com/docs/) — CSS import order and FocusStyleManager API
- [Zustand GitHub](https://github.com/pmndrs/zustand) — useSyncExternalStore, v4 vs v5 API

### Tertiary (LOW confidence)
- WebSearch: Blueprint v5 dark theme Vite gotchas — no authoritative source found, inferred from official Blueprint docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against npm registry
- Architecture: HIGH — patterns derived directly from existing codebase analysis
- Pitfalls: HIGH for Cesium/React (well-documented community issue); MEDIUM for Blueprint CSS ordering
- Bug status (line 509): HIGH — directly read the file

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable libraries — 30 days)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P0-BUILD | Initialize Vite + React + TypeScript at `src/frontend-react/` with vite-plugin-cesium | Scaffold already exists; vite.config.ts and package.json confirmed correct |
| P0-STORE | Zustand SimulationStore with all sim state and UI state | Pattern 1 documents full store shape; types derived from websocket.js and api_main.py |
| P0-WS | useWebSocket hook — single WS connection dispatching to Zustand | Pattern 2 is a direct port of websocket.js |
| P0-CESIUM | CesiumContainer + Cesium hooks (drones, targets, zones, flows, compass) | Patterns 3+4 document Viewer lifecycle and entity hook pattern |
| P0-SIDEBAR | Blueprint Tabs (MISSION/ASSETS/ENEMIES) with resizer | Pattern 5 covers dark theme; sidebar.js resizer maps to useResizable hook |
| P0-PANELS | DroneCard, EnemyCard, StrikeBoard components in Blueprint | Pattern with Blueprint Card, Tag, ProgressBar documented |
| P0-DRONECAM | Canvas PIP with requestAnimationFrame hook | Pitfall 7 documents cleanup pattern; dronecam.js is source reference |
| P0-ASSISTANT | AI assistant message log panel | assistant.js maps directly to a scrolling Blueprint log panel |
| P0-BUG | Audit and fix sim_engine.py line 509 mode exclusion tuple | Bug may already be fixed — audit task documented in Open Questions |
| P0-THEATER | Wire theater YAML speed_kmh, threat_range_km into sim | Pattern 10 documents spawn-time wiring approach |
| P0-LOG | JSONL event logger (event_logger.py) | Pattern 8 documents asyncio queue + background writer pattern |
| P0-SENSORS | Multi-sensor UAV spawn (sensors: list[str]) | Pattern 9 documents weighted random distribution |
| P0-ECHARTS | ECharts install + base palantir dark theme stub | Package already in package.json; theme/palantir.ts is an empty stub |
| P0-LAUNCHER | Update palantir.sh to use Vite dev server | Open Question 4 covers the shell script change |
</phase_requirements>
