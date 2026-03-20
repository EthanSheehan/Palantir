---
phase: 8
slug: adaptive-isr-closed-loop
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `src/python/tests/` |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_adaptive_isr.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_adaptive_isr.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| *Populated after planning* | | | FR-7 | unit+integration | `pytest test_adaptive_isr.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_adaptive_isr.py` — stubs for FR-7 (ISR priority, coverage modes, retasking)
- [ ] Fixtures for mock AssessmentResult, UAV fleet state, target list

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ISRQueue.tsx renders priority list | FR-7 | React component visual | Open dashboard, verify queue displays with correct ordering |
| Coverage mode toggle switches behavior | FR-7 | Full-stack integration | Toggle balanced↔threat_adaptive, observe UAV redistribution on Cesium map |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
