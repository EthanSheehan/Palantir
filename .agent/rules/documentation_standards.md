---
description: "Standards for documentation: Code docstrings and Research documentation."
globs: ["**/*.md", "**/*.py", "**/*.m"]
---

# Documentation Standards

## 1. Zero-Hallucination Policy

- **Never** document features that do not exist "yet".
- **Never** invent API signatures that are not implemented.
- If a feature is planned, mark it explicitly as `[PLANNED]`.

## 2. Code Documentation (Docstrings)

- **Python**: Use Google-style docstrings.
  ```python
  def calculate_thrust(isp: float, mdot: float) -> float:
      """
      Calculates rocket thrust based on specific impulse and mass flow rate.

      Args:
          isp: Specific impulse in seconds.
          mdot: Mass flow rate in kg/s.

      Returns:
          Thrust in Newtons.
      """
  ```
- **MATLAB**: Use standard function headers.
  ```matlab
  function F = calculate_thrust(Isp, mdot)
  % CALCULATE_THRUST Calculates rocket thrust.
  %   F = CALCULATE_THRUST(Isp, mdot) returns the thrust in Newtons.
  %
  %   Inputs:
  %       Isp - Specific impulse (s)
  %       mdot - Mass flow rate (kg/s)
  ```

## 3. Research Documentation

- Significant engineering decisions, derivations, and physics verification must be documented in `/docs`.
- Use **LaTeX** for heavy math.
- Use **Markdown** for architectural decisions (`/docs/architecture.md`).
- **Changelog**: Maintain a `CHANGELOG.md` in the root (Keep a Changelog format).

## 4. Updates

- **Rule**: If you change the code, you **MUST** update the documentation in the same turn.
- Code and Docs must never diverge.
