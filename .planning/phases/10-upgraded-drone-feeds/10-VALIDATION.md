---
phase: 10
slug: upgraded-drone-feeds
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python) + TypeScript compile check (frontend) |
| **Config file** | default discovery at `src/python/tests/` |
| **Quick run command** | `./venv/bin/python3 -m pytest src/python/tests/ -x -q` |
| **Full suite command** | `./venv/bin/python3 -m pytest src/python/tests/ && cd src/frontend-react && npx tsc --noEmit` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd src/frontend-react && npx tsc --noEmit`
- **After every plan wave:** Run `./venv/bin/python3 -m pytest src/python/tests/ && cd src/frontend-react && npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | FR-9 | unit | `pytest src/python/tests/test_sim_engine.py -k "fov_targets or sensor_quality" -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | FR-9 | smoke | `cd src/frontend-react && npx tsc --noEmit` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 1 | FR-9 | smoke | `cd src/frontend-react && npx tsc --noEmit` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 2 | FR-9 | smoke | `cd src/frontend-react && npx tsc --noEmit` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/python/tests/test_sim_engine.py` — add assertions for `fov_targets` and `sensor_quality` in `get_state()` output

*Existing TypeScript compile check covers all frontend smoke tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| EO/IR green thermal rendering | FR-9 | Visual rendering fidelity | Open drone cam, select EO/IR mode, verify green tint with glowing targets |
| SAR amber radar returns | FR-9 | Visual rendering fidelity | Select SAR mode, verify amber color scheme with velocity vectors |
| SIGINT waterfall scrolling | FR-9 | Visual animation correctness | Select SIGINT mode, verify heatmap scrolls and shows emitter data |
| PIP/SPLIT/QUAD layouts | FR-9 | Layout visual correctness | Toggle each layout, verify correct slot arrangement |
| Compass tape heading | FR-9 | Visual HUD correctness | Rotate drone, verify compass tape updates smoothly |
| Threat warning flash | FR-9 | Visual feedback | Move drone near SAM envelope, verify red flash |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
