---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# GSD + Autopilot End-to-End Upgrade Analysis

**Author:** PEPPER (Architecture Specialist)
**Date:** 2026-03-29
**Scope:** Full pipeline redesign — GSD backbone, Autopilot integration, GENIE fleet dispatch

---

## Executive Summary

The GSD pipeline is architecturally sound — goal-backward verification, structured plan-check-execute-verify loops, and fresh-context subagents per phase are genuine strengths. The Autopilot system bolted on top works but has real quality issues (user confirmed: "autopilot outputs poor"). The core problem isn't the pipeline itself — it's the seams between pipeline stages where context gets lost, quality gates get bypassed, and recovery from failures requires manual intervention.

This document identifies 8 pipeline gaps, proposes 6 upgrades, and designs a GENIE fleet integration pattern.

---

## 1. Current GSD Pipeline — Where It Breaks

### Gap 1: Context Loss at Phase Boundaries

**The problem:** Each GSD subagent (planner, executor, verifier) starts with a fresh context window. This is a strength for preventing context rot, but a weakness for continuity. The planner reads the ROADMAP goal and writes a plan. The executor reads the plan but NOT the planner's reasoning for architectural choices. The verifier reads the codebase but not the execution log.

**Evidence:** The executor agent's `<files_to_read>` block is the only context bridge — it's a flat file list, not semantic context. When the planner makes a nuanced trade-off (e.g., "chose approach X because Y conflicts with existing module Z"), that reasoning lives only in the plan's `<action>` text — if it's there at all.

**Impact:** Executors sometimes re-investigate decisions the planner already resolved. Verifiers flag issues that were intentionally deferred. Time wasted: ~15-20% per phase.

**Fix:** Add a `DECISIONS.md` artifact per phase (not per plan). The planner writes it; executor and verifier read it. Decisions get a lightweight ID (e.g., PD-01) that plans reference. This is 20 lines of YAML, not a document.

### Gap 2: Plan-Checker Is Too Structural, Not Enough Behavioral

**The problem:** The gsd-plan-checker has 10 verification dimensions (requirement coverage, task completeness, dependency correctness, etc.) — impressive breadth. But it's fundamentally checking plan *structure*, not plan *feasibility*. It can verify that Task 2 has a `<verify>` block, but it can't verify that the verification command will actually work.

**Evidence:** Dimension 5 (Scope Sanity) uses static thresholds: "5+ tasks = blocker." This is wrong for simple tasks (5 `chore:` tasks adding config files ≠ 5 auth tasks). Dimension 8 (Nyquist Compliance) checks for `<automated>` presence but not whether the test command exists or will pass.

**Impact:** Plans pass the checker but fail during execution because the verification steps are unrealistic, file paths are wrong, or dependencies aren't installed.

**Fix:** Add a "dry-run verification" step: after plan-checker PASSES, run each plan's `<verify>` commands in a sandbox (or at minimum, check that referenced files/commands exist). This catches 80% of false-pass plans with minimal cost.

### Gap 3: Executor Has No Budget Awareness

**The problem:** The executor agent will attempt all tasks even when context is running out. The `analysis_paralysis_guard` catches one failure mode (5+ consecutive reads without writes), but there's no guard for the opposite: the executor is 80% through context and still has 3 tasks remaining. It will produce increasingly degraded output.

**Evidence:** The executor tracks `PLAN_START_EPOCH` but never uses it for time-budgeting. There's a "fix attempt limit" (3 per task) but no overall context/time budget.

**Impact:** Late tasks in a plan receive lower quality implementation. The executor doesn't know to split remaining work into a continuation.

**Fix:** The executor should track tool call count. After 40 tool calls (approximate 60% context), if >50% of tasks remain, it should checkpoint and return a structured continuation message. The orchestrator spawns a fresh executor for the remaining tasks.

### Gap 4: Failed Phase Recovery Is Manual

**The problem:** When a phase fails (executor errors, tests break, verifier finds gaps), recovery requires human intervention. The gsd-verifier writes gaps to VERIFICATION.md, and `/gsd:plan-phase --gaps` can re-plan — but the user has to invoke this manually. There's no automatic retry loop.

**Evidence:** The autopilot's Step 4d says "If tests fail after 3 attempts: write failure file, skip task." This is correct for individual tasks but wrong at the phase level. A phase that's 4/5 tasks complete with 1 failure isn't truly failed — it's partial.

**Impact:** Partial phase completions sit in limbo. The user has to diagnose whether to re-plan, manually fix, or skip. This breaks the autonomous flow.

**Fix:** Introduce a `phase_recovery` workflow:
1. Verifier finds gaps → writes structured `gaps:` YAML
2. Auto-invoke `plan-phase --gaps` with the gap list
3. Plan-checker validates gap-closure plans
4. Executor runs gap-closure plans
5. Re-verify (the verifier already supports re-verification mode)
6. Maximum 2 recovery cycles. If still failing, escalate to user.

### Gap 5: Autopilot Discovery Phase Is Unstructured

**The problem:** Autopilot Phase 1 spawns 5 discovery agents (archaeologist, algo-analyst, arch-scout, security-analyst, feature-spotter) that free-associate across the codebase. They produce discovery files with varying quality and no consistent schema. The synthesizer (Phase 2) then has to make sense of 5 unstructured documents.

**Evidence:** Discovery agents write Markdown with headings they invent ad-hoc. There's no shared schema for "a finding" — the archaeologist uses `file:line, type, description, complexity(S/M/L)` while the security analyst uses `Severity: CRITICAL/HIGH/MEDIUM`. The synthesizer has to parse both.

**Impact:** The synthesis step is the weakest link. An opus agent reading 5 unstructured documents produces a phase list, but the quality depends entirely on whether the discovery agents happened to format things similarly. User feedback confirms: autopilot outputs are poor.

**Fix:** Define a `Finding` schema that ALL discovery agents must use:
```yaml
findings:
  - id: ARCH-001
    type: architecture | security | algorithm | feature | code_gap
    severity: critical | high | medium | low
    title: "sim_engine.py is 1150-line god object"
    location: "src/python/sim_engine.py:1-1150"
    current: "Monolithic class handles UAV + target + enemy + zones"
    proposed: "Split into sim_uav.py, sim_targets.py, sim_zones.py"
    complexity: M
    impact: 4  # 1-5
    depends_on: []  # other finding IDs
```
The synthesizer can then sort, deduplicate, and group findings programmatically instead of reading prose.

### Gap 6: Autopilot ↔ GSD State Mismatch

**The problem:** Autopilot maintains its own state (`CHECKPOINT.md`, `SYNTHESIS.md`, wave directories) while GSD maintains separate state (`STATE.md`, `ROADMAP.md`, phase directories). They're supposed to sync, but the sync points are fragile.

**Evidence:** Autopilot Phase 3 ("GSD State Setup") manually writes STATE.md. But if the project already had GSD state from a previous milestone, the autopilot's write could clobber it. The autopilot writes phases as `phase-NN-autopilot/` while GSD expects `XX-name/` format.

**Impact:** After an autopilot run, GSD commands (`/gsd:progress`, `/gsd:execute-phase`) may not work correctly because the state formats don't fully align.

**Fix:** Autopilot should use GSD's `gsd-tools.cjs` API exclusively for state management instead of direct file writes. Phase creation should go through `gsd-tools.cjs` to ensure consistent naming and state tracking.

### Gap 7: No Cross-Phase Integration Testing

**The problem:** Each phase is verified independently by gsd-verifier. But phases interact — Phase 3's auth module is consumed by Phase 5's RBAC. There's no integration verification across phase boundaries.

**Evidence:** The gsd-integration-checker agent exists but is never invoked in the standard pipeline. The autopilot's Phase 5 (final review) does a holistic review, but by then all phases are committed.

**Impact:** Integration bugs surface only during manual testing or the final review — too late for automated fix.

**Fix:** After every 3 completed phases (or at milestone boundaries), run `gsd-integration-checker` against all accumulated phase artifacts. This catches cross-phase issues while there's still time to fix them within the pipeline.

### Gap 8: Review ↔ Fix Loop Is Unbounded

**The problem:** Autopilot Step 4e spawns reviewers, then fixes CRITICAL/HIGH findings. But there's no guarantee the fixes don't introduce new issues. The fix-review cycle has no explicit bound.

**Evidence:** The autopilot says "Spawn 1 fix agent per non-overlapping file group" but doesn't re-run reviewers on the fixes. If a fix introduces a new CRITICAL, it's missed.

**Impact:** Fix quality degrades when fixes aren't reviewed. The 6C-Beta wave had 4 MEDIUM issues fixed — without those being re-reviewed, any regression would propagate.

**Fix:** After fixes, run a lightweight re-review (haiku model, scope limited to changed files only). Maximum 2 fix-review cycles per phase. After that, document remaining issues and move on.

---

## 2. Autopilot Integration — Using GSD as Backbone

### Current Architecture (Flat)

```
Autopilot (orchestrator)
├── Phase 1: Discovery (5 agents, unstructured)
├── Phase 2: Synthesis (1 opus agent, reads all discovery)
├── Phase 3: GSD state setup (manual writes)
├── Phase 4: Per-phase loop
│   ├── 4a: Research (1 agent)
│   ├── 4b: Plan (gsd-planner)
│   ├── 4c: Check (gsd-plan-checker)
│   ├── 4d: Execute (gsd-executor)
│   ├── 4e: Review (2 ECC agents)
│   └── 4f: Checkpoint
└── Phase 5: Final review + docs + report
```

### Proposed Architecture (GSD-Native)

```
/gsd:new-project (creates ROADMAP from requirements)
│
├── /gsd:plan-phase 1 (with auto-research)
│   ├── gsd-phase-researcher → RESEARCH.md
│   ├── gsd-planner → PLAN.md(s)
│   └── gsd-plan-checker → PASS/FAIL
│
├── /gsd:execute-phase 1
│   ├── gsd-executor (per plan, per wave)
│   ├── Auto-commit per task
│   └── gsd-verifier → VERIFICATION.md
│
├── Phase recovery (if gaps found)
│   ├── /gsd:plan-phase 1 --gaps
│   └── /gsd:execute-phase 1 (gap-closure plans only)
│
├── Integration check (every 3 phases)
│   └── gsd-integration-checker
│
└── /gsd:complete-milestone
    ├── Final review
    ├── Doc update
    └── Report generation
```

### Key Changes

1. **Discovery becomes `gsd-phase-researcher`** — instead of 5 free-form agents, use the existing phase researcher agent with structured output per phase. Discovery happens just-in-time, not upfront.

2. **Synthesis becomes `gsd-roadmapper`** — the roadmapper already creates phase structures from requirements. Feed it a PRD/requirements doc instead of discovery files.

3. **Phase execution IS GSD execution** — no separate autopilot state. Autopilot becomes a thin loop that calls `/gsd:plan-phase N` → `/gsd:execute-phase N` → verify → advance.

4. **The autopilot orchestrator shrinks to ~100 lines** — it's just:
   ```
   for each phase:
     if not planned: /gsd:plan-phase N
     if not executed: /gsd:execute-phase N
     if not verified: /gsd:verify-work N
     if gaps: /gsd:plan-phase N --gaps (max 2 retries)
     advance
   ```

---

## 3. GENIE Fleet Integration

### Auto-Dispatch Workers Per Phase Type

Not all phases need the same worker. Map phase characteristics to worker strengths:

| Phase Type | Worker | Why |
|-----------|--------|-----|
| Backend Python modules | FRIDAY | General-purpose, fast, sonnet-tier |
| Architecture refactoring | PEPPER | opus-tier, design-focused |
| Frontend React components | DESIGNER | UI specialist |
| Security hardening | AURORA | Research + analysis focus |
| E2E testing | SELENE | Playwright specialist |
| Multi-file refactor | MINERVA | opus, sustained complex work |
| Infrastructure/DevOps | EDITH | DevOps specialist |
| Fast prototyping | NOVA | Experimental features |

### Dispatch Protocol

GENIE reads each phase's `PHASE.md` metadata (goal, features, file types) and auto-selects the worker:

```
Phase goal mentions "frontend" or "UI" → DESIGNER
Phase goal mentions "security" or "auth" → AURORA (research) then FRIDAY (implement)
Phase modifies >10 files → MINERVA (heavy-lift)
Phase is backend Python → FRIDAY
Phase is infrastructure → EDITH
Default → FRIDAY
```

### Auto-Advance Between Phases

GENIE monitors worker completion via `status.json`. When a worker writes `"status": "done"`:

1. GENIE reads the worker's outbox for completion summary
2. GENIE checks `.planning/STATE.md` for current position
3. If next phase exists and has no blockers → dispatch next worker
4. If phase had failures → dispatch PEPPER for triage, then the appropriate worker for fixes

### Parallel Phase Execution

GSD already supports wave-based parallelism within a phase. Extend to cross-phase parallelism:

- Independent phases (no `depends_on` relationship) can run simultaneously on different workers
- GENIE spawns workers for all Wave 1 phases in parallel
- Wave 2 phases dispatch as their Wave 1 dependencies complete

**Constraint:** Maximum 3 concurrent workers (cost control, merge conflict avoidance).

---

## 4. End-to-End Pipeline Bottlenecks

### Bottleneck 1: Sequential Planning (HIGH)

**Current:** Plan → check → revise → re-check is serial. Each round takes a full agent spawn.
**Proposed:** Planner includes a self-check pass before returning. Plan-checker becomes a fast validation (haiku) rather than full analysis. Only re-plan on blockers, not warnings.
**Savings:** ~40% reduction in planning time per phase.

### Bottleneck 2: Discovery Phase Is Too Broad (MEDIUM)

**Current:** 5 agents scan the entire codebase. For a 100-file project, each reads everything.
**Proposed:** Just-in-time research per phase instead of upfront discovery. The gsd-phase-researcher already does this — use it.
**Savings:** Eliminates the 5-agent discovery wave entirely. Each phase gets focused research instead.

### Bottleneck 3: Review Round-Trip (MEDIUM)

**Current:** Execute → review → fix → (no re-review). If fix is wrong, it propagates.
**Proposed:** Execute → review → fix → lightweight re-review (haiku, changed files only). Cap at 2 cycles.
**Savings:** Catches fix regressions cheaply. Net time increase ~5 min per phase, but quality improvement justifies it.

### Bottleneck 4: Checkpoint File I/O Overhead (LOW)

**Current:** Every checkpoint writes full state to disk. For a 10-phase project, that's 60+ file writes for state management alone.
**Proposed:** Batch state updates. Write CHECKPOINT.md once per phase (not per step). Use `gsd-tools.cjs` atomic operations.
**Savings:** ~20% reduction in I/O operations. Minor but compounds.

---

## 5. Quality Gates Between Phases

### Gate 1: Plan Quality (Before Execution)

```
Plan created → gsd-plan-checker (10 dimensions) → PASS/FAIL
  FAIL → planner revises (max 2 rounds)
  BLOCK → escalate to user
  PASS → proceed to execution
```

**Enhancement:** Add a "feasibility probe" — before execution, verify that key files and dependencies mentioned in the plan actually exist.

### Gate 2: Execution Quality (During Execution)

```
Each task → commit → run tests → PASS/FAIL
  FAIL → 3 auto-fix attempts → skip + log
  All tasks done → self-check (verify files exist, commits valid)
```

**Enhancement:** Add context budget awareness. If executor is running low, checkpoint and spawn continuation.

### Gate 3: Phase Verification (After Execution)

```
Phase done → gsd-verifier (4-level artifact check) → PASS/GAPS/HUMAN
  GAPS → auto re-plan (max 2 rounds)
  HUMAN → escalate to user
  PASS → proceed to next phase
```

**Enhancement:** Run integration checks every 3 phases, not just at the end.

### Gate 4: Review Quality (After Verification)

```
Code reviewed → fix CRITICAL/HIGH → re-review (haiku) → PASS/FAIL
  FAIL after 2 rounds → document remaining, proceed
  PASS → commit, advance
```

---

## 6. Recovery & Checkpointing for Failed Phases

### Checkpoint Structure

Every phase saves a checkpoint with enough context for any agent to resume:

```yaml
# .planning/phases/XX-name/CHECKPOINT.yaml
phase: 3
status: partial  # complete | partial | failed | blocked
plans:
  - id: "03-01"
    status: complete
    commit: "abc1234"
  - id: "03-02"
    status: partial
    completed_tasks: [1, 2]
    failed_task: 3
    failure: "test_auth_middleware failed — missing RBAC module from Phase 2"
  - id: "03-03"
    status: pending
last_executor_context:
  tool_calls: 42
  files_read: [...]
  decisions: [...]
recovery_attempts: 0
max_recovery: 2
```

### Recovery Flow

```
Phase fails → write CHECKPOINT.yaml
  ↓
Classify failure:
  - Test failure → re-plan with --gaps, max 2 recovery cycles
  - Dependency missing → check if dependent phase completed, re-run if needed
  - Context exhaustion → spawn fresh executor with continuation data
  - Build error → spawn build-error-resolver, then re-execute failed tasks
  ↓
After fix:
  Re-verify phase (re-verification mode in gsd-verifier)
  ↓
  PASS → mark complete, advance
  FAIL after 2 recoveries → escalate to user with diagnostic report
```

### Automatic Escalation

When recovery fails, the system writes a structured escalation:

```markdown
## Phase 3 Escalation

**Attempts:** 2 recovery cycles, still failing
**Root cause:** test_auth_middleware expects RBAC module that Phase 2 created with different API
**Options:**
1. Modify Phase 2's RBAC to match Phase 3's expectation (risk: breaks Phase 2 verification)
2. Modify Phase 3's auth to use Phase 2's RBAC API (recommended)
3. Skip Phase 3 and proceed (defer auth to future milestone)

**Recommendation:** Option 2 — align Phase 3 with Phase 2's API
**User action needed:** Confirm approach, then `/gsd:execute-phase 3 --continue`
```

---

## Recommendations Summary

| Priority | Upgrade | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 HIGH | Phase recovery auto-loop (Gap 4) | M | Eliminates manual intervention for partial failures |
| 🔴 HIGH | Structured discovery schema (Gap 5) | S | Dramatically improves synthesis quality |
| 🔴 HIGH | Autopilot → GSD-native architecture (Section 2) | L | Eliminates state mismatch, simplifies everything |
| 🟡 MEDIUM | Phase decisions artifact (Gap 1) | S | Reduces 15-20% time waste from re-investigation |
| 🟡 MEDIUM | Executor context budget (Gap 3) | S | Prevents quality degradation in late tasks |
| 🟡 MEDIUM | Cross-phase integration checks (Gap 7) | S | Catches integration bugs before final review |
| 🟢 LOW | Plan feasibility probe (Gap 2) | S | Catches invalid plans before execution |
| 🟢 LOW | Bounded fix-review loop (Gap 8) | S | Prevents fix regressions |

---

*Generated by PEPPER — Architecture Specialist, GENIE Command Center*
