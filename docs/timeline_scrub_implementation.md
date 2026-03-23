# Timeline Scrub Implementation

## Problem

The mission planner's timeline needed to scrub back into the database to show historical domain state — drone positions, targets, missions — at any past point in time. The original implementation had a 10-minute in-memory snapshot buffer on the frontend, no backend persistence for historical replay, and targets existed only in client-side arrays (lost on refresh).

## Architecture: "Moving the Index Pointer"

The core principle: the timeline scrub simply changes **which data** the 3D viewer renders. There is one rendering path (`updateSimulation`), and the only thing that changes between live and scrub mode is the data source.

```
Live mode:   WS message → updateSimulation(liveData)
Scrub mode:  timeline click → _applyHistoricalState(ms) → updateSimulation(historicalData)
```

No separate scrub rendering system. No position property swapping. No render loop hacking. Same function, different data.

## Backend: Historical State Reconstruction

### Snapshot Persistence
- `domain_snapshots` table stores full domain state every 30 seconds (configurable via `SNAPSHOT_INTERVAL_SEC`)
- Retention: 24 hours by default (`SNAPSHOT_RETENTION_HOURS`)
- Captured by `snapshot_capture_loop()` in `main.py`
- `SnapshotRepo` handles insert, nearest-before-time query, range query, pruning

### State-at-Time API
- `GET /api/v1/timeline/state?at=<ISO timestamp>` — reconstructs full state at any past time
- `GET /api/v1/timeline/range` — returns earliest/latest available snapshot timestamps
- `SnapshotService.reconstruct_state_at(timestamp)`:
  1. Find nearest snapshot before the target time
  2. Query `event_log` for all events between snapshot time and target time
  3. Replay events onto the snapshot state (asset telemetry, aimpoint/target CRUD, mission state changes, etc.)
  4. Return the reconstructed state

### Event Log
- Every domain mutation is persisted to the append-only `event_log` table
- Indexed on `timestamp`, `entity_type+entity_id`, and `type`
- Supports time-range queries for replay

## Frontend: Data Flow

### Live Mode
```
WS /ws/stream (10Hz) → ws.onmessage
  → AppState.pushSnapshot(data)          // buffer for local scrub
  → if timeMode === 'live':
      updateSimulation(payload.data)     // renders on Cesium
```

### Scrub Mode (Within Local Buffer ~10 min)
```
User clicks/drags timeline
  → _applyHistoricalState(ms)
  → AppState.getSnapshotAt(ms)           // binary search in local buffer
  → window.updateSimulation(snapshot)    // same render path as live
  → store.setHistoricalState(...)        // for React panels
```

### Scrub Mode (Beyond Local Buffer)
```
User clicks/drags timeline
  → _applyHistoricalState(ms)
  → _doHistoricalFetch(ms)              // throttled async fetch
  → GET /api/v1/timeline/state?at=ms
  → window.updateSimulation(simData)    // convert + render
  → store.setHistoricalState(state)     // for React panels
```

### Return to Live
```
Double-click timeline
  → AppState.setTimeCursor(null)         // timeMode = 'live'
  → store.setHistoricalState(null)       // clear historical
  → Next WS message resumes live updateSimulation
```

## Key Implementation Decisions

### 1. ConstantPositionProperty Instead of SampledPositionProperty

The original Cesium entity system used `SampledPositionProperty` with Hermite interpolation for smooth drone movement. This caused problems during scrub because:
- The interpolation buffer retained live samples that blended with historical positions
- The Cesium clock kept advancing, evaluating properties at live time
- Tethers and trails captured the position property in closures

**Fix**: All entity positions now use `ConstantPositionProperty`, set directly on each `updateSimulation` call. At 10Hz update rate, the movement is still smooth enough. This eliminates all interpolation-related scrub artifacts.

### 2. Single Rendering Path

Previous attempts had separate rendering systems for live and scrub:
- `updateSimulation()` for live (adding samples to SampledPositionProperty)
- `scrubToSnapshot()` for scrub (replacing with ConstantPositionProperty)
- `restoreLivePositions()` for returning to live

These fought each other. The `time.cursorChanged` AppState subscription ran `scrubToSnapshot` which stashed live properties, while the WS handler ran `updateSimulation` which set different properties. The alternation between these two systems on each frame caused the stuttering.

**Fix**: Removed `scrubToSnapshot`, `restoreLivePositions`, and the `time.cursorChanged` subscription entirely. Both live and scrub feed data through `updateSimulation`. The WS handler is completely silent during scrub mode — only `_applyHistoricalState` calls `updateSimulation`.

### 3. Tether Closure Fix

The tether (vertical line from ground to drone) used a `CallbackProperty` that captured `positionProperty` in a closure at entity creation time:
```javascript
// OLD — captures initial positionProperty, never updates
positions: new Cesium.CallbackProperty((time) => {
    const currentPos = positionProperty.getValue(time);
```

When `marker.position` was replaced with a new ConstantPositionProperty during scrub, the tether still read from the original captured variable — drawing a line to the live/initial position.

**Fix**: Changed to read from `marker.position` directly:
```javascript
// NEW — always reads current position
positions: new Cesium.CallbackProperty((time) => {
    const currentPos = marker.position.getValue(time);
```

### 4. WS Handler Silence During Scrub

The WS handler receives live data at 10Hz. During scrub, it must not feed live data to `updateSimulation`:
```javascript
if (typeof AppState === 'undefined' || AppState.state.timeMode === 'live') {
    updateSimulation(payload.data);
}
// In scrub mode: do nothing — timeline panel calls updateSimulation directly
```

Snapshots are still pushed to the local buffer regardless of mode (for future scrub within the buffer).

### 5. Throttled Backend Fetch

Beyond the local buffer, historical data requires a backend fetch. The fetch is throttled (not debounced) — fires immediately if no fetch is in flight, queues the latest request otherwise:
```
mousemove 1 → fetch fires immediately
mousemove 2 → fetch in flight → queue ms2
mousemove 3 → overwrite queue with ms3
fetch 1 completes → fire queued ms3
```

This provides regular updates during drag scrub (~every 200ms) instead of only when the user stops.

### 6. Timeline Range from Backend

The gold scrubbable range on the timeline shows the full backend snapshot range, not just the local buffer:
```javascript
const rangeStart = _backendRange ? _backendRange.earliest : (localBuf ? localBuf.start : null);
```
Fetched via `GET /api/v1/timeline/range` on init and refreshed every 30 seconds.

### 7. Live Telemetry Suppression

During scrub, live telemetry from the event WebSocket (`/ws/events`) is suppressed from updating the Zustand store:
```typescript
AppState.subscribe('assets.telemetry', (asset: Asset) => {
    if (store.getState().historicalState.active) return;  // suppress during scrub
    guarded(() => store.getState().updateAsset(asset));
});
```

## Files Changed

### Backend (New)
- `backend/app/services/target_service.py` — Aimpoint/Target CRUD with EventBus
- `backend/app/services/snapshot_service.py` — Snapshot capture + state reconstruction
- `backend/app/api/targets.py` — Target REST endpoints
- `backend/app/api/aimpoints.py` — Aimpoint REST endpoints

### Backend (Modified)
- `backend/app/domain/enums.py` — AimpointType, TargetState enums
- `backend/app/domain/models.py` — Aimpoint, Target models; TaskTarget.target_id/aimpoint_id
- `backend/app/persistence/database.py` — aimpoints, targets, domain_snapshots tables
- `backend/app/persistence/repositories.py` — AimpointRepo, TargetRepo, SnapshotRepo
- `backend/app/dependencies.py` — Wire new repos/services
- `backend/app/api/router.py` — Register new routes
- `backend/app/api/timeline.py` — /state and /range endpoints
- `backend/app/api/ws.py` — Aimpoints/targets in WS initial snapshot
- `backend/app/api/tasks.py` — Accept target_id/aimpoint_id
- `backend/app/config.py` — SNAPSHOT_INTERVAL_SEC, SNAPSHOT_RETENTION_HOURS
- `backend/app/adapters/playback_adapter.py` — Event log replay
- `backend/main.py` — Snapshot capture/prune loop

### Frontend (Modified)
- `frontend/app.js` — ConstantPositionProperty rendering, single scrub path, tether fix, aimpoint/target Cesium sync, removed scrubToSnapshot system
- `frontend/panels/timeline-panel.js` — _applyHistoricalState, _doHistoricalFetch, backend range display
- `frontend/state.js` — Aimpoint/target Maps, event handling
- `frontend/index.html` — Cache busters
- `frontend/app/store/types.ts` — Aimpoint, Target, HistoricalSnapshot interfaces
- `frontend/app/store/appStore.ts` — Aimpoint/target state + actions, historicalState
- `frontend/app/store/selectors.ts` — useAimpointList, useTargetList
- `frontend/app/services/apiClient.ts` — Aimpoint/target/historical API methods
- `frontend/app/store/adapters/legacyAppStateBridge.ts` — Aimpoint/target bridging, telemetry suppression
- `frontend/app/store/adapters/cesiumBridge.ts` — Historical mode restore-on-exit
- `frontend/app/bootstrap/main.tsx` — Expose store, init historical mode
- `frontend/app/panels/targets/TargetsPanel.tsx` — Store-driven, API CRUD, renamed labels
- `frontend/app/components/SearchBar.tsx` — Search from store
