---
tags: [grid_sentinel, autopilot, research, worker-output]
---
# Claude Code Built-in Features — Deep Dive for GENIE Integration

**Researcher:** NOVA
**Date:** 2026-03-29
**Branch:** feature/unreal-isaac-target-tracking

---

## Executive Summary

This document catalogs every Claude Code built-in feature, tool, and extension point discovered through direct schema inspection, file system exploration, and live API queries. Each finding is analyzed for GENIE integration potential.

**Key discoveries:**
- RemoteTrigger API is already live and in use (GENIE-fleet-alert trigger exists)
- CronCreate is session-based by default but supports `durable: true` for persistence
- TeamCreate + SendMessage is the native multi-agent coordination layer — directly parallels GENIE's dispatch system
- Hook system supports `additionalContext` injection (advisory), `decision: "block"` (hard block), and parameter modification
- StatusLine accepts any Node.js command — can embed GENIE mode indicators today
- LSP integration enables real-time code intelligence for agents
- Plan Mode has a formal API (EnterPlanMode/ExitPlanMode) — can be mirrored for GENIE mode

---

## 1. Status Line & UI Customization

### Feature: Custom StatusLine Command
**Description:** `settings.json` accepts a `statusLine` key with `{type: "command", command: "..."}`. The command receives a JSON payload via stdin containing:
- `model.display_name` — current model name
- `workspace.current_dir` — current directory
- `session_id` — unique session ID
- `context_window.remaining_percentage` — real-time context usage

The command outputs an ANSI-colored string rendered in the Claude Code status bar.

**GENIE Integration:** GENIE mode indicator. When `GENIE_WORKER` env var is set, the statusline can show worker name, current task from `status.json`, and GENIE dispatch connection status. This is how plan mode text appears on the status line — same mechanism.

**Implementation:**
```javascript
// In gsd-statusline.js — add GENIE worker section:
const workerName = process.env.GENIE_WORKER;
if (workerName) {
  const statusPath = path.join(homeDir, '.claude', 'dispatch', workerName, 'status.json');
  if (fs.existsSync(statusPath)) {
    const s = JSON.parse(fs.readFileSync(statusPath, 'utf8'));
    const workerTag = `\x1b[35m[${workerName}]\x1b[0m`;
    const taskSnip = s.task?.slice(0, 40) || 'idle';
    process.stdout.write(`${workerTag} ${taskSnip} │ ...rest of line`);
    return;
  }
}
```

**Priority:** Must — zero infrastructure cost, instant GENIE mode visibility on status bar.

---

### Feature: GENIE Mode via Status Line + Hook
**Description:** Plan mode shows on the status line because `EnterPlanMode` transitions the session state. We can replicate this for GENIE mode by: (a) writing a flag file when GENIE mode is active, (b) reading it in the statusline script, (c) using a PreToolUse hook to enforce GENIE-only behavior.

**GENIE Integration:** "GENIE mode" becomes a first-class mode visible to the user, like plan mode. Status line shows `[GENIE MODE]` in a distinct color. Hook blocks non-orchestration actions.

**Implementation:** See Section 3 (Hooks) for the enforcement mechanism. The statusline reads `~/.claude/dispatch/GENIE/mode.json` if it exists.

**Priority:** Must — this was the original user request.

---

## 2. Built-in Mode System

### Feature: EnterPlanMode / ExitPlanMode
**Description:** Formal mode transition tools. `EnterPlanMode` takes no parameters. `ExitPlanMode` accepts:
- `allowedPrompts`: array of `{tool: "Bash", prompt: "semantic description"}` for permission grants

When plan mode is active, Claude cannot execute tools — it can only explore and plan. The mode is reflected in the UI status line automatically.

**GENIE Integration:**
- Use `EnterPlanMode` at the start of GENIE orchestration sessions to signal "planning phase"
- `ExitPlanMode` with `allowedPrompts` can pre-authorize the exact set of worker spawns about to happen
- The plan approval workflow (`plan_approval_request` / `plan_approval_response` via SendMessage) mirrors this for multi-agent approval flows

**Priority:** Should — useful for the GENIE planning phase before dispatching workers.

---

### Feature: Plan Approval Protocol (Multi-Agent)
**Description:** Via SendMessage, agents can send `{type: "plan_approval_request", request_id: "..."}` to teammates. The recipient approves with `{type: "plan_approval_response", request_id: "...", approve: true/false, feedback: "..."}`. This is built into the TeamCreate/SendMessage protocol.

**GENIE Integration:** GENIE can request plan approval from a "lead" agent before dispatching a full worker fleet. Workers can send `plan_approval_request` to GENIE for high-risk operations.

**Priority:** Should — formalizes the approval workflow already implicit in GENIE.

---

## 3. Hook System Deep Dive

### Feature: PreToolUse — Block + Advisory
**Description:** PreToolUse hooks receive a JSON payload:
```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "rm -rf ..."},
  "session_id": "...",
  "cwd": "..."
}
```
Output options:
- `{decision: "approve"}` — allow the tool
- `{decision: "block", reason: "..."}` — hard block (returns error to agent)
- `{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: "..."}}` — advisory warning injected into agent context

The worker-safety-guard.js uses hard blocking for dangerous patterns. The prompt-guard uses advisory for injection detection.

**GENIE Integration:** GENIE mode enforcement hook. When `GENIE_WORKER=GENIE` is set:
1. Block `Agent()` calls with non-worker subagent_types (enforce "GENIE delegates only")
2. Block `Edit`/`Write` to project files (GENIE should not implement)
3. Block `git commit` (only workers commit)
4. Advisory warn on any non-orchestration action

**Priority:** Must — this is the technical foundation for GENIE mode lock.

---

### Feature: PostToolUse — Context Injection
**Description:** PostToolUse hooks can inject `additionalContext` strings into the agent's conversation context after each tool use. The context-monitor uses this to inject `CONTEXT WARNING` messages when usage is high.

The hook receives:
```json
{
  "tool_name": "...",
  "tool_input": {...},
  "tool_response": {...},
  "session_id": "...",
  "cwd": "..."
}
```

**GENIE Integration:**
- Worker heartbeat hook already uses PostToolUse to update `last_heartbeat` in status.json (worker-heartbeat-hook.js)
- Can inject GENIE dispatch confirmations: "Worker FRIDAY assigned task X — status: working"
- Can inject GENIE system health after each Bash tool: "3/4 workers healthy, 1 blocked"

**Priority:** Should — heartbeat hook already exists; extend it with GENIE health summaries.

---

### Feature: Stop Hook
**Description:** Runs when the session ends. Used for cleanup, final state saves, and session summaries. Can trigger `continuous-learning/evaluate-session.sh` as shown in the active-behaviors rules.

**GENIE Integration:**
- On worker session end: write final status.json with `"status": "done"`
- Trigger GENIE notification via outbox file
- Save session memory via `session_save` in memory-utils.sh
- Auto-commit any uncommitted work

**Priority:** Should — ensures no worker leaves without proper handoff, even if it crashes.

---

### Feature: Hook Matcher System
**Description:** Hooks can match specific tools via `matcher` field (e.g., `"Bash|Edit|Write|Agent"`). This enables tool-specific enforcement without running the hook on every tool call.

**Current matchers in use:**
- PostToolUse: `"Bash|Edit|Write|MultiEdit|Agent|Task"` → context monitor
- PostToolUse: `"Bash|Edit|Write|Agent"` → worker heartbeat
- PreToolUse: `"Write|Edit"` → prompt injection guard
- PreToolUse: `"Bash"` → worker safety guard

**GENIE Integration:** Add a dedicated `"Agent"` matcher for GENIE mode that validates all subagent spawns include `mode: "auto"` and valid team_name.

**Priority:** Should.

---

## 4. Agent/Subagent System Internals

### Feature: Agent Tool — Full Parameter Set
**Description:** The Agent tool accepts:
- `subagent_type`: agent definition from `.claude/agents/` or built-in
- `prompt`: task description
- `mode`: `"auto"` | `"acceptEdits"` | `"bypassPermissions"` | `"default"` | `"dontAsk"` | `"plan"`
- `model`: `"sonnet"` | `"opus"` | `"haiku"` (model override)
- `name`: addressable name for SendMessage
- `team_name`: join a team
- `run_in_background`: bool — async execution
- `isolation`: `"worktree"` — isolated git worktree
- `description`: 3-5 word UI summary

**GENIE Integration:** Workers should always use `mode: "auto"` and `team_name` to enable SendMessage coordination. Background agents are ideal for doc-updater and security-reviewer post-processing.

**Priority:** Must — already documented in protocol, but hook enforcement would catch violations.

---

### Feature: SendMessage — Native Inter-Agent Protocol
**Description:** SendMessage enables direct agent-to-agent communication within a team:
- `to`: teammate name or `"*"` for broadcast
- `message`: string or structured protocol object
- `summary`: 5-10 word UI preview

Built-in protocol messages:
- `{type: "shutdown_request"}` — graceful agent termination
- `{type: "shutdown_response", request_id, approve}` — acceptance
- `{type: "plan_approval_request", request_id}` — request approval
- `{type: "plan_approval_response", request_id, approve, feedback}` — approve/reject with feedback

Messages are delivered automatically — no polling required. The system queues mid-turn messages.

**GENIE Integration:** This is a richer alternative to the file-based mailbox for agents running in the same Claude Code session. For cross-terminal workers (the current GENIE model), the file-based mailbox remains necessary. But for same-session subagents, SendMessage is faster.

**Priority:** Should — hybrid model: file mailbox for cross-terminal workers, SendMessage for same-session agent teams.

---

### Feature: TeamCreate / TeamDelete
**Description:**
- `TeamCreate(team_name, description, agent_type)` — creates `~/.claude/teams/{name}/config.json` and `~/.claude/tasks/{name}/` directory
- Team config contains members array with `{name, agentId, agentType, model, joinedAt, cwd, subscriptions}`
- `TeamDelete()` — removes team + task directories after all members shut down

**Existing teams found:** `autopilot-grid_sentinel-8310`, `autopilot-grid_sentinel-8389`, `expressive-discovering-minsky`, etc. — these are autopilot runs.

**GENIE Integration:** GENIE can create a named team for each dispatch batch. Workers join via `team_name` parameter. GENIE reads `~/.claude/teams/{name}/config.json` to discover all active members. At mission completion, `TeamDelete()` cleans up.

**Priority:** Should — enhances worker discovery and cleanup.

---

### Feature: Worktree Isolation
**Description:** Agent tool `isolation: "worktree"` creates a temporary git worktree for the agent. If the agent makes no changes, the worktree is auto-cleaned. If changes are made, the branch name and path are returned for review/merge.

`EnterWorktree(name)` / `ExitWorktree(action: "keep"|"remove")` enable manual worktree sessions in the main conversation.

**GENIE Integration:** Workers doing experimental/risky changes (e.g., large refactors) should use `isolation: "worktree"`. GENIE receives the branch name on completion and can trigger a merge review before committing to main.

**Priority:** Should — especially valuable for NOVA (fast prototyping) and SELENE (E2E test isolation).

---

## 5. Task System

### Feature: Task Lifecycle (TaskOutput, TaskStop)
**Description:**
- `TaskOutput(task_id, block, timeout)` — get output from background tasks. DEPRECATED: prefer Reading the output file path directly.
- `TaskStop(task_id)` — terminate a running background task
- Background tasks return an output file path; a `<task-notification>` is delivered when complete
- Task files stored in `~/.claude/tasks/{team-name}/`

Task IDs visible via `/tasks` command.

**GENIE Integration:**
- GENIE can track background agent task IDs and poll via TaskOutput for status
- TaskStop enables GENIE kill switches for runaway workers without needing a kill message
- Task output files persist — useful for cross-session result access

**Priority:** Should — adds programmatic kill switch to GENIE worker management.

---

## 6. Remote & Scheduling Features

### Feature: RemoteTrigger API
**Description:** Full REST API for cloud-hosted Claude Code sessions. Actions: `list`, `get`, `create`, `update`, `run`. A trigger can be:
- Cron-scheduled (`cron_expression`)
- Manually fired (`run`)
- Configured with a `session_context` including `allowed_tools`, `model`, `sources` (git repos)
- Persisted server-side (survives restarts)

**Live example found:** `GENIE-fleet-alert` trigger already exists in the system — configured with `allowed_tools: [Bash, Read, Write, Edit, Glob, Grep]`, model `claude-sonnet-4-6`, source `EthanSheehan/Grid-Sentinel` repo. Currently disabled (cron `0 0 1 1 *` = Jan 1st only).

**GENIE Integration:**
1. **GENIE health check trigger**: Create a trigger that fires every 15 minutes to check all worker statuses and report via outbox
2. **Daily standup trigger**: Fire each morning, summarize overnight worker progress
3. **Emergency spawn trigger**: Manually fire to spawn a new worker when one stalls
4. **Watch trigger**: Fires when specific files change (via git webhook or cron poll)

**Priority:** Must — RemoteTrigger is the "always-on" layer that makes GENIE resilient to terminal crashes.

---

### Feature: CronCreate (Session-Based + Durable)
**Description:**
- `CronCreate(cron, prompt, recurring, durable)` — schedule a prompt to fire on a cron schedule
- Default: in-memory, dies when session ends
- `durable: true`: persists to `.claude/scheduled_tasks.json`, survives restarts
- `recurring: false`: one-shot, auto-deletes after firing
- Returns a job ID for `CronDelete(id)`
- Auto-expires recurring jobs after 7 days
- `CronList()` shows all active jobs

**GENIE Integration:**
1. **Worker heartbeat monitor**: Every 2 minutes, check if any worker's `last_heartbeat` is stale
2. **GENIE inbox poller**: Every minute, scan outbox files from all workers
3. **Auto-progress report**: Every 30 minutes, generate a status summary for the user
4. **Durable daily health check**: `durable: true` for a 9am standup that survives Claude restarts

**Priority:** Must — CronCreate enables GENIE to be truly autonomous without manual `/genie monitor` invocations.

---

## 7. MCP (Model Context Protocol) Integration

### Feature: ListMcpResourcesTool + ReadMcpResourceTool
**Description:**
- `ListMcpResourcesTool(server?)` — lists all resources from configured MCP servers
- `ReadMcpResourceTool(server, uri)` — reads a specific resource by URI
- Resources include standard MCP fields + a `server` field

**Configured MCP servers:** None in `~/.claude/settings.json` (`mcpServers: {}`), but plugins provide MCP servers:
- `context7` — documentation lookup
- `playwright` — browser automation
- `firecrawl` — web scraping
- `claude-ai-Canva` — design tools
- `claude-ai-Gmail` — email access

**GENIE Integration:**
1. **Custom GENIE MCP server**: Build a Node.js MCP server that exposes GENIE dispatch state as resources. Workers can call `ReadMcpResourceTool("genie-dispatch", "worker://FRIDAY/status")` instead of reading files
2. **Context7 for worker research**: Workers doing research phases should use `mcp__plugin_context7_context7__query-docs` for library documentation
3. **Playwright for SELENE worker**: SELENE's E2E test runs go through `mcp__plugin_playwright_playwright__*` tools

**Priority:**
- Custom GENIE MCP server: Nice-to-have (file-based mailbox works, but MCP would be cleaner)
- Context7 + Playwright usage: Must for SELENE and research workers

---

## 8. Notebook & Advanced Tools

### Feature: NotebookEdit
**Description:** Operates on Jupyter `.ipynb` files. Can `replace`, `insert`, or `delete` cells. Supports `code` and `markdown` cell types. Cell is identified by `cell_id` (0-indexed) or insertion position.

**GENIE Integration:** AURORA (research agent) can produce Jupyter reports for analysis tasks. Notebooks are ideal for data-heavy research outputs that mix code, charts, and narrative.

**Priority:** Nice-to-have.

---

### Feature: LSP (Language Server Protocol)
**Description:** Operations available:
- `goToDefinition`, `findReferences`, `hover` — code intelligence
- `documentSymbol`, `workspaceSymbol` — symbol discovery
- `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls` — call graph

Requires LSP server config. Currently enabled: `pyright-lsp` (Python), `typescript-lsp` (TS), `gopls-lsp` (Go).

**GENIE Integration:**
- Code reviewer agents (PEPPER, ARIA) can use LSP for accurate symbol resolution instead of grep
- `workspaceSymbol` enables cross-file refactoring with precise reference tracking
- `incomingCalls`/`outgoingCalls` maps impact radius of a change before committing

**Priority:** Should — especially for PEPPER (architecture analysis) and refactor tasks.

---

### Feature: EnterWorktree / ExitWorktree
**Description:** Creates an isolated git worktree in `.claude/worktrees/` with a new branch. Session CWD switches to the worktree. On exit, `action: "keep"` preserves the branch, `action: "remove"` deletes it. `discard_changes: true` required for forced removal with uncommitted work.

**GENIE Integration:** GENIE can instruct workers to `EnterWorktree("feature-X")` before risky work, then merge the resulting branch after review. This isolates each worker's work to its own branch even when workers share the same terminal context.

**Priority:** Should.

---

### Feature: WebFetch / WebSearch
**Description:**
- `WebFetch(url, prompt)` — fetches URL content, converts HTML to markdown, processes with a fast model. 15-minute cache. Upgrades HTTP to HTTPS automatically.
- `WebSearch(query, allowed_domains, blocked_domains)` — real-time web search with source attribution

**GENIE Integration:**
- AURORA and research workers should default to these for any external data gathering
- Workers using Context7 plugin should prefer `mcp__plugin_context7_context7__query-docs` for library docs (more reliable than WebFetch for structured docs)
- WebSearch enables GENIE to check for Claude Code updates, security advisories, or relevant research

**Priority:** Must — already in use; document in worker protocol explicitly.

---

## 9. Skill System Architecture

### Feature: Skill Discovery and Invocation
**Description:** Skills are loaded via the `Skill` tool with `skill: "name"` and optional `args`. Skills are markdown files in `~/.claude/skills/{name}/` directories. The skill system:
- Skills are loaded into the conversation context when invoked
- Skills can reference other tools but cannot directly call other skills (no chaining API)
- Skills are discoverable via the system prompt `<system-reminder>` listing
- Skills can be global (`~/.claude/skills/`) or project-level (`.claude/skills/`)

**Current skill categories found:**
- Workflow skills: `genie`, `autopilot`, `gsd:*`, `monitor`, `build`, `review`
- Language skills: `python-patterns`, `golang-patterns`, `rust-patterns`, etc.
- Agent skills: `enterprise-agent-ops`, `autonomous-loops`, `configure-ecc`
- Toolchain skills: `tdd-workflow`, `security-review`, `deployment-patterns`

**GENIE Integration:**
1. **GENIE skill**: Already exists at `~/.claude/skills/genie/`. This is the entry point for GENIE mode.
2. **Worker-specific skills**: Each worker could have a `~/.claude/skills/genie-{worker}/` with their specialization guidance
3. **Skill composition via tasks**: Multiple skills can be loaded in sequence by chaining Skill tool calls
4. **Skill as mode enforcer**: The genie skill can set expectations about what GENIE should and should not do (already partially implemented via feedback_genie_mode_lock.md)

**Priority:** Must — skill is the entry point; improve it with mode lock instructions.

---

### Feature: Custom Agent Definitions
**Description:** Agent definitions live in `~/.claude/agents/` as markdown files. Current GENIE workers are defined there (friday.md, nova.md, pepper.md, aria.md, etc. confirmed in `~/.claude/agents/`). These are used as `subagent_type` values in Agent tool calls.

Each agent definition includes:
- Identity and persona description
- Available tools list
- Operating rules and protocol references

**GENIE Integration:** Agent definitions are already the foundation of GENIE workers. Enhancement opportunities:
1. Add `team_name` parameter guidance to each definition
2. Add `isolation: "worktree"` guidance for appropriate worker types
3. Add SendMessage protocol documentation to each definition

**Priority:** Should — incremental improvement to existing infrastructure.

---

## 10. Settings & Configuration

### Feature: settings.json Full Option Set
**Description:** Confirmed keys from live `~/.claude/settings.json`:

```json
{
  "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" },
  "permissions": {
    "allow": ["*"],
    "defaultMode": "auto"
  },
  "model": "claude-opus-4-6",
  "hooks": {
    "SessionStart": [...],
    "PostToolUse": [...],
    "PreToolUse": [...],
    "Stop": [...]
  },
  "statusLine": { "type": "command", "command": "..." },
  "enabledPlugins": { "plugin-name@marketplace": true },
  "extraKnownMarketplaces": { "name": { "source": { "source": "github", "repo": "..." } } },
  "mcpServers": {},
  "skipAutoPermissionPrompt": true
}
```

**Key settings for GENIE:**

| Setting | Purpose | GENIE Use |
|---------|---------|-----------|
| `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Enables TeamCreate/SendMessage | Already enabled |
| `env.GENIE_WORKER` | Identifies worker context to hooks | Set per worker terminal |
| `permissions.defaultMode` | Auto-approves tools | Already `auto` |
| `skipAutoPermissionPrompt` | No permission dialogs | Already `true` |
| `hooks.SessionStart` | Runs at session start | Add GENIE worker init hook |
| `hooks.Stop` | Runs at session end | Add final status update hook |

**Per-Project Settings:** A `.claude/settings.json` in the project directory overrides or extends the global settings. Workers operating in `C:\Users\ethan\Documents\GitHub\Grid-Sentinel` could have project-specific hook additions.

**Priority:** Must — the `env.GENIE_WORKER` pattern enables all hook-based enforcement.

---

## 11. Context Bridge: StatusLine ↔ Hooks

### Feature: Statusline-to-Hook Bridge File
**Description:** The statusline writes context metrics to `%TEMP%/claude-ctx-{session_id}.json`:
```json
{
  "session_id": "...",
  "remaining_percentage": 45.2,
  "used_pct": 67,
  "timestamp": 1234567890
}
```
PostToolUse hooks read this file to inject context warnings into agent conversation. This is the **bridge pattern** — one hook writes state, another reads it. No IPC, no network — just temp files.

**GENIE Integration:** Extend the bridge pattern for GENIE:
1. **Worker state bridge**: Write worker status to a temp file, read in statusline
2. **GENIE health bridge**: GENIE writes fleet health to a bridge file, read by workers via PostToolUse hook to inject "GENIE reports FRIDAY is blocked"
3. **Session-to-dispatch bridge**: When GENIE spawns a worker, write the session_id to that worker's dispatch dir

**Priority:** Should — elegant zero-dependency IPC already in production.

---

## 12. AskUserQuestion — Interactive Decision Points

### Feature: AskUserQuestion
**Description:** Presents 1-4 questions with 2-4 options each. Supports:
- `multiSelect: true` for non-exclusive choices
- `preview` field for visual mockups (code/ASCII art)
- `header` chip (max 12 chars) for visual grouping
- `annotations` for user notes on selections
- Side-by-side preview layout when any option has `preview`

**GENIE Integration:**
1. **Worker dispatch confirmation**: Before spawning 5+ workers, ask user for approval with a preview of the task assignments
2. **Conflict resolution**: When two workers modify the same file, ask user which version to keep (with diffs as previews)
3. **Mode selection**: GENIE startup: "Which mode? [Orchestrate / Plan / Monitor / Debug]"

**Priority:** Should — good for UX polish on complex dispatches.

---

## 13. Channels / Remote Settings

### Feature: Channels (channelsEnabled)
**Description:** `~/.claude/remote-settings.json` contains `{"channelsEnabled": true}`. This is a server-side feature flag. When enabled, Claude Code can receive push notifications or "channels" — likely related to the RemoteTrigger API enabling real-time event delivery.

**GENIE Integration:** Channels could enable GENIE to receive push notifications when workers complete tasks, rather than polling outbox files. If channels deliver RemoteTrigger fire events, GENIE could be notified the moment a scheduled task runs.

**Priority:** Nice-to-have — investigate further; channels API is not yet documented publicly.

---

## Priority Matrix

### Must-Have Integrations

| Feature | Implementation | Effort |
|---------|---------------|--------|
| StatusLine GENIE worker indicator | Extend `gsd-statusline.js` to read `GENIE_WORKER` env + status.json | Low |
| GENIE mode enforcement hook | New PreToolUse hook: block non-orchestration actions when `GENIE_WORKER=GENIE` | Medium |
| CronCreate for GENIE inbox polling | Add `CronCreate` call in `/genie` skill startup, `durable: true` | Low |
| RemoteTrigger for GENIE health checks | Create/update trigger to run GENIE health check every 15min | Low |
| Stop hook for worker session end | Add to global settings: runs `session_save` + writes final status | Low |
| GENIE_WORKER env var in worker spawns | Add `env: {GENIE_WORKER: "FRIDAY"}` to each worker's dispatch command | Low |

### Should-Have Integrations

| Feature | Implementation | Effort |
|---------|---------------|--------|
| TeamCreate for dispatch batches | Integrate into GENIE dispatch flow | Medium |
| SendMessage for same-session agents | Hybrid: file mailbox for cross-terminal, SendMessage for same-session | Medium |
| Worktree isolation for risky workers | Add `isolation: "worktree"` to agent definitions for NOVA/SELENE | Low |
| LSP for code review agents | Document in PEPPER and ARIA agent definitions | Low |
| PostToolUse GENIE health injection | Extend worker-heartbeat-hook.js with fleet health summary | Medium |
| Plan approval protocol | Implement for GENIE plan review before large dispatches | Medium |

### Nice-to-Have Integrations

| Feature | Implementation | Effort |
|---------|---------------|--------|
| Custom GENIE MCP server | Build Node.js MCP server exposing dispatch state as resources | High |
| Notebook reports for AURORA | Add .ipynb output capability to AURORA agent definition | Low |
| Channels integration | Wait for public API documentation | Unknown |
| AskUserQuestion dispatch confirmation | Add to GENIE dispatch flow for 5+ worker spawns | Low |

---

## Implementation Quick-Wins (Do Today)

### 1. GENIE Mode Status Line (30 min)
Add to `gsd-statusline.js`:
```javascript
// GENIE/GENIE mode indicator
const isJarvisMode = fs.existsSync(path.join(claudeDir, 'dispatch', 'GENIE', 'mode-active.json'));
if (isJarvisMode) {
  const modeData = JSON.parse(fs.readFileSync(...));
  prefix = `\x1b[35m🎯 GENIE\x1b[0m │ `;
}
const workerName = process.env.GENIE_WORKER;
if (workerName) {
  const statusPath = path.join(claudeDir, 'dispatch', workerName, 'status.json');
  // ... show worker name + task snippet
}
```

### 2. GENIE Mode Lock Hook (45 min)
New file `~/.claude/hooks/genie-mode-guard.js`:
```javascript
// PreToolUse hook: when GENIE_WORKER=GENIE, block implementation actions
// Allow: Agent, Read, Glob, Grep, Bash(ls/cat/git log), Write(dispatch dirs only)
// Block: Edit, Write(project files), Bash(git commit/npm/python)
```
Register in settings.json PreToolUse with matcher `"Bash|Edit|Write"`.

### 3. CronCreate for Inbox Polling (15 min)
In the `/genie` skill, add:
```
On activation: CronCreate(cron: "*/2 * * * *", prompt: "Check ~/.claude/dispatch/*/outbox/*.md for new worker messages and process them", durable: true, recurring: true)
```

### 4. GENIE_WORKER in Worker Spawns (15 min)
When `genie-spawn.ps1` launches a worker, pass `GENIE_WORKER=<WORKER_NAME>` as an environment variable. This enables all hook-based enforcement automatically.

---

## Hidden Gems Found

1. **Bridge file pattern** — statusline writes to temp, hooks read from temp. Zero-dependency IPC. Can be extended for any cross-hook state sharing.

2. **`additionalContext` in hooks** — hooks can inject text into the agent's live conversation context without blocking. This is how context warnings appear. GENIE can use this to inject worker status updates directly into the working context.

3. **Team config at `~/.claude/teams/{name}/config.json`** — machine-readable member registry. Workers can discover their teammates without GENIE telling them. Auto-discovery pattern.

4. **`CLAUDE_CONFIG_DIR` env var** — Claude Code respects this for custom config directories. Workers could use this to point to isolated config dirs if needed.

5. **`durable: true` on CronCreate** — persists scheduled tasks to `.claude/scheduled_tasks.json`. GENIE monitoring survives Claude restarts. This was not documented in the worker protocol.

6. **RemoteTrigger `run` action** — manually fires a trigger. GENIE can create a trigger for each worker and fire it programmatically as a recovery mechanism when the terminal is closed.

7. **`plan_approval_request` via SendMessage** — built-in gating mechanism. No custom protocol needed for GENIE to pause a worker and ask for approval before a risky operation.

8. **`isolation: "worktree"` on Agent** — auto-cleanup if no changes. Zero-cost to add this to all NOVA/experimental worker spawns. If the work is throwaway, no cleanup needed.

---

*Research complete. All findings based on direct file inspection, schema fetching, and live API queries.*
