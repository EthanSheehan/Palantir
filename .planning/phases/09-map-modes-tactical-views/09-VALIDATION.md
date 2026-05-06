---
phase: 9
slug: map-modes-tactical-views
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
tags: [grid_sentinel, planning, gsd]
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (frontend React/TypeScript) |
| **Config file** | `src/frontend-react/vitest.config.ts` or "none — Wave 0 installs" |
| **Quick run command** | `cd src/frontend-react && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd src/frontend-react && npx vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd src/frontend-react && npx vitest run --reporter=verbose`
- **After every plan wave:** Run `cd src/frontend-react && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | map-mode-store | unit | `vitest run mapModeStore` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | keyboard-shortcuts | unit | `vitest run useMapModeKeys` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | coverage-layer | unit | `vitest run coverageLayer` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | threat-layer | unit | `vitest run threatLayer` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | fusion-layer | unit | `vitest run fusionLayer` | ❌ W0 | ⬜ pending |
| 09-02-04 | 02 | 1 | terrain-layer | unit | `vitest run terrainLayer` | ❌ W0 | ⬜ pending |
| 09-02-05 | 02 | 1 | swarm-layer | unit | `vitest run swarmLayer` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | map-mode-bar | unit | `vitest run MapModeBar` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 2 | layer-panel | unit | `vitest run LayerPanel` | ❌ W0 | ⬜ pending |
| 09-03-03 | 03 | 2 | camera-presets | unit | `vitest run CameraPresets` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/frontend-react/src/__tests__/mapModeStore.test.ts` — store state transitions
- [ ] `src/frontend-react/src/__tests__/useMapModeKeys.test.ts` — keyboard shortcut hook
- [ ] `src/frontend-react/src/__tests__/layers/` — layer hook test stubs
- [ ] vitest config confirmed or installed

*Existing infrastructure may cover some — verify before creating.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual layer rendering on Cesium globe | all layers | Cesium WebGL rendering cannot be unit tested | Toggle each mode (keys 1-6), verify correct layers appear |
| Camera preset transitions | camera-presets | Camera animation is visual | Click each preset button, verify camera moves to expected viewpoint |
| Layer toggle persistence across mode switch | layer-panel | State interaction with visual rendering | Toggle layer OFF, switch modes, switch back, verify layer still OFF |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
