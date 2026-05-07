"""
agents/registry.py
==================
Plug-in agent registry. Lets the AIPChatPanel route slash-commands to any
registered agent without the WebSocket handler caring which one.

Each registered agent is a coroutine `(query: str, ctx) -> tuple[str, dict]`
returning (display_text, structured_meta). Each handler now tries the live
LLMAdapter on `ctx.llm_adapter` first and falls back to a deterministic
heuristic if the adapter is unavailable / fails / returns empty content. The
heuristic path is what existing tests pin against, so they stay green when no
LLM keys are configured.
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
# Shared LLM bridge — used by every chat-style handler below.
# ---------------------------------------------------------------------------


async def _ask_llm(
    ctx: Any,
    system_prompt: str,
    user_prompt: str,
    *,
    model_hint: str = "default",
    max_tokens: int = 700,
) -> tuple[str, dict] | None:
    """Run a single completion against ctx.llm_adapter, return (text, meta)
    or None if no LLM is reachable / call failed / response was empty.

    The operator can override the agent's preferred tier via
    `ctx._operator_model_hint` ("auto" defers to the agent's default).
    """
    adapter = getattr(ctx, "llm_adapter", None)
    if adapter is None or not getattr(adapter, "is_available", lambda: False)():
        return None
    operator_hint = getattr(ctx, "_operator_model_hint", "auto")
    if operator_hint and operator_hint != "auto":
        model_hint = operator_hint
    try:
        response = await adapter.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model_hint=model_hint,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_llm_call_failed", extra={"error": str(exc)})
        return None
    text = (response.content or "").strip()
    if not text:
        return None
    return text, {
        "provider": response.provider,
        "model": response.model,
        "tokens_used": response.tokens_used,
        "model_hint": model_hint,
    }


def _sim_summary(sim: Any) -> dict[str, Any]:
    """Compact JSON-serialisable view of the live SimulationModel for prompts."""
    if sim is None:
        return {}
    try:
        targets = list(getattr(sim, "targets", {}).values())
        uavs = list(getattr(sim, "uavs", {}).values())
    except Exception:  # noqa: BLE001
        return {}
    by_state: dict[str, int] = {}
    by_type: dict[str, int] = {}
    nominated: list[dict] = []
    for t in targets:
        by_state[(t.state or "UNKNOWN")] = by_state.get(t.state or "UNKNOWN", 0) + 1
        by_type[t.type] = by_type.get(t.type, 0) + 1
        if (t.state or "").upper() == "NOMINATED":
            nominated.append({
                "id": t.id,
                "type": t.type,
                "fused_confidence": round(getattr(t, "fused_confidence", 0.0), 3),
                "sensor_count": getattr(t, "sensor_count", 0),
            })
    return {
        "uav_count": len(uavs),
        "target_count": len(targets),
        "targets_by_state": by_state,
        "targets_by_type": by_type,
        "nominated": nominated[:8],
        "theater": getattr(sim, "theater_name", "unknown"),
    }


# ---------------------------------------------------------------------------
# Heuristic baselines — fallback when no LLM is available
# ---------------------------------------------------------------------------


async def _heuristic_unknown(query: str, ctx: Any) -> tuple[str, dict]:
    return (f"[heuristic] unknown agent. Query: {query}", {})


# ---------------------------------------------------------------------------
# Per-agent handlers — each tries LLM first, falls back to heuristic
# ---------------------------------------------------------------------------


_ISR_SYSTEM = (
    "You are the ISR Observer for the Grid-Sentinel C2 system. Your job is "
    "cross-INT track correlation and concise reporting on sensor fusion "
    "status. Reply in <=4 short sentences, factual, plain text. Cite "
    "specific target IDs when relevant."
)


@register_agent("isr_observer")
async def _isr_observer(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    if sim is None:
        return ("[heuristic] sim unavailable.", {})
    summary = _sim_summary(sim)
    n_targets = summary.get("target_count", 0)
    n_uavs = summary.get("uav_count", 0)

    user_prompt = (
        f"Operator query: {query!r}\n"
        f"Live sim snapshot: {summary}\n"
        "Report current ISR posture: how many targets, sensor coverage gaps "
        "(if any), and which states dominate."
    )
    llm = await _ask_llm(ctx, _ISR_SYSTEM, user_prompt, model_hint="fast", max_tokens=400)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "target_count": n_targets, "uav_count": n_uavs}

    return (
        f"ISR Observer: tracking {n_targets} target(s) across {n_uavs} UAV(s). "
        f"Sensor fusion active. Heuristic only — full LangGraph agent not connected.",
        {"target_count": n_targets, "uav_count": n_uavs},
    )


_STRATEGY_SYSTEM = (
    "You are the Strategy Analyst. Evaluate ROE compliance and target "
    "priority for the operator. Reply in <=5 short sentences. Call out "
    "specific NOMINATED targets if any, by ID."
)


@register_agent("strategy_analyst")
async def _strategy_analyst(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    summary = _sim_summary(sim) if sim is not None else {}
    nominated = summary.get("nominated", []) if summary else []

    if sim is not None:
        roe = getattr(ctx, "roe_engine", None)
        rule_count = len(roe.rules) if roe is not None and hasattr(roe, "rules") else 0
        user_prompt = (
            f"Operator query: {query!r}\n"
            f"Sim snapshot: {summary}\n"
            f"ROE rules loaded: {rule_count}\n"
            "Evaluate priority + ROE posture. Recommend whether the operator "
            "should approve any NOMINATED targets and why."
        )
        llm = await _ask_llm(ctx, _STRATEGY_SYSTEM, user_prompt, model_hint="default", max_tokens=500)
        if llm is not None:
            text, meta = llm
            return text, {**meta, "nominated_count": len(nominated)}

    return (
        f"Strategy: {len(nominated)} target(s) currently nominated. "
        f"ROE evaluation per-target — see Workbench NOMINATED column for review.",
        {"nominated_count": len(nominated)},
    )


_TACTICS_SYSTEM = (
    "You are the Tactical Planner. Generate one or two concise Course of "
    "Action options for the operator's situation. Each COA <=3 sentences "
    "with effector + Pk estimate."
)


@register_agent("tactical_planner")
async def _tactical_planner(query: str, ctx: Any) -> tuple[str, dict]:
    sim = getattr(ctx, "sim", None)
    summary = _sim_summary(sim) if sim is not None else {}

    user_prompt = (
        f"Operator query: {query!r}\n"
        f"Sim snapshot: {summary}\n"
        "Propose 1-2 COAs. Briefly justify each (effector, Pk, tradeoffs)."
    )
    llm = await _ask_llm(ctx, _TACTICS_SYSTEM, user_prompt, model_hint="reasoning", max_tokens=600)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "snapshot": summary}

    return (
        "Tactical Planner: COA generation requires a selected target. "
        "Use the Asset Tasking drawer (right panel) for sensor recommendations, "
        "or specify `/tactics for target #NNNN` to scope.",
        {},
    )


@register_agent("effectors_agent")
async def _effectors_agent(query: str, ctx: Any) -> tuple[str, dict]:
    system = (
        "You are the Effectors Agent. Report the status of the effector "
        "pipeline (AFATDS / JREAP / JADOCS / AMPS) in <=3 sentences."
    )
    sim = getattr(ctx, "sim", None)
    summary = _sim_summary(sim) if sim is not None else {}
    user_prompt = (
        f"Operator query: {query!r}\n"
        f"Sim snapshot: {summary}\n"
        "Summarise effector readiness; mention each channel by name."
    )
    llm = await _ask_llm(ctx, system, user_prompt, model_hint="fast", max_tokens=300)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "effectors": ["AFATDS", "JREAP", "JADOCS", "AMPS"]}

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
    summary = _sim_summary(sim)
    by_type = summary.get("targets_by_type", {})

    system = (
        "You are the Pattern Analyzer. Identify any noteworthy target-type "
        "patterns (clusters, repeats, RF-emitter convoys). Reply in <=4 "
        "sentences."
    )
    user_prompt = (
        f"Operator query: {query!r}\n"
        f"Targets-by-type: {by_type}\n"
        f"Targets-by-state: {summary.get('targets_by_state', {})}\n"
        "Call out anything tactically significant."
    )
    llm = await _ask_llm(ctx, system, user_prompt, model_hint="fast", max_tokens=300)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "by_type": by_type}

    summary_text = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    return (
        f"Pattern: {summary_text or 'no targets yet'}. Activity windows derived from "
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
    summary = _sim_summary(sim)
    n_uavs = summary.get("uav_count", 0)
    n_targets = summary.get("target_count", 0)

    system = (
        "You are the Battlespace Manager. Describe threat clusters, coverage "
        "gaps, or movement corridors at a high level. <=4 sentences."
    )
    user_prompt = f"Operator query: {query!r}\nSim snapshot: {summary}"
    llm = await _ask_llm(ctx, system, user_prompt, model_hint="default", max_tokens=400)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "friendly_count": n_uavs, "contact_count": n_targets}

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
    summary = _sim_summary(sim)
    by_state = summary.get("targets_by_state", {})
    n_uavs = summary.get("uav_count", 0)

    system = (
        "You are the Synthesis & Query Agent for Grid-Sentinel. Produce a "
        "concise SITREP in plain prose (<=6 sentences). Cite numbers and "
        "specific target IDs. Do not invent data."
    )
    user_prompt = (
        f"Commander query: {query!r}\n"
        f"Sim snapshot: {summary}\n"
        "Synthesize the current operational picture."
    )
    llm = await _ask_llm(ctx, system, user_prompt, model_hint="fast", max_tokens=600)
    if llm is not None:
        text, meta = llm
        return text, {**meta, "by_state": by_state, "uav_count": n_uavs}

    summary_text = ", ".join(f"{k}={v}" for k, v in sorted(by_state.items()))
    return (
        f"SITREP: {n_uavs} UAVs in theater; targets by state: {summary_text or 'none'}. "
        f"Query: '{query}'.",
        {"by_state": by_state, "uav_count": n_uavs},
    )


@register_agent("decision_replay")
async def _decision_replay(query: str, ctx: Any) -> tuple[str, dict]:
    """Re-run a past engagement against effectors_agent with a deterministic
    RNG seed. Beyond-Maven differentiator: postmortem replay for AAR /
    JAGINT-style review. Maven is forward-only; we let the operator
    re-litigate any past kill-chain decision.

    Query is expected to contain a target_id digit. Pulls the most recent
    engagement_executed record for that target out of audit_log, reconstructs
    a minimal CourseOfAction + target_data, and runs the engagement at a
    fixed seed (default 42) so the replay is reproducible.
    """
    import re
    import random as _random
    try:
        from audit_log import audit_log as _audit_log
        from agents.effectors_agent import EffectorsAgent
        from schemas.ontology import CourseOfAction, Effector
    except Exception as exc:  # noqa: BLE001
        return (f"[heuristic] decision_replay unavailable: {exc}", {})

    m = re.search(r"\b(\d{1,5})\b", query or "")
    if not m:
        return (
            "Decision replay: include a target ID in the query "
            "(e.g. `/replay 0042` or `/replay target 17`).",
            {},
        )
    target_id = int(m.group(1))

    matches = _audit_log.query(action_type="engagement_executed", target_id=target_id)
    if not matches:
        return (
            f"Decision replay: no engagement_executed record for target #{target_id:04d}.",
            {"target_id": target_id, "found": False},
        )
    original = matches[-1]
    original_details = original.get("details", {})

    seed = 42
    rng = _random.Random(seed)
    coa = CourseOfAction(
        coa_id=str(original_details.get("coa_id", "replay-coa")),
        coa_type="replay",
        target_track_id=str(target_id),
        effector=Effector(
            effector_id="replay",
            name=str(original_details.get("effector", "UNKNOWN")),
            effector_type="Kinetic",
            status="AVAILABLE",
        ),
        time_to_target_minutes=1.0,
        probability_of_kill=float(original_details.get("modified_pk", 0.5)),
        munition_efficiency_cost=1.0,
        rationalization="Decision replay (postmortem AAR)",
    )
    target_data = {
        "id": target_id,
        "type": "UNKNOWN",
        "state": "VERIFIED",
        "lat": 0.0,
        "lon": 0.0,
    }
    agent = EffectorsAgent(rng=rng)
    try:
        result = await agent.execute_engagement(coa, target_data)
    except Exception as exc:  # noqa: BLE001
        return (
            f"Decision replay: failed to re-run engagement: {exc}",
            {"target_id": target_id, "found": True, "error": str(exc)},
        )

    text = (
        f"Decision replay #{target_id:04d}\n"
        f"  original: {original_details.get('damage_level', '?')} via {original_details.get('effector', '?')} "
        f"(Pk={original_details.get('modified_pk', '?')})\n"
        f"  replay   (seed={seed}): {result.damage_level} via {result.effector_used} "
        f"(hit={result.hit}, BDA conf={result.bda_confidence:.2f})"
    )
    return text, {
        "target_id": target_id,
        "found": True,
        "seed": seed,
        "original_damage_level": original_details.get("damage_level"),
        "replay_damage_level": result.damage_level,
        "replay_hit": result.hit,
        "match": original_details.get("damage_level") == result.damage_level,
    }


@register_agent("self_critic")
async def _self_critic(query: str, ctx: Any) -> tuple[str, dict]:
    """Reflective AI — reviews recent audit_log records and surfaces findings.

    Beyond-Maven differentiator: Maven is forward-only — it tasks, executes,
    moves on. We add a second-order agent that watches the system's own
    behaviour for patterns (repeated COA churn, slow nominations, recurring
    rejections on the same target) and feeds them back as INTEL events.
    """
    try:
        from audit_log import audit_log as _audit_log
    except Exception:  # noqa: BLE001
        return ("[heuristic] audit_log unavailable.", {})

    records = _audit_log.to_json()[-200:]  # last 200 audit events
    if not records:
        return ("Self-critic: no audit history yet — nothing to review.", {"finding_count": 0})

    # Heuristic findings (always available):
    by_target: dict[int, list[dict]] = {}
    coa_counts: dict[int, int] = {}
    rejections: dict[int, int] = {}
    for r in records:
        tid = r.get("target_id")
        if tid is None:
            continue
        by_target.setdefault(tid, []).append(r)
        if r.get("action_type") == "coa_authorized":
            coa_counts[tid] = coa_counts.get(tid, 0) + 1
        if r.get("action_type") == "nomination_rejected":
            rejections[tid] = rejections.get(tid, 0) + 1

    findings: list[str] = []
    for tid, count in coa_counts.items():
        if count >= 3:
            findings.append(f"Target #{tid:04d}: {count} COA authorisations in window — consider escalation.")
    for tid, count in rejections.items():
        if count >= 2:
            findings.append(f"Target #{tid:04d}: {count} repeated nomination rejections — track may be invalid.")

    text = (
        "Self-critic findings:\n" + "\n".join(f"  • {f}" for f in findings)
        if findings
        else f"Self-critic: reviewed {len(records)} audit events, no patterns of concern."
    )
    meta = {"finding_count": len(findings), "records_reviewed": len(records)}

    # If LLM is available, ask it to interpret the findings
    if findings:
        system = (
            "You are a self-critic AI for an autonomous C2 system. Given a "
            "list of pattern findings from the audit log, write 2-4 plain "
            "English sentences highlighting the most important. Cite "
            "specific target IDs."
        )
        user = "Findings:\n" + "\n".join(findings) + f"\n\nOperator query: {query!r}"
        llm = await _ask_llm(ctx, system, user, model_hint="reasoning", max_tokens=400)
        if llm is not None:
            t, m = llm
            return t, {**m, **meta}

    return text, meta


@register_agent("performance_auditor")
async def _auditor(query: str, ctx: Any) -> tuple[str, dict]:
    system = (
        "You are the Performance Auditor. Comment briefly on system health, "
        "agent activity, and any latency hotspots. <=3 sentences."
    )
    sim = getattr(ctx, "sim", None)
    summary = _sim_summary(sim) if sim is not None else {}
    user_prompt = f"Operator query: {query!r}\nSnapshot: {summary}"
    llm = await _ask_llm(ctx, system, user_prompt, model_hint="fast", max_tokens=250)
    if llm is not None:
        return llm

    return (
        "Performance Auditor: SLA dashboard exposes per-stage F2T2EA latency. "
        "Open it via the SLA rail button or press 'S'.",
        {},
    )


def list_agents() -> list[str]:
    """Return a sorted list of registered agent keys."""
    return sorted(_REGISTRY.keys())
