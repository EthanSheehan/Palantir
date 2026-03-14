---
description: "Standards and checks required before committing code."
globs: ["**/*"]
---

# Commit Standards

Before committing any code, you MUST verify that the following standards are met.

## 1. Quality Checks

- **Compilation/Syntax**: Ensure the code has no syntax errors.
- **Linting**: Run available linters (e.g., `eslint`, `flake8`) and fix _all_ errors.
- **Testing**:
  - Run relevant unit tests for the changed components.
  - If a test fails, **DO NOT COMMIT**. Fix the test or the code first.
- **No Debugging Artifacts**: Remove `console.log`, `print()`, `debugger` statements, or temporary comments like `// TODO: fix this later` (unless converted to a proper tracked issue).

## 2. Security & Sensitivity

- **No Secrets**: Check for API keys, passwords, tokens, or private URLs.
- **No Personal Data**: Ensure no PII (Personally Identifiable Information) is hardcoded.
- **Config Files**: verify you are not committing local config files (e.g., `.env`, local settings) unless they are templates (e.g., `.env.example`).

## 3. Commit Message

Adhere strictly to the **Conventional Commits** format defined in `git_etiquette.md`:

- **Format**: `type(scope): description`
- **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Description**:
  - Use the imperative mood ("add" not "added").
  - No period at the end of the subject line.
  - Mention issue numbers if applicable (e.g., `Closes #123`).

## 4. Atomic Commits

- Do not bundle unrelated changes.
- If you have modifying 3 distinct features, make 3 distinct commits.
