---
description: "Protocol for reviewing Pull Requests using the code-review-checklist skill."
---

# PR Review Protocol

## Trigger

Use this workflow when a Pull Request is opened or updated.

## Steps

1.  **Checkout Branch**:
    `git checkout <pr-branch>`

2.  **Run Tests**:
    - Python: `pytest`
    - MATLAB: Run verification scripts

3.  **Code Review**:
    - Use the `code-review-checklist` skill rules.
    - Check for:
      - Security vulnerabilities (Injection, Secrets)
      - Performance bottlenecks (Loops in Python, pre-allocation in MATLAB)
      - "Zero-Hallucination" documentation compliance
      - Typing (Python)

4.  **Feedback**:
    - If issues found: Comment on the PR.
    - If clean: Approve.
