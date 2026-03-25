"""
forward_sim.py
==============
Decision-oriented digital twin — project simulation state forward for each
COA candidate, score outcomes, and rank alternatives before committing.

Public API:
  clone_simulation(model)               → SimulationModel (deepcopy)
  score_state(model)                    → float
  project_forward(model, ticks=50)      → float
  evaluate_coas(model, coas, ticks=50)  → list[dict]  (async)
"""

from __future__ import annotations

import asyncio
import copy
import sys
from typing import Any

import structlog

logger = structlog.get_logger()

# The SimulationModel graph (grid neighbor lists) can exceed default recursion depth.
_DEEPCOPY_RECURSION_LIMIT = 10000

# Weights for the scoring function
_WEIGHT_VERIFIED = 3.0  # each verified target adds this
_WEIGHT_DETECTED = 0.5  # partial credit for detected/classified
_WEIGHT_DESTROYED = -5.0  # destroyed targets penalise the score
_WEIGHT_FUEL = 0.2  # per UAV fuel-hours available
_FUEL_FULL_HOURS = 6.0  # reference "full" fuel level for normalisation
_ACTIVE_THREAT_STATES = {"DETECTED", "CLASSIFIED", "VERIFIED", "TRACKED", "LOCKED", "NOMINATED"}


def clone_simulation(model: Any) -> Any:
    """
    Return a deep copy of *model* so projections never mutate the original.

    The simulation grid contains circular neighbor references that require a
    higher recursion limit than Python's default 1000.
    """
    old_limit = sys.getrecursionlimit()
    try:
        if old_limit < _DEEPCOPY_RECURSION_LIMIT:
            sys.setrecursionlimit(_DEEPCOPY_RECURSION_LIMIT)
        return copy.deepcopy(model)
    finally:
        sys.setrecursionlimit(old_limit)


def score_state(model: Any) -> float:
    """
    Score a simulation state snapshot.

    Higher is better:
      + verified / tracked targets (high information value)
      + partial credit for detected / classified targets
      + healthy drone fleet (fuel)
      - destroyed or escaped targets (bad outcomes)
      - active high-confidence threats remaining (unresolved)
    """
    total = 0.0

    for target in model.targets.values():
        state = getattr(target, "state", "UNDETECTED")
        if state == "VERIFIED":
            total += _WEIGHT_VERIFIED
        elif state in ("CLASSIFIED", "TRACKED", "LOCKED", "NOMINATED"):
            total += _WEIGHT_VERIFIED * 0.6
        elif state == "DETECTED":
            total += _WEIGHT_DETECTED
        elif state in ("DESTROYED", "ESCAPED"):
            total += _WEIGHT_DESTROYED

    for uav in model.uavs.values():
        fuel = getattr(uav, "fuel_hours", _FUEL_FULL_HOURS)
        fuel_ratio = min(1.0, fuel / _FUEL_FULL_HOURS)
        total += _WEIGHT_FUEL * fuel_ratio

    return max(0.0, total)


def _summarise_state(model: Any) -> dict:
    """Build a compact summary dict from a projected model state."""
    verified = sum(1 for t in model.targets.values() if getattr(t, "state", "") == "VERIFIED")
    active_threats = sum(1 for t in model.targets.values() if getattr(t, "state", "") in _ACTIVE_THREAT_STATES)
    total_fuel = sum(getattr(u, "fuel_hours", _FUEL_FULL_HOURS) for u in model.uavs.values())
    num_uavs = len(model.uavs)
    drone_health = round(total_fuel / (num_uavs * _FUEL_FULL_HOURS), 3) if num_uavs else 0.0

    return {
        "verified_targets": verified,
        "active_threats": active_threats,
        "drone_health": drone_health,
    }


def project_forward(model: Any, ticks: int = 50) -> float:
    """
    Clone *model*, run *ticks* simulation ticks, and return the final score.

    The original model is never modified.
    """
    cloned = clone_simulation(model)
    for _ in range(ticks):
        try:
            cloned.tick()
        except Exception as exc:
            logger.warning("project_forward_tick_error", error=str(exc))
            break
    return score_state(cloned)


async def evaluate_coas(
    model: Any,
    coas: list[dict],
    ticks: int = 50,
) -> list[dict]:
    """
    Evaluate each COA by projecting the simulation forward *ticks* steps.

    Each COA is evaluated in a thread pool (asyncio.to_thread) so multiple
    candidates run in parallel without blocking the event loop.

    Returns the COA list sorted by ``projected_score`` descending, with two
    new fields added to each entry:
      - ``projected_score`` (float)
      - ``projected_state_summary`` (dict: verified_targets, active_threats, drone_health)
    """
    if not coas:
        return []

    async def _evaluate_single(coa: dict) -> dict:
        score = await asyncio.to_thread(project_forward, model, ticks)
        # Build state summary from a fresh projection for summary data
        summary = await asyncio.to_thread(_project_and_summarise, model, ticks)
        result = dict(coa)
        result["projected_score"] = score
        result["projected_state_summary"] = summary
        return result

    evaluated = await asyncio.gather(*[_evaluate_single(coa) for coa in coas])
    return sorted(evaluated, key=lambda c: c["projected_score"], reverse=True)


def _project_and_summarise(model: Any, ticks: int) -> dict:
    """Clone model, tick forward, return state summary."""
    cloned = clone_simulation(model)
    for _ in range(ticks):
        try:
            cloned.tick()
        except Exception as exc:
            logger.warning("project_summarise_tick_error", error=str(exc))
            break
    return _summarise_state(cloned)
