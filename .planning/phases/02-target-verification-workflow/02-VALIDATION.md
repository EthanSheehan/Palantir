---
phase: 2
slug: target-verification-workflow
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `src/python/tests/conftest.py` (sys.path setup) |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/test_verification.py -x` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./venv/bin/python3 -m pytest src/python/tests/test_verification.py -x`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/ -x --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | FR-2 (promote classify) | unit | `pytest test_verification.py::TestEvaluateState::test_detected_to_classified -x` | Wave 1 | ⬜ pending |
| 02-01-02 | 01 | 1 | FR-2 (promote verify sensor) | unit | `pytest test_verification.py::TestEvaluateState::test_classified_to_verified_sensors -x` | Wave 1 | ⬜ pending |
| 02-01-03 | 01 | 1 | FR-2 (promote verify time) | unit | `pytest test_verification.py::TestEvaluateState::test_classified_to_verified_sustained -x` | Wave 1 | ⬜ pending |
| 02-01-04 | 01 | 1 | FR-2 (regression) | unit | `pytest test_verification.py::TestEvaluateState::test_regression -x` | Wave 1 | ⬜ pending |
| 02-01-05 | 01 | 1 | FR-2 (terminal guard) | unit | `pytest test_verification.py::TestEvaluateState::test_terminal_states_not_regressed -x` | Wave 1 | ⬜ pending |
| 02-01-06 | 01 | 1 | FR-2 (SAM fast) | unit | `pytest test_verification.py::TestThresholds::test_sam_thresholds_lower -x` | Wave 1 | ⬜ pending |
| 02-01-07 | 01 | 1 | FR-2 (demo fast) | unit | `pytest test_verification.py::TestDemoFast::test_demo_fast_halves_time -x` | Wave 1 | ⬜ pending |
| 02-01-08 | 01 | 1 | FR-2 (pure function) | unit | `pytest test_verification.py::TestPurity -x` | Wave 1 | ⬜ pending |
| 02-02-01 | 02 | 2 | FR-2 (sim timer) | integration | `pytest test_verification.py::TestSimIntegration::test_timer_increments -x` | Wave 2 | ⬜ pending |
| 02-02-02 | 02 | 2 | FR-2 (sim promote) | integration | `pytest test_verification.py::TestSimIntegration::test_auto_promotion -x` | Wave 2 | ⬜ pending |
| 02-02-03 | 02 | 2 | FR-2 (pipeline gate) | integration | `pytest test_verification.py::TestPipelineGate::test_gate_fires_on_verified_only -x` | Wave 2 | ⬜ pending |
| 02-02-04 | 02 | 2 | FR-2 (manual verify) | integration | `pytest test_verification.py::TestManualVerify -x` | Wave 2 | ⬜ pending |
| 02-02-05 | 02 | 2 | FR-2 (state broadcast) | integration | `pytest test_verification.py::TestBroadcast -x` | Wave 2 | ⬜ pending |
| 02-03-01 | 03 | 3 | FR-2 (UI stepper) | smoke | Manual browser test | — | ⬜ pending |
| 02-03-02 | 03 | 3 | FR-2 (UI verify btn) | smoke | Manual browser test | — | ⬜ pending |
| 02-01-09 | 01 | 1 | NFR-4 (coverage) | coverage | `pytest test_verification.py --cov=verification_engine --cov-report=term-missing` | Wave 1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_verification.py` — stubs for all FR-2 unit tests (write before verification_engine.py)
- [ ] `src/python/verification_engine.py` — implement to make tests green

*Existing pytest infrastructure covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| VerificationStepper renders step dots | FR-2 UI | No Playwright/E2E setup yet | Load UI, observe target cards show DETECTED→CLASSIFIED→VERIFIED dots |
| VERIFY button visible on CLASSIFIED only | FR-2 UI | No Playwright/E2E setup yet | Click VERIFY on CLASSIFIED target, confirm it promotes to VERIFIED |
| Demo timing feels natural | FR-2 Demo | Subjective timing assessment | Run `./palantir.sh --demo`, watch targets climb through states |

*All Python behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
