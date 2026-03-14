---
description: "Python development best practices for engineering."
globs: ["**/*.py"]
---

# Python Best Practices

## 1. Type Safety & Validation

- **Strict Typing**: Always use Type Hints for function arguments and return values. `mypy` or `pyright` compliance is expected.
- **Runtime Validation**: Use `pydantic` for data models and configuration.
  ```python
  from pydantic import BaseModel
  class Config(BaseModel):
      thrust_target: float
  ```

## 2. NumPy Vectorization

- **No Loops**: Avoid `for` loops for math. Use `numpy` vectorization.
- **Broadcasting**: Leverage numpy broadcasting rules for dimensions.
- **Bad**:
  ```python
  res = []
  for x in data: res.append(x**2)
  ```
- **Good**:
  ```python
  res = data**2
  ```

## 3. Project Structure

- **/src/python**: Root of the package.
- **Tests**: Mirror the source structure in `/tests`.
- **Scripts**: Entry points in `/src/python/scripts` or root `main.py`.
- **Imports**: Use absolute imports within the package (e.g., `from src.python.utils import math`).

## 4. Dependencies

- Use a virtual environment (`venv`).
- Keep `requirements.txt` minimal (production deps).
- Use `requirements-dev.txt` for tools (ruff, mypy, pytest).
- Prefer `scipy`, `numpy`, `matplotlib` for engineering.

## 5. Testing

- Use `pytest` for all testing.
- **Fixtures**: Use `conftest.py` for shared verification setups.
- **Coverage**: Aim for high coverage on core algorithmic logic.
