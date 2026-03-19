---
phase: 00-foundation-react-migration
plan: "02"
subsystem: frontend-react
tags: [react, typescript, cesium, websocket, zustand, vite]
dependency_graph:
  requires:
    - phase: 00-01
      provides: "Zustand store with setSimData, addAssistantMessage, setCachedCoas, setConnected actions"
  provides: [P0-WS, P0-CESIUM]
  affects: [00-03, 00-04, 00-05, all plans needing sendMessage or viewerRef]
tech_stack:
  added: []
  patterns:
    - "useWebSocket: WS→Zustand bridge hook, no DOM events, sendMessage via useCallback"
    - "useCesiumViewer: ref-based Viewer lifecycle hook, returns viewerRef for child hooks"
    - "ViewerContext: React context for passing viewerRef down to Cesium entity hooks"
    - "WebSocketContext: app-level context exposing sendMessage without prop drilling"
key_files:
  created:
    - src/frontend-react/src/hooks/useWebSocket.ts
    - src/frontend-react/src/hooks/useCesiumViewer.ts
    - src/frontend-react/src/cesium/CesiumContainer.tsx
    - src/frontend-react/src/shared/api.ts
  modified:
    - src/frontend-react/src/App.tsx
decisions:
  - "window.location.hostname instead of hardcoded localhost: Vite dev proxy works transparently"
  - "Null-guard sun/moon/skyAtmosphere: Cesium types allow undefined in some configurations"
  - "ViewerContext default is { current: null } not null: avoids null-check in every consumer"
  - "WebSocketContext at App root: mirrors vanilla JS global state.ws pattern without globals"

requirements-completed: [P0-WS, P0-CESIUM]

metrics:
  duration: "~2min"
  completed_date: "2026-03-19"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 00 Plan 02: WebSocket Hook, Cesium Viewer Lifecycle, and App Layout

**Live WS→Zustand pipeline and Cesium globe with dark CARTO tiles wired into flex App layout via context providers.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-19
- **Completed:** 2026-03-19
- **Tasks:** 2/2
- **Files modified:** 5 (4 created, 1 updated)

## Accomplishments

- `useWebSocket` hook replaces vanilla `connectWebSocket()` — dispatches all 3 message types directly to Zustand, no DOM events
- `useCesiumViewer` hook creates Viewer with identical settings to `map.js` lines 8-57: same tiles, clock, sky atmosphere, fog
- `CesiumContainer` mounts Viewer via ref, exports `ViewerContext` for downstream entity hooks (Plans 03-05)
- `App` wires both hooks at root level and exposes `WebSocketContext` / `useSendMessage` for the whole component tree

## Task Commits

Each task was committed atomically:

1. **Task 1: useWebSocket, useCesiumViewer, api.ts** - `5d23ec8` (feat)
2. **Task 2: CesiumContainer + App layout** - `8ba6aeb` (feat)

## Files Created/Modified

- `src/frontend-react/src/hooks/useWebSocket.ts` — WS→Zustand bridge; auto-reconnect at 1s; handles state/ASSISTANT_MESSAGE/HITL_UPDATE
- `src/frontend-react/src/hooks/useCesiumViewer.ts` — Viewer lifecycle; exact map.js settings; cleans up on unmount
- `src/frontend-react/src/cesium/CesiumContainer.tsx` — Mounts viewer into div ref; provides ViewerContext and useViewerRef
- `src/frontend-react/src/shared/api.ts` — fetchTheaters + switchTheater typed wrappers for Vite proxy
- `src/frontend-react/src/App.tsx` — Flex layout; useWebSocket at root; WebSocketContext + useSendMessage exports

## Decisions Made

- `window.location.hostname` instead of hardcoded `localhost` — Vite dev proxy handles `ws://<host>:8000/ws` transparently in all environments
- Added null-guards for `sun`, `moon`, `skyAtmosphere` — Cesium types allow undefined in some non-standard viewer configs; defensive is safer
- `ViewerContext` default is `{ current: null }` (not `null`) — consumers can call `.current` without null-checking the ref itself
- `WebSocketContext` at App root — mirrors vanilla JS `state.ws` global pattern but React-idiomatic; zero prop drilling

## Deviations from Plan

### Prior-Session Work

**Task 1 files and Task 2 files were pre-created in a prior session**
- `useWebSocket.ts`, `useCesiumViewer.ts`, and `api.ts` were committed as `5d23ec8` before this execution session
- `CesiumContainer.tsx` and `App.tsx` (Task 2) existed on disk but were uncommitted
- This execution session verified all files matched spec, then committed Task 2 work (`8ba6aeb`)
- No re-work required — files were correct on disk

**Total deviations:** 0 auto-fixes needed — all plan content was already correctly implemented.

## Issues Encountered

None — TypeScript type-check passed with zero errors. Both commits clean.

## Self-Check: PASSED

Files verified:
- FOUND: src/frontend-react/src/hooks/useWebSocket.ts
- FOUND: src/frontend-react/src/hooks/useCesiumViewer.ts
- FOUND: src/frontend-react/src/cesium/CesiumContainer.tsx
- FOUND: src/frontend-react/src/shared/api.ts
- FOUND: src/frontend-react/src/App.tsx

Commits verified:
- FOUND: 5d23ec8 (Task 1)
- FOUND: 8ba6aeb (Task 2)

## Next Phase Readiness

- `viewerRef` accessible via `useViewerRef()` in any component under `<CesiumContainer>` — ready for Plans 03-05 entity hooks
- `sendMessage` accessible via `useSendMessage()` anywhere under `<App>` — ready for drone control commands
- `useSimStore` populated from live WS data each tick — ready for reactive UI components
- No blockers for Plan 03 (drone entity rendering)

---
*Phase: 00-foundation-react-migration*
*Completed: 2026-03-19*
