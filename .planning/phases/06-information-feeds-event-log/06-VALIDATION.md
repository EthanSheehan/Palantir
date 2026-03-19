---
phase: 6
slug: information-feeds-event-log
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `src/python/tests/conftest.py` |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_feeds.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_feeds.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | FR-5-STATE | integration | `pytest tests/test_feeds.py::test_state_feed_subscription -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | FR-5-INTEL | unit | `pytest tests/test_feeds.py::test_intel_feed_state_transition -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | FR-5-SENSOR | unit | `pytest tests/test_feeds.py::test_sensor_feed_cadence -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | FR-5-COMMAND | unit | `pytest tests/test_feeds.py::test_command_feed_coverage -x` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 1 | FR-5-SUB | integration | `pytest tests/test_feeds.py::test_subscription_filtering -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | FR-10 | unit | `pytest tests/test_event_logger.py -x` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 1 | FR-10-ROTATION | unit | `pytest tests/test_feeds.py::test_log_rotation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_feeds.py` — stubs for FR-5-STATE, FR-5-INTEL, FR-5-SENSOR, FR-5-COMMAND, FR-5-SUB, FR-10-ROTATION

*Existing infrastructure covers test_event_logger.py.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| IntelFeed.tsx renders events with correct color tags | UI visual | CSS/visual fidelity | Open MISSION tab, trigger target detection, verify Blueprint Tag colors match FEED_INTENT mapping |
| CommandLog.tsx shows source attribution | UI visual | Tabular rendering | Issue commands via dashboard, verify operator/autopilot source column displays correctly |
| DroneCam.tsx fusion overlay positioning | UI visual | Overlay position over canvas | Click drone card, verify confidence/verification text overlays appear over video feed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
