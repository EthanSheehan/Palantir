---
name: go
description: Master command — start the full integrated pipeline (ECC + GSD + DevFleet + Ralph) for any task
argument-hint: "<what to build or do> [--plan-only] [--autonomous]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
  - Skill
  - AskUserQuestion
---
<objective>
Single entry point that activates the full integrated development pipeline. One command to rule them all.

This command:
1. Loads session context (resumes if previous session exists)
2. Searches for relevant skills
3. Classifies the task and assembles an agent team
4. Plans using the right system (ECC/GSD/DevFleet/Ralph)
5. Executes with autonomous model selection
6. Reviews with parallel ECC agents
7. Auto-saves session state on completion

**Flags:**
- `--plan-only` — Plan but don't execute (good for review before starting)
- `--autonomous` — Full autonomous mode: plan + execute + review without stopping

**Model selection is automatic:**
- haiku: research, file discovery, doc updates
- sonnet: coding, reviews, TDD, standard planning
- opus: architecture, security deep-dive, multi-phase planning
</objective>

<context>
Task: $ARGUMENTS
</context>

<process>
## Phase 0: Context Bootstrap

1. Check for recent session files in `~/.claude/saved-sessions/` — if one exists from today, load it for context
2. Read memory index (`MEMORY.md`) for relevant project context
3. Search for matching skills (`~/.claude/skills/`) for the task domain

## Phase 1: Classify & Assemble Team

Spawn an Explore agent (haiku) to analyze:
- Number of files affected
- Whether changes are independent (parallelizable) or sequential
- Which subsystems are involved

**Classification:**

| Scope | Files | System | Team |
|-------|-------|--------|------|
| Small | 1-3 | ECC only | planner + tdd-guide + reviewer |
| Medium (parallel) | 4-10, independent | DevFleet + ECC | planner + DevFleet missions + reviewers |
| Medium (sequential) | 4-10, dependent | GSD quick + ECC | GSD planner + executor + reviewers |
| Large | 10+ | GSD + DevFleet + ECC | architect + GSD phases + DevFleet + reviewers |
| Batch | 20+ tasks | Ralph | Ralph setup + reviewers post-completion |

## Phase 2: Plan

Based on classification, execute the appropriate planning:

**Small:** Launch `everything-claude-code:planner` (sonnet)
**Medium-parallel:** Launch `everything-claude-code:planner` (sonnet) → decompose into DevFleet missions
**Medium-sequential:** Run `/gsd:quick --discuss --research --full`
**Large:**
  1. Launch `everything-claude-code:architect` (opus) for architecture
  2. Run `/gsd:plan-phase` for phased breakdown
  3. Map plans to DevFleet mission DAG
**Batch:** Write tasks to `.ralph/fix_plan.md`

If `--plan-only`: present plan and stop here.

## Phase 3: Execute

**Small:** Write code directly with TDD (`everything-claude-code:tdd-guide`, sonnet)
**Medium-parallel:** Dispatch DevFleet missions (sonnet per mission, parallel worktrees)
**Medium-sequential:** Run `/gsd:execute-phase` (fresh context per plan)
**Large:** GSD phases → DevFleet execution → wave by wave
**Batch:** Tell user to run `ralph --monitor`

## Phase 4: Review (ALWAYS parallel team)

Launch in a single message:
- `everything-claude-code:python-reviewer` (sonnet) — Python changes
- `everything-claude-code:code-reviewer` (sonnet) — non-Python changes
- `everything-claude-code:security-reviewer` (sonnet, opus for auth/crypto)
- `everything-claude-code:doc-updater` (haiku, background) — if significant changes

## Phase 5: Fix & Finalize

Address CRITICAL and HIGH findings. Re-run reviewers if substantial changes made.

## Phase 6: Save State

1. Save progress to memory (decisions, what was built, what's next)
2. Update `.planning/STATE.md` if GSD was used
3. Update `.ralph/fix_plan.md` if Ralph tasks completed
4. Report what was built, reviewed, and what's ready for commit
5. Do NOT commit unless user explicitly asks

If context is getting heavy, auto-save session and recommend new chat.
</process>
