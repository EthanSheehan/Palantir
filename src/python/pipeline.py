"""
F2T2EA Kill-Chain Orchestrator
==============================
Ties the four MAS agents into a sequential pipeline:

  ISR Observer  →  Strategy Analyst  →  Tactical Planner  →  [HITL]  →  Effectors Agent

The pipeline halts at the HITL gate and only proceeds to execution
when a commander explicitly approves a COA.
"""

from typing import Any, List, Optional

from schemas.ontology import (
    CourseOfAction,
    Effector,
    EffectorsAgentOutput,
    ISRObserverOutput,
    StrategyAnalystOutput,
    TacticalPlannerOutput,
)
from agents.isr_observer import ISRObserverAgent
from agents.strategy_analyst import StrategyAnalystAgent
from agents.tactical_planner import TacticalPlannerAgent
from agents.effectors_agent import EffectorsAgent


class F2T2EAPipeline:
    """End-to-end orchestrator for the Find-Fix-Track-Target-Engage-Assess chain."""

    def __init__(
        self,
        llm_client: Any,
        available_effectors: Optional[List[Effector]] = None,
    ):
        self.observer = ISRObserverAgent(llm_client)
        self.analyst = StrategyAnalystAgent(llm_client)
        self.planner = TacticalPlannerAgent(llm_client, available_effectors)
        self.effector = EffectorsAgent(llm_client)

    # ── Phase 1-3: Find → Fix → Track ────────────────────────────────────
    def find_fix_track(self, raw_sensor_data: str) -> ISRObserverOutput:
        """ISR Observer fuses raw sensor data into tracks."""
        return self.observer.process_sensor_data(raw_sensor_data)

    # ── Phase 4: Target (Nominate) ────────────────────────────────────────
    def target(self, isr_output: ISRObserverOutput) -> StrategyAnalystOutput:
        """Strategy Analyst evaluates tracks against ROE."""
        return self.analyst.evaluate_tracks(isr_output)

    # ── Phase 5a: Generate COAs ───────────────────────────────────────────
    def generate_coas(self, analyst_output: StrategyAnalystOutput) -> List[TacticalPlannerOutput]:
        """Tactical Planner generates 3 COAs per nominated target."""
        return self.planner.generate_coas(analyst_output)

    # ── HITL Gate ─────────────────────────────────────────────────────────
    @staticmethod
    def hitl_approve(coa: CourseOfAction) -> bool:
        """
        Human-in-the-Loop approval gate.
        In production this would surface the COA to a commander UI.
        Returns True if the commander approves the strike.
        """
        print(f"\n{'='*60}")
        print("COMMANDER APPROVAL REQUIRED")
        print(f"{'='*60}")
        print(f"  COA ID       : {coa.coa_id}")
        print(f"  Type         : {coa.coa_type}")
        print(f"  Effector     : {coa.effector.name}")
        print(f"  Pk           : {coa.probability_of_kill:.0%}")
        print(f"  ETA          : {coa.time_to_target_minutes:.1f} min")
        print(f"  Rationale    : {coa.rationalization}")
        print(f"{'='*60}")
        decision = input("  [A]pprove / [R]eject / Re[T]ask → ").strip().upper()
        return decision == "A"

    # ── Phase 5b-6: Engage → Assess ──────────────────────────────────────
    def engage_assess(self, approved_coa: CourseOfAction) -> EffectorsAgentOutput:
        """Effectors Agent executes strike and performs BDA."""
        return self.effector.execute_strike(approved_coa)

    # ── Full Pipeline ─────────────────────────────────────────────────────
    def run(self, raw_sensor_data: str, auto_approve: bool = False) -> dict:
        """
        Execute the complete F2T2EA pipeline.

        Args:
            raw_sensor_data: Multi-source sensor payload.
            auto_approve: If True, skip HITL approval (for testing only).

        Returns:
            Dict containing all intermediate and final outputs.
        """
        isr_output = self.find_fix_track(raw_sensor_data)
        analyst_output = self.target(isr_output)
        tactical_outputs = self.generate_coas(analyst_output)

        engagement_results: List[EffectorsAgentOutput] = []
        for plan in tactical_outputs:
            for coa in plan.coas:
                approved = auto_approve or self.hitl_approve(coa)
                if approved:
                    result = self.engage_assess(coa)
                    engagement_results.append(result)

        return {
            "isr_output": isr_output,
            "analyst_output": analyst_output,
            "tactical_outputs": tactical_outputs,
            "engagement_results": engagement_results,
        }
