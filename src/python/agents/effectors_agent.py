import json
from typing import Any
from schemas.ontology import (
    CourseOfAction,
    EffectorsAgentOutput,
)

EFFECTORS_AGENT_PROMPT = """You are the Effectors Agent for Project Antigravity.

Your primary function is to manage technical handshakes for strike tasking
and perform Battle Damage Assessment (BDA) post-strike.

Instructions:

1. Tasking: Accept a commander-approved COA and translate it into execution
   parameters for the assigned effector. Output the current task_status
   ("Tasked", "In-Flight", "Complete").

2. Battle Damage Assessment: After strike completion, ingest post-strike
   imagery or intelligence and assess the outcome:
   - "Target Destroyed"
   - "Target Damaged"
   - "Target Missed"
   - "Assessment Pending"

3. Reasoning Trace: Provide a reasoning string explaining how the BDA
   conclusion was reached (per PRD §3.2 Reasoning Traces).

4. Feedback Loop: If the target was not destroyed, recommend re-engagement
   or continued monitoring in the reasoning field.

Constraint: Execution only occurs AFTER commander approval via HITL.
Output must be strictly valid JSON matching the EffectorsAgentOutput schema.
"""


class EffectorsAgent:
    def __init__(self, llm_client: Any):
        """
        Initialize the Effectors Agent.

        Args:
            llm_client: An initialized LLM client.
        """
        self.llm_client = llm_client
        self.system_prompt = EFFECTORS_AGENT_PROMPT

    def _generate_response(self, context: str) -> str:
        """
        Wrapper to call the underlying LLM.
        """
        if self.llm_client is None:
            # Heuristic / Mock fallback for development
            data = json.loads(context)
            if data.get("action") == "EXECUTE":
                return json.dumps({
                    "strike_id": "STRIKE-MOCK-001",
                    "task_status": "Complete",
                    "bda_result": "Target Destroyed",
                    "reasoning": "Heuristic execution: Strike confirmed by mock effector handshake."
                })
            return json.dumps({
                "strike_id": data.get("strike_id", "STRIKE-MOCK-001"),
                "task_status": "Complete",
                "bda_result": "Target Destroyed",
                "reasoning": "Heuristic BDA: Post-strike visual confirms destruction."
            })
        
        # Example for OpenAI client:
        # ...

    def execute_strike(self, approved_coa: CourseOfAction) -> EffectorsAgentOutput:
        """
        Task an effector with a commander-approved COA.
        """
        context = json.dumps({
            "action": "EXECUTE",
            "approved_coa": approved_coa.model_dump(),
        }, indent=2)
        response_content = self._generate_response(context)
        return EffectorsAgentOutput.model_validate_json(response_content)

    def assess_damage(self, strike_id: str, post_strike_data: str) -> EffectorsAgentOutput:
        """
        Perform BDA after a strike using post-strike imagery/intelligence.
        """
        context = json.dumps({
            "action": "BDA",
            "strike_id": strike_id,
            "post_strike_data": post_strike_data,
        }, indent=2)
        response_content = self._generate_response(context)
        return EffectorsAgentOutput.model_validate_json(response_content)
