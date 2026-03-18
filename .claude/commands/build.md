---
name: build
description: Full integrated build pipeline — plan, implement, review, commit using all four systems (ECC + GSD + DevFleet + Ralph)
argument-hint: "<description of what to build> [--gsd] [--devfleet] [--ralph] [--quick]"
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
Integrated build pipeline that orchestrates everything-claude-code (ECC), GSD, DevFleet, and Ralph based on task complexity.

**Autonomous model selection:** Choose the right model for each sub-task:
- **haiku** — lightweight agents, file discovery, doc updates, codebase mapping
- **sonnet** — main coding work, code generation, test writing, code review, most agents
- **opus** — architectural decisions, complex debugging, security deep-dive, multi-phase planning

**Routing logic:**
- `--quick` or small task (1-3 files, bug fix) → ECC agents only
- `--devfleet` or parallelizable feature (4-10 files, independent parts) → DevFleet worktrees + ECC review
- `--gsd` or multi-phase feature (10+ files) → GSD plan → DevFleet execute → ECC review
- `--ralph` or batch/unattended (20+ tasks) → Ralph autonomous loop
- No flag → auto-detect based on task description and codebase analysis

**CORE RULE: Always assemble an agent team.** Never implement alone — spawn subagents for every phase.
</objective>

<context>
Task: $ARGUMENTS
</context>

<process>
## Step 1: Classify the task

Read the task description. Spawn an Explore agent (haiku) to estimate scope:
- How many files will be affected?
- Are the changes independent (parallelizable) or sequential?
- Does it span multiple subsystems?

Classify:
- **small** (1-3 files, single concern) → ECC pipeline
- **medium-sequential** (4-10 files, changes depend on each other) → GSD quick + ECC review
- **medium-parallel** (4-10 files, independent parts) → DevFleet + ECC review
- **large** (10+ files, multi-phase) → GSD phases → DevFleet execution → ECC review
- **batch** (20+ tasks, PRD) → Ralph loop

## Step 2: Plan

**small**: Spawn `everything-claude-code:planner` (sonnet)
**medium-sequential**: Spawn `everything-claude-code:planner` (sonnet) or use `/gsd:quick --discuss --research`
**medium-parallel**: Spawn `everything-claude-code:planner` (sonnet) → decompose into DevFleet missions
**large**: Use `/gsd:plan-phase` (opus for planning) → map plans to DevFleet mission DAG
**batch**: Write tasks to `.ralph/fix_plan.md`, inform user to run `ralph --monitor`

## Step 3: Implement

**small**: Write code directly. Spawn `everything-claude-code:tdd-guide` (sonnet) for tests.
**medium-sequential**: Write code with TDD. Use Agent tool with `isolation: "worktree"` for risky changes.
**medium-parallel**: Use `/everything-claude-code:devfleet` — dispatch each unit as a mission (sonnet per mission). Independent missions run in parallel worktrees.
**large**: GSD executes phases. Each phase plan dispatches to DevFleet for parallel worktree execution.
**batch**: Ralph handles autonomously.

## Step 4: Review (ALWAYS parallel agent team)

After implementation completes, launch review team in a single message:
- `everything-claude-code:python-reviewer` (sonnet) — for Python changes
- `everything-claude-code:code-reviewer` (sonnet) — for non-Python changes
- `everything-claude-code:security-reviewer` (sonnet, upgrade to opus for auth/crypto)

All three launch in parallel. For large changes, also spawn:
- `everything-claude-code:doc-updater` (haiku, background)

## Step 5: Fix findings

Address CRITICAL and HIGH issues. If significant changes made, re-launch review team.

## Step 6: Report

Summarize: what was built, which system executed it, review findings, and what's ready for commit.
Do NOT commit unless user explicitly asks.
</process>
