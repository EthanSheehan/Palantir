---
description: "Active Rule: Automatically commit changes when a significant milestone is reached."
globs: ["**/*"]
---

# Auto-Commit at Milestones

## Trigger

This rule is active at all times. You must proactively check if a "Milestone" has been reached after every major step or successful verification.

## milestones

A **Milestone** is defined as:

1.  **Tests Passed**: A previously failing test suite now passes.
2.  **Feature Complete**: A distinct sub-task from `task.md` or `implementation_plan.md` is marked as done.
3.  **Refactor Complete**: A specific refactoring goal (e.g., "Rename variables", "Extract function") is finished and verified.
4.  **Verification Success**: A verification script runs successfully after changes.

## Action

When a milestone is reached:

1.  **Do NOT ask the user for permission** to commit (unless explicitely told otherwise).
2.  **Generate a Conventional Commit Message**:
    - `feat: ...` for new features
    - `fix: ...` for bug fixes
    - `refactor: ...` for code restructuring
    - `docs: ...` for documentation updates
    - `test: ...` for adding/fixing tests
    - `chore: ...` for maintenance
3.  **Execute**: `git add .` and `git commit -m "type: description"`

## Exceptions

- Do not commit if the build is broken.
- Do not commit if the code is in a clearly broken intermediate state.
