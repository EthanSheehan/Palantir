---
phase: 7
slug: battlespace-assessment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | none — conftest.py adds src/python to sys.path |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_battlespace.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_battlespace.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | FR-6.1 | unit | `pytest tests/test_battlespace.py::TestClustering -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | FR-6.2 | unit | `pytest tests/test_battlespace.py::TestCoverageGaps -x` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | FR-6.3 | unit | `pytest tests/test_battlespace.py::TestZoneThreatScoring -x` | ❌ W0 | ⬜ pending |
| 07-01-04 | 01 | 1 | FR-6.4 | unit | `pytest tests/test_battlespace.py::TestMovementCorridors -x` | ❌ W0 | ⬜ pending |
| 07-01-05 | 01 | 1 | FR-6.5 | integration | `pytest tests/test_sim_integration.py -x -k assessment` | ❌ W0 | ⬜ pending |
| 07-01-06 | 01 | 1 | FR-6.6 | unit | `pytest tests/test_battlespace.py::TestEdgeCases -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_battlespace.py` — stubs for FR-6.1 through FR-6.6 (new module, no existing tests)
- [ ] `src/python/tests/test_sim_integration.py` — add assessment-wire test (existing file, add test)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cesium convex hull overlays render correctly | FR-7.3 | Visual rendering | Launch frontend, verify colored hull polygons appear around clustered targets |
| SAM engagement envelopes display at correct radius | FR-7.3 | Visual + geospatial | Check envelope radius matches `threat_range_km` from theater YAML |
| Movement corridor polylines track target history | FR-7.3 | Visual rendering | Verify polylines trace target movement paths on Cesium globe |
| ECharts zone heatmap renders with correct threat scores | FR-7.3 | Visual rendering | Open Assessment tab, verify heatmap values match zone threat scores |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
