---
name: monitor
description: View or manage the usage monitor — shows tokens, cost, burn rate (auto-starts every session)
argument-hint: "[--daily] [--weekly] [--monthly] [--session] [--stop] [--status]"
allowed-tools:
  - Bash
  - Read
---
<objective>
The claude-monitor auto-starts in the background on every session via the SessionStart hook.

This command lets you:
- Check if it's running (`--status`)
- Switch views (`--daily`, `--monthly`, `--session`)
- Stop it (`--stop`)
- Restart it if stopped (no flags)

The monitor runs in a separate process and does NOT consume Claude Code context.
</objective>

<context>
Flags: $ARGUMENTS
</context>

<process>
## Determine action from flags

**`--status` or no flags and monitor already running:**
Check if monitor is running and show current state:
```bash
if pgrep -f "claude_monitor" > /dev/null 2>&1; then
  PID=$(pgrep -f "claude_monitor")
  echo "claude-monitor is running (PID: $PID)"
  echo "View in another terminal: python3 -m claude_monitor"
  echo "Logs: /tmp/claude-monitor.log"
else
  echo "claude-monitor is not running"
fi
```

**`--stop`:**
```bash
pkill -f "claude_monitor" && echo "Stopped" || echo "Not running"
```

**`--daily`, `--monthly`, `--session`:**
Kill existing and restart with new view:
```bash
pkill -f "claude_monitor" 2>/dev/null
nohup python3 -m claude_monitor --view <view> > /tmp/claude-monitor.log 2>&1 &
echo "Monitor restarted with <view> view (PID: $!)"
```

**`--weekly`:**
Show a weekly summary by reading Claude's usage data for the last 7 days:
```bash
pkill -f "claude_monitor" 2>/dev/null
nohup python3 -m claude_monitor --view daily > /tmp/claude-monitor.log 2>&1 &
echo "Monitor started with daily view (shows last 7+ days of usage)"
```
Also compute a quick inline weekly summary: read session data from `~/.config/claude/` or `~/.claude/` usage logs, sum tokens and costs for the past 7 days, and display inline.

**No flags and monitor NOT running:**
Start with default realtime view:
```bash
nohup python3 -m claude_monitor --view realtime > /tmp/claude-monitor.log 2>&1 &
echo "Monitor started (PID: $!)"
```

## Show inline usage hint

After any action, show:
```
Usage monitor commands:
  /monitor              — Check status / restart if stopped
  /monitor --daily      — Switch to daily aggregated view
  /monitor --weekly     — Weekly summary (last 7 days)
  /monitor --monthly    — Switch to monthly budget view
  /monitor --session    — Switch to session breakdown view
  /monitor --stop       — Stop the background monitor

To view the dashboard directly: open another terminal and run:
  claude-monitor
  claude-monitor --view daily
  claude-monitor --view monthly
```
</process>
