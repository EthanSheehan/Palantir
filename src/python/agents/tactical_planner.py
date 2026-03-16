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
  • heuristic (default) – deterministic scoring, no LLM required.
  • llm – forwards asset data + target context to an LLM for structured
    reasoning (requires an ``llm_client``).
"""

import json
import math
import uuid
from typing import Any, List, Optional

from schemas.ontology import (
    CourseOfAction,
    Effector,
    StrategyAnalystOutput,
    TacticalPlannerOutput,
    TargetNomination,
    Track,
)
from mission_data.asset_registry import get_available_effectors

# ── System prompt fed to the LLM for structured reasoning ──────────────────
TACTICAL_PLANNER_PROMPT = """\
You are the Tactical Planner Agent for Project Antigravity.

Your primary function is to generate Courses of Action (COAs) for every target
nominated by the Strategy Analyst.

Instructions:

1. For each nominated target, generate exactly 3 COAs:
   a) **Fastest** – minimise time-to-target.
   b) **Highest Pk** – maximise probability of kill.
   c) **Lowest Cost** – minimise munition-efficiency cost.

2. Effector Matching: Select the best-fit effector (kinetic or non-kinetic)
   from the available asset pool for each COA type.

3. Reasoning Trace: Every COA MUST include a "rationalization" string
   explaining why a specific effector was chosen (per PRD §3.2).

4. Output: Return a TacticalPlannerOutput per nominated target containing
   the three COAs.

Constraint: Do NOT execute any strike. Your outputs feed HITL review.
Output must be strictly valid JSON matching the TacticalPlannerOutput schema.
"""


# ═══════════════════════════════════════════════════════════════════════════
#  Heuristic helpers (pure-python, no LLM)
# ═══════════════════════════════════════════════════════════════════════════

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _estimate_time_to_target(asset: dict, target_lat: float, target_lon: float) -> float:
    """Return estimated time-to-target in minutes."""
    # Non-kinetic / cyber assets have a fixed response time
    if "time_to_effect_min" in asset:
        return asset["time_to_effect_min"]

    # Rocket / artillery with a fixed flight time (e.g., HIMARS)
    if "rocket_flight_time_min" in asset:
        return asset["rocket_flight_time_min"]

    dist = _haversine_km(asset["lat"], asset["lon"], target_lat, target_lon)
    speed = asset.get("speed_kmh", 0.0)
    if speed <= 0:
        return float("inf")
    return (dist / speed) * 60.0  # hours → minutes


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


# ═══════════════════════════════════════════════════════════════════════════
#  Agent class
# ═══════════════════════════════════════════════════════════════════════════

class TacticalPlannerAgent:
    """
    Generates three COAs for each nominated target track.

    Operates in two modes:
      • **heuristic** (default, ``llm_client=None``) – pure-python scoring
        against the Asset Registry.  No external calls required.
      • **llm** – forwards asset data + target context to an LLM for
        structured reasoning (requires an ``llm_client``).
    """

    def __init__(
        self,
        llm_client: Any = None,
        available_effectors: Optional[List[Effector]] = None,
    ):
        """
        Args:
            llm_client: An initialized LLM client (e.g., OpenAI).
                        If ``None``, the heuristic planner is used.
            available_effectors: Optional override of the effector list.
        """
        self.llm_client = llm_client
        self.available_effectors = available_effectors
        self.system_prompt = TACTICAL_PLANNER_PROMPT

    # ── Primary entry point ────────────────────────────────────────────────
    def generate_coas(
        self,
        analyst_output: StrategyAnalystOutput,
        tracks: List[Track],
    ) -> List[TacticalPlannerOutput]:
        """
        Generate COAs for every nominated target in the analyst output.

        Args:
            analyst_output: Output from the Strategy Analyst containing
                            target nominations.
            tracks: List of fused Tracks from the ISR Observer so we can
                    look up lat/lon for each nominated track_id.

        Returns:
            A list of ``TacticalPlannerOutput``, one per nominated target.
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

    # ── Heuristic path ─────────────────────────────────────────────────────
    def _generate_heuristic(
        self,
        nomination: TargetNomination,
        track: Track,
    ) -> TacticalPlannerOutput:
        """Score every available effector and pick the best per metric."""
        assets = get_available_effectors()
        scored = [_score_asset(a, track.lat, track.lon) for a in assets]

        # COA 1 – Fastest
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

        # COA 2 – Highest Pk
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

        # COA 3 – Lowest Cost
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

    # ── LLM path (activate when provider is chosen) ────────────────────────
    def _generate_via_llm(
        self,
        nomination: TargetNomination,
        track: Track,
    ) -> TacticalPlannerOutput:
        """Forward asset registry + target context to the LLM."""
        assets = get_available_effectors()
        context = json.dumps({
            "nomination": nomination.model_dump(),
            "track": track.model_dump(),
            "available_effectors": [
                a["effector"].model_dump() for a in assets
            ],
        }, indent=2)

        # Example for OpenAI-compatible client:
        # response = self.llm_client.beta.chat.completions.parse(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": context},
        #     ],
        #     response_format=TacticalPlannerOutput,
        # )
        # return TacticalPlannerOutput.model_validate_json(
        #     response.choices[0].message.content
        # )
        raise NotImplementedError("LLM integration needs to be completed.")
