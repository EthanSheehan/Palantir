---
phase: 3
slug: drone-modes-autonomy
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest in venv) |
| **Config file** | `src/python/tests/conftest.py` |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_drone_modes.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_drone_modes.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestSupportMode -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestVerifyMode -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestOverwatchMode -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestBdaMode -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestAutonomyManual -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestAutonomyAutonomous -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestAutonomySupervised -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestPerDroneOverride -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestApproveTransition -x` | ❌ W0 | ⬜ pending |
| 03-02-06 | 02 | 1 | FR-3 | unit | `pytest tests/test_drone_modes.py::TestRejectTransition -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | FR-3 | integration | `pytest tests/test_drone_modes.py::TestModeExclusion -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_drone_modes.py` — stubs for all FR-3 behaviors above

*Existing infrastructure covers conftest.py and framework.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AutonomyToggle renders correctly | FR-3 | React component visual check | Open UI, toggle MANUAL/SUPERVISED/AUTONOMOUS, verify visual state |
| TransitionToast countdown renders | FR-3 | Toast animation/timing visual | Set SUPERVISED, trigger transition, verify countdown + approve/reject buttons |
| New mode colors in Cesium | FR-3 | Visual color verification | Place drones in each new mode, verify teal/amber/indigo/gray-blue |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
