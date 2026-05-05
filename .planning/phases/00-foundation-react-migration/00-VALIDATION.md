---
phase: 0
slug: foundation-react-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + Vite/vitest (TypeScript) |
| **Config file** | `vite.config.ts` (includes vitest config) |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ && cd src/frontend-react && npm run build` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/ -x -q`
- **After every plan wave:** Run full suite (Python tests + Vite build check)
- **Before `/gsd:verify-work`:** Full suite must be green + Vite dev server starts
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 0-build-tooling | 01 | 1 | Build tooling | build | `cd src/frontend-react && npm run build` | ❌ W0 | ⬜ pending |
| 0-store-types | 01 | 1 | Store/types | build | `cd src/frontend-react && npx tsc --noEmit` | ❌ W0 | ⬜ pending |
| 0-ws-hook | 01 | 2 | WebSocket hook | build | `cd src/frontend-react && npx tsc --noEmit` | ❌ W0 | ⬜ pending |
| 0-cesium-drones | 02 | 2 | Cesium drones | manual | Verify drones render on globe | ❌ W0 | ⬜ pending |
| 0-cesium-targets | 02 | 2 | Cesium targets | manual | Verify targets render on globe | ❌ W0 | ⬜ pending |
| 0-sidebar | 03 | 3 | Sidebar tabs | manual | Verify MISSION/ASSETS/ENEMIES tab switching | ❌ W0 | ⬜ pending |
| 0-drone-cards | 03 | 3 | Drone cards | manual | Verify mode buttons send WS messages | ❌ W0 | ⬜ pending |
| 0-enemy-cards | 03 | 3 | Enemy cards | manual | Verify target selection + map fly-to | ❌ W0 | ⬜ pending |
| 0-strikeboard | 03 | 3 | Strike board | manual | Verify approve/reject/authorize flow | ❌ W0 | ⬜ pending |
| 0-python-bugfix | 04 | 1 | sim_engine fix | unit | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` | ✅ | ⬜ pending |
| 0-event-logger | 04 | 1 | Event logger | unit | `./venv/bin/python3 -m pytest src/python/tests/test_event_logger.py` | ❌ W0 | ⬜ pending |
| 0-multi-sensor | 04 | 1 | Multi-sensor UAV | unit | `./venv/bin/python3 -m pytest src/python/tests/test_sim_engine.py` | ✅ | ⬜ pending |
| 0-grid_sentinel-sh | 05 | 4 | grid_sentinel.sh | manual | `./grid_sentinel.sh --no-browser` starts Vite on :5173 | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_event_logger.py` — stubs for event logger tests
- [ ] `src/frontend-react/` — npm deps installed (`npm install` in Wave 1)

*Existing pytest infrastructure covers Python test requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cesium globe renders drones | 0.3 Cesium hooks | No headless Cesium renderer | Start dev server, verify drone entities appear |
| Cesium globe renders targets | 0.3 Cesium hooks | No headless Cesium renderer | Start dev server, verify target billboards appear |
| Sidebar resize drag | 0.2 resizer | DOM interaction | Drag sidebar resizer, verify Cesium reflows |
| Drone cam canvas renders | 0.2 DroneCamPIP | Canvas rendering | Select drone, verify PIP shows synthetic feed |
| Demo autopilot end-to-end | 0.8 checkpoint | Full system integration | `./grid_sentinel.sh --demo`, observe kill chain |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
