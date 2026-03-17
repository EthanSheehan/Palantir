# Upgrade Swarm Plan — Agent Team Assignments

**Date:** 2026-03-17
**PRD:** docs/PRD_v2_upgrade.md

---

## Execution Strategy

The upgrade is organized into **5 parallel workstreams** executed by specialized agent teams. Workstreams have explicit dependencies — a workstream can start once its prerequisite deliverables exist, not when the entire prior phase completes.

```
Timeline (approximate ordering, not calendar):

Stream A: Simulation Core ████████████████░░░░░░░░░░░░░░░░
Stream B: Frontend/UI     ░░░░░░████████████████░░░░░░░░░░
Stream C: Agent Layer     ░░░░░░░░░░████████████████░░░░░░
Stream D: Theater/Fidelity░░░░░░░░░░░░░░████████████████░░
Stream E: Quality         ████████████████████████████████

Dependencies:
  B needs A (drone modes, target events, video sim)
  C needs A (detection events, sensor model)
  C needs B (HITL UI for gates)
  D needs A (sensor model, target behaviors)
  E runs continuously
```

---

## Workstream A: Simulation Core (Drone-Target Interaction)

**Owner Agent:** `everything-claude-code:planner` → `everything-claude-code:tdd-guide`
**Files:** `src/python/sim_engine.py`, `src/python/vision/video_simulator.py`, new: `src/python/sensor_model.py`, `src/python/target_behavior.py`

### Tasks (in order)

| Step | Description | Agent | Depends On |
|------|-------------|-------|------------|
| A1 | Design sensor model: Pd = f(range, RCS, altitude) | `planner` | — |
| A2 | Write tests for sensor model (RED) | `tdd-guide` | A1 |
| A3 | Implement `sensor_model.py` (GREEN) | implement | A2 |
| A4 | Expand drone modes: SCANNING → VIEWING → FOLLOWING → PAINTING | implement | A3 |
| A5 | Expand target states: UNDETECTED → DETECTED → TRACKED → IDENTIFIED → LOCKED | implement | A3 |
| A6 | Write tests for drone-target interaction (RED) | `tdd-guide` | A4, A5 |
| A7 | Implement drone mode transitions + target state machine (GREEN) | implement | A6 |
| A8 | Integrate video simulator with sim_engine targets | implement | A7 |
| A9 | Publish detection/track/lock events via WebSocket | implement | A7 |
| A10 | Add target behavior module (shoot-and-scoot, patrol, concealment) | implement | A5 |

### Review (parallel after A9)
- `python-reviewer` — review all new Python code
- `security-reviewer` — check for issues

---

## Workstream B: Frontend (Grid 9 + Target Interaction UI)

**Owner Agent:** `everything-claude-code:planner` → `everything-claude-code:code-reviewer`
**Files:** `src/frontend/app.js`, `src/frontend/index.html`, `src/frontend/style.css`, new modules

### Tasks (in order)

| Step | Description | Agent | Depends On |
|------|-------------|-------|------------|
| B1 | Merge grid 9 layout as new src/frontend baseline | implement | — |
| B2 | Verify existing E2E tests pass on grid 9 base | `build-error-resolver` | B1 |
| B3 | Add ENEMIES tab with full target list (type, status, coords) | implement | A9 (events) |
| B4 | Add drone action buttons: VIEW / FOLLOW / PAINT | implement | A4 (modes) |
| B5 | Implement Tactical HUD — live video feed from selected drone | implement | A8 (video sim) |
| B6 | Build Strike Board panel (nominated targets, COA options, approve/reject) | implement | — |
| B7 | Add target visualization on map (threat icons, detection rings, lock indicator) | implement | A5 (states) |
| B8 | Wire agent message feed (kill chain progress + recommendations) | implement | C2 (ISR Observer) |
| B9 | Modularize app.js into <400-line modules | `refactor-cleaner` | B1-B8 |
| B10 | Drone camera PIP (picture-in-picture) modal | implement | A8, B5 |

### Review (parallel after B9)
- `code-reviewer` — review all frontend changes
- `security-reviewer` — check for XSS, injection

---

## Workstream C: AI Agent Completion (F2T2EA Kill Chain)

**Owner Agent:** `everything-claude-code:planner` → `everything-claude-code:tdd-guide`
**Files:** `src/python/agents/*.py`, new: `src/python/llm_adapter.py`

### Tasks (in order)

| Step | Description | Agent | Depends On |
|------|-------------|-------|------------|
| C1 | Implement LLM adapter: Ollama integration + heuristic fallback | implement | — |
| C2 | Write tests for ISR Observer (RED) | `tdd-guide` | C1, A3 |
| C3 | Implement ISR Observer: sensor fusion, track correlation, classification | implement | C2 |
| C4 | Write tests for Strategy Analyst (RED) | `tdd-guide` | C3 |
| C5 | Implement Strategy Analyst: ROE eval, priority scoring, strike board nomination | implement | C4 |
| C6 | Implement HITL Gate 1: target nomination → Strike Board → operator approval | implement | C5, B6 |
| C7 | Write tests for Tactical Planner (RED) | `tdd-guide` | C6 |
| C8 | Implement Tactical Planner: COA generation with LLM + heuristic fallback | implement | C7 |
| C9 | Implement HITL Gate 2: COA → operator authorization | implement | C8, B6 |
| C10 | Write tests for Effectors Agent (RED) | `tdd-guide` | C9 |
| C11 | Implement Effectors Agent: engagement simulation, BDA, feedback loop | implement | C10 |
| C12 | Implement Pattern Analyzer (currently NotImplementedError) | implement | C3 |
| C13 | Implement AI Tasking Manager: auto-retask drones to priority targets | implement | C3, A4 |
| C14 | Implement Battlespace Manager: threat rings, WEZ, no-fly areas | implement | A3 |
| C15 | Implement Synthesis Query Agent: SITREP generation | implement | C3-C11 |
| C16 | Wire agent reasoning traces to frontend display | implement | B8 |

### Review (parallel after C11)
- `python-reviewer` — review all agent code
- `security-reviewer` — check for prompt injection, data leaks

---

## Workstream D: Theater Config & Simulation Fidelity

**Owner Agent:** `everything-claude-code:planner`
**Files:** new: `theaters/*.yaml`, `src/python/theater_loader.py`

### Tasks (in order)

| Step | Description | Agent | Depends On |
|------|-------------|-------|------------|
| D1 | Design theater config YAML format | `planner` | — |
| D2 | Write theater loader (parse YAML → initialize sim_engine) | implement | D1, A3 |
| D3 | Create Romania theater file (current hardcoded values → config) | implement | D2 |
| D4 | Create South China Sea theater file | implement | D2 |
| D5 | Create Baltic theater file | implement | D2 |
| D6 | Add theater selector to frontend (dropdown or mission setup screen) | implement | D2, B1 |
| D7 | Add expanded unit types (MANPADS, radar, C2 node, logistics, MLRS) | implement | A10, D3 |
| D8 | Implement red force reactive AI (shoot-and-scoot, camouflage, decoys) | implement | A10, D7 |
| D9 | Add weather layer (affects sensor Pd) | implement | A3, D2 |
| D10 | UAV endurance model (fuel/battery, RTB, handoff) | implement | A4 |

### Review (parallel after D8)
- `python-reviewer` — review simulation code
- `architect` — review theater config design

---

## Workstream E: Quality & Hardening (Continuous)

**Owner Agent:** `everything-claude-code:build-error-resolver` + `everything-claude-code:security-reviewer`
**Files:** All

### Tasks (ongoing throughout all phases)

| Step | Description | Agent | Trigger |
|------|-------------|-------|---------|
| E1 | Replace all `print()` with `structlog` | implement | Start of project |
| E2 | Fix requirements.txt (add missing deps) | implement | Start of project |
| E3 | Create `.env.example`, remove hardcoded keys | `security-reviewer` | Start of project |
| E4 | Replace bare `except:` with typed handlers | implement | Start of project |
| E5 | Fix WebSocket 0.1s timeout, add backpressure | implement | After A9 |
| E6 | Add Pydantic validation for all WS payloads | implement | After A9 |
| E7 | Run `python-reviewer` after every Python change | `python-reviewer` | Every PR |
| E8 | Run `security-reviewer` before any commit | `security-reviewer` | Every commit |
| E9 | Run `build-error-resolver` on any test failure | `build-error-resolver` | Test failure |
| E10 | Integration test: full kill chain end-to-end | `tdd-guide` | After C11 |
| E11 | Update E2E Playwright tests for new UI | implement | After B9 |

---

## Agent Roster

| Agent | Role in Swarm | Invocation |
|-------|--------------|------------|
| **Planner** | Designs each phase before coding starts | `everything-claude-code:planner` |
| **Architect** | Reviews system design decisions (theater config, LLM adapter, state machine) | `everything-claude-code:architect` |
| **TDD Guide** | Writes tests first for every new module | `everything-claude-code:tdd-guide` |
| **Python Reviewer** | Reviews all Python code after writing | `everything-claude-code:python-reviewer` |
| **Code Reviewer** | Reviews all frontend JS/TS code after writing | `everything-claude-code:code-reviewer` |
| **Security Reviewer** | Checks for vulnerabilities before commits | `everything-claude-code:security-reviewer` |
| **Build Error Resolver** | Fixes broken tests/builds | `everything-claude-code:build-error-resolver` |
| **Refactor Cleaner** | Modularizes monolithic files | `everything-claude-code:refactor-cleaner` |
| **Doc Updater** | Updates CLAUDE.md and docs after major changes | `everything-claude-code:doc-updater` |

---

## Parallel Execution Rules

1. **Always launch independent agents in parallel** (single message, multiple Agent tool calls)
2. **After writing Python code:** launch `python-reviewer` + `security-reviewer` simultaneously
3. **After writing frontend code:** launch `code-reviewer` + `security-reviewer` simultaneously
4. **Before committing:** launch `security-reviewer`
5. **On test failure:** launch `build-error-resolver` immediately
6. **Workstreams A and E start immediately** — no prerequisites
7. **Workstream B starts when** A4 + A5 deliver drone modes and target states
8. **Workstream C starts when** A3 delivers sensor model and C1 (LLM adapter) is done
9. **Workstream D starts when** A3 + A10 deliver sensor model and target behaviors

---

## Definition of Done

A phase is complete when:
- [ ] All tests pass (unit + integration + E2E where applicable)
- [ ] `python-reviewer` reports no CRITICAL or HIGH issues
- [ ] `security-reviewer` reports no CRITICAL issues
- [ ] Code follows project style (immutability, <800 line files, proper error handling)
- [ ] Feature works end-to-end in the running system (`./palantir.sh`)
- [ ] CLAUDE.md updated if architecture changed

---

## Recommended Execution Order (for single-operator workflow)

If executing sequentially with Claude Code:

```
1. E1-E4 (quick wins: logging, requirements, secrets, error handling)
2. A1-A3 (sensor model — foundation for everything)
3. A4-A5 (drone modes + target states)
4. A6-A9 (drone-target interaction + events)
5. B1-B2 (grid 9 merge + E2E verification)
6. C1 (LLM adapter)
7. B3-B7 (enemies tab, action buttons, strike board, target viz)
8. A10 (target behaviors)
9. C2-C11 (full agent chain: ISR → Strategy → Tactical → Effectors)
10. B8-B10 (agent feed, modularize, PIP)
11. D1-D6 (theater config + 3 theaters)
12. D7-D10 (unit expansion, red AI, weather, endurance)
13. C12-C16 (remaining agents: pattern, tasking, battlespace, synthesis)
14. E5-E11 (WS hardening, validation, integration tests, E2E update)
```
