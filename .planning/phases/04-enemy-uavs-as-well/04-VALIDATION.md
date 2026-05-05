---
phase: 4
slug: enemy-uavs-as-well
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `src/python/tests/` (existing test dir) |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_enemy_uavs.py -x -q` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_enemy_uavs.py -x -q`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | EnemyUAV class | unit | `pytest test_enemy_uavs.py -k test_enemy_uav_creation` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | Flight mechanics | unit | `pytest test_enemy_uavs.py -k test_enemy_uav_movement` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | Behavior modes | unit | `pytest test_enemy_uavs.py -k test_enemy_uav_behaviors` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | Detection integration | integration | `pytest test_enemy_uavs.py -k test_enemy_detection` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | Sensor fusion | integration | `pytest test_enemy_uavs.py -k test_enemy_sensor_fusion` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | Intercept mechanics | unit | `pytest test_enemy_uavs.py -k test_intercept_mechanic` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 2 | Evasion behavior | unit | `pytest test_enemy_uavs.py -k test_evasion_behavior` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | WebSocket broadcast | integration | `pytest test_enemy_uavs.py -k test_websocket_enemy_state` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 3 | Frontend Cesium hook | manual | Browser visual check | N/A | ⬜ pending |
| 04-05-02 | 05 | 3 | Enemy UAV card | manual | Browser visual check | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_enemy_uavs.py` — stubs for all enemy UAV unit and integration tests
- [ ] Shared fixtures for EnemyUAV instances with default configs

*Existing infrastructure covers framework and conftest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cesium enemy UAV entities render | Frontend display | Visual/WebGL rendering | Start system, verify red UAV markers on globe |
| EnemyUAVCard sidebar display | UI component | Interactive UI check | Click enemy UAV, verify card shows behaviors and threat level |
| Demo autopilot auto-intercept | Demo mode flow | End-to-end timing | Run `./grid_sentinel.sh --demo`, verify enemy UAVs appear and get intercepted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
