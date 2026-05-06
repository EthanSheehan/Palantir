---
tags: [grid_sentinel, grid_sentinel_2, port_status]
---
# grid-sentinel-2 Incremental Port Status

**Date:** 2026-05-06

## Background

`grid-sentinel-2` (formerly `ams-grid-2`) is an orphan rebuild of the frontend (no shared ancestry with `main`, ~257 commits). Its top-level layout is `frontend/` plus a separate `backend/`. Per the planning decision recorded in `claude/plans/implement-planned-upgrades-for-cosmic-bachman.md`, features are being ported **incrementally** into the existing `src/frontend-react/` rather than swapped wholesale.

## What's already been ported (commits already on `main`/`worker/edith`)

The "AMS integration" commit series already brought these into `src/frontend-react/`:

- `1a71800 feat: add SearchBar component with flyTo camera bridge` — `src/frontend-react/src/components/SearchBar.tsx`
- `2568e2c feat: add 3D trajectory trails behind drones`
- `a2ad318 feat: add satellite lens inset viewer + drone launch phase animation` — `useSatelliteLens.ts`
- `2192f90 feat: add multi-UAV selection, workspace modes, and layout persistence` — `WorkspaceMode = 'isr' | 'plan'` in `store/types.ts:232`
- `17b66e3 feat: add ops alerts panel and planned targets with REST API` — `OpsAlertsPanel`, `PlannedTargetsPanel`, `target_store.py`, `ops_alerts.py`
- `ed4fe96 feat: add timeline scrub dock + launcher theater config` — `BottomTimelineDock.tsx`
- `182492c feat: add timeline scrub + historical playback (AMS Wave 4A)`
- `d055eb7 feat: add launcher integration with Cesium map entities and WebSocket launch action` — `useCesiumLaunchers.ts`, launcher assets
- Blueprint.js dependency was already wired — `@blueprintjs/core ^5.13`, `@blueprintjs/icons ^5.14`, `@blueprintjs/select ^5.3` in `src/frontend-react/package.json`

## What's still NOT ported

These layout-chrome components from `grid-sentinel-2` are not present on `main`:

| Source on `grid-sentinel-2` | Description | Risk |
|------|-------------|------|
| `frontend/app/layout/VerticalTaskbar.tsx` (+ .css, ~117 lines) | Vertical-rail taskbar with File/View popovers and ISR/Plan tab buttons | Low — additive component; existing `panels/Sidebar.tsx` already exposes ISR/Plan switching, so the new component is a parallel UI surface, not a replacement |
| `frontend/app/layout/TopCommandBar.tsx` | Header-area command bar | Low — additive |
| `frontend/app/layout/LeftRail.tsx` | Left navigation rail | Medium — overlaps with existing `Sidebar.tsx` |
| `frontend/app/layout/RightInspectorDrawer.tsx` | Right-side inspector drawer | Medium — overlaps with the per-tab inspector content already in `Sidebar.tsx` |
| `frontend/app/layout/WorkspaceLayout.tsx` | Top-level workspace shell | High — restructures app layout root; would touch `App.tsx` |
| `frontend/app/panels/macrogrid/MacrogridPanel.tsx` | Macro-grid theater overview | Low — net-new panel |
| `frontend/app/panels/missions/MissionsPanel.tsx` | Missions panel | Low — net-new panel |
| `frontend/app/panels/inspector/InspectorPanel.tsx` | Inspector panel | Medium — overlaps with existing inspector logic |
| Timeline ETA projection bars (`ee4c18d`) | Purple projected-duration bars on timeline swimming lanes; velocity-based ETA on asset cards | Medium — original implementation lives in `frontend/panels/timeline-panel.js` (vanilla JS) and `frontend/app.js`; needs reimplementation against React `BottomTimelineDock.tsx` rather than a copy-paste |

## Why the remaining ports stopped here

1. **No running dev server in this session.** Per drive-level CLAUDE.md, `venv/` is recreated per machine; this Mac doesn't have one yet. UI ports without visual verification carry too much regression risk.
2. **The layout-chrome ports involve real UX trade-offs.** `WorkspaceLayout` would restructure `App.tsx`; `LeftRail` and `RightInspectorDrawer` overlap with the existing `Sidebar.tsx`. These are design decisions, not mechanical ports — they need a side-by-side visual comparison.
3. **The Timeline ETA work is in vanilla JS on `grid-sentinel-2`.** Direct file copy doesn't work; the logic must be re-implemented against the existing React `BottomTimelineDock.tsx`. That's a small new feature, not a port — better tracked as a separate task with its own design.

## Recommended next steps (in order of value / risk)

1. **VerticalTaskbar (additive, low risk).** Copy `frontend/app/layout/VerticalTaskbar.tsx` and `.css` into `src/frontend-react/src/components/`, fix the import path for Blueprint, wire it into `App.tsx` as an opt-in alternate to the current sidebar tab switcher, gate by a feature flag if the user wants to A/B test.
2. **MacrogridPanel + MissionsPanel (additive, low risk).** Two net-new panels; add to the existing sidebar tab list.
3. **TopCommandBar (additive, low risk).** Header strip; doesn't conflict with anything existing.
4. **Timeline ETA bars (re-implementation).** Add velocity-based ETA computation to the existing React `BottomTimelineDock.tsx`. This is a feature, not a port — open a fresh task.
5. **WorkspaceLayout + LeftRail + RightInspectorDrawer (high-risk redesign).** Defer until the user wants a top-level layout overhaul. These should be a single coordinated PR with visual screenshots.

## Out of scope for this round

The 257 orphan commits on `grid-sentinel-2` include a lot of internal experimentation (SQLite stores, MAVLink stubs, playback adapters in `backend/app/`) that doesn't apply to the FastAPI architecture on `main`. Don't try to port the backend layer.
