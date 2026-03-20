# Phase 5: Swarm Coordination - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated swarm coordination that dispatches complementary sensors to targets, accelerating the verification pipeline. Backend SwarmCoordinator module + sim_engine integration + React SwarmPanel + Cesium swarm lines.

</domain>

<decisions>
## Implementation Decisions

### Swarm Algorithm Behavior
- Conservative auto-tasking — max 50% of fleet assigned to swarm tasks at any time
- Minimum 2 UAVs always reserved in IDLE/SEARCH (never fully drain coverage)
- Priority scoring: threat_level × (1 - confidence) × time_detected
- Auto-release UAVs back to SEARCH when target reaches VERIFIED state

### Operator Control
- "Request Swarm" button on target cards for manual swarm initiation
- Whole-swarm release (not per-UAV) — "Release Swarm" button releases all UAVs on that target
- Autonomy tier integration: AUTONOMOUS auto-assigns, SUPERVISED recommends + 30s auto-approve, MANUAL recommend-only
- Manual mode commands override swarm — operator always has final say

### Visual Feedback
- Dashed cyan polylines on Cesium map from swarm UAVs to their assigned target
- SwarmPanel section inside existing Enemies tab — per-target sensor coverage display
- 3 sensor icons (EO_IR/SAR/SIGINT) — filled when contributing, outline when gap exists
- No toast notifications for swarm changes — rely on visual indicators to avoid noise

### Swarm Task Lifecycle
- 120-second timeout per swarm task — auto-release if not resolved
- Immediate release on target destroyed/escaped — UAVs return to SEARCH
- Re-evaluate assignments every 5 seconds (50 ticks) — balances responsiveness vs performance
- Include active_swarm_tasks in get_state() broadcast — frontend needs swarm data

### Claude's Discretion
- Internal data structure choices for SwarmTask and TaskingOrder dataclasses
- Exact greedy assignment algorithm implementation details
- Cesium polyline styling specifics (dash pattern, opacity, width)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sim_engine.py` already defines SUPPORT mode with `SUPPORT_ORBIT_RADIUS_DEG = 0.027`
- `AUTONOMOUS_TRANSITIONS` table includes `("IDLE", "swarm_support_requested"): "SUPPORT"`
- `sensor_fusion.py` has `SensorContribution` and `fuse_detections()` — reuse for gap analysis
- `verification_engine.py` has `evaluate_target_state()` with per-type thresholds
- `_pick_sensors()` distributes EO_IR (50%), SAR (20%), SIGINT (10%), dual-sensor (20%)
- `useCesiumDrones.ts` and `useCesiumClickHandlers.ts` — existing Cesium entity patterns
- `EnemiesTab.tsx` with `EnemyUAVCard.tsx` — existing enemy panel structure

### Established Patterns
- Frozen dataclasses for immutable data (`SensorContribution`, `FusionResult`)
- UAV has `.sensors: List[str]` and `.mode` fields
- Target has `.sensor_contributions`, `.detected_by_sensor`, `.verification_state`
- `get_state()` serializes full sim state as JSON for WebSocket broadcast
- Zustand `SimulationStore.ts` for frontend state management
- Custom event bridge (`palantir:send`) for Cesium→React WebSocket communication

### Integration Points
- `sim_engine.py` tick loop — hook SwarmCoordinator after detection/fusion step
- `api_main.py` WebSocket actions — add `request_swarm` and `release_swarm`
- `get_state()` — include `active_swarm_tasks` array
- `EnemiesTab.tsx` — add SwarmPanel section per target
- Cesium hooks — new `useCesiumSwarmLines.ts` for dashed polylines

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following ROADMAP algorithm spec.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
