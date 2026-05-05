# Wave 6C-Alpha Frontend Review Fixes

## Summary

All HIGH and MEDIUM issues from Wave 6C-Alpha reviews addressed. Items 1-3 were already fixed in the codebase; items 4-10 required code changes.

---

## Already Fixed (no changes needed)

### Fix 1 — Code HIGH-1: CommandPalette wiring in App.tsx
**Status:** Already complete.
`paletteOpen` state, Ctrl+K keydown handler, and `<CommandPalette isOpen={paletteOpen} onClose={...} />` were all present at lines 26, 68-72, and 109 of `App.tsx`.

### Fix 2 — Security H-2: grid_sentinel:send event bridge allowlist
**Status:** Already complete.
`App.tsx` lines 31-44 already contain an `ALLOWED_ACTIONS` Set with `move_drone`, `scan_area`, `follow_target`, `paint_target`, `intercept_target`, `intercept_enemy`, `cancel_track`, `request_swarm`, `release_swarm`, `verify_target`. Unauthorized actions are silently dropped.

### Fix 3 — Code HIGH-2: ConnectionStatus useEffect dependency array
**Status:** Already complete.
`ConnectionStatus.tsx` already uses `useSimStore(s => s.targets?.length ?? 0)` as `tickCount` and the `useEffect` dep array is `[connected, tickCount]` (lines 32-49).

---

## Changes Made

### Fix 4 — Security M-1 / Code MEDIUM-3: CommandPalette AUTONOMOUS bypasses safety gate
**Files changed:**
- `src/frontend-react/src/overlays/CommandPalette.tsx`
- `src/frontend-react/src/panels/mission/AutonomyToggle.tsx`

**Changes:**
- CommandPalette AUTONOMOUS command now dispatches `window.dispatchEvent(new CustomEvent('grid_sentinel:openAutonomyBriefing'))` instead of calling `onClose()` directly
- AutonomyToggle adds a `useEffect` that listens for `grid_sentinel:openAutonomyBriefing` and sets `briefingOpen(true)`, routing through the existing confirmation dialog

### Fix 5 — Code MEDIUM-6: KillChainRibbon uses includes() — replaced with Set
**File changed:** `src/frontend-react/src/overlays/KillChainRibbon.tsx`

**Change:** Replaced `phase.states.some(s => t.state?.toUpperCase().includes(s))` with `new Set(phase.states)` per-phase and `stateSet.has(t.state?.toUpperCase() ?? '')`. Prevents partial string matches (e.g. "ASSESSED" matching "ASSESS") and improves lookup performance.

### Fix 6 — Security M-3: useWebSocket JSON.parse try/catch
**File changed:** `src/frontend-react/src/hooks/useWebSocket.ts`

**Change:** Wrapped `JSON.parse(event.data)` in try/catch. On parse failure, logs `console.error('WebSocket: malformed message', err)` and returns early, preventing unhandled exceptions from malformed server messages.

### Fix 7 — Security I-3: ws:// hardcoded scheme
**File changed:** `src/frontend-react/src/hooks/useWebSocket.ts`

**Change:** Added `const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';` before the WebSocket constructor. Connection URL is now `${scheme}://${window.location.hostname}:8000/ws`, supporting TLS deployments.

### Fix 8 — Security M-4: CesiumContextMenu nomination confirmation
**File changed:** `src/frontend-react/src/cesium/CesiumContextMenu.tsx`

**Change:** Added `window.confirm(`Confirm nomination for target ${numericId}?`)` guard before sending `approve_nomination`. If the operator cancels, the action is not sent and the menu stays open.

### Fix 9 — Code MEDIUM-2: EngagementHistory hardcoded outcome
**File changed:** `src/frontend-react/src/panels/assessment/EngagementHistory.tsx`

**Change:** Outcome now reads `(ev as Record<string, unknown>).outcome` from the event payload when `ev.action === 'engagement_result'`, falling back to `'DESTROYED'` only if the field is absent. For non-result events, outcome remains `'PENDING'`.

### Fix 10 — Code LOW-4: ConnectionStatus data-status attribute
**File changed:** `src/frontend-react/src/components/ConnectionStatus.tsx`

**Change:** Added `data-status={connected ? 'connected' : 'disconnected'}` to the indicator dot `<div>`. Enables CSS selectors and automated test assertions to check connection state.

---

## TypeScript Build Check

`node_modules` is not installed in the frontend directory (no npm install run), so `tsc --noEmit` could not be executed. All edits were verified to be syntactically correct via manual review.

---

## Files Changed

| File | Issues Fixed |
|------|-------------|
| `src/frontend-react/src/overlays/CommandPalette.tsx` | Fix 4 |
| `src/frontend-react/src/panels/mission/AutonomyToggle.tsx` | Fix 4 |
| `src/frontend-react/src/overlays/KillChainRibbon.tsx` | Fix 5 |
| `src/frontend-react/src/hooks/useWebSocket.ts` | Fix 6, Fix 7 |
| `src/frontend-react/src/cesium/CesiumContextMenu.tsx` | Fix 8 |
| `src/frontend-react/src/panels/assessment/EngagementHistory.tsx` | Fix 9 |
| `src/frontend-react/src/components/ConnectionStatus.tsx` | Fix 10 |
