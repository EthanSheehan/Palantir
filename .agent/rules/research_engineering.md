---
description: "Standards for Research Engineering. Scientific rigor and correctness."
globs: ["**/*"]
---

# Research Engineering Standards

## 1. Zero-Flair, All-Function

- Do not aim to be "chatty". Aim to be **correct**.
- Prioritize mathematical correctness over user comfort.

## 2. The Scientific Method

1.  **Hypothesis**: Define the engineering problem constraints (e.g., Latency < 10ms, Error < 1%).
2.  **Review**: Select the _optimal_ tool (Python vs MATLAB vs C++). Don't default to Python if C++ is needed for 1kHz control loops.
3.  **Implementation**: Write code that is strictly typed and documented.
4.  **Verification**: Prove correctness via tests or derivation.

## 3. Strict Implementation

- **No Placeholders**: Never write `// TODO: implement logic`. Write the logic.
- **Rigor**: If the physics requires a quaternion transformation, implement the full quaternion math. Do not approximate unless explicitly stated.
- **Error Handling**: Crash early. No silent failures in control systems.
- **Units**: Always document units in docstrings or comments.

## 4. Documentation

- Document the _physics_ sources (e.g., "Equation 3.4 from Anderson's Aerodynamics").
- Use LaTeX for equations in documentation.
- Maintain a separate `/docs/derivations.tex` (or .md) for heavy proofs.
