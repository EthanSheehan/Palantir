# Integrated Claude Code Workflow

This project uses four complementary AI development systems working together, with autonomous model selection and mandatory agent team assembly.

## The Four Systems

### 1. everything-claude-code (ECC)
**Role:** Code quality agents — review, TDD, security, build resolution, documentation.

ECC provides 15+ specialized agents that run proactively after every code change. They are the quality backbone of every pipeline.

**Invocation:** `subagent_type: "everything-claude-code:<agent-name>"` via the Agent tool.

**Key agents:**

| Agent | Purpose | Default Model |
|-------|---------|---------------|
| `planner` | Implementation planning | sonnet |
| `architect` | System design | opus |
| `tdd-guide` | Write tests first | sonnet |
| `python-reviewer` | Python code review | sonnet |
| `code-reviewer` | Non-Python code review | sonnet |
| `security-reviewer` | OWASP, secrets, injection | sonnet (opus for auth/crypto) |
| `build-error-resolver` | Fix failing builds/tests | sonnet |
| `doc-updater` | Documentation sync | haiku |
| `refactor-cleaner` | Dead code removal | haiku |
| `e2e-runner` | End-to-end test flows | sonnet |
| `database-reviewer` | Schema/query review | sonnet |

### 2. GSD (Get Shit Done)
**Role:** Spec-driven phased development with fresh context windows per plan — prevents context rot.

GSD decomposes large features into phases, creates plans with dependency graphs, and executes them in parallel waves. Each plan runs in a fresh 200k context window.

**Invocation:** `/gsd:*` slash commands (38 available).

**Key commands:**

| Command | Purpose |
|---------|---------|
| `/gsd:new-project` | Initialize with requirements + roadmap |
| `/gsd:discuss-phase N` | Capture decisions before planning |
| `/gsd:plan-phase N` | Research + plan with fresh context |
| `/gsd:execute-phase N` | Execute plans in parallel waves |
| `/gsd:verify-work N` | User acceptance testing |
| `/gsd:quick` | Ad-hoc task with GSD guarantees |
| `/gsd:progress` | Show current progress |
| `/gsd:map-codebase` | Analyze existing codebase |
| `/gsd:health` | System health check |
| `/gsd:debug` | Diagnose issues |

**State:** `.planning/` directory (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md).

### 3. DevFleet
**Role:** Parallel execution in isolated git worktrees with a mission DAG.

DevFleet runs multiple Claude agents simultaneously, each in its own git worktree. Missions auto-merge on completion and auto-dispatch dependent work.

**Invocation:** `/everything-claude-code:devfleet` or via the Agent tool with `isolation: "worktree"`.

**When it helps most:**
- Features with independent parts that touch different files
- Large refactors where each module can be handled separately
- Any work that can be parallelized without merge conflicts

### 4. Ralph
**Role:** Autonomous loop execution for unattended batch task processing.

Ralph wraps the Claude CLI in a `while true` loop with circuit breakers, rate limiting, and stagnation detection. Set it up, walk away, review results.

**Invocation:** `ralph --monitor` from terminal (external to Claude Code).

**Config:** `.ralph/` directory (PROMPT.md, AGENT.md, fix_plan.md).

---

## Integrated Commands

These project-level slash commands orchestrate all four systems:

### `/build <description> [flags]`
Full implementation pipeline. Auto-detects the right system based on task complexity.

**Flags:**
- `--quick` — Force ECC-only pipeline (small tasks)
- `--devfleet` — Force DevFleet parallel worktrees
- `--gsd` — Force GSD phased execution
- `--ralph` — Force Ralph autonomous loop

**Auto-routing (no flags):**

| Detected Scope | Files | System Used |
|---------------|-------|-------------|
| Small | 1-3 | ECC agents only |
| Medium (parallel) | 4-10, independent parts | DevFleet + ECC review |
| Medium (sequential) | 4-10, dependent changes | GSD quick + ECC review |
| Large | 10+ | GSD phases → DevFleet → ECC review |
| Batch | 20+ tasks | Ralph loop |

**What it does:**
1. Classifies task scope (spawns Explore agent to estimate)
2. Plans using appropriate system
3. Implements (directly, via DevFleet, GSD, or Ralph)
4. Reviews with parallel ECC agents (always)
5. Reports findings — does NOT commit

### `/smart-plan <description>`
Analyzes a task and produces an implementation plan using the optimal system.

- Spawns haiku agent to estimate scope
- Selects system based on file count and parallelizability
- Presents plan with mission DAG / phase breakdown
- Recommends next command to run

### `/review [--deep] [--security]`
Runs all ECC review agents on uncommitted changes.

- Detects Python vs non-Python files changed
- Launches `python-reviewer` + `code-reviewer` + `security-reviewer` in parallel
- `--deep`: Uses opus for all reviewers
- `--security`: Only runs security-reviewer with opus
- Groups findings by severity (CRITICAL → LOW)

### `/ralph-run <description or PRD path>`
Sets up Ralph for autonomous batch execution.

- Parses input into discrete tasks
- Writes to `.ralph/fix_plan.md`
- Updates `.ralph/PROMPT.md` with context
- Tells user to run `ralph --monitor` from terminal

### `/status`
Unified dashboard across all four systems.

Shows: git status, GSD phase progress, DevFleet mission status, Ralph task completion, uncommitted changes.

---

## How the Systems Combine

### GSD + DevFleet (large features)
```
/gsd:plan-phase N    → produces plans with wave groupings
DevFleet             → executes each plan as isolated worktree mission
                       parallel within waves, sequential between waves
ECC review agents    → review merged output (parallel)
```

### ECC + DevFleet (medium features)
```
ECC planner          → decomposes task into independent units
DevFleet             → runs each unit in parallel worktrees
ECC reviewers        → review each unit + integration (parallel)
```

### Ralph + DevFleet (batch work)
```
Ralph loop           → reads fix_plan.md, one task per iteration
Each iteration       → can spawn DevFleet for parallelizable subtasks
Circuit breaker      → monitors for stagnation
```

---

## Agent Teams (Mandatory)

Every non-trivial task spawns a team. Agents in the same wave run in parallel (single message, multiple Agent calls). Waves run sequentially.

### Wave Execution Pattern
```
Wave 1 (parallel): Explore agent + codebase mapper        [haiku]
    ↓ results feed into
Wave 2 (parallel): planner + architect (if needed)        [sonnet/opus]
    ↓ plan feeds into
Wave 3 (sequential): tdd-guide → implementation            [sonnet]
    ↓ code feeds into
Wave 4 (parallel): python-reviewer + security-reviewer     [sonnet]
                   + doc-updater (background)               [haiku]
    ↓ findings feed into
Wave 5: fix review issues                                  [sonnet]
```

### Minimum Team Sizes

| Task Type | Min Agents | Example Team |
|-----------|-----------|--------------|
| Bug fix | 2 | tdd-guide + python-reviewer |
| Small feature | 3 | planner + python-reviewer + security-reviewer |
| Medium feature | 4 | planner + tdd-guide + python-reviewer + security-reviewer |
| Large feature | 5+ | architect + planner + tdd-guide + reviewers + doc-updater |

---

## Autonomous Model Selection

Each agent automatically gets the optimal model:

| Model | Cost | When Used |
|-------|------|-----------|
| **haiku** | $ | File discovery, doc updates, codebase mapping, consistency checks |
| **sonnet** | $$ | Code generation, reviews, TDD, standard planning |
| **opus** | $$$ | Architecture decisions, security deep-dive on auth/crypto, multi-phase planning |

Upgrade to opus when: reviewing auth/crypto code, planning 10+ file features, making architectural decisions, debugging cascading failures.

---

## Automatic Behaviors

These run without user prompting:

1. **Skill Discovery** — searches 109 installed skills before every task
2. **Continuous Learning** — saves patterns, preferences, and decisions to memory
3. **Documentation Sync** — checks if docs need updating after code changes
4. **Memory Management** — saves context so new sessions spin up in <30 seconds
5. **Context Health Monitoring** — GSD hook tracks context usage, recommends new chat at ~70%
6. **Agent Team Assembly** — always spawns parallel subagents, never works alone

---

## GSD Commands (Full List)

| Command | Purpose |
|---------|---------|
| `/gsd:new-project` | Initialize project |
| `/gsd:discuss-phase N` | Capture decisions |
| `/gsd:plan-phase N` | Plan a phase |
| `/gsd:execute-phase N` | Execute a phase |
| `/gsd:verify-work N` | UAT |
| `/gsd:complete-milestone` | Close milestone |
| `/gsd:new-milestone` | Start new milestone |
| `/gsd:quick` | Ad-hoc task |
| `/gsd:do` | Direct execution |
| `/gsd:progress` | Progress dashboard |
| `/gsd:debug` | Diagnose issues |
| `/gsd:health` | System health |
| `/gsd:map-codebase` | Analyze codebase |
| `/gsd:add-phase` | Add a phase |
| `/gsd:insert-phase` | Insert phase at position |
| `/gsd:remove-phase` | Remove a phase |
| `/gsd:add-todo` | Add a TODO |
| `/gsd:check-todos` | Review TODOs |
| `/gsd:add-tests` | Add test coverage |
| `/gsd:note` | Save a note |
| `/gsd:stats` | Project statistics |
| `/gsd:settings` | Configure GSD |
| `/gsd:set-profile` | Set model profile |
| `/gsd:pause-work` | Pause current work |
| `/gsd:resume-work` | Resume paused work |
| `/gsd:cleanup` | Clean up state |
| `/gsd:update` | Update GSD |
| `/gsd:help` | Show help |
| `/gsd:autonomous` | Autonomous mode |
| `/gsd:audit-milestone` | Audit milestone |
| `/gsd:plan-milestone-gaps` | Plan milestone gaps |
| `/gsd:research-phase` | Research phase |
| `/gsd:validate-phase` | Validate phase |
| `/gsd:list-phase-assumptions` | List assumptions |
| `/gsd:ui-phase` | UI-focused phase |
| `/gsd:ui-review` | UI review |
| `/gsd:reapply-patches` | Reapply patches |

---

## Master Command: `/go`

**The single entry point for everything.** One command that bootstraps the full pipeline:

```
/go Add WebSocket heartbeat with configurable interval
/go --plan-only Implement real-time BDA pipeline
/go --autonomous Fix all failing tests
```

**What `/go` does:**
1. Loads previous session context (if exists)
2. Reads memory for project state
3. Searches for relevant skills
4. Classifies task scope → selects system (ECC/GSD/DevFleet/Ralph)
5. Assembles agent team with optimal models
6. Plans → Executes → Reviews (parallel agents)
7. Auto-saves session state on completion

**Flags:**
- `--plan-only` — Plan but don't execute
- `--autonomous` — Full auto: plan + execute + review without stopping

---

## Session Management

Sessions preserve full context across Claude Code conversations.

### Save Session
```
/everything-claude-code:save-session
```
Captures: what was built, what worked, what failed, current file states, decisions made, exact next step. Saves to `~/.claude/saved-sessions/YYYY-MM-DD-<id>-session.md`.

### Resume Session
```
/everything-claude-code:resume-session                    # Most recent
/everything-claude-code:resume-session 2026-03-18         # By date
/everything-claude-code:resume-session path/to/file.md    # Specific file
```
Loads session file, displays briefing (project, state, blockers, next step), waits for instructions.

### Manage Sessions
```
/everything-claude-code:sessions list
/everything-claude-code:sessions info <id>
/everything-claude-code:sessions alias <id> my-alias
```

### Auto-Save on Context Rot

The system automatically saves and recommends a new chat when:
- Context usage hits ~70%
- You've completed 3+ major tasks in one conversation
- The conversation shifts to a fundamentally different topic
- Response quality degrades (re-reading files, missing details)

**Procedure:** Save session → save memory → inform user → provide resume command.

---

## Usage Monitoring

`claude-monitor` **auto-starts in the background on every Claude Code session** via a SessionStart hook. No manual launch needed.

### Installation

```bash
pip3 install claude-monitor
```

### Auto-Start

The hook at `~/.claude/hooks/claude-monitor-launcher.sh` runs on every session start. It:
- Checks if a monitor is already running (deduplicates)
- Launches `python3 -m claude_monitor --view realtime` in the background
- Logs to `/tmp/claude-monitor.log`

### Slash Commands

| Command | Purpose |
|---------|---------|
| `/monitor` | Check status / restart if stopped |
| `/monitor --daily` | Switch to daily aggregated view |
| `/monitor --weekly` | Weekly summary (last 7 days) |
| `/monitor --monthly` | Switch to monthly budget/trend view |
| `/monitor --session` | Switch to current session breakdown |
| `/monitor --stop` | Stop the background monitor |

### Viewing the Dashboard

The monitor runs headless in the background. To see the visual dashboard, open a **separate terminal**:

```bash
claude-monitor                  # Real-time burn rate + progress bars
claude-monitor --view daily     # Daily aggregated stats
claude-monitor --view monthly   # Monthly budget analysis
claude-monitor --view session   # Current session breakdown
```

Aliases: `claude-monitor`, `cmonitor`, `ccmonitor`, `ccm`

### What It Tracks

- Token consumption (input/output) with progress bars against plan limits
- Message counts per session
- Cost per session with model-specific pricing
- Burn rate — how fast you're consuming tokens
- ML-based P90 predictions — analyzes last 8 days of usage
- 5-hour rolling session window tracking
