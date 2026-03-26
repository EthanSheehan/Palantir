# Wave 6C-Beta: Global Alert Center + Floating Strike Board

## Status: COMPLETE

## Files Created

### `src/frontend-react/src/overlays/GlobalAlertCenter.tsx` (new, ~220 lines)
- Floating overlay component with a badge button (bottom-right corner, z-index 8900)
- Badge shows unread alert count; glows red when alerts are present
- Expandable panel shows last 20 critical alerts
- Alert types: NOMINATION, ENGAGEMENT, TRANSITION, CONNECTION, CRITICAL
- Auto-dismisses non-critical alerts after 10s via setInterval
- Sources:
  - `strikeBoard` — fires NOMINATION alert when new PENDING entries appear
  - `commandEvents` — fires ENGAGEMENT alert on `authorize_coa` / `approve_nomination`
  - `pendingTransitions` — fires TRANSITION alert when UAVs await mode transitions
  - `connected` — fires CONNECTION alert on drop/restore
- Each alert has optional action button that navigates to a sidebar tab (via `setActiveTab`)
- "Clear all" button in header
- Keyboard shortcut hint in footer

### `src/frontend-react/src/overlays/FloatingStrikeBoard.tsx` (new, ~170 lines)
- Detachable overlay showing PENDING nominations with countdown timer (top-right, z-index 8800)
- `NominationRow` component: per-entry 5-minute countdown timer via `useCountdown` hook
- Timer color: green (>2min), yellow (<2min), red (<1min)
- APPROVE / REJECT / RETASK buttons on each pending entry send WebSocket messages
- Resolved entries (last 6) shown in compact "Recent" section
- Header badge shows pending count, highlights amber when nominations exist
- Empty state message when no strike packages

## Files Modified

### `src/frontend-react/src/App.tsx`
- Added imports for `GlobalAlertCenter` and `FloatingStrikeBoard`
- Added `alertCenterVisible` and `strikeBoardVisible` state
- Added keyboard shortcuts: `G` toggles alert center, `B` toggles floating strike board
- Rendered both overlays outside `WebSocketContext.Provider` (same pattern as `CommandPalette`)

## Design Decisions
- `GlobalAlertCenter` badge uses z-index 8900, `FloatingStrikeBoard` uses 8800 (below alert center)
- No modifications to `SimulationStore.ts` — reads existing `strikeBoard`, `commandEvents`, `pendingTransitions`, `connected` fields
- Alert deduplication via `prevPendingCount` / `prevCommandCount` refs
- Immutable patterns throughout — all state updates use spread/filter/map
- Blueprint `Button` and `Tag` used for interactive elements; plain `<button>` for dismiss icons
