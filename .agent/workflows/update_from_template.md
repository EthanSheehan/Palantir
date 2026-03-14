---
description: "Workflow to update the current project from the upstream Antigravity template."
---

# Update from Template

## Trigger

Use this workflow when you want to pull the latest rules, skills, or structure from the Antigravity template.

## Prerequisites

- The upstream template must be added as a remote named `template`.
- `git remote add template https://github.com/EthanSheehan/Antigravity.git`

## Steps

1.  **Fetch Upstream**:
    `git fetch template`

2.  **Merge Updates**:
    - We merge with `--allow-unrelated-histories` if disjoint.
    - `git merge template/main --no-commit --allow-unrelated-histories`

3.  **Conflict Resolution**:
    - **Accept Theirs** (`--theirs`) for: `/.agent/rules`, `/.agent/skills`, `/.agent/workflows`.
    - **Manual** for: `README.md`, `/src`, `/configs`.

4.  **Update Skills**:
    - If `/.agent/skills` has changed, ensure new skills are indexed.

5.  **Commit**:
    `git commit -m "chore: update from Antigravity template"`
