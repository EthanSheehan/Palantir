---
description: Structured workflow for committing code with quality and security checks.
---

# Commit Workflow

This workflow guides you through the process of committing code, ensuring all standards from `commit_standards.md` and `git_etiquette.md` are met.

## Step-by-Step Instructions

1.  **Check Status**
    - Run `git status` to see what files are changed.
    - Run `git diff` to review the actual changes line-by-line.

2.  **Verify Standards**
    - **Quality**: Does the code compile? Are there lint errors?
    - **Testing**: Have you run the relevant tests? do they pass?
    - **Cleanup**: Are all debug prints/comments removed?
    - **Security**: scanned for secrets or PII?

3.  **Stage Changes**
    - Run `git add <files>` for the specific files you want to commit.
    - Avoid `git add .` unless you are certain you want _everything_ (including untracked files).
    - create multiple commits where necessary

4.  **Craft Commit Message**
    - Use the format: `type(scope): description`
    - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
    - Example: `fix(auth): handle null token in login flow`

5.  **Commit**
    - Run `git commit -m "type(scope): description"`

6.  **Push (Optional)**
    - If ready to share, run `git push`.
