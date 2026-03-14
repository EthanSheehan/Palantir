# Antigravity Project Template

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Overview

Welcome to an **Antigravity** project. This repository is a meticulously structured engineering workspace designed for high-performance Python and MATLAB development, specifically tailored for aerospace, control systems, and physics simulations.

It comes equipped with:

- **Unified Directory Structure**: Clean separation of code, config, data, and docs.
- **Embedded Agent Skills**: A full library of AI-assisted skills in `/.agent/skills`.
- **Strict Engineering Rules**: Automated enforcement of documentation rigor and commit etiquette.

## Directory Structure

```plaintext
/src
    /python        # Python source code
    /matlab        # MATLAB scripts and Simulink models
/configs           # Configuration files (.json, .yaml)
/data              # Simulation data (gitignored if large)
/docs              # System diagrams and documentation
/tex               # LaTeX files for papers/reports
/.agent            # AI Agent configuration (Rules, Skills, Workflows)
```

## Getting Started

### Prerequisites

- **Python**: 3.10+
- **MATLAB**: 2023b+ (Recommended)
- **GitKraken** (Optional, for advanced git viz)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-org/your-repo.git
    cd your-repo
    ```

2.  **Initialize Environment (Python):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Usage

### MATLAB Workflows

All MATLAB scripts are located in `/src/matlab`.

- Open VS Code and use the MATLAB extension to execute scripts directly.
- Ensure your path includes `/src/matlab` if calling functions from the root.

### Python Workflows

- Place core logic in `/src/python`.
- Use `pytest` for testing.

## Documentation Standards

This project adheres to strict **Scientific Rigor**.

- **Code**: Must be documented with clear docstrings explaining _why_, not just _what_.
- **Research**: Significant derivations must be documented in `/docs` using LaTeX or Markdown with MathJax.
- **No Hallucinations**: Documentation describes only what exists.

## Contributing

1.  Create a feature branch: `git checkout -b feat/new-control-law`
2.  Commit your changes: `git commit -m "feat: implement PID controller"`
3.  Push to the branch: `git push origin feat/new-control-law`
4.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
