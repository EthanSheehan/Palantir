---
phase: 5
slug: swarm-coordination
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — tests discovered by pattern |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_swarm_coordinator.py -x -q` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_swarm_coordinator.py -x -q`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | FR-4 | unit | `pytest tests/test_swarm_coordinator.py::test_assigns_nearest_matching_uav -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 1 | FR-4 | unit | `pytest tests/test_swarm_coordinator.py::test_idle_guard_respected -x` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | 1 | FR-4 | unit | `pytest tests/test_swarm_coordinator.py::test_no_assignment_when_fully_covered -x` | ❌ W0 | ⬜ pending |
| 5-01-04 | 01 | 1 | FR-4 | unit | `pytest tests/test_swarm_coordinator.py::test_no_duplicate_sensor -x` | ❌ W0 | ⬜ pending |
| 5-02-01 | 02 | 1 | FR-4 | integration | `pytest tests/test_swarm_coordinator.py::test_request_release_swarm -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 02 | 1 | FR-4 | integration | `pytest tests/test_swarm_coordinator.py::test_swarm_state_in_broadcast -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_swarm_coordinator.py` — stubs for FR-4 (all unit + integration tests)
- [ ] `SwarmTask` and `TaskingOrder` types in `src/frontend-react/src/store/types.ts`

*Existing test infrastructure (pytest) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cesium dashed cyan polylines visible between swarm members | FR-4 | Visual rendering requires browser | Open map, trigger swarm assignment, verify dashed cyan lines appear between UAVs and target |
| SwarmPanel sensor icons show filled/hollow correctly | FR-4 | Visual rendering requires browser | Open ENEMIES tab, verify EO_IR/SAR/SIGINT icons show correct fill state |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
