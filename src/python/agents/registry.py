"""
agents/registry.py
==================
Plug-in agent registry. Lets the AIPChatPanel route slash-commands to any
registered agent without the WebSocket handler caring which one.

Each registered agent is a coroutine `(query: str, ctx) -> tuple[str, dict]`
returning (display_text, structured_meta). Heuristic stand-ins are provided so
the chat panel works the moment the registry is imported, even before the LLM
chain is wired into every agent.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Tuple

logger = logging.getLogger(__name__)

AgentHandler = Callable[[str, Any], Awaitable[Tuple[str, dict]]]

_REGISTRY: dict[str, AgentHandler] = {}


def register_agent(key: str):
    """Decorator: `@register_agent("synthesis_query_agent")`."""
    def _wrap(fn: AgentHandler) -> AgentHandler:
        _REGISTRY[key] = fn
        return fn
    return _wrap


def get_agent(key: str) -> AgentHandler:
    """Look up an agent handler. Falls back to synthesis_query_agent if unknown."""
    if key in _REGISTRY:
        return _REGISTRY[key]
    return _REGISTRY.get("synthesis_query_agent", _heuristic_unknown)


# ---------------------------------------------------------------------------
# Heuristic baseline handlers — replaced by real LangGraph agents over time
# ---------------------------------------------------------------------------


async def _heuristic_unknown(query: str, ctx: Any) -> tuple[str, dict]:
    return (f"[heuristic] unknown agent. Query: {query}", {})


@register_agent("isr_observer")
async def _isr_observer(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    if sim is None:
        return ("[heuristic] sim unavailable.", {})
    n_targets = len(sim.targets) if hasattr(sim, "targets") else 0
    n_uavs = len(sim.uavs) if hasattr(sim, "uavs") else 0
    return (
        f"ISR Observer: tracking {n_targets} target(s) across {n_uavs} UAV(s). "
        f"Sensor fusion active. Heuristic only — full LangGraph agent not connected.",
        {"target_count": n_targets, "uav_count": n_uavs},
    )


@register_agent("strategy_analyst")
async def _strategy_analyst(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    nominated = 0
    if sim is not None and hasattr(sim, "targets"):
        nominated = sum(1 for t in sim.targets.values() if (t.state or "").upper() == "NOMINATED")
    return (
        f"Strategy: {nominated} target(s) currently nominated. "
        f"ROE evaluation per-target — see Workbench NOMINATED column for review.",
        {"nominated_count": nominated},
    )


@register_agent("tactical_planner")
async def _tactical_planner(query: str, ctx: Any) -> tuple[str, dict]:
    return (
        "Tactical Planner: COA generation requires a selected target. "
        "Use the Asset Tasking drawer (right panel) for sensor recommendations, "
        "or specify `/tactics for target #NNNN` to scope.",
        {},
    )


@register_agent("effectors_agent")
async def _effectors_agent(query: str, ctx: Any) -> tuple[str, dict]:
    return (
        "Effectors: AFATDS/JREAP/JADOCS/AMPS stubs available. "
        "Approved nominations dispatch automatically when AUTONOMOUS or after operator authorisation.",
        {"effectors": ["AFATDS", "JREAP", "JADOCS", "AMPS"]},
    )


@register_agent("pattern_analyzer")
async def _pattern_analyzer(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    if sim is None or not hasattr(sim, "targets"):
        return ("[heuristic] sim unavailable.", {})
    by_type: dict[str, int] = {}
    for t in sim.targets.values():
        by_type[t.type] = by_type.get(t.type, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    return (
        f"Pattern: {summary or 'no targets yet'}. Activity windows derived from "
        f"position-history deque per target.",
        {"by_type": by_type},
    )


@register_agent("ai_tasking_manager")
async def _tasking(query: str, ctx: Any) -> tuple[str, dict]:
    return (
        "Tasking Manager: select a target, then open the Asset Tasking drawer "
        "(right panel) for ranked recommendations with why-traces.",
        {},
    )


@register_agent("battlespace_manager")
async def _battlespace(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    if sim is None:
        return ("[heuristic] sim unavailable.", {})
    n_uavs = len(sim.uavs) if hasattr(sim, "uavs") else 0
    n_targets = len(sim.targets) if hasattr(sim, "targets") else 0
    return (
        f"Battlespace: {n_uavs} friendly assets, {n_targets} contacts. "
        f"Threat clusters / coverage gaps / movement corridors computed by "
        f"battlespace_assessment.py — see ASSESS sidebar tab for live overlay.",
        {"friendly_count": n_uavs, "contact_count": n_targets},
    )


@register_agent("synthesis_query_agent")
async def _synthesis(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    if sim is None:
        return ("[heuristic] sim unavailable.", {})
    by_state: dict[str, int] = {}
    for t in sim.targets.values():
        by_state[t.state or "UNKNOWN"] = by_state.get(t.state or "UNKNOWN", 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_state.items()))
    n_uavs = len(sim.uavs)
    return (
        f"SITREP: {n_uavs} UAVs in theater; targets by state: {summary or 'none'}. "
        f"Query: '{query}'.",
        {"by_state": by_state, "uav_count": n_uavs},
    )


@register_agent("performance_auditor")
async def _auditor(query: str, ctx: Any) -> tuple[str, dict]:
    return (
        "Performance Auditor: SLA dashboard exposes per-stage F2T2EA latency. "
        "Open it via the SLA rail button or press 'S'.",
        {},
    )


def list_agents() -> list[str]:
    """Return a sorted list of registered agent keys."""
    return sorted(_REGISTRY.keys())
