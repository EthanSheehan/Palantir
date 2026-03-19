---
phase: 1
slug: multi-sensor-target-fusion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `src/python/tests/conftest.py` (sys.path setup only) |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_sensor_fusion.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_sensor_fusion.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | P1-FUSE-MATH | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_empty_contributions -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | P1-FUSE-SINGLE | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_single_contribution -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | P1-FUSE-MULTI | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_two_types_fuse_higher -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | P1-FUSE-SAME-TYPE | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_same_type_uses_max -x` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | P1-FUSE-BOUNDS | unit | `pytest test_sensor_fusion.py::TestFuseDetections::test_confidence_bounded -x` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 1 | P1-FUSE-FROZEN | unit | `pytest test_sensor_fusion.py::TestImmutability -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | P1-SIM-MULTI | integration | `pytest test_sim_integration.py::TestMultiSensorFusion -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | P1-SIM-CONFIDENCE | integration | `pytest test_sim_integration.py::TestMultiSensorFusion::test_fused_higher_than_single -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | P1-SIM-DEGRADE | integration | `pytest test_sim_integration.py::TestMultiSensorFusion::test_confidence_degrades_on_removal -x` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 2 | P1-SIM-CANCEL | integration | `pytest test_sim_integration.py::TestCancelTrackMulti -x` | ❌ W0 | ⬜ pending |
| 01-02-05 | 02 | 2 | P1-STATE | integration | `pytest test_sim_integration.py::TestGetStatePhase1 -x` | ❌ W0 | ⬜ pending |
| 01-02-06 | 02 | 2 | P1-COMPAT | integration | `pytest test_sim_integration.py::TestBackwardCompat -x` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | P1-UI | smoke | Manual / browser | — | ⬜ pending |
| 01-03-02 | 03 | 3 | P1-UI-BADGE | smoke | Manual / browser | — | ⬜ pending |
| 01-03-03 | 03 | 3 | P1-CESIUM | smoke | Manual / Cesium viewer | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_sensor_fusion.py` — stubs for P1-FUSE-* (write before sensor_fusion.py)
- [ ] Extend `src/python/tests/test_sim_integration.py` — stubs for P1-SIM-*, P1-STATE, P1-COMPAT

*Existing pytest infrastructure covers all framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FusionBar renders with per-sensor colors | P1-UI | Visual ECharts rendering — no headless browser yet | Open frontend, navigate to ENEMIES tab, verify stacked bar with blue/green/amber |
| SensorBadge shows correct count | P1-UI-BADGE | Visual Blueprint Tag — no headless browser | Verify badge text matches `sensor_count` from WebSocket payload |
| Fusion ring appears and scales | P1-CESIUM | Cesium 3D rendering — requires GPU | Open Cesium view, verify cyan ring around detected targets, confirm opacity scales with sensor_count |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
