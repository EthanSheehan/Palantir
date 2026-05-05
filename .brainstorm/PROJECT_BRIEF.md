# Grid-Sentinel — Project Brief

## Purpose
Grid-Sentinel is a decision-centric AI-assisted Command & Control (C2) system automating the F2T2EA kill chain (Find, Fix, Track, Target, Engage, Assess) using multi-agent AI orchestration, coordinated drone swarm operations, multi-sensor fusion, physics-based tactical simulation, and a professional React+Blueprint+Cesium 3D geospatial frontend.

## Stack
- **Backend**: Python 3, FastAPI, WebSocket (10Hz sim loop), LangGraph/LangChain agents
- **Frontend**: React + Vite + TypeScript, Blueprint dark theme, Zustand state, CesiumJS 3D globe
- **AI**: 9 LangGraph agents (ISR observer, strategy analyst, tactical planner, effectors, pattern analyzer, AI tasking manager, battlespace manager, synthesis query, performance auditor), multi-provider LLM fallback (Gemini → Anthropic → heuristic)
- **Dependencies**: numpy, opencv, structlog, pydantic, anthropic, google-genai, ollama

## Scale
- ~83 Python files (~22k LOC), ~10.8k TS/TSX files, 475 tests across 23 test files
- Key modules: api_main (1113 LOC), sim_engine (1553 LOC), 9 agents, video simulator (666 LOC)

## Architecture
Four subsystems: (1) FastAPI backend with dual WebSocket model (dashboard + simulator clients), (2) Simulation engine with verification state machine, sensor fusion, swarm coordination, battlespace assessment, ISR priority, intel feeds, (3) React frontend with 4 sidebar tabs, 6 map modes, 5 Cesium layer overlays, multi-layout drone camera PIP with 4 sensor modes, (4) AI agent layer with 9 LangGraph/LangChain agents communicating via Pydantic ontology.

## Active Work / Recent Progress
Just completed v1.0 Swarm Upgrade milestone (10 phases): sensor fusion, verification engine, battlespace assessment, enemy UAV simulation, ISR priority queue, intel feed system, swarm coordination, adaptive ISR, 6 map modes with Cesium layers, upgraded drone feeds with multi-layout PIP. Full v2.0 documentation overhaul done.

## Known Gaps
- Demo mode only (no real sensor/hardware integration)
- No persistent data storage (all in-memory simulation state)
- Limited test coverage for frontend (React components)
- No CI/CD pipeline
- LLM agents require API keys and have no offline fallback beyond basic heuristics
- Theater configs are YAML-based, no UI for theater editing
- No replay/recording system for after-action review
- No multi-user collaboration or role-based access
