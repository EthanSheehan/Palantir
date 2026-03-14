---
description: "Systematic debugging protocol. MUST be followed upon error."
globs: ["**/*"]
---

# Systematic Debugging

**Core Principle**: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.

## The Process

### Phase 1: Investigation

1.  **Read** the error message completely.
2.  **Reproduce** the error consistently.
3.  **Check** recent changes (git diff).
4.  **Trace** the data flow.

### Phase 2: Hypothesis

1.  Form a single hypothesis: "I think X breaks because Y".
2.  Verify this hypothesis _without_ fixing it yet (e.g., adding a log/print).

### Phase 3: Action

1.  Create a **Failing Test Case** (if possible).
2.  Implement the fix.
3.  Verify the test passes.

## Red Flags

- "I'll just try changing this parameter." -> **STOP**.
- "Maybe it's a race condition?" (Guessing) -> **STOP**.
- Applying 3+ fixes that fail -> **STOP** and re-evaluate architecture.
