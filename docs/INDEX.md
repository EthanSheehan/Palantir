# Palantir C2 Documentation Index

**Last Updated: 2026-03-17**

Complete guide to Palantir documentation. Choose your path based on your role.

## Quick Navigation

### I'm a Developer
Start here to set up your environment and contribute code.

1. **[CONTRIBUTING.md](CONTRIBUTING.md)** — Setup, scripts, testing, code style, PR workflow
2. **[ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)** — Environment configuration reference
3. **[CODEMAPS.md](CODEMAPS.md)** — Architecture and module structure
4. **[README.md](../README.md)** — Quick start and overview
5. **[../CLAUDE.md](../CLAUDE.md)** — Agent workflow and AI architecture

**Quick Commands:**
```bash
# Setup
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env

# Run
./palantir.sh

# Test
./venv/bin/python3 -m pytest src/python/tests/
```

---

### I'm Setting Up Deployment
Operations and deployment guidance.

1. **[RUNBOOK.md](RUNBOOK.md)** — Deployment, health checks, monitoring, troubleshooting
2. **[ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)** — Production configuration
3. **[CODEMAPS.md](CODEMAPS.md)** — Architecture for scaling decisions
4. **[API_REFERENCE.md](API_REFERENCE.md)** — API endpoints and WebSocket

**Quick Deployment:**
```bash
# Local
./palantir.sh

# Docker
docker build -t palantir .
docker run -e OPENAI_API_KEY=sk-... -p 8000:8000 palantir

# Health check
curl http://localhost:8000/api/theaters
```

---

### I'm Building APIs / Frontend
Integration and API documentation.

1. **[API_REFERENCE.md](API_REFERENCE.md)** — REST endpoints, WebSocket messages, data models
2. **[CODEMAPS.md](CODEMAPS.md)** — Architecture and data flow
3. **[ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)** — Configuration for testing
4. **[CONTRIBUTING.md](CONTRIBUTING.md)** — Code style and testing

**Quick WebSocket Test:**
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws
# Send: {"client_type": "DASHBOARD"}
```

---

### I'm Reviewing Architecture
System design and scalability.

1. **[CODEMAPS.md](CODEMAPS.md)** — Complete architecture overview
2. **[API_REFERENCE.md](API_REFERENCE.md)** — API design and data models
3. **[RUNBOOK.md](RUNBOOK.md)** — Scaling and performance
4. **[../CLAUDE.md](../CLAUDE.md)** — Agent design and AI pipeline
5. **[PRD_v2_upgrade.md](PRD_v2_upgrade.md)** — Roadmap and design decisions

---

### I'm Troubleshooting Issues
Fast problem solving.

1. **[RUNBOOK.md](RUNBOOK.md)** — Common issues and fixes
2. **[ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)** — Configuration troubleshooting
3. **[CONTRIBUTING.md](CONTRIBUTING.md)** — Development troubleshooting
4. **[API_REFERENCE.md](API_REFERENCE.md)** — API error codes

---

## All Documentation Files

### Core Documentation (Generated from Code)
These are generated from source code and kept current automatically.

| File | Purpose | Audience | Updated |
|------|---------|----------|---------|
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Development setup, testing, code style, PR workflow | Developers | 2026-03-17 |
| **[RUNBOOK.md](RUNBOOK.md)** | Deployment, operations, monitoring, troubleshooting | DevOps/Ops | 2026-03-17 |
| **[CODEMAPS.md](CODEMAPS.md)** | Architecture, modules, data flow, configuration | Architects | 2026-03-17 |
| **[ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)** | Environment variable reference and examples | All | 2026-03-17 |
| **[API_REFERENCE.md](API_REFERENCE.md)** | REST endpoints, WebSocket, data models | Developers | 2026-03-17 |
| **[UPDATE_SUMMARY.md](UPDATE_SUMMARY.md)** | Documentation maintenance and freshness | Maintainers | 2026-03-17 |

### Primary Documentation (Maintained)
Keep these up-to-date manually when code changes.

| File | Purpose | Audience | Updated |
|------|---------|----------|---------|
| **[../README.md](../README.md)** | Quick start, overview, API summary | Everyone | 2026-03-17 |
| **[../CLAUDE.md](../CLAUDE.md)** | Agent workflow, development pipeline | Developers | 2026-03-17 |

### Reference Documentation (Strategic)
Kept for historical context and strategic planning.

| File | Purpose | Audience | Updated |
|------|---------|----------|---------|
| **[PRD.md](PRD.md)** | Product requirements (v1) | Stakeholders | 2026-03-16 |
| **[PRD_v2_upgrade.md](PRD_v2_upgrade.md)** | v2 upgrade roadmap | Stakeholders | 2026-03-17 |
| **[project_charter.md](project_charter.md)** | Project vision and scope | Stakeholders | 2026-03-16 |
| **[project_context.md](project_context.md)** | Historical context | Researchers | 2026-03-16 |
| **[upgrade_swarm_plan.md](upgrade_swarm_plan.md)** | Implementation roadmap | Project Leads | 2026-03-17 |

### Agent Documentation (System Prompts)
LLM system prompts for the AI agent layer.

| File | Agent | Updated |
|------|-------|---------|
| [prompts/01_isr_observer_agent.md](prompts/01_isr_observer_agent.md) | ISR Observer | 2026-03-14 |
| [prompts/02_strategy_analyst_agent.md](prompts/02_strategy_analyst_agent.md) | Strategy Analyst | 2026-03-14 |
| [prompts/03_ai_tasking_manager.md](prompts/03_ai_tasking_manager.md) | AI Tasking Manager | 2026-03-14 |
| [prompts/04_tactical_planner_agent.md](prompts/04_tactical_planner_agent.md) | Tactical Planner | 2026-03-14 |
| [prompts/05_effectors_agent.md](prompts/05_effectors_agent.md) | Effectors Agent | 2026-03-14 |
| [prompts/06_data_synthesizer_agent.md](prompts/06_data_synthesizer_agent.md) | Data Synthesizer | 2026-03-14 |
| [prompts/07_battlespace_management_agent.md](prompts/07_battlespace_management_agent.md) | Battlespace Manager | 2026-03-14 |
| [prompts/08_pattern_analyzer_agent.md](prompts/08_pattern_analyzer_agent.md) | Pattern Analyzer | 2026-03-14 |
| [prompts/08_performance_auditor_agent.md](prompts/08_performance_auditor_agent.md) | Performance Auditor | 2026-03-14 |
| [prompts/09_synthesis_query_agent.md](prompts/09_synthesis_query_agent.md) | Synthesis Query Agent | 2026-03-14 |
| [prompts/10_ontology_maintenance_agent.md](prompts/10_ontology_maintenance_agent.md) | Ontology Maintenance | 2026-03-15 |

---

## Documentation by Topic

### Getting Started
- [CONTRIBUTING.md](CONTRIBUTING.md) — Setup and first steps
- [README.md](../README.md) — High-level overview
- [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) — Configuration

### Development
- [CONTRIBUTING.md](CONTRIBUTING.md) — Code style, testing, workflow
- [../CLAUDE.md](../CLAUDE.md) — Agent workflow
- [CODEMAPS.md](CODEMAPS.md) — Architecture reference

### API Integration
- [API_REFERENCE.md](API_REFERENCE.md) — Endpoints and WebSocket
- [CODEMAPS.md](CODEMAPS.md) — Data models and flow
- [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) — Configuration

### Operations
- [RUNBOOK.md](RUNBOOK.md) — Deployment and troubleshooting
- [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) — Server config
- [CODEMAPS.md](CODEMAPS.md) — Architecture

### Testing
- [CONTRIBUTING.md](CONTRIBUTING.md) — Test requirements and TDD
- [API_REFERENCE.md](API_REFERENCE.md) — WebSocket testing
- [README.md](../README.md) — Quick test command

### Scaling
- [RUNBOOK.md](RUNBOOK.md) — Performance tuning and scaling
- [CODEMAPS.md](CODEMAPS.md) — Architecture limits
- [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) — Tuning parameters

---

## Content Organization

### By Audience

**👨‍💻 Developers**
- Start: [CONTRIBUTING.md](CONTRIBUTING.md)
- Reference: [API_REFERENCE.md](API_REFERENCE.md), [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)
- Deep dive: [CODEMAPS.md](CODEMAPS.md), [../CLAUDE.md](../CLAUDE.md)

**🚀 DevOps / Operations**
- Start: [RUNBOOK.md](RUNBOOK.md)
- Reference: [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)
- Architecture: [CODEMAPS.md](CODEMAPS.md)

**🏗️ Architects**
- Start: [CODEMAPS.md](CODEMAPS.md)
- Design: [API_REFERENCE.md](API_REFERENCE.md), [PRD_v2_upgrade.md](PRD_v2_upgrade.md)
- Scaling: [RUNBOOK.md](RUNBOOK.md)

**📋 Project Leads**
- Overview: [README.md](../README.md)
- Strategy: [PRD_v2_upgrade.md](PRD_v2_upgrade.md), [project_charter.md](project_charter.md)
- Progress: [upgrade_swarm_plan.md](upgrade_swarm_plan.md)

**🔍 Maintainers**
- Maintenance: [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md)
- Content: [INDEX.md](INDEX.md) (this file)
- Versioning: Check git log for changes

### By Task

| Task | Start Here | Then Read |
|------|-----------|-----------|
| Set up development environment | [CONTRIBUTING.md](CONTRIBUTING.md) | [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) |
| Write new feature | [CONTRIBUTING.md](CONTRIBUTING.md) | [CODEMAPS.md](CODEMAPS.md) |
| Integrate with API | [API_REFERENCE.md](API_REFERENCE.md) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Deploy to production | [RUNBOOK.md](RUNBOOK.md) | [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md) |
| Troubleshoot issue | [RUNBOOK.md](RUNBOOK.md) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Understand architecture | [CODEMAPS.md](CODEMAPS.md) | [../CLAUDE.md](../CLAUDE.md) |
| Scale the system | [RUNBOOK.md](RUNBOOK.md) | [CODEMAPS.md](CODEMAPS.md) |
| Review code | [CONTRIBUTING.md](CONTRIBUTING.md) | [../CLAUDE.md](../CLAUDE.md) |

---

## Search Tips

### Looking for environment variables?
→ [ENVIRONMENT_VARS.md](ENVIRONMENT_VARS.md)

### Looking for how to run tests?
→ [CONTRIBUTING.md](CONTRIBUTING.md) — Testing section

### Looking for API endpoints?
→ [API_REFERENCE.md](API_REFERENCE.md)

### Looking for deployment instructions?
→ [RUNBOOK.md](RUNBOOK.md) — Deployment section

### Looking for how to add new feature?
→ [CONTRIBUTING.md](CONTRIBUTING.md) — Contributing workflow

### Looking for system architecture?
→ [CODEMAPS.md](CODEMAPS.md)

### Looking for troubleshooting help?
→ [RUNBOOK.md](RUNBOOK.md) — Common issues section

### Looking for agent information?
→ [../CLAUDE.md](../CLAUDE.md) or [CODEMAPS.md](CODEMAPS.md)

### Looking for WebSocket messages?
→ [API_REFERENCE.md](API_REFERENCE.md) — WebSocket API section

### Looking for code style guide?
→ [CONTRIBUTING.md](CONTRIBUTING.md) — Code style section

---

## Documentation Freshness

All documentation is generated from source code to ensure accuracy. Timestamps indicate when each document was last updated from the actual codebase.

**Last Batch Update: 2026-03-17**

Files generated from:
- `palantir.sh` — Launch scripts and commands
- `requirements.txt` — Python dependencies
- `.env.example` — Environment configuration
- `package.json` — npm scripts
- `src/python/` — Python source code
- `src/frontend/` — Frontend source code
- Recent git commits — Change summary

To keep documentation current, update relevant files when making code changes (see [UPDATE_SUMMARY.md](UPDATE_SUMMARY.md) for details).

---

## Feedback & Questions

**Have a question?** Check the relevant documentation above.

**Found an error?** Please:
1. Verify against source code (it should match)
2. Open a GitHub issue
3. Consider submitting a documentation PR

**Want to contribute documentation?** See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Related Resources

- **GitHub Repository**: https://github.com/EthanSheehan/Palantir
- **Interactive API Docs**: `http://localhost:8000/docs` (when running)
- **Project Vision**: [project_charter.md](project_charter.md)
- **Upgrade Roadmap**: [PRD_v2_upgrade.md](PRD_v2_upgrade.md)

---

**Navigation Tip**: Bookmark this page for quick access to all Palantir documentation.
