---
name: ralph-run
description: Set up and launch Ralph autonomous loop for batch task execution
argument-hint: "<task description or path to PRD>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - AskUserQuestion
---
<objective>
Prepare the Ralph autonomous loop for unattended execution. This command:
1. Writes tasks to `.ralph/fix_plan.md`
2. Updates `.ralph/PROMPT.md` with context
3. Provides the command to launch Ralph

Ralph runs outside Claude Code as a CLI wrapper — this command sets it up, the user launches it.
</objective>

<context>
Input: $ARGUMENTS
</context>

<process>
## Step 1: Parse input

If input is a file path (e.g., `prd.md`), read it and extract tasks.
If input is a description, break it into discrete tasks.

## Step 2: Write fix_plan.md

Write tasks to `.ralph/fix_plan.md` in Ralph's expected format:
```markdown
# Fix Plan

## Tasks

- [ ] Task 1: description
- [ ] Task 2: description
...
```

## Step 3: Update PROMPT.md

Update `.ralph/PROMPT.md` with relevant project context for this batch of work.

## Step 4: Inform user

Tell the user:
```
Ralph is configured. Launch from terminal:
  ralph --monitor

Or for background execution:
  ralph &
```

Do NOT launch Ralph directly — it must run in a separate terminal.
</process>
