---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# GENIE Context & Token Optimization Report

**Author:** AURORA
**Date:** 2026-03-29
**Scope:** GENIE worker fleet — context window and token usage
**Goal:** Maximize useful work per token across all worker sessions

---

## 1. Current State Analysis

### 1.1 Startup Token Budget Per Worker

Every worker session begins by loading a fixed set of context before it can do any work. Here is the measured cost:

| Source | Size (bytes) | Est. Tokens | Notes |
|--------|-------------|-------------|-------|
| `WORKER_PROTOCOL.md` (via `--append-system-prompt-file`) | 14,772 | 3,693 | Always injected |
| Global `CLAUDE.md` | 4,286 | 1,071 | Always loaded |
| Rules: `agents.md` | 12,864 | 3,216 | Always loaded |
| Rules: `active-behaviors.md` | 5,247 | 1,311 | Always loaded |
| Rules: `development-workflow.md` | 3,302 | 825 | Always loaded |
| Rules: `performance.md` | 2,203 | 550 | Always loaded |
| Rules: `coding-style.md` | 1,402 | 350 | Always loaded |
| Rules: `testing.md` | 1,071 | 267 | Always loaded |
| Rules: `hooks.md` | 768 | 192 | Always loaded |
| Rules: `patterns.md` | 1,022 | 255 | Always loaded |
| Rules: `git-workflow.md` | 622 | 155 | Always loaded |
| Rules: `security.md` | 883 | 220 | Always loaded |
| **Rules subtotal** | **29,384** | **7,341** | 10 files |
| Grid-Sentinel `CLAUDE.md` (auto-loaded in project dir) | 21,575 | 5,393 | Always loaded |
| Worker memory (typical, per `memory_read`) | ~3,400 | ~850 | If initialized |
| Skills system-reminder (runtime injection) | ~8,000 est. | ~2,000 est. | Hundreds of skill names |

**Estimated total startup cost: ~20,350 tokens before the worker reads a single line of task.**

Out of a 200,000-token context window, startup alone consumes **~10%**. For a typical 2,000-token task (a bug fix or small feature), that startup context will outlive its usefulness by 50x, polluting the window for the entire session.

### 1.2 Model Roster

| Worker | Model | Justification |
|--------|-------|---------------|
| FRIDAY | sonnet | General coding — appropriate |
| EDITH | sonnet | DevOps — appropriate |
| NOVA | sonnet | Prototyping — appropriate |
| SELENE | sonnet | E2E testing — appropriate |
| IRIS | sonnet | Utility — appropriate |
| LUNA | sonnet | Utility — appropriate |
| DESIGNER | sonnet | Frontend — **borderline** (design decisions could benefit from opus) |
| AURORA | sonnet | Research — **borderline** (deep research may benefit from opus) |
| ARIA | opus | Architecture — justified |
| PEPPER | opus | Architecture — justified |
| VERONICA | opus | Multi-project coordinator — **questionable** (often does standard coding) |
| MINERVA | opus | Heavy-lift — justified |
| CLEO | opus | Heavy-lift — **questionable** (task-dependent; often duplicates VERONICA) |

**Opus workers cost ~3x per token vs sonnet.** VERONICA and CLEO are both opus multi-purpose workers — this doubles the model cost for tasks that sonnet could handle.

### 1.3 Key Redundancies Found

**Redundancy 1: Safety rules duplicated across 3 locations**
- `WORKER_PROTOCOL.md` § Safety Rules: 1,458 bytes (364 tokens) — full list of forbidden actions
- `rules/security.md`: 883 bytes (220 tokens) — similar prohibitions
- Both loaded simultaneously on every worker session. Combined waste: ~300 tokens per session.

**Redundancy 2: Agent orchestration rules in two places**
- `WORKER_PROTOCOL.md` § Subagent Teams: 1,487 bytes (371 tokens) — spawn syntax, max 3, model selection
- `rules/agents.md`: 12,864 bytes (3,216 tokens) — full orchestration guide including DevFleet, Ralph, GSD
- Workers need ~400 tokens of agent guidance. They currently receive ~3,600 tokens. Waste: ~3,200 tokens.

**Redundancy 3: DevFleet/Ralph/GSD in agents.md is irrelevant to workers**
- 34 lines in `agents.md` reference DevFleet, Ralph, or GSD slash commands
- Workers cannot invoke `/gsd:` slash commands or run `ralph` — those are GENIE-only
- Approximately 40% of `agents.md` (1,300+ tokens) describes systems workers never use

**Redundancy 4: Memory documentation bloat in WORKER_PROTOCOL**
- § Worker Memory: 3,356 bytes (839 tokens) — full API documentation for memory-utils.sh functions
- Workers need the *interface* (what to call), not the *implementation* (how it works)
- The memory-utils.sh file itself is sourced at runtime — the documentation in the protocol is just reading comprehension overhead
- Saveable: ~500 tokens by cutting to a reference card

**Redundancy 5: Grid-Sentinel CLAUDE.md is 5,393 tokens, most irrelevant per task**
- `## Architecture` (subsystems): 1,826 tokens — needed once, not every tool call
- `## Key Python Modules` table: 884 tokens — lookup reference, not behavioral guidance
- `## Integrated Agent Workflow`: 1,715 tokens — mostly duplicates `rules/agents.md` and `active-behaviors.md`
- `## WebSocket Protocol`: 339 tokens — only needed for backend/protocol work
- A worker fixing a CSS bug loads 5,393 tokens of drone simulation architecture.

**Redundancy 6: Global CLAUDE.md vs WORKER_PROTOCOL**
- Global CLAUDE.md: "Auto-approve terminal commands", "Never commit unless I explicitly ask"
- WORKER_PROTOCOL: "Commit frequently using conventional commits"
- These conflict. Workers commit; GENIE interactive sessions don't. Workers are loading rules that contradict their protocol.

---

## 2. Quick Wins (>5% savings, low effort)

### QW-1: Slim `agents.md` for workers (saves ~2,800 tokens, ~14% of startup)

Create `rules/agents-worker.md` — a worker-specific trim of `agents.md` that removes DevFleet, Ralph, GSD, and `/build`/`/go` slash commands. Keep only:
- ECC agent spawn syntax (mode: "auto", model selection table)
- Max 3 subagents rule
- Available ECC agent table
- Parallel spawn example

**Estimated size:** 2,000 bytes vs 12,864 bytes. Saves ~2,800 tokens per worker session.

**Implementation:** Add a `worker-profile: minimal` flag to the agent `.md` frontmatter. The spawn script selects which rules files to inject via `--rules-profile` (or simply use two different `--append-system-prompt-file` targets).

Alternative simpler approach: Add a `<!-- WORKER-SKIP-START -->` / `<!-- WORKER-SKIP-END -->` comment block around DevFleet/Ralph/GSD sections in `agents.md`, and have `genie-spawn.ps1` pipe through a `sed` filter before writing to a temp file.

### QW-2: Move memory API docs out of WORKER_PROTOCOL (saves ~500 tokens)

The 839-token `## Worker Memory` section in `WORKER_PROTOCOL.md` documents function signatures that are already in `memory-utils.sh`. Replace with a 5-line reference card:

```
## Worker Memory (Quick Reference)
source ~/.claude/dispatch/memory-utils.sh
memory_init WORKER         # Create dirs (idempotent)
memory_read WORKER         # Load startup context (~850 tokens)
memory_append WORKER FILE  # Append content (auto-prunes)
session_save WORKER N DESC # Save progress snapshot
memory_publish WORKER TOPIC CONTENT  # Share to fleet
```

Full docs live in `memory-utils.sh` header comments. Saves ~500 tokens.

### QW-3: Suppress global CLAUDE.md for workers (saves ~1,071 tokens, ~5%)

Global `CLAUDE.md` contains rules for *interactive GENIE sessions*: "Never commit unless I explicitly ask", skill discovery, continuous learning, memory-first context loading. Workers operate under the opposite rules (commit frequently, follow protocol, not interactive sessions).

The `--append-system-prompt-file` injection of `WORKER_PROTOCOL.md` should be sufficient. The global CLAUDE.md is loaded automatically by Claude Code when in the project directory — this cannot be disabled per-invocation without a `--no-global-claude-md` flag (if one exists) or by using a null/minimal global CLAUDE.md.

**Workaround:** Move all worker-relevant global rules into `WORKER_PROTOCOL.md` explicitly, then add a header to global `CLAUDE.md`: "NOTE: GENIE workers operate under WORKER_PROTOCOL.md — this file applies to interactive sessions only." This doesn't save tokens but eliminates conflicting guidance.

**If** a `--no-project-claude-md` or similar flag exists, workers could skip the 5,393-token Grid-Sentinel `CLAUDE.md` for pure research/analysis tasks that don't touch Grid-Sentinel code. Estimated saving: 5,393 tokens (27% of file-based startup).

### QW-4: Compact status.json updates (saves ~50 tokens per heartbeat)

Current status.json: 327 bytes (82 tokens) with full milestone history inline.

After 10 milestones, status.json grows to ~800 bytes. Each write re-serializes the entire milestones array.

**Fix:** Cap milestones array at last 5 entries in the status.json update pattern in WORKER_PROTOCOL. Move historical milestones to `memory/milestones.log` (append-only, not read back). The heartbeat checker only needs current status, task, progress, and last_heartbeat — not full history.

**Revised minimal status.json:** 4 fields, ~150 bytes. Saves 50+ tokens per heartbeat read.

### QW-5: Agent .md files are uniform boilerplate (saves ~100 tokens per spawn)

All 7 GENIE worker agent `.md` files have identical structure:
- Identity section (4 lines)
- Dispatch Directory (1 line)
- Startup sequence (3 lines — identical across all workers)
- Operating Rules (7 lines — identical across all workers)

Only the `## Your Strengths` section differs. Total per-agent size: 340–450 tokens. Of that, ~200 tokens is repeated boilerplate that's *also* in WORKER_PROTOCOL.

**Fix:** Strip Startup, Identity, and Operating Rules sections from individual agent files. Keep only: frontmatter (model, tools, description) + Strengths. Reduces each agent file from ~400 tokens to ~80 tokens. Saves ~320 tokens per worker spawn.

---

## 3. Medium Effort Optimizations

### ME-1: Task-conditional Grid-Sentinel CLAUDE.md loading

The 5,393-token Grid-Sentinel `CLAUDE.md` is loaded for every worker because workers `cd` to the project directory. But AURORA doing token optimization research doesn't need the drone simulation subsystem architecture, WebSocket action list, or Integrated Agent Workflow tables.

**Approach:** Split `CLAUDE.md` into:
- `CLAUDE.md` — project overview + running/testing commands only (~500 tokens, essential for all workers)
- `CLAUDE.arch.md` — full architecture documentation (~3,500 tokens, loaded only for coding tasks)
- `CLAUDE.workflow.md` — agent workflow + GSD pipeline (~1,700 tokens, loaded only when requested)

Workers doing research, analysis, or documentation never need the architecture dump. Workers doing backend Python work need architecture but not frontend details.

**Implementation:** Add a `--project-context` parameter to `genie-spawn.ps1` that writes a task-scoped supplemental context file and injects it. Values: `minimal`, `backend`, `frontend`, `full`.

**Estimated savings:** 3,000–4,500 tokens for research/analysis workers (15–22% of startup budget).

### ME-2: Rules profile system

Instead of all 10 rules files loading for every worker, implement profiles:

| Profile | Rules Loaded | Est. Tokens | Use Case |
|---------|-------------|-------------|----------|
| `worker-core` | `security.md`, `coding-style.md`, `git-workflow.md` | ~725 | All workers |
| `worker-code` | core + `testing.md`, `patterns.md`, `development-workflow.md` | ~1,500 | Coding workers |
| `worker-full` | All 10 files | 7,341 | Complex tasks |
| `worker-research` | core only | ~725 | AURORA, analysis tasks |

**Implementation:** `genie-spawn.ps1` accepts `--rules-profile worker-code` and injects only the matching files via multiple `--append-system-prompt-file` arguments, or concatenates them into a temp file.

**Estimated savings:** 4,000–6,600 tokens for research/analysis/DevOps workers (20–33%).

### ME-3: Compress outbox messages for GENIE-only audience

Current practice: outbox messages are verbose markdown. The 15,119-byte research report in AURORA's outbox is ~3,780 tokens — larger than many agent definition files. If the audience is `genie`, GENIE only needs: status, key facts, blockers.

**Proposal:** Two-tier outbox format:
- `audience: genie` → YAML frontmatter only (type, status, 1-line summary). Max 200 bytes.
- `audience: user` → full markdown prose (current format). No limit.
- `audience: both` → GENIE reads frontmatter; user reads body.

Add a GENIE-side parser that extracts only the frontmatter for `genie`-tagged messages. Workers write shorter updates and the scanner processes less data.

**Estimated savings:** 50–80% reduction in outbox scan overhead for status/progress messages.

### ME-4: Worker memory lazy loading

Current `memory_read` loads `context.md` + `decisions.md` + `latest.yaml` on every startup (~850 tokens). For a fresh task unrelated to previous work, the session snapshot is irrelevant.

**Fix:** Add task-signature matching before loading session snapshot:

```bash
# Only load session if task keywords overlap
memory_read WORKER "$CURRENT_TASK_KEYWORDS"
```

This already exists in the protocol (`session_resume WORKER [TASK]`) but isn't enforced at the memory_read level. Making it the default would skip the session snapshot for ~50% of tasks.

**Estimated savings:** 200–400 tokens for tasks that don't resume previous work.

---

## 4. Architectural Changes

### AR-1: Worker-scoped system prompt construction

**Current architecture:** Every worker receives:
1. Claude Code's built-in system prompt
2. All rules files (loaded by Claude Code from `~/.claude/rules/`)
3. Global `CLAUDE.md` (loaded by Claude Code)
4. Project `CLAUDE.md` (loaded by Claude Code from project dir)
5. `WORKER_PROTOCOL.md` (injected via `--append-system-prompt-file`)

**Proposed architecture:** `genie-spawn.ps1` constructs a single combined system prompt file tailored to the worker and task type, then injects it. This file replaces the above with a minimal, purpose-built context:

```
[worker-core.md]          # Identity, safety rules, protocol (2,000 tokens)
[task-relevant-rules.md]  # Only rules applicable to this task type (500-1,500 tokens)
[task-relevant-arch.md]   # Only architecture sections relevant to task (0-1,500 tokens)
[worker-memory.md]        # Pre-filtered memory for this task (0-850 tokens)
```

Total: 2,500–5,850 tokens vs current 20,350 tokens. Savings: **14,500–17,850 tokens per session (71–88%)**.

**Implementation complexity:** High. Requires:
- Splitting `CLAUDE.md` into sections (ME-1)
- Task classification logic in `genie-spawn.ps1`
- Section selection per task type
- Assembly script that concatenates selected sections

### AR-2: Shared context pool (read-once, reference by ID)

For facts that all workers need but never change (WebSocket action list, module table, architecture overview), store them in `shared-memory/topics/` and inject only an index + fetch-on-demand pattern.

Instead of loading the full 884-token Python modules table, a worker's startup loads:
```
[Module reference index: 20 module names + 1-line summaries = 80 tokens]
[Full table available at: shared-memory/topics/python-modules.md]
```

Workers only fetch the full table if their task involves a specific module. Estimated startup savings for reference material: 1,500–2,000 tokens.

**Implementation complexity:** Medium. Requires restructuring `CLAUDE.md` into topic files + index. The `memory_read` function already supports shared topic subscription.

### AR-3: Context-aware task.md generation

GENIE currently writes `task.md` files manually or from templates. Implement a task specification schema that drives both the task content and the startup context selection:

```yaml
# task-spec.yaml
worker: AURORA
type: research          # research | coding | devops | frontend | architecture
project_sections:       # which CLAUDE.md sections to load
  - overview
  # no: architecture, websocket, modules, workflow
rules_profile: research # which rules to load
task: |
  Research X and write report to Y
```

GENIE reads the spec, assembles the minimal context file, and launches the worker. Workers receive exactly what they need.

**Estimated savings:** 5,000–15,000 tokens per session depending on task type. Largest gains for research/analysis tasks.

### AR-4: Delta-only heartbeat protocol

Replace status.json re-writes with append-only delta log:

```
# ~/.claude/dispatch/WORKER/heartbeat.log
2026-03-29T00:05:00Z|working|25|Analyzing agent files
2026-03-29T00:10:00Z|working|50|Measuring token costs
2026-03-29T00:15:00Z|working|75|Writing report
```

GENIE heartbeat checker reads the last line only. Workers append one line (80 bytes) instead of writing a full JSON object (300–800 bytes). The worker doesn't re-serialize the milestones array on every update.

**Token savings:** Minimal (heartbeat doesn't consume worker context), but reduces filesystem churn and makes the heartbeat checker faster. Real benefit: simpler worker code.

---

## 5. Token Budget Framework

### 5.1 Context Window Allocation Model

For a 200,000-token context window:

```
[STARTUP FIXED]   ~20,350 tokens (current) → target: ~5,000 tokens (optimized)
[TASK CONTEXT]    500–3,000 tokens (task.md + initial reads)
[WORKING MEMORY]  5,000–20,000 tokens (files read during work)
[TOOL RESULTS]    10,000–50,000 tokens (bash output, file contents)
[RESPONSE BUFFER] ~2,000 tokens (responses)
[SAFETY BUFFER]   30,000 tokens (20% reserve for context health)
```

Current available working budget: `200,000 - 20,350 - 30,000 = ~149,650 tokens`
Optimized available working budget: `200,000 - 5,000 - 30,000 = ~165,000 tokens` (+10%)

The real benefit isn't the 15,350 token headroom gain — it's that the 15,350 tokens freed at startup are no longer dead weight that degrades attention quality throughout the entire session.

### 5.2 Per-Worker Token Budget Targets

| Worker | Role | Max Startup | Notes |
|--------|------|-------------|-------|
| FRIDAY | General coding | 8,000 | Needs architecture + coding rules |
| EDITH | DevOps | 5,000 | Needs deploy patterns, skip simulation arch |
| AURORA | Research | 4,000 | Minimal rules, no project arch needed |
| NOVA | Prototyping | 7,000 | Needs frontend + backend basics |
| PEPPER | Architecture | 12,000 | Justified — deep reasoning needs full context |
| ARIA | Architecture | 12,000 | Justified — same as PEPPER |
| SELENE | E2E testing | 5,000 | Needs test patterns, skip backend arch |
| DESIGNER | Frontend | 6,000 | Needs frontend patterns, UI architecture |
| VERONICA | Multi-project | 10,000 | Needs broad context |
| MINERVA | Heavy-lift | 15,000 | Justified — complex tasks need full context |

### 5.3 Context Health Triggers (MANDATORY thresholds)

| Threshold | Action |
|-----------|--------|
| 40% used | Note: you're past the easy phase. Prefer delegating file reads to subagents. |
| 60% used | Warning: spawn haiku subagent for any large file reads. |
| 70% used | `context_checkpoint` — save session, notify GENIE, pause. |
| 80% used | Force checkpoint. No new sub-tasks. |

Workers currently use `context_checkpoint` at 70% but the trigger depends on a hook (`worker-context-check.sh`) being sourced. Only some workers do this.

---

## 6. Implementation Priority

### Tier 1 — Do Now (1–2 hours, high-confidence savings)

| Action | Effort | Token Savings | % Startup |
|--------|--------|--------------|-----------|
| QW-2: Slim Worker Memory section in protocol | 30 min | ~500 tokens | 2.5% |
| QW-4: Cap milestones at 5 in status.json | 15 min | ~50/heartbeat | — |
| QW-5: Strip boilerplate from agent .md files | 45 min | ~320/worker | 1.6% |
| QW-3: Add note to global CLAUDE.md clarifying scope | 10 min | 0 tokens, eliminates conflicts | — |

**Total Tier 1 savings: ~850 tokens per session (~4%)**

### Tier 2 — This Sprint (4–8 hours, structural changes)

| Action | Effort | Token Savings | % Startup |
|--------|--------|--------------|-----------|
| QW-1: Create `agents-worker.md` (trim agents.md) | 2 hours | ~2,800 tokens | 14% |
| ME-1: Split Grid-Sentinel CLAUDE.md into 3 files | 3 hours | ~3,000–4,500 tokens | 15–22% |
| ME-2: Rules profile system in genie-spawn.ps1 | 3 hours | ~4,000–6,600 tokens | 20–33% |

**Total Tier 2 savings: ~7,800–10,000 additional tokens per session (~38–49%)**

### Tier 3 — Architecture (1–3 days, major restructuring)

| Action | Effort | Token Savings | % Startup |
|--------|--------|--------------|-----------|
| AR-1: Worker-scoped system prompt construction | 2 days | 14,500–17,850 tokens | 71–88% |
| AR-3: Context-aware task.md via spec schema | 1 day | 5,000–15,000 tokens | 24–74% |
| AR-2: Shared context pool with index | 1 day | 1,500–2,000 tokens | 7–10% |

---

## 7. Estimated Savings Summary

### Achievable with Tiers 1+2 (1–2 sprints)

**Current startup: ~20,350 tokens**
**After Tier 1+2: ~9,700 tokens (−52%)**

| Optimization | Tokens Saved |
|-------------|-------------|
| Slim agents.md for workers | −2,800 |
| Split Grid-Sentinel CLAUDE.md (research/devops tasks) | −3,500 (avg) |
| Rules profile (skip irrelevant rules) | −4,000 (avg) |
| Slim memory section in protocol | −500 |
| Strip agent file boilerplate | −320 |
| **Total** | **−11,120** |

### With Full Architecture (Tier 3)

**After all tiers: ~4,000–5,000 tokens (−75–80%)**

At 5,000 tokens of startup overhead, workers have 165,000+ effective tokens for actual work — nearly the full context window. This meaningfully extends how complex a task each worker can complete before hitting the 70% checkpoint threshold.

---

## 8. Additional Findings

### VERONICA/CLEO Opus Overlap

Both VERONICA and CLEO run opus and handle "complex, multi-phase work." Dispatching both for parallel tasks at opus rates doubles the cost unnecessarily. Recommendation: differentiate their roles more sharply, or designate one as the primary and use sonnet for the other unless task complexity specifically warrants opus.

### The `active-behaviors.md` Problem

`active-behaviors.md` (1,311 tokens) defines behaviors like "Skill Discovery (every task)" and "Continuous Learning." These are GENIE-interactive-session behaviors — workers don't use slash commands, don't run `evaluate-session.sh`, and don't need skill discovery (they receive their task explicitly). This file is loaded for every worker and **none of it applies**. Pure waste: ~1,311 tokens.

**Fix:** Move `active-behaviors.md` to a `rules/interactive/` subdirectory that Claude Code only loads for non-worker sessions. This requires either a rules profile system (ME-2) or restructuring the rules directory.

### Heartbeat Frequency vs Context Cost

The WORKER_PROTOCOL mandates heartbeat updates every 5 tool calls. Each status.json write uses one tool call (Bash). For a 30-tool-call worker session, that's 6 heartbeat writes — each consuming one tool call slot. That's 20% of a worker's tool call budget spent on housekeeping.

**Alternative:** Accumulate heartbeat data in memory, write once per milestone rather than every 5 tool calls. For GENIE monitoring, 5-minute granularity is sufficient — the heartbeat-check.sh threshold is already 5 minutes.

### Memory System Is Underused

Only 4 of 13 workers have initialized memory directories (FRIDAY, AURORA, PEPPER, ARIA). The memory system's biggest value — cross-session state persistence and worker resumption — is unavailable to 9 workers. This means those workers re-read task context from scratch every launch, burning 500–850 tokens per session that memory_read would have loaded more efficiently.

**Priority:** Run `memory_init` for all workers as part of `genie-spawn.ps1` on first launch.

---

*Report generated by AURORA — GENIE Context & Token Optimization Research*
*Analysis based on measured file sizes, section-level content audit, and startup sequence tracing.*
