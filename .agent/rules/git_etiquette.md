---
description: "Git etiquette, commit messages, and branching strategy."
globs: ["**/*"]
---

# Git Etiquette

## 1. Commit Messages

Follow the **Conventional Commits** specification:

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

**Example**:
`feat(controls): add PID gains for roll axis`

## 2. Branching Strategy

- **main**: Production-ready code.
- **dev**: Integration branch.
- **feat/name**: Feature branches (short-lived).
- **fix/name**: Bug fix branches.

## 3. Atomic Commits

- Commit often.
- Each commit should represent a logical unit of work.
- Do not squash everything into one "done" commit at the end of the week.
