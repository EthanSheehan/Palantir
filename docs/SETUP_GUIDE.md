# Setup Guide: Integrated Claude Code Workflow

Step-by-step instructions to replicate the full four-system integrated Claude Code setup (ECC + GSD + DevFleet + Ralph) with autonomous model selection and agent teams.

## Prerequisites

- **Claude Code CLI** installed and authenticated (`claude` command available)
- **Node.js / npm** (for GSD and MCP servers)
- **Python 3.10+** with venv
- **Git** configured
- **macOS** (adjust paths for Linux)
- **Homebrew** (macOS only, for coreutils)

---

## Step 1: Install everything-claude-code (ECC)

ECC is a Claude Code plugin from the marketplace.

```bash
# Enable the plugin (run inside Claude Code or configure settings.json)
# Add to ~/.claude/settings.json under "enabledPlugins":
"everything-claude-code@everything-claude-code": true
```

Add the marketplace source to `~/.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": {
    "everything-claude-code": {
      "source": {
        "source": "github",
        "repo": "affaan-m/everything-claude-code"
      }
    }
  }
}
```

**Verify:** In a Claude Code session, ECC agents should be available as `subagent_type: "everything-claude-code:<name>"`.

---

## Step 2: Install GSD (Get Shit Done)

```bash
# Install globally to ~/.claude/
npx get-shit-done-cc@latest --claude --global
```

This installs:
- 38 slash commands → `~/.claude/commands/gsd/`
- 15 agents → `~/.claude/agents/`
- 3 hooks → `~/.claude/hooks/`
- Workflows → `~/.claude/get-shit-done/`

**Verify:** In Claude Code, run `/gsd:help`.

---

## Step 3: Install Ralph

```bash
# Install coreutils (macOS only — provides gtimeout)
brew install coreutils

# Clone and install
cd /tmp
git clone https://github.com/frankbria/ralph-claude-code.git
cd ralph-claude-code
bash install.sh

# Add to PATH (add to ~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"
```

This installs:
- CLI commands → `~/.local/bin/` (ralph, ralph-monitor, ralph-setup, ralph-enable, ralph-enable-ci)
- Global config → `~/.ralph/`

**Enable for your project:**
```bash
cd /path/to/your/project
ralph-enable-ci
```

Then update `.ralph/AGENT.md` with your project's build/test/run commands, and `.ralph/PROMPT.md` with the correct project type.

**Verify:** `ralph --help` shows usage.

---

## Step 4: Configure settings.json

Your `~/.claude/settings.json` should include these sections:

```json
{
  "permissions": {
    "allow": ["*"]
  },
  "model": "claude-opus-4-6",
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/skills/continuous-learning/evaluate-session.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"$HOME/.claude/hooks/gsd-check-update.js\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node \"$HOME/.claude/hooks/gsd-context-monitor.js\""
          }
        ]
      }
    ]
  },
  "enabledPlugins": {
    "everything-claude-code@everything-claude-code": true,
    "context7@claude-plugins-official": true,
    "playwright@claude-plugins-official": true,
    "github@claude-plugins-official": true,
    "code-review@claude-plugins-official": true,
    "commit-commands@claude-plugins-official": true,
    "feature-dev@claude-plugins-official": true,
    "pr-review-toolkit@claude-plugins-official": true,
    "hookify@claude-plugins-official": true,
    "claude-md-management@claude-plugins-official": true,
    "agent-sdk-dev@claude-plugins-official": true
  },
  "extraKnownMarketplaces": {
    "claude-plugins-official": {
      "source": {
        "source": "github",
        "repo": "anthropics/claude-plugins-official"
      }
    },
    "everything-claude-code": {
      "source": {
        "source": "github",
        "repo": "affaan-m/everything-claude-code"
      }
    }
  },
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  },
  "statusLine": {
    "type": "command",
    "command": "node \"$HOME/.claude/hooks/gsd-statusline.js\""
  }
}
```

Adjust `permissions`, `mcpServers`, and `enabledPlugins` to your needs. The critical pieces are:
- The three GSD hooks (Stop is continuous-learning, SessionStart is GSD update check, PostToolUse is context monitor)
- The ECC plugin enabled
- The GSD statusline

---

## Step 5: Create Global Rules

Create these files under `~/.claude/rules/`:

### `~/.claude/rules/agents.md`
The main orchestration rules. Contains:
- Core rule: always spawn agent teams
- Team composition rules with minimum sizes
- Wave execution pattern
- Autonomous model selection matrix
- System selection guide (ECC vs GSD vs DevFleet vs Ralph)
- DevFleet integration patterns

**See:** The full content is in the project repo at `~/.claude/rules/agents.md`.

### `~/.claude/rules/active-behaviors.md`
Automatic behaviors that run every session:
- Skill discovery before every task
- Continuous learning from every conversation
- Documentation sync after code changes
- Memory-first context loading
- Context health monitoring

### `~/.claude/rules/performance.md`
Model selection strategy and context window management:
- haiku / sonnet / opus selection criteria
- Active context hygiene (delegate to subagents)
- When to recommend a new chat (70% context, topic shift)

### `~/.claude/rules/development-workflow.md`
The full development pipeline:
- Research & reuse (mandatory before implementation)
- ECC standard pipeline
- GSD multi-phase pipeline
- Ralph autonomous pipeline

### Other rules files:
- `coding-style.md` — immutability, file organization, error handling
- `git-workflow.md` — commit format, PR process
- `security.md` — mandatory security checks before commit
- `testing.md` — 80% coverage, TDD workflow
- `hooks.md` — hook types and best practices
- `patterns.md` — repository pattern, API response format

---

## Step 6: Create Global CLAUDE.md

`~/.claude/CLAUDE.md` is loaded in every session. It should contain:

1. **Communication Style** — concise, no filler, no emojis
2. **Code Preferences** — use venv, prefer editing, don't over-engineer
3. **Git Workflow** — never commit unless asked, use `gh` CLI
4. **Tool Usage** — parallel calls, dedicated tools over Bash
5. **Skill Discovery** — always search for relevant skills before starting
6. **Continuous Learning** — save patterns, corrections, preferences to memory
7. **Documentation Updates** — proactively update docs after code changes
8. **Memory Management** — save context aggressively for fast session spin-up
9. **Active Context Management** — monitor context, recommend new chat at 70%

---

## Step 7: Create Project Commands

Create `.claude/commands/` in your project directory with these slash commands:

### `build.md`
Full pipeline — auto-routes to ECC/GSD/DevFleet/Ralph based on task complexity. Includes scope detection, wave-based team assembly, and parallel review.

### `smart-plan.md`
Intelligent planning — analyzes task scope and picks the optimal system. Presents plan with mission DAG and recommended next command.

### `review.md`
Parallel ECC review — launches python-reviewer + security-reviewer + code-reviewer in one message. Supports `--deep` (opus) and `--security` flags.

### `ralph-run.md`
Ralph setup — parses task description or PRD into `.ralph/fix_plan.md` tasks and configures the autonomous loop.

### `status.md`
Unified dashboard — shows git status, GSD progress, DevFleet missions, Ralph tasks.

### `go.md` (Master Command)
Single entry point that runs the full pipeline. Loads session context, searches skills, classifies task, assembles agent team, plans, executes, reviews, and auto-saves. Supports `--plan-only` and `--autonomous` flags.

---

## Step 8: Install Usage Monitor (Auto-Starts Every Session)

```bash
pip3 install claude-monitor
# Or: uv tool install claude-monitor
# Or: pipx install claude-monitor
```

### Auto-Start Hook

Create the launcher script at `~/.claude/hooks/claude-monitor-launcher.sh`:

```bash
#!/bin/bash
# Auto-launch claude-monitor on session start (if not already running)
if pgrep -f "claude_monitor" > /dev/null 2>&1; then
  exit 0  # Already running
fi
if ! python3 -c "import claude_monitor" 2>/dev/null; then
  exit 0  # Not installed, skip silently
fi
nohup python3 -m claude_monitor --view realtime > /tmp/claude-monitor.log 2>&1 &
echo "claude-monitor started (PID: $!)" > /tmp/claude-monitor-pid.txt
```

Make it executable:
```bash
chmod +x ~/.claude/hooks/claude-monitor-launcher.sh
```

Add to `~/.claude/settings.json` under `hooks.SessionStart[0].hooks`:
```json
{
  "type": "command",
  "command": "bash \"/path/to/.claude/hooks/claude-monitor-launcher.sh\""
}
```

### Viewing the Dashboard

The monitor runs headless in background. To see it, open a **separate terminal**:

```bash
claude-monitor                  # Real-time burn rate + progress bars
claude-monitor --view daily     # Daily aggregated stats
claude-monitor --view monthly   # Monthly budget analysis
claude-monitor --view session   # Current session breakdown
```

### Managing via Claude Code

```
/monitor              — Check status / restart if stopped
/monitor --daily      — Switch to daily view
/monitor --weekly     — Weekly summary (last 7 days)
/monitor --monthly    — Switch to monthly view
/monitor --session    — Switch to session view
/monitor --stop       — Stop the background monitor
```

Aliases: `claude-monitor`, `cmonitor`, `ccmonitor`, `ccm`

---

## Step 9: Create Project CLAUDE.md

Your project's `CLAUDE.md` should include:
1. What the project is
2. How to run / test / install
3. Architecture overview
4. The four-system integration table
5. When to use which system
6. Agent trigger table (proactive usage)
7. Development pipelines for each system
8. Parallel execution rules

---

## Step 10: Set Up Memory

Create the memory directory and index:

```bash
mkdir -p ~/.claude/projects/<project-path-encoded>/memory/
```

Create `MEMORY.md` as an index of memory files. Save memories for:
- User preferences and role
- Feedback / corrections
- Project context and decisions
- External references

---

## Verification Checklist

Run these checks to confirm everything works:

```bash
# GSD
ls ~/.claude/commands/gsd/ | wc -l          # Should be 38
ls ~/.claude/agents/gsd-*.md | wc -l        # Should be 15
ls ~/.claude/hooks/gsd-*.js | wc -l         # Should be 3

# Ralph
which ralph                                  # Should show ~/.local/bin/ralph
ls .ralph/                                   # Should show AGENT.md, PROMPT.md, fix_plan.md

# ECC
# In Claude Code, verify agents respond:
# Agent(subagent_type="everything-claude-code:planner", ...)

# Settings
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print('Hooks:', list(d.get('hooks',{}).keys())); print('Plugins:', len(d.get('enabledPlugins',{})))"

# Project commands
ls .claude/commands/                         # Should show build.md, review.md, etc.

# Rules
ls ~/.claude/rules/                          # Should show 11 .md files

# Memory
ls ~/.claude/projects/*/memory/MEMORY.md     # Should exist
```

---

## Quick Start

After setup, here's how to use the system:

```bash
# Start Claude Code in your project
cd /path/to/project
claude

# MASTER COMMAND — does everything (plan + execute + review)
> /go Add WebSocket heartbeat with configurable interval
> /go --plan-only Implement real-time BDA pipeline   # Plan only
> /go --autonomous Fix all failing tests              # Full auto

# Or use individual commands:
> /build Add new endpoint        # Full pipeline with system selection
> /smart-plan New BDA pipeline   # Plan only, pick system
> /review --deep                 # Review uncommitted changes
> /ralph-run tasks.md            # Set up autonomous batch
> /status                        # Dashboard across all systems

# GSD for phased development
> /gsd:plan-phase 1
> /gsd:execute-phase 1
> /gsd:verify-work 1

# Session management
> /everything-claude-code:save-session     # Save before closing
> /everything-claude-code:resume-session   # Resume in new chat

# Run usage monitor in a separate terminal
$ claude-monitor
```

---

## Troubleshooting

**GSD commands not appearing:**
```bash
npx get-shit-done-cc@latest --claude --global  # Reinstall
```

**Ralph not in PATH:**
```bash
export PATH="$HOME/.local/bin:$PATH"  # Add to shell rc
```

**ECC agents not available:**
Check `~/.claude/settings.json` has `"everything-claude-code@everything-claude-code": true` in `enabledPlugins`.

**Context monitor not firing:**
Check `~/.claude/hooks/gsd-context-monitor.js` exists and the PostToolUse hook is configured in settings.json.

**DevFleet not available:**
DevFleet is part of ECC. Ensure the ECC plugin is enabled. Use `/everything-claude-code:devfleet` to invoke.

**Continuous learning hook fails:**
Check `~/.claude/skills/continuous-learning/evaluate-session.sh` exists and is executable (`chmod +x`).

**claude-monitor not found:**
```bash
pip3 install claude-monitor  # Reinstall
# Or add pip bin to PATH: export PATH="$(python3 -m site --user-base)/bin:$PATH"
```

**Session files disappearing:**
Always save to `~/.claude/saved-sessions/` (NOT `~/.claude/sessions/`). Claude Code auto-deletes unrecognized files from `~/.claude/sessions/`. Always use Bash heredoc to write session files, never the Write tool.
