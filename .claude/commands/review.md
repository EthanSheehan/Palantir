---
name: review
description: Run all review agents (ECC) on recent changes in parallel with autonomous model selection
argument-hint: "[--security] [--deep]"
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Agent
---
<objective>
Run the full review suite from everything-claude-code on current uncommitted changes.

**Model selection:**
- Standard review: sonnet for all reviewers (parallel)
- `--deep`: opus for security reviewer, sonnet for code reviewers
- `--security`: only run security-reviewer with opus

Always launches reviewers in parallel.
</objective>

<context>
Flags: $ARGUMENTS
</context>

<process>
## Step 1: Identify changes

Run `git diff` and `git diff --cached` to see what changed. Identify Python vs non-Python files.

## Step 2: Launch reviewers in parallel

Based on changes detected:

**Python files changed:**
- Launch `everything-claude-code:python-reviewer` (model: sonnet, or opus if --deep)

**Non-Python files changed:**
- Launch `everything-claude-code:code-reviewer` (model: sonnet, or opus if --deep)

**Always:**
- Launch `everything-claude-code:security-reviewer` (model: sonnet, or opus if --deep or --security)

All three launch in a single parallel message.

## Step 3: Summarize findings

Collect results from all reviewers. Present findings grouped by severity:
- CRITICAL — must fix before commit
- HIGH — should fix before commit
- MEDIUM — fix when convenient
- LOW — informational
</process>
