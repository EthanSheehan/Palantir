# Palantir Swarm Upgrade — Roadmap

## Phase Overview

```
Phase 0: Foundation & React Migration     [BUILD TOOLING + UI FRAMEWORK]
    ↓ DEMO: Blueprint UI renders existing functionality
Phase 1: Multi-Sensor Target Fusion       [FOUNDATION — sensor data model]
    ↓ DEMO: Fused confidence visible, multi-sensor rings
Phase 2: Target Verification Workflow     [TARGET STATES — kill chain gate]
    ↓ DEMO: DETECTED→CLASSIFIED→VERIFIED stepper
Phase 3: Drone Modes & Autonomy           [HUMAN/AUTO — 3-tier control]
    ↓ DEMO: SUPPORT/VERIFY/OVERWATCH/BDA modes + autonomy toggle
Phase 4: Enemy UAVs                       [ADVERSARY AIR — threat drones in sim]
    ↓ DEMO: Enemy UAVs on map, detection, evasion behaviors
Phase 5: Swarm Coordination               [SWARM INTELLIGENCE — auto-tasking]
    ↓ DEMO: UAVs auto-dispatch complementary sensors
Phase 6: Information Feeds & Event Log    [CHANNELS — typed feeds + audit]
    ↓ DEMO: Intel feed, command log, sensor subscriptions
Phase 7: Battlespace Assessment           [COP — threat clusters, gaps]
    ↓ DEMO: Threat clusters, coverage gaps, heatmap
Phase 8: Adaptive ISR & Closed Loop       [CAPSTONE — autonomous retasking]
    ↓ DEMO: Full closed loop: detect→fuse→verify→task→assess→adapt
Phase 9: Map Modes & Tactical Views       [VISUALIZATION — 6 view modes]
    ↓ DEMO: OPS/ISR/THREAT/FUSION/SWARM/TERRAIN toggles
Phase 10: Upgraded Drone Feeds            [SENSOR DISPLAYS — EO/SAR/SIGINT]
    ↓ FINAL DEMO: Full system end-to-end
```

---

## Phase 0: Foundation & React Migration

**Goal**: Migrate frontend from vanilla JS to React+TypeScript+Blueprint. Set up Vite build, wrap CesiumJS, establish component architecture. Fix known bugs. Wire unused theater config. Add event logging.

**Why first**: Every subsequent phase adds UI. Building on vanilla JS means 9x the DOM manipulation work. React+Blueprint once → all phases benefit.
**Plans:** 6/7 plans executed
**Requirements:** [P0-BUILD, P0-STORE, P0-WS, P0-CESIUM, P0-SIDEBAR, P0-PANELS, P0-DRONECAM, P0-ASSISTANT, P0-ECHARTS, P0-LAUNCHER]

Plans:
- [x] 00-01-PLAN.md — Fix Vite config, create types, Zustand store, shared utilities, React entry
- [ ] 00-02-PLAN.md — WebSocket hook, Cesium Viewer lifecycle, CesiumContainer, App layout
- [ ] 00-03-PLAN.md — Cesium entity hooks (drones, targets, zones, flow lines)
- [ ] 00-04-PLAN.md — Sidebar, tabs, mission panel (theater, assistant, strike board, grid controls)
- [ ] 00-05-PLAN.md — Drone cards, enemy cards, threat summary (ASSETS + ENEMIES tabs)
- [ ] 00-06-PLAN.md — Remaining Cesium hooks (compass, macro track, clicks, waypoints, lock indicators), drone cam PIP, demo banner
- [ ] 00-07-PLAN.md — ECharts dark theme, palantir.sh launcher update, final integration checkpoint

### 0.1 Build Tooling
- Initialize Vite + React + TypeScript project at `src/frontend-react/` (parallel to existing `src/frontend/`)
- Configure `vite-plugin-cesium` for CesiumJS asset handling
- Set up Blueprint CSS imports (dark theme: `@blueprintjs/core/lib/css/blueprint.css`)
- Configure proxy to FastAPI backend (port 8000)
- Replace `serve.py` with Vite dev server (HMR)
- Production build outputs to `dist/` for deployment

### 0.2 Project Structure (validated by architecture review)

```
src/frontend-react/
  index.html
  vite.config.ts
  tsconfig.json
  package.json

  src/
    main.tsx                              # React root, Blueprint dark theme
    App.tsx                               # Top layout: Sidebar + CesiumContainer

    store/
      SimulationStore.ts                  # Zustand: simState, selections, UI state
      types.ts                            # TS interfaces: UAV, Target, Zone, StrikeEntry, etc.

    hooks/
      useWebSocket.ts                     # Single WS connection, dispatches to Zustand
      useCesiumViewer.ts                  # Ref-based Cesium Viewer lifecycle
      useDroneCam.ts                      # Canvas render loop for synthetic EO
      useResizable.ts                     # Sidebar resize drag

    cesium/                               # IMPERATIVE Cesium hooks (not resium)
      CesiumContainer.tsx                 # Mounts Viewer into div ref, composes hooks
      useCesiumDrones.ts                  # SampledPositionProperty entities (from drones.js)
      useCesiumTargets.ts                 # Target billboards + threat rings (from targets.js)
      useCesiumZones.ts                   # GroundPrimitive zone grid (from map.js)
      useCesiumFlowLines.ts              # Flow polylines (from app.js)
      useCesiumCompass.ts                 # Compass needle + ring (from map.js)
      useCesiumMacroTrack.ts             # Camera delta tracking (from map.js)
      useCesiumClickHandlers.ts          # Entity pick + selection (from mapclicks.js)
      useCesiumRangeRings.ts             # Range ring toggle (from rangerings.js)
      useCesiumWaypoints.ts              # Waypoint cylinder + trajectory (from drones.js)
      useCesiumLockIndicators.ts         # PAINT lock ring on targets (from drones.js)
      CameraControls.tsx                  # Global view / decouple buttons
      DetailMapDialog.tsx                 # Second Viewer in Blueprint Dialog

    panels/
      Sidebar.tsx                         # Blueprint Card wrapper + resizer
      SidebarTabs.tsx                     # Tabs: MISSION / ASSETS / ENEMIES

      mission/
        MissionTab.tsx                    # Composition root
        TheaterSelector.tsx               # Blueprint HTMLSelect
        AssistantWidget.tsx               # AI assistant message log
        StrikeBoard.tsx                   # Strike board with approval flow
        StrikeBoardEntry.tsx              # Single strike entry card
        StrikeBoardCoa.tsx                # COA sub-card
        GridControls.tsx                  # Grid visibility + waypoint + reset

      assets/
        AssetsTab.tsx                      # Drone list root
        DroneCard.tsx                      # Single drone (Blueprint Card)
        DroneCardDetails.tsx              # Expanded tracked-drone details
        DroneModeButtons.tsx              # SEARCH/FOLLOW/PAINT/INTERCEPT ButtonGroup
        DroneActionButtons.tsx            # Waypoint, Range, Detail buttons

      enemies/
        EnemiesTab.tsx                     # Target list root
        ThreatSummary.tsx                 # Active/neutralized count bar
        EnemyCard.tsx                      # Single enemy (Blueprint Card)

    overlays/
      DemoBanner.tsx                      # "DEMO MODE" banner
      DroneCamPIP.tsx                     # Canvas PIP with useDroneCam

    shared/
      constants.ts                        # MODE_STYLES, TARGET_MAP, STATE_COLORS
      geo.ts                              # haversine, bearing, imbalanceColor
      api.ts                              # fetch wrappers for /api/* endpoints

    theme/
      palantir.ts                         # ECharts dark theme matching Blueprint
```

### 0.3 Cesium Integration Strategy

**Custom ref-based hooks, NOT resium.** The existing codebase uses `SampledPositionProperty` with Hermite interpolation, `GroundPrimitive` batch updates, and `CallbackProperty` — none of which resium wraps well.

Each Cesium hook follows this pattern:
```typescript
export function useCesiumDrones(viewerRef: RefObject<Cesium.Viewer>) {
  const uavs = useSimStore(state => state.uavs);  // Zustand subscription
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});
  useEffect(() => { /* create/update entities — same logic as drones.js */ }, [uavs]);
}
```

### 0.4 Component Migration (order matters)
1. `App.tsx` + `CesiumContainer.tsx` — layout shell + Cesium viewer
2. `useWebSocket.ts` + `SimulationStore.ts` — data pipeline
3. `useCesiumDrones.ts` + `useCesiumTargets.ts` + `useCesiumZones.ts` — entities on map
4. `Sidebar.tsx` + `SidebarTabs.tsx` — Blueprint Tabs (MISSION/ASSETS/ENEMIES)
5. `DroneCard.tsx` + mode buttons — Blueprint Cards replacing dronelist.js
6. `EnemyCard.tsx` — Blueprint Cards replacing enemies.js
7. `StrikeBoard.tsx` — Blueprint Cards + Buttons replacing strikeboard.js
8. `DroneCamPIP.tsx` — Canvas ref wrapper for dronecam.js
9. `AssistantWidget.tsx` — AI assistant panel
10. Remaining Cesium hooks (compass, macro track, clicks, waypoints, range rings)

### 0.4 Bug Fixes
- Fix `sim_engine.py:509`: `("FOLLOW", "FOLLOW", "PAINT")` → `("FOLLOW", "PAINT", "INTERCEPT")`
- Wire theater YAML `speed_kmh`, `threat_range_km`, `detection_range_km` into sim

### 0.5 Event Logging Infrastructure
- `src/python/event_logger.py`: append JSONL to `logs/events-{date}.jsonl`
- Log: detections, state transitions, mode changes, commands, nominations, engagements
- Each event: `{timestamp, event_type, data}`
- Rotate daily, configurable retention

### 0.6 Multi-Sensor UAV Setup
- Modify UAV spawn: random sensor distribution (50% EO_IR, 30% SAR, 20% SIGINT)
- Some UAVs get 2 sensors: `sensors: list[str]` field (10% of fleet gets dual-sensor)
- Theater YAML gains optional `sensor_distribution` config
- Update state broadcast to include `sensors` list per UAV

### 0.7 ECharts Setup
- Install `echarts` + `echarts-for-react`
- Create base chart theme matching Blueprint dark + Palantir style
- Stub chart components for later phases

### 0.8 Demo Checkpoint
- [ ] Vite dev server serves React app with hot reload
- [ ] Cesium globe renders with dark tiles, zone grid, drones, targets
- [ ] Sidebar tabs work (MISSION/ASSETS/ENEMIES) with Blueprint styling
- [ ] Drone cards with mode buttons functional
- [ ] Target cards with state badges functional
- [ ] Strike board approve/reject/authorize flow works
- [ ] Drone cam canvas renders in React wrapper
- [ ] Demo autopilot runs end-to-end without errors
- [ ] `./palantir.sh` updated to use Vite build
- [ ] All existing WebSocket actions work

### 0.9 Files Changed

| File | Action | Notes |
|------|--------|-------|
| `src/frontend/package.json` | **NEW** | React, Blueprint, Vite, ECharts deps |
| `src/frontend/vite.config.ts` | **NEW** | Cesium plugin, proxy config |
| `src/frontend/tsconfig.json` | **NEW** | TypeScript config |
| `src/frontend/src/App.tsx` | **NEW** | Layout shell |
| `src/frontend/src/store.ts` | **NEW** | Zustand store (replaces state.js) |
| `src/frontend/src/hooks/useWebSocket.ts` | **NEW** | WebSocket hook |
| `src/frontend/src/components/CesiumMap.tsx` | **NEW** | Cesium wrapper |
| `src/frontend/src/components/Sidebar.tsx` | **NEW** | Blueprint Tabs |
| `src/frontend/src/components/DroneList.tsx` | **NEW** | Blueprint drone cards |
| `src/frontend/src/components/EnemyList.tsx` | **NEW** | Blueprint target cards |
| `src/frontend/src/components/StrikeBoard.tsx` | **NEW** | Blueprint strike board |
| `src/frontend/src/components/DroneCam.tsx` | **NEW** | Canvas wrapper |
| `src/frontend/src/components/Assistant.tsx` | **NEW** | AI assistant panel |
| `src/frontend/src/cesium/droneManager.ts` | **NEW** | Cesium drone entities (from drones.js) |
| `src/frontend/src/cesium/targetManager.ts` | **NEW** | Cesium target entities (from targets.js) |
| `src/frontend/src/cesium/zoneManager.ts` | **NEW** | Zone primitives (from map.js) |
| `src/frontend/src/theme/palantir.ts` | **NEW** | ECharts dark theme |
| `src/python/sim_engine.py` | MODIFY | Bug fix line 509, sensor distribution |
| `src/python/event_logger.py` | **NEW** | JSONL event logging |
| `src/python/api_main.py` | MODIFY | Wire event logger |
| `palantir.sh` | MODIFY | Update to use Vite build |

**Risk**: HIGH — full frontend rewrite. Mitigate by keeping Cesium entity management as imperative code (hooks with refs), only migrating DOM panels to React components.

**Estimated new lines**: ~2,500 (React components + TypeScript + config)

---

## Phase 1: Multi-Sensor Target Fusion

**Goal**: Multiple UAVs contribute detections to the same target. Fused confidence increases with more sensors. Foundation for everything else.

**Depends on**: Phase 0 (React UI for displaying fusion data)
**Plans:** 3/3 plans complete
**Requirements:** [P1-FUSE-MODULE, P1-TARGET-FIELDS, P1-UAV-FIELDS, P1-DETECT-LOOP, P1-CANCEL, P1-ASSIGN, P1-BROADCAST, P1-TESTS, P1-TS-TYPES, P1-FUSIONBAR, P1-BADGE, P1-ENEMYCARD, P1-DRONECARD, P1-CESIUM-RING]

Plans:
- [x] 01-01-PLAN.md — TDD sensor fusion module (pure functions + unit tests)
- [x] 01-02-PLAN.md — sim_engine migration (multi-tracking fields, detection loop rewrite, integration tests)
- [ ] 01-03-PLAN.md — React components (FusionBar, SensorBadge, EnemyCard, DroneCard, Cesium fusion ring)
### 1.1 Data Model Changes

**`sim_engine.py` — Target class**:
```python
# REPLACE single tracking
self.tracked_by_uav_id → self.tracked_by_uav_ids: list[int] = []
# ADD
self.sensor_contributions: list[dict] = []
self.fused_confidence: float = 0.0
self.sensor_count: int = 0
```

**`sim_engine.py` — UAV class**:
```python
# REPLACE single tracking
self.tracked_target_id → self.tracked_target_ids: list[int] = []
# ADD
self.primary_target_id: Optional[int] = None
self.sensors: list[str] = ["EO_IR"]  # multi-sensor capable
```

### 1.2 New Module: `src/python/sensor_fusion.py`
- `SensorContribution` dataclass (uav_id, sensor_type, confidence, range, bearing, timestamp)
- `FusedDetection` dataclass (fused_confidence, classification, sensor_count, sensor_types, contributions)
- `fuse_detections()` — complementary fusion: `1 - product(1 - ci)`
- Pure function, no side effects

### 1.3 Detection Loop Rewrite
- Accumulate ALL detections per target (not just best single)
- Call `fuse_detections()` per target per tick
- Update target fusion fields
- Emit detection events to event logger

### 1.4 Tracking Migration
- `_assign_target()` → add to lists, set primary
- `cancel_track()` → remove from lists
- `_update_tracking_modes()` → iterate tracked_target_ids
- `command_follow/paint/intercept` → set primary_target_id
- `demo_autopilot()` → use new fields

### 1.5 WebSocket Protocol
Target payload gains: `fused_confidence`, `sensor_count`, `contributing_uav_ids`, `sensor_contributions[]`
UAV payload gains: `tracked_target_ids`, `primary_target_id`, `sensors`

### 1.6 React Components
- `FusionBar.tsx` — stacked horizontal bar (EO_IR=blue, SAR=green, SIGINT=yellow) showing per-sensor confidence contribution
- `SensorBadge.tsx` — "3 SENSORS" count badge
- Update `EnemyList.tsx` — fusion bar + sensor badge + contributing UAV list
- Update `DroneList.tsx` — show all tracked targets, highlight primary
- Cesium: fusion ring around targets (ring thickness/opacity scales with sensor_count)

### 1.7 Demo Checkpoint
- [ ] Multiple UAVs near target → fused confidence climbs above any single sensor
- [ ] ECharts fusion bar shows per-sensor breakdown with colors
- [ ] Removing UAV from area → fused confidence degrades
- [ ] Target cards show sensor count and contributing UAVs
- [ ] Drone cards show all tracked targets with primary highlighted
- [ ] Existing follow/paint/intercept commands still work
- [ ] Demo autopilot runs without errors

### 1.8 Files Changed

| File | Action |
|------|--------|
| `src/python/sensor_fusion.py` | **NEW** (~150 lines) |
| `src/python/sim_engine.py` | MODIFY (~100 lines) |
| `src/python/api_main.py` | MODIFY (~30 lines) |
| `src/python/tests/test_sensor_fusion.py` | **NEW** (~100 lines) |
| `src/frontend/src/components/FusionBar.tsx` | **NEW** (~80 lines) |
| `src/frontend/src/components/SensorBadge.tsx` | **NEW** (~30 lines) |
| `src/frontend/src/components/EnemyList.tsx` | MODIFY (~50 lines) |
| `src/frontend/src/components/DroneList.tsx` | MODIFY (~30 lines) |
| `src/frontend/src/cesium/targetManager.ts` | MODIFY (~30 lines) |

**Risk**: MEDIUM — 1:1 tracking assumption is deep. Must update atomically.

---

## Phase 2: Target Verification Workflow

**Goal**: Targets progress through verification pipeline before nomination. Multi-sensor evidence required.

**Depends on**: Phase 1 (fused confidence + sensor types for verification criteria)

### 2.1 Extended State Machine
```
UNDETECTED → DETECTED → CLASSIFIED → VERIFIED → NOMINATED → LOCKED → ENGAGED → DESTROYED|ESCAPED
```

Promotion rules:
- DETECTED → CLASSIFIED: `fused_confidence >= 0.6` AND 1+ sensor
- CLASSIFIED → VERIFIED: `fused_confidence >= 0.8` AND (2+ sensor types OR sustained > 15s)
- VERIFIED → NOMINATED: ISR + Strategy pipeline (existing)
- Regression: no sensors observe for T seconds → regress one state

Configurable thresholds per target type (SAMs verify faster due to high threat).

### 2.2 New Module: `src/python/verification_engine.py`
- `evaluate_target_state()` — pure function, returns new state
- `VERIFICATION_THRESHOLDS` — per target type
- Time-decay regression logic
- `DEMO_FAST` preset: halves all thresholds

### 2.3 Pipeline Gate
- `_process_new_detection()` only fires on VERIFIED targets (not DETECTED)
- Manual `verify_target` WebSocket action for operator fast-track

### 2.4 React Components
- `VerificationStepper.tsx` — Blueprint Steps/ProgressBar showing DETECTED→CLASSIFIED→VERIFIED→NOMINATED
- Each step: colored dot (gray=pending, amber=current, green=passed)
- Progress bar showing confidence toward next threshold
- Manual "VERIFY" button on CLASSIFIED targets (Blueprint Button, intent=warning)
- Update `EnemyList.tsx` — integrate stepper, new state colors

### 2.5 Demo Checkpoint
- [ ] Targets appear as DETECTED with low confidence
- [ ] More UAV sensors → confidence climbs → CLASSIFIED auto-promotion
- [ ] Second sensor type → VERIFIED auto-promotion
- [ ] Only VERIFIED targets hit strike board
- [ ] Manual VERIFY button fast-tracks CLASSIFIED target
- [ ] Losing sensor contact → regression after timeout
- [ ] Demo timing feels natural (DEMO_FAST preset)

### 2.6 Files Changed

| File | Action |
|------|--------|
| `src/python/verification_engine.py` | **NEW** (~120 lines) |
| `src/python/sim_engine.py` | MODIFY (~60 lines) |
| `src/python/api_main.py` | MODIFY (~40 lines) |
| `src/python/tests/test_verification.py` | **NEW** (~120 lines) |
| `src/frontend/src/components/VerificationStepper.tsx` | **NEW** (~100 lines) |
| `src/frontend/src/components/EnemyList.tsx` | MODIFY (~80 lines) |

**Risk**: LOW — additive new states. Only breaking change: nominations require VERIFIED (intentional).

---

## Phase 3: Drone Modes & Autonomy

**Goal**: New modes (SUPPORT, VERIFY, OVERWATCH, BDA) + 3-tier autonomy (MANUAL/SUPERVISED/AUTONOMOUS).

**Depends on**: Phase 1 (sensor contribution for SUPPORT) + Phase 2 (verification triggers for VERIFY)

**Plans:** 3/3 plans complete
**Requirements:** [FR-3]

Plans:
- [ ] 03-01-PLAN.md — TDD new mode behaviors (SUPPORT/VERIFY/OVERWATCH/BDA) + autonomy system in sim_engine.py
- [ ] 03-02-PLAN.md — Wire 4 new WS actions (set_autonomy_level, set_drone_autonomy, approve/reject_transition)
- [ ] 03-03-PLAN.md — React frontend (AutonomyToggle, TransitionToast, mode buttons, store, Cesium colors)

### 3.1 New Modes
- **SUPPORT**: wide orbit (~3km), provides secondary sensor data to target
- **VERIFY**: sensor-specific pass (EO_IR: perpendicular cross, SAR: parallel track, SIGINT: loiter)
- **OVERWATCH**: racetrack pattern for area denial, persistent coverage
- **BDA**: post-engagement tight orbit, auto-transitions after 30s

### 3.2 Autonomy Levels
- Level 0 MANUAL: all transitions require operator command
- Level 1 SUPERVISED: system recommends, operator approves (auto-approve after N seconds)
- Level 2 AUTONOMOUS: system freely transitions, operator can override

### 3.3 Transition Rules
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
    ("ANY", "fuel_below_threshold"): "RTB",
}
```

### 3.4 WebSocket Actions
- `set_autonomy_level` (fleet-wide)
- `set_drone_autonomy` (per-drone override)
- `approve_transition` / `reject_transition` (SUPERVISED mode)

### 3.5 React Components
- `AutonomyToggle.tsx` — Blueprint SegmentedControl: MANUAL/SUPERVISED/AUTONOMOUS
- `TransitionToast.tsx` — Blueprint Toast notification for SUPERVISED recommendations with approve/reject + countdown
- Update `DroneList.tsx` — new mode buttons (SUPPORT, VERIFY), mode source indicator (HUMAN/AUTO), all tracked targets
- New mode colors: SUPPORT=teal, VERIFY=amber, OVERWATCH=indigo, BDA=gray-blue

### 3.6 Files Changed

| File | Action |
|------|--------|
| `src/python/sim_engine.py` | MODIFY (~200 lines — new mode behaviors) |
| `src/python/api_main.py` | MODIFY (~60 lines — new actions) |
| `src/python/tests/test_drone_modes.py` | **NEW** (~150 lines) |
| `src/frontend/src/components/AutonomyToggle.tsx` | **NEW** (~60 lines) |
| `src/frontend/src/components/TransitionToast.tsx` | **NEW** (~80 lines) |
| `src/frontend/src/components/DroneList.tsx` | MODIFY (~100 lines) |
| `src/frontend/src/cesium/droneManager.ts` | MODIFY (~30 lines) |

**Risk**: MEDIUM — new modes interact with zone repositioning and tracking. Need minimum-idle-count constraint.

---

## Phase 4: Enemy UAVs

**Goal**: Add adversary UAVs to the simulation. Enemy drones with configurable behaviors (recon, attack, jamming), detection by friendly sensors, threat classification, and evasion/intercept mechanics.

**Depends on**: Phase 3 (drone modes — reuses flight model, mode system, and autonomy framework)

**Plans:** 3 plans
**Requirements:** [EUAV-01, EUAV-02, EUAV-03, EUAV-04, EUAV-05, EUAV-06, EUAV-07, EUAV-08, EUAV-09, EUAV-10, EUAV-11, EUAV-12, EUAV-13]

Plans:
- [ ] 04-01-PLAN.md — TDD EnemyUAV class, behaviors (RECON/ATTACK/JAMMING), detection loop, get_state broadcast
- [ ] 04-02-PLAN.md — Frontend types, Zustand store, Cesium enemy UAV hook, EnemyUAVCard in ENEMIES tab
- [ ] 04-03-PLAN.md — Evasion with hysteresis, intercept kill mechanic, theater YAML config, demo autopilot auto-intercept
---

## Phase 5: Swarm Coordination

**Goal**: UAVs coordinate as a swarm. System auto-tasks complementary sensors to accelerate verification.

**Depends on**: Phases 1+2+3+4 (fusion + verification + modes + enemy UAVs)

**Plans:** 3 plans
**Requirements:** [FR-4]

Plans:
- [ ] 05-01-PLAN.md — TDD SwarmCoordinator module (frozen dataclasses, greedy assignment, idle guard, unit tests)
- [ ] 05-02-PLAN.md — sim_engine integration (tick hook, SUPPORT mode, get_state broadcast, WS actions, integration tests)
- [ ] 05-03-PLAN.md — React frontend (SwarmTask types, SwarmPanel component, Cesium dashed swarm lines)

### 5.1 New Module: `src/python/swarm_coordinator.py`
- `SwarmCoordinator` class: runs each tick after detection
- `evaluate_and_assign()` — greedy assignment: identify sensor gaps per target, dispatch nearest matching UAV
- `SwarmTask` dataclass (target_id, assigned_uav_ids, sensor_coverage, formation_type)
- `TaskingOrder` dataclass (uav_id, target_id, mode, reason, priority)
- Minimum idle count enforced (don't drain all UAVs to one target)

### 5.2 Algorithm
```
1. For each DETECTED/CLASSIFIED target: identify missing sensor types, score by threat × (1-confidence) × time
2. Sort targets by score (highest first)
3. For each: find nearest IDLE/SEARCH UAV with matching sensor
4. Skip if assigning drops IDLE below min_idle_count
5. Issue TaskingOrder → SUPPORT mode
```

### 8.3 React Components
- `SwarmPanel.tsx` — per-target sensor coverage indicator (EO_IR/SAR/SIGINT icons, filled when contributing)
- "Request Swarm" / "Release Swarm" buttons on target cards
- Cesium: formation lines between swarm members (dashed cyan polylines)

### 5.4 Files Changed

| File | Action |
|------|--------|
| `src/python/swarm_coordinator.py` | **NEW** (~300 lines) |
| `src/python/sim_engine.py` | MODIFY (~80 lines) |
| `src/python/api_main.py` | MODIFY (~40 lines) |
| `src/python/tests/test_swarm_coordinator.py` | **NEW** (~150 lines) |
| `src/frontend/src/components/SwarmPanel.tsx` | **NEW** (~150 lines) |
| `src/frontend/src/components/EnemyList.tsx` | MODIFY (~30 lines) |
| `src/frontend/src/cesium/swarmLines.ts` | **NEW** (~80 lines) |

**Risk**: MEDIUM — must not starve area coverage. Swarm tasks must take priority over zone balancing.

---

## Phase 6: Information Feeds & Event Log

**Goal**: Multiple specialized feed types over WebSocket. Rich event logging.

**Depends on**: Phases 1-5 (fusion, verification, modes, enemy UAVs, swarm data to feed)

**Plans:** 3 plans
**Requirements:** [FR-5, FR-10]

Plans:
- [ ] 06-01-PLAN.md — TDD IntelFeedRouter, subscription-filtered broadcast, event logger enhancement
- [ ] 06-02-PLAN.md — Frontend feed types, Zustand slices, useWebSocket routing, IntelFeed + CommandLog components
- [ ] 06-03-PLAN.md — 2Hz SENSOR_FEED loop, DroneCam fusion overlay, human verification

### 6.1 Feed Types
- **STATE_FEED** (10Hz): existing, enhanced with fusion/swarm/autonomy data
- **INTEL_FEED** (event-driven): target state transitions, verifications, threat assessments
- **SENSOR_FEED** (2Hz per UAV): raw per-UAV detection results, subscribable
- **COMMAND_FEED** (event-driven): all commands + mode transitions with source attribution
- **DRONE_VIDEO_FEED** (existing): enhanced with fusion overlays

### 6.2 Subscription Protocol
```json
{"action": "subscribe", "feeds": ["STATE_FEED", "INTEL_FEED"]}
{"action": "subscribe_sensor_feed", "uav_ids": [5, 7]}
```

### 8.3 React Components
- `IntelFeed.tsx` — real-time intel event list (Blueprint Card stream, color-coded, filterable)
- `CommandLog.tsx` — audit trail (Blueprint HTMLTable, source attribution)
- Update `DroneCam.tsx` — overlay fused confidence, verification status on HUD

### 6.4 Event Logger Enhancement
- Wire all feed events through `event_logger.py`
- Each event appended to JSONL with full context
- Log rotation + configurable retention

### 6.5 Files Changed

| File | Action |
|------|--------|
| `src/python/intel_feed.py` | **NEW** (~100 lines) |
| `src/python/api_main.py` | MODIFY (~150 lines) |
| `src/python/event_logger.py` | MODIFY (~50 lines) |
| `src/python/tests/test_feeds.py` | **NEW** (~80 lines) |
| `src/frontend/src/components/IntelFeed.tsx` | **NEW** (~150 lines) |
| `src/frontend/src/components/CommandLog.tsx` | **NEW** (~120 lines) |
| `src/frontend/src/hooks/useWebSocket.ts` | MODIFY (~40 lines — subscription support) |

**Risk**: LOW-MEDIUM — additional WS traffic. Mitigation: feeds are subscribe-only, sensor feed throttled to 2Hz.

---

## Phase 7: Battlespace Assessment

**Goal**: Live Common Operating Picture. Threat clusters, coverage gaps, zone threat scores, movement corridors.

**Depends on**: Phase 2 (verification states) + Phase 5 (swarm for addressing gaps)

### 7.1 New Module: `src/python/battlespace_assessment.py`
- `BattlespaceAssessor` class: runs every 5s
- `_cluster_targets()` — DBSCAN-like with type affinity (SAM_BATTERY, CONVOY, CP_COMPLEX, AD_NETWORK)
- `_identify_coverage_gaps()` — zones with no UAV presence
- `_score_zone_threats()` — aggregate threat per grid zone
- `_detect_movement_corridors()` — patrol routes from target movement history
- Consume theater YAML `threat_range_km` for SAM engagement envelopes

### 7.2 Activate Dormant Agents
- `battlespace_manager.py` — activate threat ring generation from verified SAM/RADAR positions
- Wire `threat_range_km` from theater YAML into ring radius

### 8.3 React Components
- `AssessmentTab.tsx` — new sidebar tab with Blueprint Cards
- `ThreatClusterCard.tsx` — cluster type, member targets, threat score
- `CoverageGapAlert.tsx` — zones needing attention
- ECharts: zone threat heatmap chart
- Cesium: convex hull overlays (colored by cluster type), SAM engagement envelopes, movement corridor polylines

### 8.4 Files Changed

| File | Action |
|------|--------|
| `src/python/battlespace_assessment.py` | **NEW** (~350 lines) |
| `src/python/sim_engine.py` | MODIFY (~40 lines — position history) |
| `src/python/api_main.py` | MODIFY (~40 lines) |
| `src/python/agents/battlespace_manager.py` | MODIFY (~60 lines) |
| `src/python/tests/test_battlespace.py` | **NEW** (~120 lines) |
| `src/frontend/src/components/AssessmentTab.tsx` | **NEW** (~200 lines) |
| `src/frontend/src/components/ThreatClusterCard.tsx` | **NEW** (~80 lines) |
| `src/frontend/src/cesium/assessmentOverlays.ts` | **NEW** (~150 lines) |

**Risk**: LOW — mostly additive read-only overlay. 5s interval prevents perf overhead.

---

## Phase 8: Adaptive ISR & Closed Loop

**Goal**: Close the loop. Battlespace assessment drives autonomous retasking.

**Depends on**: All prior phases (capstone)

### 8.1 Activate AI Tasking Manager
- Implement `_generate_response_heuristic()` — score targets by verification gap, match UAV sensors
- ISR priority queue: outstanding intelligence requirements ranked by urgency

### 8.2 Adaptive Coverage
- `coverage_mode`: "balanced" (current zone-imbalance) vs "threat_adaptive" (assessment-driven)
- Threat-adaptive redistributes IDLE UAVs to high-threat coverage gaps
- Toggle via WebSocket action

### 8.3 React Components
- `ISRQueue.tsx` — priority queue of intel requirements (Blueprint HTMLTable)
- Coverage mode toggle (Blueprint SegmentedControl)
- Update `DroneList.tsx` — per-UAV tasking status with source attribution

### 8.4 Files Changed

| File | Action |
|------|--------|
| `src/python/agents/ai_tasking_manager.py` | MODIFY (~100 lines) |
| `src/python/isr_priority.py` | **NEW** (~120 lines) |
| `src/python/sim_engine.py` | MODIFY (~80 lines) |
| `src/python/api_main.py` | MODIFY (~60 lines) |
| `src/python/tests/test_adaptive_isr.py` | **NEW** (~120 lines) |
| `src/frontend/src/components/ISRQueue.tsx` | **NEW** (~120 lines) |
| `src/frontend/src/components/DroneList.tsx` | MODIFY (~40 lines) |

**Risk**: HIGH — changes fundamental UAV assignment logic. Extensive testing needed.

---

## Phase 9: Map Modes & Tactical Views

**Goal**: 6 map visualization modes with keyboard shortcuts.

**Depends on**: Phase 1 (FUSION mode), Phase 5 (SWARM mode), Phase 7 (THREAT mode)

### 9.1 Map Modes
| Mode | Key | Layers |
|------|-----|--------|
| OPERATIONAL | 1 | 3/3 | Complete   | 2026-03-19 | 2 | 3/3 | Complete   | 2026-03-19 | 3 | threat heatmap, clusters, SAM envelopes, corridors |
| FUSION | 4 | fusion rings, sensor lines, verification bars |
| SWARM | 5 | formation lines, assignment arrows, sensor diversity |
| TERRAIN | 6 | 3D terrain, LOS analysis, terrain masking |

### 9.2 React Components
- `MapModeBar.tsx` — Blueprint ButtonGroup for mode selection
- `LayerPanel.tsx` — Blueprint Checkbox list for individual layer toggles
- `CameraPresets.tsx` — Theater Overview, Top-Down, Oblique, Free Camera buttons
- Cesium layers: `coverageLayer.ts`, `threatLayer.ts`, `fusionLayer.ts`, `terrainLayer.ts`, `swarmLayer.ts`

### 9.3 Files Changed

| File | Action |
|------|--------|
| `src/frontend/src/components/MapModeBar.tsx` | **NEW** (~100 lines) |
| `src/frontend/src/components/LayerPanel.tsx` | **NEW** (~80 lines) |
| `src/frontend/src/cesium/layers/coverageLayer.ts` | **NEW** (~150 lines) |
| `src/frontend/src/cesium/layers/threatLayer.ts` | **NEW** (~150 lines) |
| `src/frontend/src/cesium/layers/fusionLayer.ts` | **NEW** (~120 lines) |
| `src/frontend/src/cesium/layers/terrainLayer.ts` | **NEW** (~150 lines) |
| `src/frontend/src/cesium/layers/swarmLayer.ts` | **NEW** (~100 lines) |
| `src/frontend/src/cesium/droneManager.ts` | MODIFY (~60 lines) |

**Risk**: LOW — layer visibility toggles are non-destructive. Performance with all layers needs testing.

---

## Phase 10: Upgraded Drone Feeds

**Goal**: Multi-mode sensor feeds (EO/IR, SAR, SIGINT), enhanced HUD, PIP/SPLIT/QUAD layouts.

**Depends on**: Phase 1 (fusion data), Phase 3 (modes), Phase 6 (SENSOR_FEED)

### 10.1 Sensor Feed Modes
- **EO/IR**: green thermal, hot targets glow, terrain noise texture
- **SAR**: amber radar returns, sharp echoes, velocity vectors
- **SIGINT**: dark blue waterfall/spectrum display, emitter classification
- **FUSION**: split-screen combining multiple sensor views

### 10.2 Enhanced HUD
- Compass tape (horizontal heading strip)
- Sensor status panel (quality, fused count, verification progress)
- Fuel gauge bar
- Multi-target bounding boxes (primary=reticle, secondary=dashed)
- Threat warning (flash when entering SAM envelope)

### 10.3 Layouts
- SINGLE (full-frame, current enhanced)
- PIP (main + picture-in-picture from supporting UAV)
- SPLIT (two sensors side-by-side)
- QUAD (2x2 grid, 4 drone feeds)

### 10.4 React Components
- Major rewrite of `DroneCam.tsx` — multi-canvas architecture
- `SigintDisplay.tsx` — ECharts waterfall chart (time vs frequency, signal intensity as heatmap)
- `CamLayoutSelector.tsx` — Blueprint ButtonGroup: SINGLE/PIP/SPLIT/QUAD
- `SensorHUD.tsx` — compass tape, fuel gauge, sensor status

### 10.5 Files Changed

| File | Action |
|------|--------|
| `src/frontend/src/components/DroneCam.tsx` | MODIFY (major rewrite ~500 lines) |
| `src/frontend/src/components/SigintDisplay.tsx` | **NEW** (~200 lines) |
| `src/frontend/src/components/CamLayoutSelector.tsx` | **NEW** (~80 lines) |
| `src/frontend/src/components/SensorHUD.tsx` | **NEW** (~150 lines) |
| `src/python/sim_engine.py` | MODIFY (~30 lines — FOV targets, sensor quality) |
| `src/python/api_main.py` | MODIFY (~20 lines) |

**Risk**: MEDIUM — canvas rendering complexity. PIP/SPLIT/QUAD need careful layout management.
