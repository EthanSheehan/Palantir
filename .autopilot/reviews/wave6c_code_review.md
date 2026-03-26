# Wave 6C-Alpha Frontend Code Review

**Reviewer:** Code Reviewer agent (Sonnet 4.6)
**Date:** 2026-03-26
**Scope:** All new and modified frontend files from Wave 6C-Alpha

---

## Summary

7 new files, 5 modified files reviewed. No CRITICAL issues found. 2 HIGH, 6 MEDIUM, 4 LOW issues identified.

---

## HIGH Issues

### HIGH-1: CommandPalette imported but never rendered or wired
**File:** `src/frontend-react/src/App.tsx:10`

`CommandPalette` is imported but there is no `paletteOpen` state, no keyboard trigger (e.g. Ctrl+K / Cmd+K), and no `<CommandPalette />` JSX in the component tree. The component is completely dead code — it will never appear to the user.

**Fix:** Add open state and trigger in App.tsx:
```tsx
const [paletteOpen, setPaletteOpen] = useState(false);

// In the keydown handler:
if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
  e.preventDefault();
  setPaletteOpen(v => !v);
  return;
}

// In JSX (outside the main layout div, alongside DetailMapDialog):
<CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
```

---

### HIGH-2: `useEffect` without dependency array runs on every render (ConnectionStatus)
**File:** `src/frontend-react/src/components/ConnectionStatus.tsx:29–46`

The `useEffect` at line 29 has no dependency array, so it fires on every single render of the component. The intent is to measure inter-tick latency, but this runs on ALL renders (prop changes, context re-renders, etc.), not just on store updates. This will produce noisy false latency readings and cause unnecessary re-renders via `setAvgLatency`.

**Fix:** Depend on the store state that represents a "new tick" — e.g. subscribe to a tick counter or a specific changing field, or attach a dependency so it only runs when the connection state or a tick-marker changes:
```tsx
const tickMarker = useSimStore(s => s.lastTickTime); // or any field that updates per tick

useEffect(() => {
  // latency measurement logic
}, [connected, tickMarker]);
```

If no tick counter exists in the store, consider adding one. The current pattern conflates "component render" with "WebSocket tick" — they are not the same.

---

## MEDIUM Issues

### MEDIUM-1: AutonomyBriefingDialog ROE values are hardcoded
**File:** `src/frontend-react/src/panels/mission/AutonomyBriefingDialog.tsx:143–148`

The ROE block displays `"Rules of Engagement: WEAPONS FREE (verified targets only)"` and `"Min confidence threshold: 75%"` as static strings, regardless of the actual backend ROE state. If the ROE changes (different theater, different scenario), this dialog will show stale/incorrect information to the operator before they confirm autonomous mode.

**Fix:** Read ROE from the store (add a `roe` field if not present) or at minimum display a warning that the displayed ROE may not reflect current configuration.

---

### MEDIUM-2: EngagementHistory outcome is always hardcoded to DESTROYED or PENDING
**File:** `src/frontend-react/src/panels/assessment/EngagementHistory.tsx:67`

```ts
outcome: ev.action === 'engagement_result' ? 'DESTROYED' : 'PENDING',
```

The `outcome` field is binary — any `engagement_result` event becomes `DESTROYED`, everything else is `PENDING`. The `EngagementRecord` type defines `'DAMAGED' | 'MISSED'` outcomes, but they are never produced. The backend likely sends outcome data in the event payload that is being ignored.

**Fix:** Map the actual backend outcome field from `ev` payload (e.g. `ev.outcome` or similar) to the display enum, with DESTROYED as fallback.

---

### MEDIUM-3: CommandPalette sets AUTONOMOUS without briefing dialog
**File:** `src/frontend-react/src/overlays/CommandPalette.tsx:88–93`

The `autonomy-autonomous` command directly sends `{ action: 'set_autonomy_level', level: 'AUTONOMOUS' }` without going through the `AutonomyBriefingDialog` confirmation flow. This bypasses the safety gate intentionally introduced in `AutonomyToggle.tsx`.

**Fix:** Either remove the AUTONOMOUS option from CommandPalette, or route it through the same briefing flow:
```ts
action: () => {
  // cannot open Dialog from here directly — emit a custom event or call a store action
  window.dispatchEvent(new CustomEvent('palantir:openAutonomyBriefing'));
},
```

---

### MEDIUM-4: Category header logic in CommandPalette is overly complex and buggy
**File:** `src/frontend-react/src/overlays/CommandPalette.tsx:258–264`

The `showCategoryHeader` ternary is nested three levels deep and references `filtered[i-1]` without checking bounds (though `i===0` is handled). More critically, the logic conflates "query mode" and "history mode" in a way that can produce duplicate or missing section headers — e.g., if a history item and a non-history item share the same category, you'll get a header mid-section.

**Fix:** Separate the two rendering modes (history vs. searched) into distinct render paths with clear logic. At minimum, simplify the ternary into a readable helper function.

---

### MEDIUM-5: `nvis.css` — aggressive `!important` override on `background` via attribute selector
**File:** `src/frontend-react/src/styles/nvis.css:32–35`

```css
body.nvis-mode [style*="background: #"],
body.nvis-mode [style*="background:#"] {
  background: var(--nvis-surface) !important;
}
```

This selects ANY element with an inline `background` hex style and overrides it with the NVIS surface color. This will break the Cesium canvas overlays (range rings, entity labels, coverage layers) that use inline background styles, as well as colored status indicators (threat level, confidence bars, BDA bars) where the hex color is semantically meaningful. The Cesium exclusion in the universal rule above only covers `canvas` and `.cesium-viewer *`, not inline-styled divs rendered by Cesium hooks.

**Fix:** Narrow the selector to known UI component classes (`.bp5-card`, `[class*="Panel"]`, etc.) rather than all inline-styled elements, or add data attributes to UI containers and scope to those.

---

### MEDIUM-6: KillChainRibbon — state matching uses `includes()` which can produce false positives
**File:** `src/frontend-react/src/overlays/KillChainRibbon.tsx:32–35`

```ts
phase.states.some(s => t.state?.toUpperCase().includes(s))
```

Using `includes` instead of exact equality means a target state of `"ASSESSED"` would match both the `ASSESS` phase (states: `['ASSESSED', 'BDA']`) and hypothetically any phase whose state string is a substring. More importantly, `'VERIFIED'` is a substring of no other state in this list, but `'ENGAGING'` includes `'ENGAGE'` — meaning a target in `ENGAGING` state would match the `ENGAGE` phase via `includes('ENGAGED')` only if `ENGAGING` contains `ENGAGED`, which it does not. This is currently safe, but fragile.

**Fix:** Use exact equality or a Set lookup:
```ts
const stateSet = new Set(phase.states);
result[phase.key] = targets.filter(t => stateSet.has(t.state?.toUpperCase() ?? '')).length;
```

---

## LOW Issues

### LOW-1: AutonomyBriefingDialog `understood` reset on cancel is redundant
**File:** `src/frontend-react/src/panels/mission/AutonomyBriefingDialog.tsx:37–39`

`setUnderstood(false)` in `handleCancel` is redundant because the Dialog will re-mount or the state resets on the next open via `useState(false)`. However, it IS correctly needed in `handleConfirm` because the parent re-renders without unmounting. This is acceptable but inconsistent — could cause momentary stale state if the dialog is re-opened before React reconciles. Document the intent or move reset to an `onClose` handler.

---

### LOW-2: EngagementHistory `bdaConfidence` uses `detection_confidence` as a proxy
**File:** `src/frontend-react/src/panels/assessment/EngagementHistory.tsx:64`

`bdaConfidence: entry?.detection_confidence ?? 0.5` uses detection confidence (a pre-engagement value) as a stand-in for BDA confidence (a post-engagement value). These are semantically different. The fallback of `0.5` will silently show a yellow BDA bar for all entries without a matched strike board entry.

**Fix:** If the backend sends actual BDA confidence in the command event, use that. Otherwise, note this is a proxy in a comment so future developers don't mistake it for real BDA data.

---

### LOW-3: MapLegend hint text says "L to close" but L also opens it
**File:** `src/frontend-react/src/overlays/MapLegend.tsx:140`

The hint text `"L to close"` is only visible when the legend is open, which is correct — but the same key opens it. This is fine UX, but the text could say `"L to toggle"` to be more accurate and avoid confusion for operators seeing it for the first time.

---

### LOW-4: `accessibility.css` `data-status` attributes not set on the ConnectionStatus dot
**File:** `src/frontend-react/src/styles/accessibility.css:41–51` vs `src/frontend-react/src/components/ConnectionStatus.tsx:53–60`

The accessibility CSS uses `[data-status="connected"]` and `[data-status="disconnected"]` selectors to add shape redundancy (outline) for colorblind mode. However, the ConnectionStatus indicator dot has no `data-status` attribute — it just sets inline `background` color. The colorblind CSS rules will never fire for this component.

**Fix:** Add `data-status={connected ? 'connected' : 'disconnected'}` to the dot `<div>`.

---

## Positive Notes

- **KillChainRibbon**: Clean, well-structured; `useMemo` correctly avoids recomputing on every render; good use of `phaseColor` to encode alert level.
- **MapLegend**: Proper conditional render (returns null, no layout thrashing). `ShapeIcon` exhaustively handles all shape variants including `null` return for unexpected values.
- **AutonomyBriefingDialog**: The two-gate pattern (checkbox + confirm button) is good UX for a safety-critical confirmation. Using `Intent.DANGER` for the confirm button is appropriate.
- **StrikeBoard batch actions**: Correct use of `Alert` for destructive confirmation. Pending action state correctly cleared after confirm.
- **nvis.css phosphor glow**: The `text-shadow` approach for phosphor glow is elegant and does not affect layout.
- **CommandPalette**: Keyboard navigation (ArrowUp/Down/Enter/Escape), `scrollIntoView`, and history persistence via localStorage are all well-implemented.

---

## File-Level Summary

| File | Status | Issues |
|------|--------|--------|
| `KillChainRibbon.tsx` | Minor | MEDIUM-6 |
| `ConnectionStatus.tsx` | Needs fix | HIGH-2 |
| `MapLegend.tsx` | Good | LOW-3 |
| `EngagementHistory.tsx` | Needs fix | MEDIUM-2, LOW-2 |
| `AutonomyBriefingDialog.tsx` | Needs fix | MEDIUM-1, LOW-1 |
| `CommandPalette.tsx` | Needs fix | HIGH-1, MEDIUM-3, MEDIUM-4 |
| `nvis.css` | Needs fix | MEDIUM-5 |
| `accessibility.css` | Minor | LOW-4 |
| `App.tsx` | Needs fix | HIGH-1 (missing render) |
| `AutonomyToggle.tsx` | Good | — |
| `StrikeBoard.tsx` | Good | — |
| `AssessmentTab.tsx` | Good | — |
| `CesiumContainer.tsx` | Good | — |
