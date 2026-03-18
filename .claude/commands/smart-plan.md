---
name: smart-plan
description: Intelligent planning that picks the right system (ECC, GSD, DevFleet, or Ralph) based on scope
argument-hint: "<feature or task description>"
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
  - Agent
  - Skill
  - AskUserQuestion
---
<objective>
Analyze a task/feature request and produce an implementation plan using the most appropriate system.

**Model selection for planning:**
- opus — architectural decisions, complex multi-phase planning
- sonnet — standard feature planning, task breakdown
- haiku — simple task classification, file discovery

**System selection:**
- 1-3 files, clear scope → ECC planner (sonnet) → direct implementation
- 4-10 files, independent parts → DevFleet parallel worktrees (sonnet per mission)
- 4-10 files, sequential deps → GSD quick --full (sonnet planning, sonnet execution)
- 10+ files or multi-phase → GSD phases → DevFleet execution (opus planning, sonnet code)
- 20+ tasks or PRD-driven → Ralph batch setup
</objective>

<context>
Task: $ARGUMENTS
</context>

<process>
## Step 1: Analyze scope (model: haiku)

Read the task description. Use Glob/Grep to estimate:
- Number of files affected
- Number of distinct changes needed
- Whether it spans multiple subsystems

## Step 2: Choose system and plan

**Small scope (1-3 files):**
Launch `everything-claude-code:planner` (model: sonnet) to create implementation plan.

**Medium scope — parallelizable (4-10 files, independent parts):**
1. Launch `everything-claude-code:planner` (model: sonnet) to decompose into units
2. Map units to DevFleet missions with dependency edges
3. Present mission DAG for user approval

**Medium scope — sequential (4-10 files, changes depend on each other):**
Use `/gsd:quick --discuss --research --full` to plan with GSD guarantees.

**Large scope (10+ files, multi-phase):**
1. Launch `everything-claude-code:architect` (model: opus) for architecture decisions
2. Use `/gsd:new-milestone` or `/gsd:plan-phase` for phased breakdown
3. Map each phase's plans to DevFleet missions for parallel worktree execution

**Batch scope (20+ tasks):**
Break into Ralph-compatible task list, write to `.ralph/fix_plan.md`.

## Step 3: Present plan

Show the user:
- System chosen and why
- Implementation plan / phases / mission DAG
- Which agents will be spawned and with which models
- Next command to run (e.g., `/build`, `/everything-claude-code:devfleet`, `/gsd:execute-phase 1`, `ralph --monitor`)
</process>
