# Phase 7: Battlespace Assessment - Research

**Researched:** 2026-03-20
**Domain:** Python spatial clustering + FastAPI integration + Cesium geospatial overlays + Blueprint/ECharts React UI
**Confidence:** HIGH

## Summary

Phase 7 adds a live Common Operating Picture layer to Grid-Sentinel: a `BattlespaceAssessor` class runs every 5 seconds, produces clusters of threats (SAM_BATTERY, CONVOY, CP_COMPLEX, AD_NETWORK), identifies coverage gaps, scores zone threats, and detects movement corridors. Results flow through the existing WebSocket state broadcast to new React components: a sidebar `AssessmentTab`, `ThreatClusterCard`, `CoverageGapAlert`, an ECharts zone heatmap, and Cesium overlays (convex hull polygons, SAM engagement envelopes, movement corridor polylines).

The project has mature patterns for all required pieces: `sensor_fusion.py` and `verification_engine.py` demonstrate pure-function design with frozen dataclasses; `useCesiumZones.ts` shows the Cesium Primitives approach for polygon overlays; `FusionBar.tsx` shows the ECharts-for-React pattern. No new third-party libraries are required — the existing stack (Python stdlib, Cesium 1.114, Blueprint 5, ECharts 5.5, echarts-for-react 3.0.2) covers everything.

The one gap is that `Target` objects have no position history, which movement corridor detection requires. This needs a bounded deque (~60 entries at 10Hz = ~6s of history) added to `Target.__init__` and updated on each tick. The `get_state()` method does NOT need to serialize the full history — the assessor reads it directly from `sim.targets`.

**Primary recommendation:** Implement `BattlespaceAssessor` as a pure-function module with frozen result dataclasses (matching the sensor_fusion.py pattern), wire it into `api_main.py`'s `simulation_loop` on a 5-second interval, and extend the `get_state()` payload with an `assessment` key.

## Standard Stack

### Core (all already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `math`, `collections.deque` | 3.9+ | Haversine distance, position history ring buffer | No dep, correct tool |
| `dataclasses` (frozen) | 3.9+ | Immutable result types for assessor output | Consistent with sensor_fusion.py pattern |
| `structlog` | in venv | Logging | Project standard |
| `Cesium` | 1.114.0 | Convex hull polygons, SAM rings, corridor polylines | Already in frontend |
| `echarts` + `echarts-for-react` | 5.5.0 / 3.0.2 | Zone threat heatmap | Already in project (FusionBar pattern) |
| `@blueprintjs/core` | 5.13.0 | Card, Tag, Intent, Icon components for sidebar tab | Project UI standard |
| `zustand` | 4.5.0 | Store extension for assessment state | Locked at 4.5.0 (Decisions Log) |

### No New Dependencies
All clustering, gap detection, and corridor analysis can be done with pure Python math. Do not add sklearn/scipy — these add large dependencies and Python 3.9 compatibility concerns, and the DBSCAN-like algorithm described is a straightforward greedy clustering that doesn't need a full ML library.

## Architecture Patterns

### Recommended Module Structure
```
src/python/
├── battlespace_assessment.py   # NEW: BattlespaceAssessor pure-function class
├── sim_engine.py               # MODIFY: add position_history deque to Target
├── api_main.py                 # MODIFY: wire assessor into simulation_loop

src/frontend-react/src/
├── store/
│   └── SimulationStore.ts      # MODIFY: add assessment field + setSimData extension
│   └── types.ts                # MODIFY: add AssessmentResult, ThreatCluster, CoverageGap types
├── panels/
│   └── assessment/
│       ├── AssessmentTab.tsx       # NEW
│       ├── ThreatClusterCard.tsx   # NEW
│       └── CoverageGapAlert.tsx    # NEW
└── cesium/
    └── assessmentOverlays.ts   # NEW: convex hull, SAM rings, corridors

src/python/tests/
└── test_battlespace.py         # NEW: ~120 lines
```

### Pattern 1: Pure-Function Assessor with Frozen Dataclasses
**What:** `BattlespaceAssessor` takes a snapshot of target/UAV state and returns immutable result objects — no instance state mutation between calls.
**When to use:** Always — consistent with `sensor_fusion.py` and `verification_engine.py`.
**Example:**
```python
# Mirrors sensor_fusion.py pattern
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class ThreatCluster:
    cluster_id: str
    cluster_type: str  # SAM_BATTERY | CONVOY | CP_COMPLEX | AD_NETWORK
    member_target_ids: tuple[int, ...]
    centroid_lon: float
    centroid_lat: float
    threat_score: float
    hull_points: tuple[tuple[float, float], ...]  # (lon, lat) pairs

@dataclass(frozen=True)
class CoverageGap:
    zone_x: int
    zone_y: int
    lon: float
    lat: float

@dataclass(frozen=True)
class MovementCorridor:
    target_id: int
    waypoints: tuple[tuple[float, float], ...]  # recent (lon, lat) positions

@dataclass(frozen=True)
class AssessmentResult:
    clusters: tuple[ThreatCluster, ...]
    coverage_gaps: tuple[CoverageGap, ...]
    zone_threat_scores: dict[tuple[int, int], float]  # (x, y) -> score 0-1
    movement_corridors: tuple[MovementCorridor, ...]
    assessed_at: float  # time.time()
```

### Pattern 2: DBSCAN-Like Greedy Clustering Without scipy
**What:** Group targets into clusters using a distance threshold + type affinity. No external library needed.
**When to use:** `_cluster_targets()`.
**Example:**
```python
# Distance threshold for clustering: ~15km in degrees
CLUSTER_RADIUS_DEG = 0.135  # 15km / 111km per degree

# Type affinity groups — targets in same group cluster preferentially
CLUSTER_AFFINITY = {
    "SAM": "AD_NETWORK",
    "RADAR": "AD_NETWORK",
    "MANPADS": "AD_NETWORK",
    "TEL": "SAM_BATTERY",
    "CP": "CP_COMPLEX",
    "C2_NODE": "CP_COMPLEX",
    "TRUCK": "CONVOY",
    "LOGISTICS": "CONVOY",
    "APC": "CONVOY",
    "ARTILLERY": "CONVOY",
}

def _cluster_targets(targets: list) -> list[ThreatCluster]:
    # Only cluster detected targets
    detected = [t for t in targets if t['state'] != 'UNDETECTED']
    visited = set()
    clusters = []

    for t in detected:
        if t['id'] in visited:
            continue
        # Collect neighbors within radius
        neighbors = [
            other for other in detected
            if other['id'] not in visited
            and math.hypot(other['lon'] - t['lon'], other['lat'] - t['lat']) < CLUSTER_RADIUS_DEG
        ]
        if len(neighbors) >= 2:
            ids = tuple(n['id'] for n in neighbors)
            visited.update(ids)
            centroid_lon = sum(n['lon'] for n in neighbors) / len(neighbors)
            centroid_lat = sum(n['lat'] for n in neighbors) / len(neighbors)
            # Determine cluster type by majority affinity
            affinity_votes = [CLUSTER_AFFINITY.get(n['type'], 'MIXED') for n in neighbors]
            cluster_type = max(set(affinity_votes), key=affinity_votes.count)
            threat_score = sum(n.get('fused_confidence', 0.0) for n in neighbors) / len(neighbors)
            hull = _compute_convex_hull([(n['lon'], n['lat']) for n in neighbors])
            clusters.append(ThreatCluster(
                cluster_id=f"CLU-{len(clusters)+1}",
                cluster_type=cluster_type,
                member_target_ids=ids,
                centroid_lon=centroid_lon,
                centroid_lat=centroid_lat,
                threat_score=threat_score,
                hull_points=hull,
            ))
    return clusters
```

### Pattern 3: Convex Hull — Pure Python (Gift Wrapping)
**What:** Compute convex hull for cluster polygon display without scipy.
**When to use:** `_compute_convex_hull()` called by `_cluster_targets()`.
**Example:**
```python
def _compute_convex_hull(points: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Gift-wrapping (Jarvis march). O(nh), fine for small clusters (<20 pts)."""
    if len(points) <= 2:
        return tuple(points)
    # Find leftmost point
    start = min(points, key=lambda p: (p[0], p[1]))
    hull = [start]
    current = start
    while True:
        candidate = points[0]
        for p in points[1:]:
            if p == current:
                continue
            cross = (candidate[0] - current[0]) * (p[1] - current[1]) \
                  - (candidate[1] - current[1]) * (p[0] - current[0])
            if cross < 0 or (cross == 0 and
                math.hypot(p[0]-current[0], p[1]-current[1]) >
                math.hypot(candidate[0]-current[0], candidate[1]-current[1])):
                candidate = p
        if candidate == hull[0]:
            break
        hull.append(candidate)
        current = candidate
        if len(hull) > len(points):
            break  # safety valve
    return tuple(hull)
```

### Pattern 4: Position History on Target (sim_engine.py modification)
**What:** Add a bounded deque to `Target.__init__` for movement corridor detection.
**When to use:** In `Target.__init__`, update in `Target.update()`.
**Key constraint:** The history must NOT be serialized in `get_state()` — only the assessor reads it directly from `sim.targets`. This prevents 10Hz payload bloat.
```python
# In Target.__init__:
from collections import deque
self.position_history: deque = deque(maxlen=60)  # ~6s at 10Hz

# In Target.update() — append after position resolves:
self.position_history.append((self.x, self.y))
```

### Pattern 5: 5-Second Assessment Timer in simulation_loop
**What:** Track elapsed time in `simulation_loop`, call assessor every 5 seconds, attach result to state payload.
**Example:**
```python
# In api_main.py simulation_loop():
_last_assessment_time = 0.0
_cached_assessment = None

async def simulation_loop():
    nonlocal _last_assessment_time, _cached_assessment
    tick_interval = 1.0 / settings.simulation_hz
    while True:
        sim.tick()
        now = time.monotonic()
        if now - _last_assessment_time >= 5.0:
            _cached_assessment = assessor.assess(sim.targets, sim.uavs, sim.grid)
            _last_assessment_time = now

        if clients:
            state = sim.get_state()
            state["strike_board"] = hitl.get_strike_board()
            state["demo_mode"] = settings.demo_mode
            if _cached_assessment:
                state["assessment"] = _serialize_assessment(_cached_assessment)
            # ...
```

### Pattern 6: Coverage Gap Detection
**What:** Zones with no UAV assigned AND at least one detected target nearby are gaps.
**When to use:** `_identify_coverage_gaps()`.
```python
def _identify_coverage_gaps(zones: list, uavs: list) -> list[CoverageGap]:
    """A zone is a gap if it has no UAV present (uav_count == 0) AND
    is not currently covered by any UAV in SEARCH/OVERWATCH."""
    covered_zones = {(u['zone_x'], u['zone_y']) for u in uavs
                     if u.get('mode') in ('SEARCH', 'OVERWATCH', 'REPOSITIONING')}
    return [
        CoverageGap(zone_x=z['x_idx'], zone_y=z['y_idx'], lon=z['lon'], lat=z['lat'])
        for z in zones
        if (z['x_idx'], z['y_idx']) not in covered_zones and z.get('uav_count', 0) == 0
    ]
```
**Note:** Zones come from `sim.get_state()["zones"]` which already has `x_idx, y_idx, lon, lat, uav_count`. The assessor gets zones via the same dict structure.

### Pattern 7: Zone Threat Scoring
**What:** Aggregate fused confidence of detected targets per grid zone.
```python
def _score_zone_threats(zones: list, targets: list) -> dict[tuple[int, int], float]:
    # Map zone bounds: each zone has lon/lat center + width/height
    # Assign each detected target to nearest zone, sum confidence
    scores: dict[tuple[int, int], float] = {}
    for t in targets:
        if t['state'] == 'UNDETECTED':
            continue
        # Find zone containing target (nearest center)
        best_zone = min(zones, key=lambda z:
            math.hypot(z['lon'] - t['lon'], z['lat'] - t['lat']))
        key = (best_zone['x_idx'], best_zone['y_idx'])
        scores[key] = min(1.0, scores.get(key, 0.0) + t.get('fused_confidence', 0.0))
    return scores
```

### Pattern 8: Cesium EllipseGeometry for SAM Engagement Envelopes
**What:** SAM rings on Cesium using `EllipseGeometry` (same as range rings pattern in `useCesiumRangeRings.ts`).
**When to use:** In `assessmentOverlays.ts` — render `threat_range_km` circles for SAM/RADAR/MANPADS targets.
```typescript
// Mirror of useCesiumRangeRings.ts pattern
const semiMajorAxis = threat_range_km * 1000; // meters
viewer.entities.add({
  position: Cesium.Cartesian3.fromDegrees(lon, lat),
  ellipse: {
    semiMajorAxis: semiMajorAxis,
    semiMinorAxis: semiMajorAxis,
    material: Cesium.Color.RED.withAlpha(0.15),
    outline: true,
    outlineColor: Cesium.Color.RED.withAlpha(0.8),
    outlineWidth: 1.5,
    height: 0,
  },
});
```

### Pattern 9: Cesium PolygonHierarchy for Convex Hull Overlays
**What:** Cluster hull polygons rendered as Cesium ground polygons (same pattern as `useCesiumZones.ts`).
```typescript
// hull_points: Array<[lon, lat]> from assessment payload
const positions = Cesium.Cartesian3.fromDegreesArray(
  hull_points.flatMap(([lon, lat]) => [lon, lat])
);
viewer.entities.add({
  polygon: {
    hierarchy: new Cesium.PolygonHierarchy(positions),
    material: clusterColor.withAlpha(0.2),
    outline: true,
    outlineColor: clusterColor,
    height: 0,
  },
});
```

### Pattern 10: ECharts Heatmap for Zone Threat Scores
**What:** `visualMap` + `heatmap` series on a virtual grid. Use `ReactECharts` (already used in `FusionBar.tsx`) with the `grid_sentinel` theme.
**Key:** ECharts heatmap data format is `[x_idx, y_idx, value]` array. For a 50x50 grid this is 2500 data points — fine for canvas renderer.
```typescript
// Source: ECharts docs — heatmap series, ReactECharts pattern from FusionBar.tsx
const option = {
  animation: false,
  tooltip: { position: 'top' },
  visualMap: {
    min: 0, max: 1,
    calculable: true,
    inRange: { color: ['#313695', '#4575b4', '#d73027', '#a50026'] },
  },
  xAxis: { type: 'category', data: Array.from({length: cols}, (_, i) => i), show: false },
  yAxis: { type: 'category', data: Array.from({length: rows}, (_, i) => i), show: false },
  series: [{
    type: 'heatmap',
    data: zone_threat_scores,  // [[x_idx, y_idx, score], ...]
    emphasis: { itemStyle: { shadowBlur: 10 } },
  }],
};
```

### Pattern 11: SidebarTabs Extension
**What:** Add a new "ASSESS" tab alongside MISSION/ASSETS/ENEMIES.
**When to use:** Modify `SidebarTabs.tsx`.
**Key constraint from existing code:** The `useEffect` in `SidebarTabs` applies imperative styles to `.bp5-tabs` and `[role="tabpanel"]`. The new tab panel must follow the same div-based layout pattern as `MissionTab`, `AssetsTab`, `EnemiesTab`.
```typescript
// In SidebarTabs.tsx — add alongside existing Tab elements:
import { AssessmentTab } from './assessment/AssessmentTab';
// ...
<Tab id="assess" title="ASSESS" panel={<AssessmentTab />} />
```

### Pattern 12: Store Extension for Assessment Data
**What:** Add `assessment` field to `SimState` and handle it in `setSimData`.
**Key constraint:** Zustand v4 `create()` pattern is locked — do NOT use `createStore` (v5).
```typescript
// In types.ts — new types
export interface ThreatCluster {
  cluster_id: string;
  cluster_type: 'SAM_BATTERY' | 'CONVOY' | 'CP_COMPLEX' | 'AD_NETWORK' | 'MIXED';
  member_target_ids: number[];
  centroid_lon: number;
  centroid_lat: number;
  threat_score: number;
  hull_points: [number, number][];
}

export interface CoverageGap {
  zone_x: number;
  zone_y: number;
  lon: number;
  lat: number;
}

export interface MovementCorridor {
  target_id: number;
  waypoints: [number, number][];
}

export interface AssessmentPayload {
  clusters: ThreatCluster[];
  coverage_gaps: CoverageGap[];
  zone_threat_scores: [number, number, number][];  // [x, y, score]
  movement_corridors: MovementCorridor[];
}
```

### Anti-Patterns to Avoid

- **Serializing position_history in get_state():** This would add up to 60 positions per target per 10Hz tick — massive payload bloat. The assessor reads history directly from `sim.targets`.
- **Using scipy/sklearn for DBSCAN:** Unnecessary dependency. Target counts are small (<50 in current theaters). The greedy greedy approach is sufficient and testable.
- **Running the assessor every tick:** Assessment at 10Hz is wasted computation. 5-second interval is correct per FR-6.
- **Entity-per-cluster on Cesium (not primitives):** For hull overlays, simple `viewer.entities.add()` with `polygon` is acceptable since clusters update at 5s intervals (not 10Hz). Primitives are only needed for high-frequency updates (see zone grid pattern).
- **Mutating ThreatCluster/AssessmentResult objects:** All result types are frozen dataclasses — the same immutability rule as `SensorContribution` and `FusedDetection`.
- **Hardcoding cluster_radius:** Extract to a module-level constant `CLUSTER_RADIUS_DEG` so it is configurable in tests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Convex hull | Full polygon clipping library | Gift-wrapping (Jarvis march) in 20 lines | Cluster sizes are < 20 points; O(nh) is fine |
| Heatmap visualization | Custom canvas drawing | ECharts heatmap series via ReactECharts | Already in project, Grid-Sentinel theme registered |
| SAM engagement rings | Custom circle math | Cesium `EllipseGeometry` / `entity.ellipse` | Project already has range rings (useCesiumRangeRings.ts) |
| Distance calculation | Custom formula | `math.hypot()` in degree space (or haversine for accuracy) | `geo_utils.haversine_distance` already exists in project |
| State management | Custom event system | Zustand store extension | Pattern established for all prior phases |

**Key insight:** Every geometric primitive needed here (circles, polygons, polylines) already has a Cesium implementation in the project. Pattern-match against existing cesium hooks, don't invent new rendering approaches.

## Common Pitfalls

### Pitfall 1: Position History Deque Not Bounded
**What goes wrong:** Unbounded position history grows memory linearly with simulation time — ~10 entries/sec × N targets × run duration.
**Why it happens:** `deque()` without `maxlen` is unbounded.
**How to avoid:** Always `deque(maxlen=60)` — 60 positions at 10Hz = 6 seconds of corridor data. Keep the `maxlen` as a named constant: `POSITION_HISTORY_MAXLEN = 60`.
**Warning signs:** Memory growth under long-running demo mode.

### Pitfall 2: Assessment Serialization — dict vs frozen dataclass
**What goes wrong:** `json.dumps(assessment_result)` fails because frozen dataclasses are not JSON-serializable.
**Why it happens:** `dataclass(frozen=True)` does not implement `__json__`.
**How to avoid:** Write a `_serialize_assessment(result: AssessmentResult) -> dict` function in `api_main.py` that explicitly converts the result to a plain dict. This matches the pattern used for `sim.get_state()` which manually builds dicts from `Target` objects.

### Pitfall 3: Cluster ID Stability Between Assessments
**What goes wrong:** Frontend renders cluster cards with `key={cluster.cluster_id}` but IDs change every 5 seconds, causing React to re-mount all cards.
**Why it happens:** Sequential IDs like `CLU-1`, `CLU-2` are assigned by iteration order, which may vary.
**How to avoid:** Derive cluster ID from a stable property — e.g. `CLU-{centroid_lon:.2f}-{centroid_lat:.2f}` or sorted member target IDs: `CLU-{'-'.join(sorted(str(id) for id in member_ids))}`.

### Pitfall 4: Assessor Runs on Empty State at Startup
**What goes wrong:** Assessor called before any targets are detected; empty lists cause division-by-zero or degenerate hull calculations.
**Why it happens:** `simulation_loop` starts immediately; first 5-second interval fires before any detections.
**How to avoid:** Guard all inner functions: `if not detected: return []`. Convex hull function must handle 0, 1, 2 point edge cases explicitly (return empty tuple or the points themselves).

### Pitfall 5: Zone Lookup is O(n_targets × n_zones)
**What goes wrong:** With a 50x50 grid (2500 zones) and 30+ targets, the `min(zones, ...)` approach in `_score_zone_threats` does 75,000 comparisons every 5 seconds.
**Why it happens:** Naive nearest-zone lookup.
**How to avoid:** Pre-compute a zone lookup by converting lon/lat to grid indices using the theater bounds and grid dimensions. `x_idx = int((lon - min_lon) / (max_lon - min_lon) * cols)`. This makes zone assignment O(1) per target.

### Pitfall 6: ECharts Heatmap Data Format
**What goes wrong:** Passing `{x: 0, y: 0, value: 0.5}` instead of `[0, 0, 0.5]` — ECharts heatmap expects array format.
**Why it happens:** Confusion with scatter series which accepts object format.
**How to avoid:** Always use `[x_idx, y_idx, score]` triples. The serializer in `api_main.py` should produce this format directly.

### Pitfall 7: assessmentOverlays.ts — Entity Accumulation
**What goes wrong:** Each 5-second assessment adds new Cesium entities without removing old ones, causing geometric accumulation on the globe.
**Why it happens:** Cesium entities are persistent until explicitly removed.
**How to avoid:** Use an `EntityCollection` ref or track added entity refs: store them in a `useRef<Cesium.Entity[]>` array, remove all on each update before adding new ones. Mirror the pattern from `useCesiumFlowLines.ts` which uses a `datasourceRef`.

## Code Examples

Verified patterns from existing project source:

### Frozen Dataclass Pattern (from sensor_fusion.py)
```python
# Source: src/python/sensor_fusion.py
@dataclass(frozen=True)
class FusedDetection:
    fused_confidence: float
    sensor_count: int
    sensor_types: tuple[str, ...]
    contributing_uav_ids: tuple[int, ...]
    contributions: tuple[SensorContribution, ...]
```

### Pure Function Pattern (from sensor_fusion.py)
```python
# Source: src/python/sensor_fusion.py
def fuse_detections(contributions: Sequence[SensorContribution]) -> FusedDetection:
    if not contributions:
        return FusedDetection(...)  # safe empty return
    # pure computation, no mutation
    return FusedDetection(...)
```

### ECharts ReactECharts Pattern (from FusionBar.tsx)
```typescript
// Source: src/frontend-react/src/panels/enemies/FusionBar.tsx
import ReactECharts from 'echarts-for-react';
// ...
<ReactECharts
  option={option}
  style={{ height: 200, width: '100%' }}
  opts={{ renderer: 'canvas' }}
  notMerge={false}
/>
```

### Cesium PolygonHierarchy Pattern (from useCesiumZones.ts)
```typescript
// Source: src/frontend-react/src/cesium/useCesiumZones.ts
const hierarchy = new Cesium.PolygonHierarchy(
  Cesium.Cartesian3.fromDegreesArray([...p1, ...p2, ...p3, ...p4])
);
new Cesium.GeometryInstance({
  geometry: new Cesium.PolygonGeometry({
    polygonHierarchy: hierarchy,
    height: 0,
  }),
});
```

### Cesium Entity Cleanup Pattern (from useCesiumFlowLines.ts)
```typescript
// Source: src/frontend-react/src/cesium/useCesiumFlowLines.ts
// Track entities in a ref, remove before re-adding
const entityRefs = useRef<Cesium.Entity[]>([]);
// On update:
entityRefs.current.forEach(e => viewer.entities.remove(e));
entityRefs.current = [];
// Then add new entities and push to entityRefs.current
```

### Zustand setSimData Extension Pattern (from SimulationStore.ts)
```typescript
// Source: src/frontend-react/src/store/SimulationStore.ts
setSimData: (data) => {
  // ...
  set({ uavs: data.uavs, targets: data.targets /* ... */ });
  if (data.autonomy_level) {
    set({ autonomyLevel: data.autonomy_level });
  }
  // Phase 7 extension follows same pattern:
  if (data.assessment) {
    set({ assessment: data.assessment });
  }
}
```

### Existing haversine_distance (from utils/geo_utils.py)
The project already has `haversine_distance(a: Coordinate, b: Coordinate) -> float` in `src/python/utils/geo_utils.py`. The assessor can use `math.hypot()` in degree space for performance (small-area approximation is fine for cluster detection at <30km scales), or call `haversine_distance` for the SAM envelope radius comparisons where accuracy matters.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM-driven battlespace manager (battlespace_manager.py) | Rule-based pure-function assessor | Phase 7 | Reliable, testable, no API key required |
| No position history on Target | Bounded deque (maxlen=60) on Target | Phase 7 | Enables corridor detection without bloating state |
| No assessment in WS payload | `assessment` key added to state broadcast | Phase 7 | Frontend gets live COP data at 5s intervals |

**Dormant activation:** `battlespace_manager.py` currently has an LLM-based `generate_mission_path()` that raises `NotImplementedError`. Phase 7 activates the threat ring generation side of this agent (reading `threat_range_km` from verified SAM/RADAR targets) without requiring the LLM — the `update_threat_rings()` and `get_active_layers()` methods already work. The assessor calls `battlespace_manager.update_threat_rings()` each cycle with computed rings from verified SAM/RADAR targets.

## Open Questions

1. **Enemy UAV phase dependency**
   - What we know: Phase 4 (Enemy UAVs) is planned but not yet executed. Phase 7 should not depend on it.
   - What's unclear: Should clusters include enemy UAVs if Phase 4 is done by the time Phase 7 runs?
   - Recommendation: Assess only `sim.targets` (red ground units). Enemy UAVs are in `sim.enemy_uavs` — ignore for now, can be added in Phase 8 (Adaptive ISR).

2. **Zone grid access in assessor**
   - What we know: `sim.get_state()["zones"]` returns zone dicts with `x_idx, y_idx, uav_count`. The assessor needs to run before `get_state()` is called.
   - What's unclear: Should the assessor take raw zone dicts or `Zone` objects from `sim.grid.zones`?
   - Recommendation: Pass `sim.get_state()["zones"]` (already computed dict list) into the assessor. This avoids coupling the assessor to `RomaniaMacroGrid` internals and keeps it testable with plain dicts.

3. **Movement corridor minimum history length**
   - What we know: `Target.position_history` will be empty at startup. Stationary targets (SAM, CP, C2_NODE) will have trivial corridors.
   - Recommendation: Only emit a corridor if `len(position_history) >= 10` AND the target has moved more than `0.005` degrees total. This filters out stationary targets and prevents noise corridors at startup.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | none — conftest.py adds src/python to sys.path |
| Quick run command | `./venv/bin/python3 -m pytest src/python/tests/test_battlespace.py -x` |
| Full suite command | `./venv/bin/python3 -m pytest src/python/tests/` |

### Phase Requirements -> Test Map
| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| FR-6.1 | Threat clustering produces correct cluster types | unit | `pytest tests/test_battlespace.py::TestClustering -x` | Wave 0 |
| FR-6.2 | Coverage gap identifies zones with no UAV | unit | `pytest tests/test_battlespace.py::TestCoverageGaps -x` | Wave 0 |
| FR-6.3 | Zone threat scoring aggregates per grid cell | unit | `pytest tests/test_battlespace.py::TestZoneThreatScoring -x` | Wave 0 |
| FR-6.4 | Movement corridor detection from position history | unit | `pytest tests/test_battlespace.py::TestMovementCorridors -x` | Wave 0 |
| FR-6.5 | 5s assessment interval wired into simulation_loop | integration | `pytest tests/test_sim_integration.py -x -k assessment` | Wave 0 |
| FR-6.6 | Empty state returns safe empty result (no exceptions) | unit | `pytest tests/test_battlespace.py::TestEdgeCases -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `./venv/bin/python3 -m pytest src/python/tests/test_battlespace.py -x`
- **Per wave merge:** `./venv/bin/python3 -m pytest src/python/tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/python/tests/test_battlespace.py` — covers FR-6.1 through FR-6.6 (new module, no existing tests)
- [ ] `test_sim_integration.py` needs an assessment-wire test added (existing file, add test)

## Sources

### Primary (HIGH confidence)
- Project source code (`src/python/sensor_fusion.py`) — frozen dataclass + pure function patterns
- Project source code (`src/python/sim_engine.py`) — Target class structure, position fields, get_state() format
- Project source code (`src/frontend-react/src/cesium/useCesiumZones.ts`) — PolygonHierarchy, GroundPrimitive pattern
- Project source code (`src/frontend-react/src/panels/enemies/FusionBar.tsx`) — ReactECharts usage pattern
- Project source code (`src/frontend-react/src/store/SimulationStore.ts`) — Zustand 4.5 pattern, setSimData extension model
- Project source code (`src/frontend-react/src/store/types.ts`) — existing TypeScript type contracts
- `theaters/romania.yaml` — `threat_range_km` field existence and values confirmed
- `src/python/theater_loader.py` — `RedUnit.threat_range_km` field confirmed parseable

### Secondary (MEDIUM confidence)
- ECharts 5 heatmap documentation — `[x, y, value]` array format for heatmap series data
- Cesium 1.114 entity ellipse API — `semiMajorAxis` in meters for circular engagement rings

### Tertiary (LOW confidence)
- Jarvis march gift-wrapping algorithm — standard CS algorithm, implementation from first principles

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, versions confirmed from package.json
- Architecture: HIGH — all patterns derived from existing project source code
- Pitfalls: HIGH — identified from direct reading of existing codebase patterns and constraints
- Cesium overlay patterns: HIGH — derived from useCesiumZones.ts and useCesiumFlowLines.ts
- ECharts heatmap format: MEDIUM — derived from FusionBar pattern + ECharts docs format knowledge

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable stack; Cesium/Blueprint/ECharts are not fast-moving for this use)
