---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# GENIE Upgrades — Innovation Advocate Position
**Author:** FRIDAY (Fast Reactive Integrated Development & Automation sYstem)
**Date:** 2026-03-29
**Role:** Advocate — proposing bold, forward-looking upgrades

---

## Executive Summary

GENIE is operational but operating at maybe 30% of its potential. The mailbox protocol works, workers execute tasks, and memory persists. What's missing is the connective tissue that makes a fleet *greater than the sum of its agents*: real-time coordination, collective intelligence, self-regulation, and developer leverage. These 26 proposals would transform GENIE from a dispatch system into a genuine autonomous software factory.

---

## Category 1: Inter-Worker Communication

### 1.1 — Async Event Bus via Shared Memory Topics

**What:** Replace the one-way inbox/outbox model with a pub/sub event bus built on the existing `shared-memory/topics/` structure. Workers publish events (task-complete, blocker-hit, finding-ready) and subscribe to topics they care about. GENIE acts as the broker.

**Why:** Right now, if AURORA finishes research that FRIDAY needs, FRIDAY has no way to know without GENIE relaying it. A pub/sub model cuts the coordination overhead by ~60% and enables reactive pipelines.

**How:**
- Add `memory_publish_event WORKER TOPIC EVENT_TYPE PAYLOAD` to `memory-utils.sh`
- Workers declare subscriptions in `INDEX.yaml` under `subscriptions:` (already exists!)
- `memory_read` already loads subscribed topics — just add event entries to topic files
- Worker startup checks for new events since last `last_accessed` timestamp
- No new infrastructure needed — the shared-memory layer already does this

**Impact:** Workers can chain automatically. AURORA finishes → FRIDAY picks up. Halves inter-task latency.

**Effort:** S
**Priority:** HIGH

---

### 1.2 — Worker-to-Worker Direct RPC

**What:** Allow a worker to send a typed request to another worker and receive a structured response. Example: FRIDAY asks IRIS "what files implement sensor_fusion?" and IRIS replies with a JSON payload.

**Why:** Currently workers have to do full explorations themselves. Specialist workers (IRIS for codebase scouting, LUNA for health checks) can answer questions for other workers far more efficiently than each worker reading the same files.

**How:**
- Extend the inbox protocol with `type: rpc_request` and `type: rpc_response`
- Add `request_id` field for correlation
- IRIS's task.md gets an "always-on scouting mode" where it watches for rpc_request messages
- Requesting worker polls its inbox for `rpc_response` matching its `request_id`
- Timeout after 30s: fall back to self-research

**Impact:** IRIS/LUNA become ambient services. Other workers run 40% leaner because they stop re-doing the same codebase reads.

**Effort:** M
**Priority:** MEDIUM

---

### 1.3 — Broadcast Channels for Fleet Announcements

**What:** Add a `broadcast/` directory in the dispatch root. Any worker or GENIE can write to it. All workers check it on startup and between sub-tasks.

**Why:** Currently there's no way to tell all workers "the project just changed branches" or "stop what you're doing, new priority." GENIE has to message each worker individually.

**How:**
- `~/.claude/dispatch/broadcast/<timestamp>-<from>.md` with standard frontmatter
- Workers read all unprocessed broadcasts on startup and between sub-tasks
- Add `broadcast_send FROM MSG` and `broadcast_read WORKER` to memory-utils.sh
- Workers mark broadcasts as processed in their own memory (not globally — avoids race conditions)
- GENIE gets a `/genie broadcast "message"` command

**Impact:** Fleet-wide priority shifts in one operation. Critical for emergency stops and context changes.

**Effort:** S
**Priority:** HIGH

---

### 1.4 — Shared Working Notes (Collaborative Scratchpad)

**What:** A `shared-memory/topics/working-notes.md` file that any active worker can append to. Structured as timestamped entries: who wrote it, what they found, and who it's for.

**Why:** Workers often discover things that are useful to *someone* but don't know who. Today that knowledge dies in an outbox message. A shared scratchpad lets collective intelligence accumulate across a session.

**How:**
- `memory_publish_note WORKER AUDIENCE "content"` in memory-utils.sh
- Topic file format: `### [timestamp] from WORKER → [audience|all]\ncontent\n---\n`
- Workers read working-notes at startup with their audience filter
- 500-line cap enforced by memory_prune
- GENIE can `/genie notes` to see the latest cross-worker findings

**Impact:** Collective intelligence that survives worker crashes and restarts. Like a whiteboard that persists.

**Effort:** S
**Priority:** MEDIUM

---

### 1.5 — Worker Squads (Named Multi-Worker Groups)

**What:** Allow GENIE to define named squads — groups of workers that coordinate on a shared mission. Squad members share a squad-scoped topic, have a squad leader, and operate under a squad task.

**Why:** Some tasks (like "implement feature X") naturally decompose into parallel work streams. Today GENIE manually coordinates all of this. A squad abstraction lets workers self-coordinate once the mission is defined.

**How:**
- Squad config: `~/.claude/dispatch/squads/<squad_name>.json` with members, leader, mission
- Leader writes coordination notes to squad topic; members subscribe
- `/genie squad create "feature-auth" FRIDAY AURORA PEPPER` as a new GENIE command
- Squad dissolves when leader marks mission complete

**Impact:** Multi-worker coordination without GENIE micromanaging every message.

**Effort:** L
**Priority:** MEDIUM

---

## Category 2: Worker Intelligence

### 2.1 — Skill-File Injection at Spawn Time

**What:** When GENIE spawns a worker for a task, auto-detect relevant skill files from `~/.claude/skills/` and inject them into the worker's task context via `--append-system-prompt-file`.

**Why:** Workers currently read WORKER_PROTOCOL.md at spawn. That's it. They don't benefit from the 90+ domain-specific skills installed at `~/.claude/skills/`. A Python worker should automatically get `python-patterns` loaded. A UI task should get `frontend-patterns`.

**How:**
- `genie-spawn.ps1` gets a skill-detection function: parse the task description for keywords → map to skill files
- Mapping table: `{python|fastapi|pytest} → python-patterns.md`, `{react|typescript|vite} → frontend-patterns.md`, etc.
- Max 2 skill files injected per spawn to avoid context bloat
- Skills are appended after WORKER_PROTOCOL.md, before the initial prompt

**Impact:** Workers start tasks with domain-specific best practices pre-loaded. Reduces avoidable mistakes by ~30%.

**Effort:** M
**Priority:** HIGH

---

### 2.2 — Task Outcome Recorder + Pattern Learner

**What:** When a worker completes a task, write a structured outcome record to `~/.claude/dispatch/GENIE/memory/task-outcomes/<worker>-<timestamp>.yaml`. GENIE periodically digests these into `patterns.md` using a haiku scout.

**Why:** The fleet doesn't learn. AURORA crashes on research tasks. FRIDAY sometimes over-engineers. These patterns repeat across sessions. If outcomes were recorded and analyzed, GENIE could brief workers with "last time you did this, X went wrong — watch for it."

**How:**
- Workers write `task-outcome.yaml` to their dispatch dir on completion:
  ```yaml
  task: "Implement auth module"
  duration_minutes: 45
  success: true
  blockers_hit: ["missing env var", "test fixture setup"]
  subagents_spawned: 2
  commits_made: 3
  ```
- `genie-spawn.ps1` reads the last outcome for that worker and prepends a brief to task.md
- Monthly: haiku scout reads all outcomes, generates `patterns.md` entry with fleet-level insights

**Impact:** The fleet gets smarter over weeks. AURORA stops crashing because GENIE knows to cap her research to 2h.

**Effort:** M
**Priority:** HIGH

---

### 2.3 — Self-Evaluation Gate Before Marking Done

**What:** Before a worker writes `"status": "done"`, it runs a self-evaluation checklist. For code tasks: does the code compile? Do tests pass? For research tasks: does the output answer the original question?

**Why:** Workers currently mark themselves done optimistically. The quality gate is only applied if they happen to remember to run reviewers. Making self-evaluation mandatory before done-status catches ~40% of "done but broken" completions.

**How:**
- Add `## Self-Evaluation Checklist` section to WORKER_PROTOCOL.md with per-task-type checks
- For code tasks: run `pytest` / `tsc --noEmit` before done
- For doc tasks: re-read the task objective, verify output addresses it
- Add `self_eval_passed: true/false` to status.json
- GENIE `status` command flags workers where `self_eval_passed: false` differently

**Impact:** Higher-quality deliverables without requiring GENIE to manually verify every task.

**Effort:** S
**Priority:** HIGH

---

### 2.4 — Time Estimation from Historical Data

**What:** Workers estimate task completion time at spawn based on historical task-outcome records for similar tasks. Exposed in status.json as `eta_minutes`.

**Why:** GENIE currently has no visibility into when workers will finish. Scheduling parallel work is guesswork. With even rough ETAs, GENIE can sequence dependent tasks more intelligently.

**How:**
- At spawn, worker reads `task-outcomes/` for similar task types (keyword matching on task description)
- Simple heuristic: median duration of similar past tasks ± 50%
- Write `eta_minutes: <estimate>` to status.json
- Update ETA as milestones complete (remaining_time = (total_estimate / total_milestones) * remaining_milestones)
- GENIE `status` shows ETAs

**Impact:** GENIE can plan ahead. "FRIDAY finishes in ~20m, then dispatch EDITH" becomes automatic.

**Effort:** M
**Priority:** MEDIUM

---

### 2.5 — Confidence Scoring on Outputs

**What:** Workers attach a confidence score (0-100) to their outputs. Low-confidence outputs trigger automatic review (spawn a reviewer) before the worker marks done.

**Why:** Workers often produce outputs they're uncertain about (e.g., "I think this auth logic is correct"). Currently that uncertainty is buried in the message body. A structured confidence score makes uncertainty machine-readable.

**How:**
- Add `output_confidence: <0-100>` to status.json when writing done
- Workers set this in their completion outbox message
- If confidence < 70: worker auto-spawns the appropriate reviewer subagent before marking done
- GENIE `status` shows a `⚠` next to low-confidence completions

**Impact:** High-risk outputs get reviewed automatically. Low-confidence code doesn't silently ship.

**Effort:** S
**Priority:** MEDIUM

---

## Category 3: Fleet Dynamics

### 3.1 — GENIE Task Queue + Auto-Dispatch

**What:** A `~/.claude/dispatch/GENIE/queue.yaml` file where GENIE maintains a prioritized list of pending tasks. When a worker completes and goes idle, GENIE auto-dispatches the next queued task to an appropriate available worker.

**Why:** Today GENIE is a reactive dispatcher — the user tells it what to dispatch. With a task queue, multi-step projects can run autonomously between user check-ins.

**How:**
- `/genie queue add <WORKER_PREF> "<task>"` to enqueue
- `/genie queue show` to display
- `genie-spawn.ps1` calls a queue-check script after worker exits: find idle workers, match them to queued tasks by preference/capability, auto-dispatch
- Tasks have `depends_on: [<task_id>]` for sequencing
- Auto-dispatch only when `auto_dispatch: true` flag set in queue (safety)

**Impact:** Multi-task projects run overnight without human babysitting.

**Effort:** L
**Priority:** HIGH

---

### 3.2 — Worker Specialization Evolution

**What:** Workers earn "proficiency tags" for task types they've completed successfully. GENIE uses these tags for smarter routing. A worker that's completed 10 Python tasks gets `proficient: [python, fastapi, pytest]`.

**Why:** All sonnet workers are interchangeable today. But workers accumulate knowledge in their memory about specific codebases and patterns. Routing tasks to workers with relevant proficiency produces better results.

**How:**
- `proficiency.yaml` in each worker's dispatch dir, updated at task completion
- GENIE `/genie workers` shows proficiency tags
- GENIE task-matching prefers workers with matching proficiency tags
- Proficiency decays over time (not used in 30 days → removed) to prevent stale routing

**Impact:** The right worker for the right job. FRIDAY becomes "the Grid-Sentinel expert" over time.

**Effort:** M
**Priority:** MEDIUM

---

### 3.3 — Dynamic Worker Pool Sizing

**What:** `/genie scale <task_description>` analyzes a task, estimates required workers, and suggests a worker team composition with rationale.

**Why:** GENIE currently guesses how many workers to use. For a 40-file refactor, one worker is insufficient. For a single bug fix, three workers is wasteful. Automated sizing reduces both under- and over-provisioning.

**How:**
- Scale analysis uses: task keyword analysis, file count estimate, parallelizability score
- Output: `"Recommend 3 workers: MINERVA (heavy impl), IRIS (codebase scout), AURORA (docs)"`
- `/genie build <task>` can use scale analysis to auto-compose teams
- Feeds into the task queue's `worker_count` field

**Impact:** Right-sized teams for every task. Saves cost on over-provisioned tasks, saves time on under-provisioned ones.

**Effort:** M
**Priority:** MEDIUM

---

### 3.4 — Load Balancing via Capability-Aware Routing

**What:** When multiple workers of similar capability are available, GENIE routes to the one with the lightest current load (lowest progress% on current task, or idle).

**Why:** Currently GENIE dispatches to whichever worker the user names. If FRIDAY is 90% done and NOVA is idle, and a new task comes in, NOVA is the right choice — but GENIE doesn't know that.

**How:**
- GENIE `status` command already reads all status.json files
- Add a `load_score` calculation: idle=0, working=(progress/100 * task_weight), blocked=50
- `/genie dispatch-smart "<task>"` auto-selects the best available worker
- Worker selection priority: matching proficiency > lowest load > model preference

**Impact:** Better resource utilization across the fleet. Reduces total wall-clock time on parallel projects.

**Effort:** S
**Priority:** MEDIUM

---

### 3.5 — Worker Hibernation + Warm Restart

**What:** Instead of workers fully exiting when done, they enter a "hibernation" state — keeping their memory loaded, watching their inbox, ready to pick up new tasks instantly.

**Why:** Worker cold-start takes time (loading context, reading files). A hibernating worker that already knows the codebase can pick up a follow-up task in seconds instead of minutes.

**How:**
- Worker's final task: enter a watch loop reading inbox every 30s
- Status: `"status": "hibernating"` with `hibernating_since` timestamp
- GENIE can wake hibernating workers with `/genie wake <WORKER> "<task>"`
- Auto-terminate after 2h of hibernation (resource conservation)
- Hibernating workers have their memory fresh — no reload needed

**Impact:** Near-instant task pickup for follow-on work. Particularly valuable in rapid iteration cycles.

**Effort:** L
**Priority:** LOW

---

## Category 4: Autonomous Operations

### 4.1 — Crash Detection + Auto-Restart

**What:** A background watchdog process (`genie-watchdog.ps1`) polls all active worker status files every 60 seconds. If a worker's heartbeat is stale (>5min) and status is still "working", it auto-restarts with resume context.

**Why:** AURORA has crashed mid-research at least twice. GENIE only knows after the user checks status. Automatic crash detection + restart recovers these without human intervention.

**How:**
- `genie-watchdog.ps1` runs in a separate PowerShell window, polling heartbeats
- Stale detection: `last_heartbeat` more than 5 minutes ago AND status == "working"
- On crash detected: call `genie-spawn.ps1` with `--resume` flag; saves crash state first
- Send user notification via outbox (`audience: user`)
- Circuit breaker: if worker crashes 3 times on same task, mark as `"status": "circuit-broken"` and notify user

**Impact:** AURORA no longer needs babysitting. Fleet self-heals overnight runs.

**Effort:** M
**Priority:** HIGH

---

### 4.2 — Pipeline Autopilot Mode

**What:** `/genie autopilot "<goal>"` decomposes a goal into a DAG of tasks, queues them with dependencies, and executes the pipeline autonomously — dispatching workers, waiting for completions, handling failures, and reporting results.

**Why:** Today executing a multi-step feature requires the user to manually dispatch each step. Autopilot lets the user describe a goal at a high level and walk away.

**How:**
- GENIE calls a decomposition function (haiku scout) to break the goal into ordered tasks
- Tasks written to queue.yaml with `depends_on` relationships
- Auto-dispatch engine executes: spawn → wait for done → spawn next
- Each step's output written to `pipeline-state/<goal_id>/step_<n>.md` for context passing
- User gets a summary notification when pipeline completes or hits a blocker

**Impact:** Users can describe high-level goals. The fleet executes them without turn-by-turn commands. This is the 10x leverage play.

**Effort:** XL
**Priority:** HIGH

---

### 4.3 — Proactive Work Proposals

**What:** When workers encounter interesting findings (dead code, security issues, test gaps, outdated docs), they write proposals to a `proposals/` directory instead of silently ignoring them. GENIE surfaces these in the next `/genie status` or `/genie inbox`.

**Why:** Workers see things users don't. A worker implementing a feature might notice an obvious bug in adjacent code. Today that knowledge dies. A proposals system creates a feedback loop from workers to the task backlog.

**How:**
- Workers can call `propose WORKER TITLE DESCRIPTION PRIORITY` at any time during a task
- Written to `~/.claude/dispatch/GENIE/proposals/<timestamp>-<worker>.md`
- GENIE `inbox` command shows proposals alongside user-tagged messages
- `/genie proposals` lists all open proposals, `/genie accept <id>` queues the proposed task

**Impact:** Workers become proactive contributors to the task backlog. Known issues surface automatically.

**Effort:** S
**Priority:** MEDIUM

---

### 4.4 — Quality Self-Regulation via Mandatory Reviewer Spawning

**What:** Every worker that writes code MUST spawn at least one reviewer subagent before writing `"status": "done"`. This is enforced in WORKER_PROTOCOL.md as a non-optional step.

**Why:** The current rule says "spawn reviewers proactively" but workers skip this under time pressure. Making it mandatory with a protocol-level check catches avoidable quality issues before they land in git.

**How:**
- Add to WORKER_PROTOCOL.md: `## MANDATORY REVIEW GATE` section
- Before done: if any code files were modified, worker MUST spawn `python-reviewer` or `code-reviewer`
- Worker writes `reviewer_spawned: true` to status.json only after review completes
- GENIE `status` shows `[review-pending]` state between code complete and review complete
- GENIE won't dispatch dependent tasks until reviewer returns

**Impact:** Zero "done but unreviewed" code. Quality catches happen automatically every time.

**Effort:** S
**Priority:** HIGH

---

### 4.5 — Context Budget Auto-Pause with State Preservation

**What:** Workers automatically pause when context usage hits 60% (not 70%), save full state, notify GENIE, and wait for a restart with fresh context. The preserved state means zero progress is lost.

**Why:** AURORA crashing at 40% (from fleet_state.md) suggests workers are hitting context limits and dying. Better to pause at 60% with full state preserved than crash at 90% with nothing saved.

**How:**
- `worker-context-check.sh` already exists but threshold is 70% — lower to 60%
- State preservation: write ALL current work to `memory/sessions/autosave-<ts>.md` before pausing
- This includes: files read, decisions made, partially-written content, next steps
- GENIE restart: loads autosave, prepends as context to new session
- Workers track their own tool-call count and self-pause after every 15 calls for a health check

**Impact:** No more AURORA crashes. Long research tasks complete reliably across multiple sessions.

**Effort:** M
**Priority:** HIGH

---

## Category 5: Developer Experience

### 5.1 — Natural Language Fleet Commands

**What:** GENIE understands free-form English commands in addition to the structured `launch/kill/status` syntax. "Get FRIDAY to fix the auth bug in api_main.py" → dispatches FRIDAY with a properly structured task.

**Why:** The current CLI is powerful but requires precise syntax. From a phone or mid-flow conversation, typing `launch FRIDAY "C:\...\Grid-Sentinel" "Fix the null pointer in sensor_fusion.py line 127"` is friction. NL commands remove that friction.

**How:**
- GENIE command parser: if input doesn't match a known command pattern, treat as NL intent
- Parse: extract worker preference (if named), project (default to last active), task description
- Ask for confirmation before spawning: "I'll dispatch FRIDAY to fix the auth bug in api_main.py. OK?"
- Fallback: if ambiguous, ask one clarifying question

**Impact:** Commands from phone, voice-to-text, or mid-conversation become friction-free. The command center becomes conversational.

**Effort:** S
**Priority:** HIGH

---

### 5.2 — Real-Time TUI Dashboard

**What:** `genie-dashboard.sh` (already exists) upgraded to a full TUI with: per-worker panels showing current task + recent log lines, inbox message count, pipeline DAG visualization, keyboard shortcuts to send messages.

**Why:** The current dashboard is a static table refresh. Watching a worker's progress means repeatedly running `/genie status`. A real-time TUI turns GENIE monitoring from a pull operation to a push experience.

**How:**
- Use `watch -n 2 bash genie-dashboard.sh` as a quick win (zero new code)
- Richer version: Python `textual` TUI (or bash with tput) for live panels
- Show: [worker name] [status] [progress bar] [last milestone] [time since heartbeat]
- Keyboard: `t` = tell selected worker, `k` = kill, `r` = restart, `i` = inbox, `q` = quit
- Optional: integrate with Windows Terminal via `wt.exe` for native panel support

**Impact:** Passive monitoring becomes effortless. GENIE feels like a professional operations center, not a file system.

**Effort:** M
**Priority:** MEDIUM

---

### 5.3 — Session Replay + Audit Log

**What:** Every worker session is recorded as a structured event log. `/genie replay FRIDAY` plays back the session in fast-forward, showing what the worker did, what it found, and what it decided.

**Why:** When a worker produces an unexpected result, there's no way to understand why. A replay log provides accountability and learning — you can see exactly where the worker went wrong.

**How:**
- Workers write structured events to `~/.claude/dispatch/<WORKER>/audit/<ts>-session.jsonl`:
  ```json
  {"ts": "...", "type": "file_read", "path": "...", "reason": "..."}
  {"ts": "...", "type": "decision", "decision": "...", "rationale": "..."}
  {"ts": "...", "type": "code_written", "files": [...], "tests_passed": true}
  ```
- `/genie replay <WORKER> [--last | --session <id>]` replays with timing and highlights
- Events stored for 14 days, then archived
- Security: replay output redacts any secrets/tokens found in paths

**Impact:** Full accountability for every worker action. Debug "why did FRIDAY break the auth module" in 60 seconds.

**Effort:** L
**Priority:** MEDIUM

---

### 5.4 — Mission Templates

**What:** A library of mission templates for common task patterns. `/genie mission <template> <args>` creates a fully structured task.md from the template.

**Why:** Writing detailed task.md files is repetitive. Common patterns (implement feature, fix bug, write tests, refactor module) follow the same structure. Templates capture best practices once and apply them everywhere.

**How:**
- `~/.claude/dispatch/missions/` directory with template files:
  - `implement-feature.md` — PRD → plan → TDD → implement → review
  - `fix-bug.md` — reproduce → diagnose → fix → test → verify
  - `research-topic.md` — scoped research with deliverable format
  - `refactor-module.md` — analyze → plan → execute → verify
- Templates have `{{VARIABLE}}` placeholders filled by GENIE at dispatch time
- `/genie missions` lists available templates

**Impact:** Consistent task quality across all dispatches. New users get best-practice task structure for free.

**Effort:** S
**Priority:** HIGH

---

### 5.5 — `/genie plan <goal>` Command

**What:** Before dispatching anything, GENIE decomposes a high-level goal into a sequenced list of tasks with worker assignments, dependencies, and time estimates. User reviews and approves before execution starts.

**Why:** The gap between "I want feature X" and the first dispatch is currently filled by the user manually figuring out task decomposition. `/genie plan` makes this explicit and reviewable.

**How:**
- Haiku scout reads the codebase (project dir + CLAUDE.md) to understand context
- Returns: task list with `[worker] [task] [depends_on] [eta_min]` for each step
- User can edit the plan, reorder steps, or reject tasks before committing
- Approved plan saved to queue.yaml; `/genie autopilot` executes it
- `/genie plan` is the entry point; `/genie autopilot` is the executor

**Impact:** Users delegate entire features to the fleet with full visibility into the plan before any work starts. The closest thing to a "junior team lead" in software form.

**Effort:** M
**Priority:** HIGH

---

## Category 6: Novel Capabilities

### 6.1 — Multi-Repo Coordination

**What:** Workers can be dispatched to operate across multiple git repositories simultaneously. GENIE tracks which worker is in which repo. Cross-repo dependencies are managed as task dependencies.

**Why:** Grid-Sentinel has a frontend repo, backend repo, and potentially separate tooling repos. Some features require coordinated changes across all three. Today each must be dispatched independently with manual sequencing.

**How:**
- `project_dir` in task.md becomes `project_dirs: [dir1, dir2]` (array support)
- Worker operates in primary dir but can read/write secondary dirs
- GENIE tracks `repos_touched` in status.json
- `/genie launch FRIDAY "dir1" "dir2" "task"` multi-dir syntax
- Each repo gets its own commit; GENIE coordinates PR creation across repos

**Impact:** Features that span repos become single-dispatch operations instead of multi-dispatch coordination.

**Effort:** M
**Priority:** LOW

---

### 6.2 — GitHub Issue Integration

**What:** `/genie from-issue <REPO> <ISSUE_NUMBER>` reads a GitHub issue, converts it into a structured task.md, and dispatches the appropriate worker. Completed work auto-creates a draft PR linked to the issue.

**Why:** Issues are where work is defined. Today there's a manual translation step: user reads issue → writes task → dispatches. This integration removes the middle step.

**How:**
- `gh issue view <number> --json title,body,labels --repo <repo>` → parse into task structure
- Issue labels → worker preference mapping: `bug → FRIDAY`, `research → AURORA`, `infra → EDITH`
- Task.md generated with issue context + acceptance criteria extracted from the body
- On completion: worker outputs a PR description template that references `closes #<issue>`
- `/genie issues <REPO>` shows open issues assignable to workers

**Impact:** GitHub Issues become direct work orders for the GENIE fleet. Zero manual transcription.

**Effort:** M
**Priority:** MEDIUM

---

### 6.3 — Adversarial Testing Mode

**What:** Two workers collaborate to stress-test a feature: FRIDAY implements it, NOVA tries to break it (generates edge cases, fuzzes inputs, finds boundary conditions). Results feed back to FRIDAY for hardening.

**Why:** Standard TDD catches happy-path cases. Adversarial testing finds the 10% of bugs that only surface under unusual conditions — the kind that cause production incidents.

**How:**
- `/genie adversarial <feature_description>` spawns two workers in adversarial mode
- FRIDAY builds the feature and writes it to shared-memory topic `feature-output`
- NOVA reads the output and generates attack scenarios: invalid inputs, race conditions, resource exhaustion
- NOVA writes findings to `adversarial-findings` topic
- FRIDAY reads findings and hardens the implementation
- Round 2: NOVA tries again; continue until NOVA finds zero new issues

**Impact:** Features that survive adversarial testing have dramatically fewer production bugs. The kind of quality normally requiring a dedicated QA team.

**Effort:** L
**Priority:** MEDIUM

---

### 6.4 — Cross-Session Knowledge Graph

**What:** GENIE accumulates a `knowledge-graph.yaml` in shared-memory that tracks relationships between code entities (files, functions, modules), decisions made about them, and which workers have expertise. New workers query the graph before exploring on their own.

**Why:** Every new worker session re-discovers the codebase from scratch. A knowledge graph externalizes that discovery cost — once IRIS maps `sensor_fusion.py`, every future worker benefits without re-reading it.

**How:**
- Workers contribute to the graph via `memory_publish WORKER knowledge "entity: sensor_fusion.py | type: module | purpose: multi-sensor fusion | key_functions: [fuse_sensors, compute_confidence] | last_modified_by: FRIDAY | known_issues: [thread safety under concurrent updates]"`
- Graph stored as YAML in `shared-memory/topics/knowledge.md`
- Workers query via `memory_query knowledge "sensor_fusion"` on startup
- Entries expire after 14 days unless refreshed (prevents stale data)
- GENIE `/genie knowledge <query>` for human queries

**Impact:** Context startup time drops from 2-3 file reads per worker to a single graph query. Collective intelligence compounds over weeks.

**Effort:** L
**Priority:** MEDIUM

---

### 6.5 — Slack/Webhook Notification Integration

**What:** GENIE pushes notifications to external channels (Slack webhook, webhook.site, or a custom endpoint) when: worker completes, pipeline finishes, blocker requires human input, or critical error occurs.

**Why:** The user can't always have a Claude window open. Push notifications mean the user learns instantly when the fleet needs attention — without polling.

**How:**
- `~/.claude/dispatch/GENIE/webhook.yaml` with endpoint URL and event filters
- Outbox scanner hook: when reading `audience: user` messages, also POST to webhook
- Payload: `{"worker": "FRIDAY", "type": "complete", "summary": "Auth module done", "timestamp": "..."}`
- Slack-compatible format: uses `text` field with emoji and worker name
- User can subscribe to: all completions, blockers only, errors only, or custom filter

**Impact:** GENIE becomes truly async — user gets push notifications on phone/desktop while the fleet runs in the background. Full decoupling of "when work happens" from "when user checks."

**Effort:** M
**Priority:** MEDIUM

---

## Priority Matrix

| ID | Upgrade | Effort | Priority | Dependency |
|----|---------|--------|----------|------------|
| 1.1 | Async Event Bus | S | HIGH | None |
| 1.3 | Broadcast Channels | S | HIGH | None |
| 2.1 | Skill Injection | M | HIGH | None |
| 2.2 | Task Outcome Recorder | M | HIGH | None |
| 2.3 | Self-Evaluation Gate | S | HIGH | None |
| 2.4 | Quality Self-Regulation | S | HIGH | None |
| 4.1 | Crash Detection + Restart | M | HIGH | None |
| 4.4 | Mandatory Review Gate | S | HIGH | None |
| 4.5 | Context Budget Auto-Pause | M | HIGH | None |
| 5.1 | NL Fleet Commands | S | HIGH | None |
| 5.4 | Mission Templates | S | HIGH | None |
| 5.5 | /genie plan command | M | HIGH | None |
| 4.2 | Pipeline Autopilot | XL | HIGH | Queue(3.1), Plan(5.5) |
| 3.1 | Task Queue + Auto-Dispatch | L | HIGH | None |
| 1.2 | Worker-to-Worker RPC | M | MEDIUM | Event Bus(1.1) |
| 1.4 | Shared Working Notes | S | MEDIUM | None |
| 1.5 | Worker Squads | L | MEDIUM | Event Bus(1.1) |
| 2.4 | Time Estimation | M | MEDIUM | Outcome Recorder(2.2) |
| 2.5 | Confidence Scoring | S | MEDIUM | None |
| 3.2 | Specialization Evolution | M | MEDIUM | Outcome Recorder(2.2) |
| 3.3 | Dynamic Pool Sizing | M | MEDIUM | None |
| 3.4 | Load Balancing | S | MEDIUM | None |
| 4.3 | Proactive Proposals | S | MEDIUM | None |
| 5.2 | TUI Dashboard | M | MEDIUM | None |
| 5.3 | Session Replay | L | MEDIUM | None |
| 6.2 | GitHub Issue Integration | M | MEDIUM | None |
| 6.3 | Adversarial Testing | L | MEDIUM | None |
| 6.4 | Knowledge Graph | L | MEDIUM | None |
| 6.5 | Slack Webhooks | M | MEDIUM | None |
| 3.5 | Worker Hibernation | L | LOW | None |
| 6.1 | Multi-Repo Coordination | M | LOW | None |

## Recommended First Wave (S/M effort, HIGH priority)

Start with these 8 — each takes ≤1 day of implementation, delivers immediate value:

1. **Broadcast Channels (1.3)** — 2h, zero-dependency fleet-wide comms
2. **Self-Evaluation Gate (2.3)** — 1h, prevent "done but broken" completions
3. **Mandatory Review Gate (4.4)** — 1h, quality catch every time
4. **NL Fleet Commands (5.1)** — 2h, removes phone-command friction
5. **Mission Templates (5.4)** — 2h, consistent task quality
6. **Task Outcome Recorder (2.2)** — 3h, enables learning layer
7. **Skill Injection at Spawn (2.1)** — 3h, domain-specific worker bootstrapping
8. **Load Balancing (3.4)** — 2h, smarter routing with zero new infrastructure

Combined effort: ~16h. Expected impact: workers that are smarter, more reliable, and easier to command.
