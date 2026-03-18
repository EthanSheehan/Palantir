---
name: status
description: Show unified status across all four systems (ECC agents, GSD progress, DevFleet missions, Ralph loop)
allowed-tools:
  - Read
  - Glob
  - Bash
---
<objective>
Show a unified dashboard of the current state across all four development systems.
</objective>

<process>
## Gather status from all systems

**Git status:**
- Run `git status` and `git log --oneline -5`

**GSD status:**
- Read `.planning/STATE.md` if it exists
- Read `.planning/ROADMAP.md` if it exists
- Show current phase, completed phases, and progress

**Ralph status:**
- Read `.ralph/fix_plan.md` — count completed vs remaining tasks
- Check `.ralph/logs/` for recent loop activity
- Report if Ralph is currently running (`ps aux | grep ralph_loop`)

**DevFleet status:**
- Check if DevFleet MCP server is running (`curl -s http://localhost:18801/mcp` or similar)
- If running, call `get_dashboard()` to show active missions, slots, and queue

**Recent changes:**
- Show `git diff --stat` for uncommitted work

Present as a concise dashboard.
</process>
