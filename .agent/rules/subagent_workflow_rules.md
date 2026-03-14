---
description: Enforce Subagent Manager Workflow for complex tasks
triggers:
  - "complex task"
  - "multi-step"
  - "orchestrate"
  - "refactor"
  - "manager"
  - "subagent"
---

# Rule: Prioritize Subagent Manager Workflow

## Context

Complex coding tasks often suffer from context loss or lack of verification when executed as a single long stream of thought.

## The Rule

When faced with **complex, multi-step tasks** or tasks requiring **multiple domains of expertise** (e.g., full-stack features, system refactors), you MUST **ALWAYS prioritize using the `subagent_workflow.md`**.

## Requirements

1.  **Adopt Manager Persona**: Explicitly state you are acting as the Manager.
2.  **Delegate**: Do not attempt to do everything yourself. Spin up specialized subagents for distinct chunks of work.
3.  **Verify**: The Manager Agent MUST explicitly verify the output of all subagents before proceeding. Blind trust is prohibited.
