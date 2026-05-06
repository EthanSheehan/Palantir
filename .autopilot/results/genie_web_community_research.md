---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# GENIE Upgrade Discovery — Web & Community Research
**Researcher:** EDITH (Enhanced Deployment Integration & Task Handler)
**Date:** 2026-03-29
**Branch:** feature/unreal-isaac-target-tracking

---

## 1. Discord/Community Finds — Cool Tricks & Patterns

### Status Line Power User Tricks

The community has gone deep on status line customization beyond the basics. Key patterns discovered:

- **CCometixLine** (Rust) — High-performance Rust binary for git state + token usage with sub-millisecond overhead. Avoids the 50-100ms Python interpreter startup on every tick.
- **ccstatusline** — The reference Python implementation. Supports powerline glyphs, themes, and color-coded context sparklines. Shows token counts, cost-to-date, model name, session duration.
- **claude-powerline** — Vim-style powerline for Claude Code with real-time tracking
- **Power user additions beyond basics:** cost tracking ($), context sparkline (▁▂▃▄▅▆▇█), compaction prediction alert ("compact in ~5 turns"), live monitor panel in second terminal, git integration (staged/modified file counts inline)

**GENIE Relevance:** GENIE's status display is currently custom. We could add a context-health sparkline and per-worker cost-to-date display to the status line. EDITH could emit OTEL metrics for GENIE to aggregate.

### Hooks Nobody Talks About

Beyond PreToolUse/PostToolUse/Stop, the community has surfaced:

- **`TeammateIdle` hook** — fires when a teammate is about to go idle. Exit code 2 sends feedback and keeps the teammate working. **Direct GENIE use case:** GENIE could hook TeammateIdle to auto-assign next task instead of workers polling.
- **`TaskCreated` / `TaskCompleted` hooks** — let external systems respond to task lifecycle events. Exit code 2 vetoes task creation/completion.
- **`MCP Elicitation` hooks** — new in CC v2.1.76. MCP servers can request structured input mid-task via interactive dialogs. Useful for HITL approval gates inside worker runs.
- **`Notification` hook** — fires when CC would show a desktop notification. Can be intercepted to route to Slack/Discord/custom channel.
- **HTTP Hooks** — remote validation services that enforce team-wide policies. GENIE could use this for a centralized policy server GENIE runs.

### Session Save/Resume Community Tricks

- `/everything-claude-code:save-session` + `/resume-session` pattern is widely used
- Community built **Claude Session Restore** — context recovery from previous sessions
- Memory files with timestamps (CC v2.1.0 feature) + custom auto-memory directories let workers leave breadcrumbs for successors
- **Vibe-Log** — local prompt analysis with strategic guidance; logs all CC interactions for retrospective analysis

### Notification Patterns

- **CC Notify** — desktop notifications for task completion alerts via PostToolUse/Stop hooks
- Workers can emit desktop, Slack, or webhook notifications on completion — useful for GENIE to get pinged when a long-running worker finishes

---

## 2. GitHub Projects — Repos Worth Studying or Integrating

### Fleet Orchestration Frameworks

#### `Dicklesworthstone/claude_code_agent_farm`
**What it does:** Runs 20-50 Claude Code agents in parallel with real-time tmux monitoring dashboard, lock-based coordination, heartbeat tracking, and multi-stack support (34 tech stacks).

**Architecture matches GENIE closely:**
- Each agent gets its own tmux pane
- Lock-based file coordination to prevent conflicts
- Real-time dashboard tracking: agent status, cycles completed, context usage, runtime, heartbeat, error count
- Configurable task distribution patterns (bug fixing, best practices sweeps)

**Key takeaway for GENIE:** Their heartbeat + lock approach for 20+ agents is battle-tested. The dashboard UI for monitoring agent status is more polished than GENIE's current status.json approach.

#### `jayminwest/overstory`
**What it does:** Multi-agent orchestration with **pluggable runtime adapters** (Claude Code, Pi, Gemini CLI, Aider, Goose, Amp), SQLite mailbox (WAL mode, ~1-5ms/query), typed protocol messages, and tiered merge conflict resolution.

**Key architectural insights:**
- SQLite WAL mode for inter-agent messaging is faster than file-based dispatch (~1-5ms vs ~50ms for file I/O)
- **Pluggable runtime:** swap in any agent runner without changing orchestration logic
- Configurable depth limit (default 2) prevents runaway spawn trees
- Team Lead can spawn sub-workers (2-level hierarchy)

**Key takeaway for GENIE:** GENIE's file-based mailbox could be augmented with SQLite for high-frequency inter-worker messaging while keeping files for GENIE→worker task dispatch.

#### `ruvnet/ruflo`
**What it does:** Enterprise-grade swarm orchestration. Hierarchical (queen/workers) or mesh (peer-to-peer) patterns. Features:
- 100+ specialized pre-built agents
- Vector memory with AgentDB (96x-164x faster semantic search)
- Rust/WASM policy engine
- Self-learning: successful workflow patterns stored and reused
- Claude Code native MCP integration
- Hive Mind: queen agents direct specialized workers via collective decision-making

**Key takeaway for GENIE:** The Hive Mind queen/worker pattern is more explicit than GENIE's flat dispatcher. Worth studying their queen-spawns-specialists pattern for GENIE.

#### `bobmatnyc/claude-mpm`
**What it does:** Claude Multi-Agent Project Manager. PM owns task routing, progress tracking, and result aggregation. Individual agents are disposable — the PM is the persistent state. GitHub-first SDK mode.

**Key takeaway for GENIE:** "PM as persistent state, agents as disposable" is exactly GENIE's model. Their GitHub-first SDK mode is interesting — GENIE could dispatch workers from GitHub issues.

#### `rohitg00/awesome-claude-code-toolkit`
135 agents, 35 skills (+400,000 via SkillKit), 42 commands, 150+ plugins, 19 hooks, 15 rules, 7 templates, 8 MCP configs. The most comprehensive toolkit available. Worth reviewing for GENIE skill inventory.

### Skills Libraries

- **`hesreallyhim/awesome-claude-code`** — Curated list: skills, agents, hooks, slash commands, alternative clients, CLAUDE.md files, status lines. Best single-source community aggregator.
- **`travisvn/awesome-claude-skills`** — Skills-focused curation
- **`BehiSecc/awesome-claude-skills`** — Another curated skills list
- **`ComposioHQ/awesome-claude-skills`** — Composio's integration-focused skills (Stripe, Notion, GitHub, Jira connectors as skills)

### Observability Stack

#### `ColeMurray/claude-code-otel`
Full OTEL (OpenTelemetry) pipeline for Claude Code fleet monitoring. Architecture: `Claude Code → OTEL Collector → Prometheus + Loki → Grafana`.

**Metrics tracked:** token usage, API costs, cache efficiency, session duration, code changes, commits, PRs, lines of code, developer productivity.

**Key takeaway for GENIE:** GENIE could run a lightweight OTEL collector. Workers already emit heartbeats to status.json — adding OTEL export would give Grafana dashboards for free.

#### `disler/claude-code-hooks-multi-agent-observability`
Uses hooks to provide real-time monitoring of multi-agent systems. Tool calls visible across all agents in real-time, filterable by agent swim lane.

**Key takeaway for GENIE:** Hook-based observability is zero-overhead vs polling. A PostToolUse hook on every worker that writes a lightweight event to a shared JSONL file would give GENIE real-time cross-worker visibility.

### Terminal Integration

#### `Dicklesworthstone/claude_code_agent_farm` — tmux dashboard
Real-time tmux monitoring panel with per-agent status rows.

#### `Ark0N/Codeman`
Manages Claude Code & Opencode in tmux sessions with a modern WebUI. Browser-based control panel for tmux sessions.

#### `craigsc/cmux`
"tmux for Claude Code" — runs a fleet of Claude agents, each in its own worktree, zero conflicts, one command each.

#### `l9c/tmux-agent-teams`
AI agent skill that enables agents to interact with Claude Code through tmux. Cross-runtime.

#### `nielsgroen/claude-tmux`
Manage Claude Code within tmux: popup with session management, git worktree, and PR support.

---

## 3. Orchestration Patterns — State of the Art

### Pattern 1: Orchestrator-Workers with File Dispatch (GENIE's Current Model)

Well-established in LangGraph, Google ADK, OpenAI Agents SDK. Central orchestrator decomposes tasks, routes to specialists, synthesizes results. GENIE's file-based variant is a sound implementation of this pattern.

**Gap vs. state of art:** Most production systems add:
- Task dependency graphs (not just sequential tasks)
- Retry/backoff on worker failure
- Circuit breakers for stalled workers
- Work-stealing (idle workers claim tasks from overloaded workers)

### Pattern 2: Shared Task List with Self-Claiming (Claude Agent Teams)

Claude's built-in Agent Teams use a shared task list (`~/.claude/tasks/{team-name}/`) with file-locking for race-condition-safe claiming. When a worker finishes, it self-claims the next unblocked task.

**Key properties:**
- File-lock based claiming prevents double-assignment
- Dependency tracking: task B blocked by task A auto-unblocks when A completes
- 5-6 tasks per teammate is the sweet spot
- Lead can force-assign or let workers self-claim

**GENIE adaptation:** GENIE could publish a shared task list file. Workers check it after completing their current task and self-claim the next one. Reduces GENIE's orchestration overhead for batch work.

### Pattern 3: Hierarchical Queen/Worker (Ruflo Hive Mind)

Queen agents own strategic planning; specialist workers execute. Queens spawn workers, provide directives, receive summaries. Workers never coordinate directly — all through queen.

Configurable depth limit prevents runaway spawning.

**GENIE adaptation:** GENIE is already playing the queen role. The enhancement is making the queen-to-worker boundary more explicit with typed message schemas (TASK, STATUS, QUESTION, RESULT, ESCALATE).

### Pattern 4: SQLite Mailbox (Overstory)

WAL-mode SQLite for inter-agent messaging: ~1-5ms per message vs ~50ms for file I/O. Typed protocol with message types. Broadcast support (one write, all subscribers see it).

Schema:
```sql
CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  from_agent TEXT,
  to_agent TEXT,  -- NULL = broadcast
  type TEXT,      -- TASK | STATUS | QUESTION | RESULT | ESCALATE
  payload JSON,
  created_at INTEGER,
  read_at INTEGER
);
```

**GENIE adaptation:** High-frequency GENIE↔worker exchanges (heartbeats, progress updates) would benefit from SQLite. Keep file-based for initial task dispatch (more inspectable).

### Pattern 5: Parallel Worktrees + Auto-Merge (DevFleet / cmux / overstory)

Each worker gets an isolated git worktree. Zero file conflicts. Work auto-merges on completion with tiered conflict resolution. Most mature implementation: overstory with tiered conflict resolution.

**GENIE workers already use worktrees** via DevFleet. The enhancement opportunity is auto-merge triggering on worker completion signal rather than requiring manual merge.

### Pattern 6: Competing Hypotheses Debate (Claude Agent Teams pattern)

Multiple workers investigate the same problem from different angles and actively try to disprove each other's theories. Surviving theory is root cause. Scales to code review (security / performance / coverage in parallel).

**GENIE adaptation:** GENIE could spawn 3-worker "debate teams" for architecture decisions or bug diagnosis. Each worker gets a different perspective mandate.

### Pattern 7: Context-Budget-Aware Spawning

Pattern from production systems: before spawning a subagent, check available context budget. Defer if budget < threshold. Prefer haiku for lightweight tasks to preserve budget for expensive ops.

Agent teams are ~7x more token-expensive than single sessions. A 3-agent team for 1 hour = full-day single-agent spend.

---

## 4. API/SDK Opportunities — New Capabilities to Leverage

### Claude Agent SDK (Python & TypeScript)

**What's new (2025-2026):**
- `tools` option: allowlist or preset (`claude_code`) of available tools per agent invocation
- **Structured outputs** (GA as of 2026): agents return validated JSON matching your schema. No more regex parsing.
- `strict` mode: ensures structured output schema compliance
- Per-agent tool allowlists reduce attack surface and cost

**GENIE use case:** GENIE workers could return structured status reports as JSON schemas instead of free-text markdown. GENIE could parse progress reports programmatically.

### Memory Tool (Claude API)

New context-editing feature + memory tool in Claude API: agents run longer, handle greater complexity by managing their own memory allocation. Workers can clear thinking blocks to free context budget.

**GENIE use case:** Workers already have `memory/` directories. The API memory tool lets them also manage in-context memory more granularly during a session.

### MCP Elicitation (CC v2.1.76+)

MCP servers can request structured user input mid-task via interactive dialogs. New hooks: `Elicitation`, `ElicitationResult`.

**GENIE use case:** GENIE could expose an MCP server that workers call when they need human approval (HITL gate). Instead of writing to outbox and polling, worker pauses, GENIE/user sees an interactive dialog, approves, worker continues.

### Agent Skills Open Standard (December 2025)

Anthropic published the Agent Skills spec as an open standard (agentskills.io). Microsoft, OpenAI, Atlassian, Figma, Cursor, GitHub, Canva, Stripe, Notion, Zapier all adopted it.

**Key property:** Skills are cross-platform. A GENIE skill written for Claude Code should work in Cursor, Windsurf, etc. without modification.

**Hot reload:** New in CC v2.1.0. Skills can be updated and take effect immediately without restarting sessions. Workers in-flight can pick up updated skills.

### Structured Outputs

GA on Claude Sonnet 4.5, Opus 4.5, Haiku 4.5. Workers can return structured JSON validated against your schema. No parsing errors from malformed worker outputs.

**GENIE use case:** Worker status.json is already structured. Extend this to worker *outputs* (findings, recommendations, code review results) — all structured JSON so GENIE can aggregate them programmatically.

### Extended Output Limits

Opus 4.6 default: 64k tokens; ceiling: 128k tokens. Sonnet 4.6 ceiling: 128k. Enables longer agent runs without hitting output truncation.

**GENIE use case:** Workers running long synthesis tasks (AURORA's research reports, MINERVA's architecture docs) no longer need to break output into chunks.

### Token Counting API

Anthropic's token counting endpoint lets you pre-flight a request before sending it. GENIE could estimate worker context consumption before dispatching and choose haiku vs. sonnet based on remaining budget.

### Cost Optimization Techniques

From community benchmarks:
- **Progressive skill disclosure** recovers ~15,000 tokens/session (82% improvement over loading everything upfront)
- **3-tier hierarchy** (1 coordinator + 3-5 specialists + 10-15 task workers) reduces cost 73% vs. flat fleet
- **Model selection gates:** haiku for file discovery/status checks/doc updates; sonnet for code; opus only for arch decisions
- Prompt caching reduces repeated system prompt costs

---

## 5. Tooling Integrations — IDE, Terminal, CI/CD Hooks

### Terminal Multiplexer

**Agent Teams + tmux Split Panes:** Claude's native Agent Teams feature supports split-pane display (one pane per teammate) when tmux is running. GENIE workers in Windows Terminal tabs could be migrated to a tmux layout for unified visibility.

**Note:** Split-pane mode has known limitations on Windows Terminal and VS Code integrated terminal. tmux on WSL is the workaround for Windows.

**cmux / claude-tmux:** Community tools for managing worker fleets in tmux:
- `claude-tmux` (nielsgroen): tmux popup with session management, git worktree, and PR support
- `cmux` (craigsc): one-command fleet management, each worker in its own worktree

### CI/CD Integration

**Claude Code in GitHub Actions (headless mode):**
```bash
claude -p "Review this PR and output a JSON report" --output-format json
```
Can be triggered as a GitHub Actions step. Community pattern: PR bot that runs security reviewer + code reviewer agents on every PR and posts structured findings as review comments.

**GENIE CI/CD opportunity:** A GENIE-dispatched EDITH worker that runs on every PR merge. Configured via `.github/workflows/genie-review.yml`. Workers run headless, output structured JSON, GENIE aggregates and posts.

### VS Code / JetBrains

**Issue:** Agent Teams split-pane mode doesn't work in VS Code integrated terminal. Workaround is tmux in external terminal.

**CC v2.1.0 workaround:** `--teammate-mode in-process` forces all teammates into the main session (no split panes), which does work in VS Code. Less visual but functional.

### OpenTelemetry Pipeline

Full observability stack community-verified:
```
CC worker (OTEL env vars) → OTEL Collector → Prometheus → Grafana
```

Environment variables for OTEL export:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
CLAUDE_CODE_ENABLE_TELEMETRY=1
```

**GENIE opportunity:** GENIE runs a local OTEL collector (Docker). Each worker sets OTEL env vars in their shell. Grafana dashboard shows all worker sessions in one view with token usage, costs, tool calls, error rates.

### MCP Server Integrations Relevant to GENIE

Top MCPs from community (50+ catalog):

| MCP | What it gives GENIE workers |
|-----|---------------------------|
| **GitHub** | Direct access to issues, PRs, code search — AURORA/IRIS can research codebase via GitHub |
| **Context7** | Current library docs pulled into context at query time — eliminates stale training data |
| **Sentry** | Error tracking in worker context — EDITH can debug production issues without context switching |
| **PostgreSQL** | Natural language DB queries — useful for Grid-Sentinel's SQLite/DB work |
| **n8n** | GENIE could trigger n8n workflows from worker completions |
| **Brave Search** | Real-time web search for AURORA/IRIS workers without MCP-less workarounds |

**Tool lazy-loading (CC feature):** Claude Code only loads tool definitions on demand (ToolSearch pattern), reducing context by ~95% vs. loading all MCPs upfront. GENIE workers with 5+ MCPs configured benefit significantly.

---

## 6. Competitive Intel — What Others Are Doing

### Cursor

- **Background Agents:** Run async in cloud sandboxes on separate branches. Each gets a full VM. Sequential within agent, but you can run multiple simultaneously (up to 8).
- **Parallel sub-agents:** Up to 8 simultaneous subagents exploring different codebase areas.
- **GENIE differentiation:** Cursor's agents are cloud VMs; GENIE workers are terminal sessions. GENIE's file-based dispatch is lower-overhead for local work but can't scale to cloud-distributed.

### Windsurf (Cascade)

- Handles multi-step tasks sequentially within a single Cascade flow
- No true parallel agent coordination — sequential only
- **GENIE differentiation:** GENIE is already ahead of Windsurf on parallelism. Windsurf's strength is its tight IDE integration.

### Antigravity

- Currently the only IDE with true multi-agent orchestration AND a built-in browser
- Multiple simultaneous agents each in separate workspace environments
- Transparency: see all agent reasoning streams side-by-side
- **GENIE differentiation:** Antigravity is purpose-built for the multi-agent use case; GENIE is a custom orchestration layer on top of Claude Code. Antigravity may outpace for new users, but GENIE is more configurable.

### GitHub Copilot Workspace

- Turns GitHub issues into implementation plans → code → PRs
- CI/CD gate: GitHub Actions auto-tests before PR created
- Deep GitHub integration: issue-to-PR automation
- **GENIE differentiation:** Copilot Workspace is GitHub-scoped; GENIE is terminal-native with broader tooling. Copilot Workspace's issue→PR pipeline is something GENIE/GENIE could add.

### What's Unique About GENIE's Terminal-Tab Approach

1. **Worker identity:** Each worker has a name (FRIDAY, EDITH, etc.), persistent memory, and specialization. Competitors treat agents as anonymous instances.
2. **File-based mailbox:** Inspectable, debuggable, no network dependency. Every message is a file you can read.
3. **Cross-session memory:** Workers persist context across restarts via structured memory files. Most competitors lose context on session end.
4. **Heterogeneous runtimes:** GENIE workers could in principle use different underlying models per worker role.
5. **GENIE as policy enforcer:** Safety rules are baked into worker protocol, not just guidelines. GENIE controls dispatch and can kill workers.

---

## 7. Top 10 Recommendations — Prioritized for GENIE

### #1 — Enable Agent Teams Experimental Feature (Immediate, Low Effort)

**What:** Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in GENIE's session settings.

**Why:** Agent Teams gives workers access to `TeammateTool`, shared task lists, and `TeammateIdle` hooks — all without changing GENIE's architecture. Workers can self-coordinate on sub-tasks, reducing GENIE's dispatch overhead for batch work.

**Impact:** Workers can claim tasks autonomously from a shared list instead of waiting for GENIE to dispatch each one.

**Caveats:** Experimental. No split-pane in Windows Terminal. Use in-process mode.

---

### #2 — SQLite Mailbox for High-Frequency Messaging (Medium Effort)

**What:** Add SQLite WAL-mode message store alongside file-based mailbox. Workers and GENIE use SQLite for heartbeats and rapid exchanges; files for initial task dispatch and final results.

**Why:** File I/O ~50ms per operation. SQLite WAL ~1-5ms. For 12 workers each sending 10 heartbeats/min, that's 120 writes/min — file approach starts creating I/O contention.

**Implementation:** Single `dispatch.db` file in `~/.claude/dispatch/`. Schema: `messages(id, from, to, type, payload, created_at, read_at)`. Workers and GENIE both have write access.

**Reference:** Overstory's implementation is open source.

---

### #3 — OTEL Observability Pipeline for GENIE (Medium Effort)

**What:** Each worker sets `OTEL_EXPORTER_OTLP_ENDPOINT` and `CLAUDE_CODE_ENABLE_TELEMETRY=1`. GENIE runs an OTEL Collector + Prometheus + Grafana via Docker Compose.

**Why:** Current observability is status.json polling. OTEL gives: real-time cross-worker token usage, cost per worker per task, tool call frequency, error rates — all in one Grafana dashboard.

**Reference:** `ColeMurray/claude-code-otel` + `disler/claude-code-hooks-multi-agent-observability`.

**Bonus:** Hook-based observability via PostToolUse writing to shared JSONL gives zero-latency cross-worker visibility.

---

### #4 — Structured Worker Outputs via JSON Schemas (Medium Effort)

**What:** Define Pydantic/TypeScript schemas for common worker output types (findings, recommendations, code review results, status reports). Workers output validated JSON; GENIE parses programmatically.

**Why:** Current worker outputs are free-text markdown in outbox. GENIE has to parse them manually or read them as prose. Structured outputs enable programmatic aggregation, deduplication, and synthesis.

**Technology:** Claude API Structured Outputs (GA). Workers use `--output-format json` or return structured output via SDK.

---

### #5 — TeammateIdle Hook for Auto-Task-Assignment (Low Effort, High Impact)

**What:** Configure a `TeammateIdle` hook in worker settings that pings GENIE when a worker goes idle. GENIE auto-dispatches next task from queue.

**Why:** Current pattern requires GENIE to manually detect idle workers and dispatch. The hook makes this reactive rather than polling-based.

**Config:**
```json
{
  "hooks": {
    "TeammateIdle": [
      { "type": "command", "command": "notify-genie-worker-idle.sh $TEAMMATE_NAME" }
    ]
  }
}
```

---

### #6 — Worker Agent Farm Pattern for Batch Sweeps (Medium Effort)

**What:** Adopt the `claude_code_agent_farm` pattern for batch improvement sweeps. When Grid-Sentinel needs systematic best-practices application across all Python files, spin up 10 workers each owning a file range, with lock-based coordination.

**Why:** Current batch work uses Ralph (sequential loop). Agent Farm runs 20-50 workers in parallel — 10-50x faster for parallelizable tasks.

**Reference:** `Dicklesworthstone/claude_code_agent_farm` — installable as a Claude skill.

---

### #7 — Skills Hot Reload + Progressive Disclosure (Low Effort)

**What:** Organize GENIE worker skills into progressive disclosure tiers. Workers load minimal core skill on startup, then dynamically load domain-specific skills as needed. Leverage CC v2.1.0 hot reload so skill updates propagate to running workers.

**Why:** Current CLAUDE.md loads everything upfront. Community benchmarks show 82% token reduction (15,000 tokens/session recovered) with progressive disclosure.

**Implementation:** Tier 1 (always loaded): identity, safety rules, mailbox protocol. Tier 2 (on-demand): domain-specific skills (DevOps, Python, security, etc.). Workers call `ToolSearch` equivalent to discover available skills.

---

### #8 — Competing Hypotheses Pattern for GENIE Decisions (Low Effort, Novel)

**What:** When GENIE faces a complex decision (architecture choice, root cause diagnosis), spawn 3 workers with different perspective mandates: Proposer, Critic, Devil's Advocate. Workers debate and converge. GENIE synthesizes.

**Why:** Single-agent analysis suffers from anchoring bias. Multi-agent debate produces more robust conclusions. CC Agent Teams documentation explicitly recommends this pattern for debugging.

**Implementation:** GENIE dispatches a "debate" task with 3 worker slots and a resolution protocol. Workers communicate via shared outbox. GENIE reads all three outputs and produces synthesis.

---

### #9 — GitHub Actions GENIE Pipeline (Medium Effort)

**What:** GENIE-dispatched EDITH worker triggered on PR events via GitHub Actions. Worker runs headless code review, outputs structured JSON, posts findings as PR review comments.

**Why:** Manual code review trigger is friction. GitHub Actions integration closes the CI/CD loop. Copilot Workspace has this natively — GENIE can replicate it.

**Config:**
```yaml
# .github/workflows/genie-review.yml
on: [pull_request]
jobs:
  genie-review:
    steps:
      - run: claude -p "Review this PR per GENIE protocol" --output-format json > review.json
      - run: gh pr review --comment --body "$(cat review.json)"
```

---

### #10 — Ruflo Hive Mind Pattern Study (Low Effort Research, Medium Implementation)

**What:** Study Ruflo's queen/worker hierarchy and vector memory patterns. Specifically: (a) typed message schemas between queen and workers, (b) vector memory for storing successful workflow patterns and routing similar future tasks, (c) self-learning loop.

**Why:** GENIE's current routing is explicit (GENIE decides which worker). Ruflo's vector memory routes tasks to the best-performing worker for that task type based on historical performance — "AURORA got high scores on research tasks, route research to AURORA."

**Implementation path:** Add a lightweight performance log per worker (task type, outcome, tokens used, time). Build a simple cosine-similarity router in GENIE that matches new tasks to historical high-performers.

---

## Appendix: Key URLs

**Official:**
- [Claude Code Agent Teams Docs](https://code.claude.com/docs/en/agent-teams)
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [Claude Code Status Line](https://code.claude.com/docs/en/statusline)
- [Agent Skills Standard](https://agentskills.io/home)
- [Claude API Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)

**Community Repos:**
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
- [awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)
- [claude_code_agent_farm](https://github.com/Dicklesworthstone/claude_code_agent_farm)
- [overstory](https://github.com/jayminwest/overstory)
- [ruflo](https://github.com/ruvnet/ruflo)
- [claude-mpm](https://github.com/bobmatnyc/claude-mpm)
- [claude-code-otel](https://github.com/ColeMurray/claude-code-otel)
- [claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability)
- [cmux](https://github.com/craigsc/cmux)
- [tmux-agent-teams](https://github.com/l9c/tmux-agent-teams)

**Articles:**
- [Multi-Agent Orchestration: Running 10+ Instances in Parallel](https://dev.to/bredmond1019/multi-agent-orchestration-running-10-claude-instances-in-parallel-part-3-29da)
- [Claude Code Swarm Orchestration Skill](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea)
- [Agent Skills Open Standard — The New Stack](https://thenewstack.io/agent-skills-anthropics-next-bid-to-define-ai-standards/)
- [Claude Code 2.1.0 — VentureBeat](https://venturebeat.com/orchestration/claude-code-2-1-0-arrives-with-smoother-workflows-and-smarter-agents)
- [Subagent Cost Explosion Warning](https://www.aicosts.ai/blog/claude-code-subagent-cost-explosion-887k-tokens-minute-crisis)
