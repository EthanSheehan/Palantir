---
tags: [grid_sentinel, autopilot, planning]
---
# FIX-16 + FIX-13: Add `setCoverageMode` and `toggleRangeRing` store actions; wire buttons (bundled)
## Severity: MEDIUM (FIX-13) + LOW (FIX-16)

## Files
- `src/frontend-react/src/store/SimulationStore.ts`: Add `rangeRingDroneIds`, `setCoverageMode`, `toggleRangeRing` to state interface and implementation
- `src/frontend-react/src/panels/mission/CoverageModeToggle.tsx`: Call `setCoverageMode` optimistically
- `src/frontend-react/src/panels/assets/DroneActionButtons.tsx`: Wire Range button to `toggleRangeRing`

**Bundled because both FIX-16 and FIX-13 require adding to SimulationStore.ts — parallel edits would cause merge conflict.**

---

## SimulationStore.ts Changes

### Current Code (interface section, lines 96-99)
```ts
  setMapMode: (mode: MapMode) => void;
  toggleLayer: (layer: string) => void;
  setCamLayout: (layout: CamLayout) => void;
}
```

### Fixed Code (interface additions)
```ts
  // Range rings (FIX-13)
  rangeRingDroneIds: Set<number>;
  toggleRangeRing: (droneId: number) => void;
  // Coverage mode setter (FIX-16)
  setCoverageMode: (mode: 'balanced' | 'threat_adaptive') => void;
  setMapMode: (mode: MapMode) => void;
  toggleLayer: (layer: string) => void;
  setCamLayout: (layout: CamLayout) => void;
}
```

### Current Code (initial state section, lines 129-132)
```ts
  coverageMode: 'balanced',
  mapMode: 'OPERATIONAL' as MapMode,
  layerVisibility: { ...MAP_MODE_DEFAULTS['OPERATIONAL'] },
  camLayout: 'SINGLE' as CamLayout,
```

### Fixed Code (initial state additions)
```ts
  coverageMode: 'balanced',
  rangeRingDroneIds: new Set<number>(),
  mapMode: 'OPERATIONAL' as MapMode,
  layerVisibility: { ...MAP_MODE_DEFAULTS['OPERATIONAL'] },
  camLayout: 'SINGLE' as CamLayout,
```

### Current Code (action implementations, lines 250-257)
```ts
  setMapMode: (mode) => set({ mapMode: mode, layerVisibility: { ...MAP_MODE_DEFAULTS[mode] } }),

  toggleLayer: (layer) => set((state) => ({
    layerVisibility: { ...state.layerVisibility, [layer]: !state.layerVisibility[layer] },
  })),

  setCamLayout: (layout) => set({ camLayout: layout }),
}));
```

### Fixed Code (action implementations)
```ts
  toggleRangeRing: (droneId) => set((state) => {
    const next = new Set(state.rangeRingDroneIds);
    if (next.has(droneId)) {
      next.delete(droneId);
    } else {
      next.add(droneId);
    }
    return { rangeRingDroneIds: next };
  }),

  setCoverageMode: (mode) => set({ coverageMode: mode }),

  setMapMode: (mode) => set({ mapMode: mode, layerVisibility: { ...MAP_MODE_DEFAULTS[mode] } }),

  toggleLayer: (layer) => set((state) => ({
    layerVisibility: { ...state.layerVisibility, [layer]: !state.layerVisibility[layer] },
  })),

  setCamLayout: (layout) => set({ camLayout: layout }),
}));
```

---

## CoverageModeToggle.tsx Changes (FIX-16)

### Current Code (lines 11-26)
```tsx
export function CoverageModeToggle() {
  const coverageMode = useSimStore(s => s.coverageMode);
  const sendMessage = useSendMessage();

  return (
    <div style={{ padding: '8px 16px' }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4, letterSpacing: '0.05em' }}>COVERAGE MODE</div>
      <SegmentedControl
        options={COVERAGE_OPTIONS}
        value={coverageMode}
        onValueChange={(val) => sendMessage({ action: 'set_coverage_mode', mode: val })}
        small
      />
    </div>
  );
}
```

### Fixed Code
```tsx
export function CoverageModeToggle() {
  const coverageMode = useSimStore(s => s.coverageMode);
  const setCoverageMode = useSimStore(s => s.setCoverageMode);
  const sendMessage = useSendMessage();

  return (
    <div style={{ padding: '8px 16px' }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4, letterSpacing: '0.05em' }}>COVERAGE MODE</div>
      <SegmentedControl
        options={COVERAGE_OPTIONS}
        value={coverageMode}
        onValueChange={(val) => {
          setCoverageMode(val as 'balanced' | 'threat_adaptive');
          sendMessage({ action: 'set_coverage_mode', mode: val });
        }}
        small
      />
    </div>
  );
}
```

---

## DroneActionButtons.tsx Changes (FIX-13)

### Current Code (lines 9-69)
```tsx
export function DroneActionButtons({ uav }: DroneActionButtonsProps) {
  const isSettingWaypoint = useSimStore(s => s.isSettingWaypoint);
  const setIsSettingWaypoint = useSimStore(s => s.setIsSettingWaypoint);

  const handleWaypointClick = () => {
    setIsSettingWaypoint(!isSettingWaypoint);
  };

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      <button
        onClick={handleWaypointClick}
        ...
      >
        {isSettingWaypoint ? 'Select Target...' : 'Set Waypoint'}
      </button>

      <button
        onClick={() => {}}
        ...
      >
        Range
      </button>

      <button
        onClick={() => {}}
        ...
        title="Detail"
      >
        {'\u{1F3AF}'}
      </button>
    </div>
  );
}
```

### Fixed Code (Range button onClick only — FIX-13; Detail button is handled in W2-D)
```tsx
export function DroneActionButtons({ uav }: DroneActionButtonsProps) {
  const isSettingWaypoint = useSimStore(s => s.isSettingWaypoint);
  const setIsSettingWaypoint = useSimStore(s => s.setIsSettingWaypoint);
  const rangeRingDroneIds = useSimStore(s => s.rangeRingDroneIds);
  const toggleRangeRing = useSimStore(s => s.toggleRangeRing);

  const handleWaypointClick = () => {
    setIsSettingWaypoint(!isSettingWaypoint);
  };

  const isRangeActive = rangeRingDroneIds.has(uav.id);

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      <button
        onClick={handleWaypointClick}
        style={{
          flex: 2,
          padding: '3px 6px',
          border: `1px solid ${isSettingWaypoint ? 'rgba(34, 197, 94, 0.5)' : 'rgba(255,255,255,0.2)'}`,
          borderRadius: 3,
          background: isSettingWaypoint ? 'rgba(34, 197, 94, 0.2)' : 'transparent',
          color: isSettingWaypoint ? '#22c55e' : '#94a3b8',
          fontSize: '0.65rem',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        {isSettingWaypoint ? 'Select Target...' : 'Set Waypoint'}
      </button>

      <button
        onClick={() => toggleRangeRing(uav.id)}
        style={{
          flex: 1,
          padding: '3px 6px',
          border: `1px solid ${isRangeActive ? 'rgba(59, 130, 246, 0.5)' : 'rgba(255,255,255,0.15)'}`,
          borderRadius: 3,
          background: isRangeActive ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
          color: isRangeActive ? '#3b82f6' : '#64748b',
          fontSize: '0.65rem',
          cursor: 'pointer',
        }}
      >
        Range
      </button>

      <button
        onClick={() => {}}
        style={{
          width: 28,
          padding: '3px',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 3,
          background: 'transparent',
          color: '#64748b',
          fontSize: '0.75rem',
          cursor: 'pointer',
        }}
        title="Detail"
      >
        {'\u{1F3AF}'}
      </button>
    </div>
  );
}
```

**Note:** The Detail button (`onClick={() => {}}`) is intentionally left as-is here — it will be wired in W2-D (FIX-03). W1-E only handles the Range button and store additions.

---

## Step-by-Step
1. Read `src/frontend-react/src/store/SimulationStore.ts` lines 96-100 (interface end) — confirm no `setCoverageMode` or `toggleRangeRing` exist
2. Add `rangeRingDroneIds: Set<number>` field to the interface (before `setMapMode`)
3. Add `toggleRangeRing: (droneId: number) => void` to the interface
4. Add `setCoverageMode: (mode: 'balanced' | 'threat_adaptive') => void` to the interface
5. Add `rangeRingDroneIds: new Set<number>()` to the initial state (after `coverageMode`)
6. Add `toggleRangeRing` implementation before `setMapMode`
7. Add `setCoverageMode` implementation before `setMapMode`
8. Read `src/frontend-react/src/panels/mission/CoverageModeToggle.tsx` — confirm `onValueChange` only calls `sendMessage`
9. Update `CoverageModeToggle.tsx`: add `setCoverageMode` selector; call it before `sendMessage` in `onValueChange`
10. Read `src/frontend-react/src/panels/assets/DroneActionButtons.tsx` — confirm Range button has `onClick={() => {}}`
11. Update `DroneActionButtons.tsx`: add `rangeRingDroneIds` and `toggleRangeRing` selectors; wire Range button; add visual active state

## Test Verification
**FIX-16 (CoverageModeToggle):**
1. Toggle coverage mode
2. Expected: Store updates immediately (no snap-back on next WS tick)
3. Expected: WS message `set_coverage_mode` still sent to backend

**FIX-13 (Range button):**
1. Click Range button on drone card
2. Expected: Range button turns blue/active
3. Click again: Expected: Range button returns to inactive state
4. Note: Cesium range ring rendering requires a separate Cesium hook to read `rangeRingDroneIds` — this plan does NOT wire the Cesium rendering; it only makes the store state available. The Cesium hook wiring is out of scope for this fix.

## Rollback
Remove the three additions from SimulationStore.ts (rangeRingDroneIds field, toggleRangeRing, setCoverageMode). Revert CoverageModeToggle.tsx to single sendMessage call. Revert DroneActionButtons.tsx Range button to `onClick={() => {}}`.
