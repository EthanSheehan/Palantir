# Palantir C2 – Multi-Agent Decision-Centric C2 System

![Project Status](https://img.shields.io/badge/status-active-success.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Overview

Welcome to **Palantir C2**. This system is a high-fidelity recreation of the multi-domain Command and Control (C2) capabilities demonstrated in the Palantir "Maven Smart System" showcase. It focuses on a **"decision-centric"** orchestration model, utilizing specialized AI agents to automate the F2T2EA kill chain.

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

## Components

### 1. C2 Dashboard (Frontend)
A high-fidelity situational awareness display built with **MapLibre GL JS** and **Tailwind CSS**.
- **3D Terrain**: Real-time 3D elevation rendering.
- **Tactical HUD**: Integrated drone feeds with telemetry overlays.
- **Map Tools**:
    - `Coordinate Readout`: Precise Lat/Lon tracking on hover.
    - `Layer Switcher`: Toggle between Dark, Satellite, and OpenStreetMap styles.
    - `Distance Ruler`: Tactical tool for measuring distance between two points.

### 2. Drone Simulator & Vision
A Python-based simulation engine for multiple UAV feeds and mission scenarios.
- **Multi-Drone Feed**: Simulatenous relay of multiple sensor streams (Viper-01, Raven-02).
- **Mission Scenarios**: Pre-configured autonomous scanning patterns (Circular, Grid).
- **Computer Vision**: Integrated telemetry relay using the Palantir Tactical Ontology.

## Getting Started

### Prerequisites

- **Python**: 3.9+ (Environment already configured with `venv/`)
- **Web Browser**: Chrome/Safari/Firefox

### Easy Startup

To launch the entire system (Backend, Drone Simulator, and Dashboard) in one command:

```bash
./palantir.sh
```

The system will:
1. Start the **API Backend** (FastAPI) on port 8000.
2. Start the **C2 Dashboard** (HTTP Server) on port 3000.
3. Start the **Drone Simulator** (Viper-01 & Raven-02).
4. Automatically open your default browser to [http://localhost:3000](http://localhost:3000).

### Running Specific Scenarios

To toggle between different mission types:

```bash
./run_scenarios.sh
```

## Python Workflows

- **Backend**: Core logic in `src/python/api_main.py`.
- **Vision**: Simulator and processing logic in `src/python/vision/`.
- **Testing**: Use `pytest` for verification.

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
