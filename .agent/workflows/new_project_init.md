---
description: "Workflow to initialize a new project using this template."
---

# New Project Initialization

## Trigger

Use this workflow immediately after cloning this template for a new specific project (e.g., `Project-X`).

## Steps

1.  **Context Gathering**:
    - **Ask the User**: "What is the specific goal of this project?" (e.g., Rocket Landing, Drone Control).
    - **Ask the User**: "What are the key Physics constraints?" (e.g., Rigid body, Fluid dynamics).
    - **Ask the User**: "confirm the Project Name".
    - Store these answers in `task.md` or a new `docs/project_context.md`.

2.  **Rename & Configure**:
    - Update `README.md` title and description.
    - Update `task.md` with the specific goals.

3.  **Environment Setup**:
    - **Python**:
      `python3 -m venv venv`
      `source venv/bin/activate`
      `pip install -r requirements.txt` (if exists)
    - **MATLAB**:
      Check for MATLAB version and path.

4.  **Project Charter**:
    - Create `docs/project_charter.md` containing:
      - **Goal**: [User Answer]
      - **Physics**: [User Answer]
      - **Success Criteria**: Define what "done" looks like.

5.  **Git Initialization**:
    - `git init` (if not already)
    - `git remote remove origin` (if cloned from template)
    - `git add .`
    - `git commit -m "chore: project init"`
    - **Ask User**: "Do you want to push to a new GitHub repo?"

6.  **Environment**:
    - Setup Python virtual env.
    - Setup MATLAB path.

7.  **Plan**:
    - active the `planning-with-files` skill to create the initial `task.md`.

8.  **Commit**:
    - Commit to the repo
