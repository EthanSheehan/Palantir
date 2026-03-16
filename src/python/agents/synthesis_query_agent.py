import json
from typing import Any
from schemas.ontology import (
    SITREPQuery,
    SynthesisQueryOutput,
    Track,
    TargetNomination,
    BattleDamageAssessment,
)

SYNTHESIS_QUERY_PROMPT = """You are the Synthesis & Query Agent (AIP Assist Layer). \
You act as the primary interface for the Commanding Officer to interact with the \
broader tactical intelligence system.

Your mission is to translate technical sensor detections into a narrative \
situational report (SITREP) for the Commanding Officer.

## Instructions:

*   **Intelligence Summarization:** Synthesize and summarize multi-source \
intelligence reports from across the battlespace.
*   **Natural Language Querying:** Answer the commander's free-form questions \
by reasoning over the provided datasets — no code required.
*   **Tactical Translation:** Convert raw tactical data and sensor detections \
into clear, non-technical language suitable for senior leadership.
*   **SITREP Generation:** Produce a structured situational report highlighting \
key threats and operational context.

## Output Requirements:

You MUST respond with **valid JSON only** conforming to the following schema:

{
  "sitrep_narrative": "<string — human-readable SITREP>",
  "key_threats": ["<string>", ...],
  "recommended_actions": ["<string>", ...],
  "data_sources_consulted": ["<string>", ...],
  "confidence": <float 0.0–1.0>
}

Constraint: Do not fabricate facts. If the provided context is insufficient to \
answer the query, state so explicitly in the narrative and set confidence ≤ 0.3.
"""


class SynthesisQueryAgent:
    """High-level natural-language interface between the CO and the data plane."""

    def __init__(self, llm_client: Any):
        """
        Initialize the Synthesis & Query Agent.

        Args:
            llm_client: An initialized LLM client (e.g., OpenAI, Anthropic,
                        or wrapped LiteLLM client).
        """
        self.llm_client = llm_client
        self.system_prompt = SYNTHESIS_QUERY_PROMPT

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_context_payload(self, query: SITREPQuery) -> str:
        """
        Assemble a human-readable context block from current tracks,
        nominations, and BDA results attached to the query.

        Returns:
            A JSON string summarising all available context for the LLM.
        """
        context: dict = {}

        if query.context_tracks:
            context["tracks"] = [
                t.model_dump(mode="json") for t in query.context_tracks
            ]

        if query.context_nominations:
            context["nominations"] = [
                n.model_dump(mode="json") for n in query.context_nominations
            ]

        if query.context_bda:
            context["bda_results"] = [
                b.model_dump(mode="json") for b in query.context_bda
            ]

        return json.dumps(context, indent=2) if context else "{}"

    def _generate_response(self, query: str, context_json: str) -> str:
        """
        Wrapper to call the underlying LLM.
        Implement according to specifically chosen LLM provider.

        Args:
            query:        The commander's free-form question.
            context_json: Serialised JSON context (tracks, nominations, BDA).

        Returns:
            Raw JSON string from the LLM conforming to SynthesisQueryOutput.
        """
        # Example for OpenAI client:
        # response = self.llm_client.beta.chat.completions.parse(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": self.system_prompt},
        #         {
        #             "role": "user",
        #             "content": (
        #                 f"Commander Query:\n{query}\n\n"
        #                 f"Current Operational Context:\n{context_json}"
        #             ),
        #         },
        #     ],
        #     response_format=SynthesisQueryOutput,
        # )
        # return response.choices[0].message.content
        raise NotImplementedError("LLM integration needs to be completed.")

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_sitrep(self, query: SITREPQuery) -> SynthesisQueryOutput:
        """
        Produce a structured SITREP from a commander's query and
        operational context.

        Args:
            query: A SITREPQuery containing the question and optional context.

        Returns:
            A validated SynthesisQueryOutput Pydantic model.
        """
        context_json = self._build_context_payload(query)
        response_content = self._generate_response(query.query, context_json)

        # Parse and validate the LLM's JSON response
        output = SynthesisQueryOutput.model_validate_json(response_content)
        return output
