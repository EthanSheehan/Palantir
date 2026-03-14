---
description: "Workflow for compiling LaTeX documents and checking for errors."
---

# LaTeX Compilation Workflow

## Trigger

Use this workflow when editing files in `/tex` or `/docs`.

## Steps

1.  **Chcek Structure**:
    - Ensure main file is clearly identified (e.g., `main.tex`).
    - Check for missing `.bib` files.

2.  **Compilation**:
    - If `pdflatex` available:
      `pdflatex -interaction=nonstopmode main.tex`
      `bibtex main`
      `pdflatex -interaction=nonstopmode main.tex`
      `pdflatex -interaction=nonstopmode main.tex`
3.  **Cleanup**:
    - Remove aux files (`*.aux`, `*.log`) using `git clean -Xdf` (be careful) or specific cleanup command.

4.  **Verification**:
    - Check log file for "undefined citation" or "overfull box" warnings.
