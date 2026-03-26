"""
forward_sim.py
==============
Decision-oriented digital twin — project simulation state forward for each
COA candidate, score outcomes, and rank alternatives before committing.

Public API:
  clone_simulation(model)               → SimulationModel (deepcopy)
  score_state(model)                    → float
  project_forward(model, ticks=50)      → dict  {"score": float, "completed": bool}
  evaluate_coas(model, coas, ticks=50)  → list[dict]  (async)
"""

from __future__ import annotations

import asyncio
import copy
import sys
import threading
from typing import Any

import structlog

logger = structlog.get_logger()

# The SimulationModel graph (grid neighbor lists) can exceed default recursion depth.
_DEEPCOPY_RECURSION_LIMIT = 10000
_RECURSION_LOCK = threading.Lock()  # M-SEC2: guard global recursion limit mutation

# H3: Limit parallel COA evaluation
_MAX_PARALLEL_COAS = 8
_MAX_COAS = 64

# M-SEC1: Hard cap on projection ticks
_MAX_TICKS = 500

# Weights for the scoring function
_WEIGHT_VERIFIED = 3.0  # each verified target adds this
_WEIGHT_DETECTED = 0.5  # partial credit for detected/classified
_WEIGHT_DESTROYED = -5.0  # destroyed targets penalise the score
_WEIGHT_FUEL = 0.2  # per UAV fuel-hours available
_FUEL_FULL_HOURS = 6.0  # reference "full" fuel level for normalisation
_ACTIVE_THREAT_STATES = {"DETECTED", "CLASSIFIED", "VERIFIED", "TRACKED", "LOCKED", "NOMINATED"}

# COA type → score bonus applied to the projected state before returning.
# This gives differentiated scores even when the base projection is identical.
# TODO: Replace with a full physics-based COA application when sim_engine
#       exposes target-state mutation APIs (e.g. mark_target_engaged).
_COA_TYPE_SCORE_BONUS = {
    "STRIKE": 2.0,       # strike COA resolves a threat → positive bonus
    "HIGHEST_PK": 1.5,   # high-Pk variant slightly better than average
    "FASTEST": 0.5,      # speed trades off against thoroughness
    "LOWEST_COST": 0.0,  # cost-optimal baseline
    "RECON": -0.5,       # recon delays resolution → slight penalty
}


def clone_simulation(model: Any) -> Any:
    """
    Return a deep copy of *model* so projections never mutate the original.

    The simulation grid contains circular neighbor references that require a
    higher recursion limit than Python's default 1000.
    """
    with _RECURSION_LOCK:
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


def _apply_coa(clone: Any, coa: dict) -> None:
    """
    Apply COA-specific mutations to the cloned simulation state before ticking.

    Currently applies a score bonus based on COA type (see _COA_TYPE_SCORE_BONUS).
    For STRIKE COAs, the first NOMINATED or VERIFIED target is marked DESTROYED
    to approximate the engagement outcome in the projection.

    TODO: When sim_engine exposes a `mark_target_engaged(target_id)` API, replace
    the manual state mutation below with that call. Also extend to handle
    `effector_name` (weapon type constraints) and `pk_estimate` (probabilistic
    engagement modelling via the CEP model).
    """
    coa_type = coa.get("type", "")

    if coa_type == "STRIKE":
        # Approximate a strike: find the highest-priority unengaged target and
        # mark it as DESTROYED in the clone so the projection reflects the outcome.
        pk = float(coa.get("pk_estimate", 0.8))
        import random
        for target in clone.targets.values():
            state = getattr(target, "state", "")
            if state in ("NOMINATED", "VERIFIED", "LOCKED"):
                # Apply pk probabilistically
                if random.random() < pk:
                    target.state = "DESTROYED"
                break  # only engage one target per COA


def _project_and_score(model: Any, coa: dict, ticks: int) -> tuple[float, dict]:
    """
    Clone *model*, apply *coa* mutations, run *ticks* ticks, and return
    ``(score, summary)`` from a single clone run.

    H2: Replaces the previous pattern where project_forward and
    _project_and_summarise each independently cloned and ticked the model.
    """
    # M-SEC1: Clamp ticks to hard maximum
    ticks = min(ticks, _MAX_TICKS)

    cloned = clone_simulation(model)
    _apply_coa(cloned, coa)

    completed = True
    for _ in range(ticks):
        try:
            cloned.tick()
        except Exception as exc:
            logger.warning("project_and_score_tick_error", error=str(exc))
            completed = False
            break

    base_score = score_state(cloned)
    # Apply COA-type bonus (differentiation even when base projection is identical)
    coa_type = coa.get("type", "")
    bonus = _COA_TYPE_SCORE_BONUS.get(coa_type, 0.0)
    score = max(0.0, base_score + bonus)

    summary = _summarise_state(cloned)
    summary["completed"] = completed
    return score, summary


def project_forward(model: Any, ticks: int = 50) -> dict:
    """
    Clone *model*, run *ticks* simulation ticks, and return a result dict.

    Returns:
      {
        "score": float,       — final scored state
        "completed": bool,    — False if a tick raised an exception
      }

    The original model is never modified.

    M4: Previously this function swallowed tick errors silently and returned
    only a float. It now surfaces whether the projection completed cleanly via
    the ``completed`` field. Callers that only need the score can use
    ``result["score"]``.
    """
    # M-SEC1: Clamp ticks to hard maximum
    ticks = min(ticks, _MAX_TICKS)

    cloned = clone_simulation(model)
    completed = True
    for _ in range(ticks):
        try:
            cloned.tick()
        except Exception as exc:
            logger.warning("project_forward_tick_error", error=str(exc))
            completed = False
            break

    return {"score": score_state(cloned), "completed": completed}


async def evaluate_coas(
    model: Any,
    coas: list[dict],
    ticks: int = 50,
) -> list[dict]:
    """
    Evaluate each COA by projecting the simulation forward *ticks* steps.

    Each COA is evaluated in a thread pool (asyncio.to_thread) so multiple
    candidates run in parallel without blocking the event loop.

    H3: Parallelism is capped at _MAX_PARALLEL_COAS (8) via a semaphore.
        COA lists longer than _MAX_COAS (64) raise ValueError immediately.

    H1: Each COA is applied to its clone via _apply_coa before ticking,
        so COAs with different types/targets receive differentiated scores.

    Returns the COA list sorted by ``projected_score`` descending, with two
    new fields added to each entry:
      - ``projected_score`` (float)
      - ``projected_state_summary`` (dict: verified_targets, active_threats, drone_health, completed)
    """
    if not coas:
        return []

    # H3: Hard cap on COA list size
    if len(coas) > _MAX_COAS:
        raise ValueError(
            f"Too many COAs: {len(coas)} exceeds maximum of {_MAX_COAS}. "
            "Prune the candidate list before calling evaluate_coas."
        )

    # H3: Semaphore limits concurrent thread pool workers
    sem = asyncio.Semaphore(_MAX_PARALLEL_COAS)

    async def _evaluate_single(coa: dict) -> dict:
        async with sem:
            # H2: single clone run returns both score and summary
            score, summary = await asyncio.to_thread(_project_and_score, model, coa, ticks)
        result = dict(coa)
        result["projected_score"] = score
        result["projected_state_summary"] = summary
        return result

    evaluated = await asyncio.gather(*[_evaluate_single(coa) for coa in coas])
    return sorted(evaluated, key=lambda c: c["projected_score"], reverse=True)
