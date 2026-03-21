"""
Tactical Planner Agent – COA (Course of Action) Generation.

Matches the best available effector to a nominated target by querying the
Asset Registry and optimising across three metrics:
  1. Time to Target
  2. Probability of Kill (Pk)
  3. Munition Efficiency (cost)

Presents three distinct COAs to the Human-in-the-Loop:
  COA-1  Fastest
  COA-2  Highest Pk
  COA-3  Lowest Cost

Two execution modes:
  * heuristic (default) -- deterministic scoring, no LLM required.
  * llm -- forwards asset data + target context to an LLM for structured
    reasoning (requires an ``LLMAdapter``).
"""

import json
import math
import uuid
from typing import Any, List, Optional

import structlog
from hitl_manager import CourseOfAction as HITLCourseOfAction
from llm_adapter import LLMAdapter
from mission_data.asset_registry import get_available_effectors
from schemas.ontology import (
    CourseOfAction,
    Effector,
    StrategyAnalystOutput,
    TacticalPlannerOutput,
    TargetNomination,
    Track,
)

logger = structlog.get_logger()

# -- System prompt fed to the LLM for structured reasoning ------------------
TACTICAL_PLANNER_PROMPT = """\
You are the Tactical Planner Agent for Project Antigravity.

Your primary function is to generate Courses of Action (COAs) for every target
nominated by the Strategy Analyst.

Instructions:

1. For each nominated target, generate exactly 3 COAs:
   a) **Fastest** -- minimise time-to-target.
   b) **Highest Pk** -- maximise probability of kill.
   c) **Lowest Cost** -- minimise munition-efficiency cost.

2. Effector Matching: Select the best-fit effector (kinetic or non-kinetic)
   from the available asset pool for each COA type.

3. Reasoning Trace: Every COA MUST include a "rationalization" string
   explaining why a specific effector was chosen (per PRD S3.2).

4. Output: Return valid JSON with the following structure for each COA:
   {
     "coas": [
       {
         "effector_name": "...",
         "effector_type": "Kinetic|Non-Kinetic",
         "time_to_effect_min": <float>,
         "pk_estimate": <float 0-1>,
         "risk_score": <float 1-10>,
         "reasoning_trace": "..."
       }
     ]
   }

Constraint: Do NOT execute any strike. Your outputs feed HITL review.
"""

COA_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "coas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "effector_name": {"type": "string"},
                    "effector_type": {"type": "string"},
                    "time_to_effect_min": {"type": "number"},
                    "pk_estimate": {"type": "number"},
                    "risk_score": {"type": "number"},
                    "reasoning_trace": {"type": "string"},
                },
                "required": [
                    "effector_name",
                    "effector_type",
                    "time_to_effect_min",
                    "pk_estimate",
                    "risk_score",
                    "reasoning_trace",
                ],
            },
            "minItems": 3,
            "maxItems": 3,
        }
    },
    "required": ["coas"],
}


# ===========================================================================
#  Heuristic helpers (pure-python, no LLM)
# ===========================================================================


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_time_to_target(asset: dict, target_lat: float, target_lon: float) -> float:
    """Return estimated time-to-target in minutes."""
    if "time_to_effect_min" in asset:
        return asset["time_to_effect_min"]
    if "rocket_flight_time_min" in asset:
        return asset["rocket_flight_time_min"]

    dist = _haversine_km(asset["lat"], asset["lon"], target_lat, target_lon)
    speed = asset.get("speed_kmh", 0.0)
    if speed <= 0:
        return float("inf")
    return (dist / speed) * 60.0


def _score_asset(asset: dict, target_lat: float, target_lon: float) -> dict:
    """Compute planning metrics for a single asset against a target."""
    return {
        "asset": asset,
        "time_min": _estimate_time_to_target(asset, target_lat, target_lon),
        "pk": asset.get("pk_rating", 0.0),
        "cost": asset.get("cost_index", 10.0),
    }


def _build_coa(
    scored: dict,
    coa_type: str,
    target_track_id: str,
    rationale: str,
) -> CourseOfAction:
    """Create a CourseOfAction from scored asset data."""
    return CourseOfAction(
        coa_id=f"COA-{uuid.uuid4().hex[:8].upper()}",
        coa_type=coa_type,
        target_track_id=target_track_id,
        effector=scored["asset"]["effector"],
        time_to_target_minutes=round(scored["time_min"], 2),
        probability_of_kill=scored["pk"],
        munition_efficiency_cost=scored["cost"],
        rationalization=rationale,
    )


def _compute_composite(pk: float, time_min: float, risk: float) -> float:
    """Weighted composite score: higher is better."""
    time_norm = 1.0 / max(time_min, 0.01)
    risk_norm = 1.0 / max(risk, 0.01)
    return round(0.4 * pk + 0.3 * time_norm + 0.3 * risk_norm, 4)


def _risk_from_cost(cost_index: float) -> float:
    """Map cost_index (1-10) to risk_score (1-10)."""
    return max(1.0, min(10.0, cost_index))


# ===========================================================================
#  Agent class
# ===========================================================================


class TacticalPlannerAgent:
    """
    Generates three COAs for each nominated target track.

    Operates in two modes:
      * **heuristic** (default, ``llm_adapter=None``) -- pure-python scoring
        against the Asset Registry. No external calls required.
      * **llm** -- forwards asset data + target context to an LLM for
        structured reasoning (requires an ``LLMAdapter``).
    """

    def __init__(
        self,
        llm_client: Any = None,
        llm_adapter: Optional[LLMAdapter] = None,
        available_effectors: Optional[List[Effector]] = None,
    ):
        self.llm_client = llm_client
        self.llm_adapter = llm_adapter
        self.available_effectors = available_effectors
        self.system_prompt = TACTICAL_PLANNER_PROMPT

    # -- Primary entry point (original sync interface) ----------------------
    def generate_coas(
        self,
        analyst_output: StrategyAnalystOutput,
        tracks: List[Track],
    ) -> List[TacticalPlannerOutput]:
        """
        Generate COAs for every nominated target in the analyst output.

        Returns a list of ``TacticalPlannerOutput``, one per nominated target.
        """
        track_lookup = {t.track_id: t for t in tracks}
        results: List[TacticalPlannerOutput] = []

        for nom in analyst_output.nominations:
            if nom.decision.value != "Nominate":
                continue

            track = track_lookup.get(nom.track_id)
            if track is None:
                continue

            if self.llm_client is not None:
                results.append(self._generate_via_llm(nom, track))
            else:
                results.append(self._generate_heuristic(nom, track))

        return results

    # -- Enhanced async entry point (HITL-compatible COAs) ------------------
    async def generate_coas_enhanced(
        self,
        target_data: dict,
        available_assets: Optional[list[dict]] = None,
    ) -> list[HITLCourseOfAction]:
        """
        Generate 3 COA options using LLM (model_hint='reasoning') or heuristic
        fallback. Returns frozen HITL CourseOfAction dataclasses ranked by
        composite score.
        """
        assets = available_assets if available_assets is not None else get_available_effectors()

        target_lat = target_data.get("lat", 0.0)
        target_lon = target_data.get("lon", 0.0)

        if self.llm_adapter is not None and self.llm_adapter.is_available():
            coas = await self._generate_coas_llm(target_data, assets)
            if coas:
                return coas

        logger.info("using_heuristic_coa_generation")
        return self._generate_coas_heuristic(target_data, assets)

    # -- Heuristic COA generation (HITL format) ----------------------------
    def _generate_coas_heuristic(
        self,
        target_data: dict,
        assets: list[dict],
    ) -> list[HITLCourseOfAction]:
        """Deterministic scoring fallback producing 3 ranked COAs."""
        target_lat = target_data.get("lat", 0.0)
        target_lon = target_data.get("lon", 0.0)

        scored = [_score_asset(a, target_lat, target_lon) for a in assets]

        fastest = min(scored, key=lambda s: s["time_min"])
        best_pk = max(scored, key=lambda s: s["pk"])
        cheapest = min(scored, key=lambda s: s["cost"])

        raw_coas = [
            self._scored_to_hitl_coa("COA-1", fastest, "Fastest option"),
            self._scored_to_hitl_coa("COA-2", best_pk, "Highest Pk option"),
            self._scored_to_hitl_coa("COA-3", cheapest, "Lowest cost option"),
        ]

        return sorted(raw_coas, key=lambda c: c.composite_score, reverse=True)

    # -- LLM COA generation (HITL format) ----------------------------------
    async def _generate_coas_llm(
        self,
        target_data: dict,
        assets: list[dict],
    ) -> list[HITLCourseOfAction]:
        """Use LLMAdapter for reasoning-enhanced COA generation."""
        context = json.dumps(
            {
                "target": target_data,
                "available_effectors": [
                    {
                        "name": a["effector"].name,
                        "type": a["effector"].effector_type,
                        "pk_rating": a.get("pk_rating", 0.0),
                        "cost_index": a.get("cost_index", 10.0),
                        "speed_kmh": a.get("speed_kmh", 0.0),
                    }
                    for a in assets
                ],
            },
            indent=2,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Generate 3 COAs for this target:\n{context}"},
        ]

        try:
            result = await self.llm_adapter.complete_structured(
                messages=messages,
                response_schema=COA_RESPONSE_SCHEMA,
                model_hint="reasoning",
            )
        except Exception as exc:
            logger.error("llm_coa_generation_failed", error=str(exc))
            return []

        if not result or "coas" not in result:
            logger.warning("llm_returned_empty_coas")
            return []

        coas = []
        for i, raw in enumerate(result["coas"][:3], start=1):
            pk = max(0.0, min(1.0, float(raw.get("pk_estimate", 0.0))))
            time_min = max(0.01, float(raw.get("time_to_effect_min", 999.0)))
            risk = max(1.0, min(10.0, float(raw.get("risk_score", 5.0))))
            coa = HITLCourseOfAction(
                id=f"COA-{i}",
                effector_name=raw.get("effector_name", "Unknown"),
                effector_type=raw.get("effector_type", "Unknown"),
                time_to_effect_min=round(time_min, 2),
                pk_estimate=round(pk, 4),
                risk_score=round(risk, 2),
                composite_score=_compute_composite(pk, time_min, risk),
                reasoning_trace=raw.get("reasoning_trace", ""),
                status="PROPOSED",
            )
            coas.append(coa)

        return sorted(coas, key=lambda c: c.composite_score, reverse=True)

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _scored_to_hitl_coa(
        coa_id: str,
        scored: dict,
        trace_prefix: str,
    ) -> HITLCourseOfAction:
        """Convert a heuristic scored dict to a frozen HITL CourseOfAction."""
        asset = scored["asset"]
        pk = scored["pk"]
        time_min = scored["time_min"]
        risk = _risk_from_cost(scored["cost"])
        effector = asset["effector"]

        return HITLCourseOfAction(
            id=coa_id,
            effector_name=effector.name,
            effector_type=effector.effector_type,
            time_to_effect_min=round(time_min, 2),
            pk_estimate=pk,
            risk_score=risk,
            composite_score=_compute_composite(pk, time_min, risk),
            reasoning_trace=(f"{trace_prefix}: {effector.name} (Pk={pk:.0%}, time={time_min:.1f}min, risk={risk:.1f})"),
            status="PROPOSED",
        )

    # -- Heuristic path (original schema) -----------------------------------
    def _generate_heuristic(
        self,
        nomination: TargetNomination,
        track: Track,
    ) -> TacticalPlannerOutput:
        """Score every available effector and pick the best per metric."""
        assets = get_available_effectors()
        scored = [_score_asset(a, track.lat, track.lon) for a in assets]

        fastest = min(scored, key=lambda s: s["time_min"])
        coa_fastest = _build_coa(
            fastest,
            "fastest",
            track.track_id,
            (
                f"Selected {fastest['asset']['effector'].name} due to shortest "
                f"estimated arrival of {fastest['time_min']:.1f} min and "
                f"minimal collateral risk ({nomination.collateral_risk})."
            ),
        )

        best_pk = max(scored, key=lambda s: s["pk"])
        coa_pk = _build_coa(
            best_pk,
            "highest_pk",
            track.track_id,
            (
                f"Selected {best_pk['asset']['effector'].name} for highest "
                f"Pk of {best_pk['pk']:.0%} against "
                f"{track.classification.value}."
            ),
        )

        cheapest = min(scored, key=lambda s: s["cost"])
        coa_cost = _build_coa(
            cheapest,
            "lowest_cost",
            track.track_id,
            (
                f"Selected {cheapest['asset']['effector'].name} for lowest "
                f"relative cost index ({cheapest['cost']}) with acceptable "
                f"Pk of {cheapest['pk']:.0%}."
            ),
        )

        return TacticalPlannerOutput(
            target_track_id=track.track_id,
            coas=[coa_fastest, coa_pk, coa_cost],
        )

    # -- LLM path (original schema) ----------------------------------------
    def _generate_via_llm(
        self,
        nomination: TargetNomination,
        track: Track,
    ) -> TacticalPlannerOutput:
        """Forward asset registry + target context to the LLM."""
        assets = get_available_effectors()
        context = json.dumps(
            {
                "nomination": nomination.model_dump(),
                "track": track.model_dump(),
                "available_effectors": [a["effector"].model_dump() for a in assets],
            },
            indent=2,
        )

        logger.warning("llm_not_implemented_falling_back_to_heuristic")
        return self._generate_heuristic(nomination, track)
