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
        Falls back to heuristic SITREP when llm_client is None.
        """
        if self.llm_client is not None:
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

        return self._heuristic_sitrep(context_json)

    def _heuristic_sitrep(self, context_json: str) -> str:
        """Build a structured SITREP from context without an LLM."""
        try:
            ctx = json.loads(context_json)
        except (json.JSONDecodeError, TypeError):
            ctx = {}

        tracks = ctx.get("tracks", [])
        nominations = ctx.get("nominations", [])
        bda_results = ctx.get("bda_results", [])

        track_count = len(tracks)
        high_priority = [t for t in tracks if t.get("is_high_priority")]
        threat_types = list({t.get("classification", "UNKNOWN") for t in tracks})

        key_threats = [
            f"{t.get('classification', 'UNKNOWN')} track {t.get('track_id', '?')} "
            f"(confidence: {t.get('confidence', 0.0):.0%})"
            for t in sorted(tracks, key=lambda x: x.get("confidence", 0.0), reverse=True)[:5]
        ]

        recommended_actions: list[str] = []
        if high_priority:
            recommended_actions.append(
                f"Review {len(high_priority)} high-priority target(s) on strike board."
            )
        if not tracks:
            recommended_actions.append("Continue ISR sweep — no tracks currently active.")
        else:
            recommended_actions.append("Maintain sensor coverage on active tracks.")

        data_sources: list[str] = []
        if tracks:
            data_sources.append("ISR Tracks")
        if nominations:
            data_sources.append("Strike Board Nominations")
        if bda_results:
            data_sources.append("Battle Damage Assessments")
        if not data_sources:
            data_sources.append("No data sources available")

        narrative = (
            f"SITREP: {track_count} active track(s) detected"
            + (f", types: {', '.join(threat_types)}" if threat_types else "")
            + f". {len(high_priority)} high-priority target(s)."
            + (f" {len(nominations)} nomination(s) pending." if nominations else "")
            + (f" {len(bda_results)} BDA report(s) available." if bda_results else "")
        )

        confidence = 0.5 if not tracks else min(
            0.9,
            sum(t.get("confidence", 0.5) for t in tracks) / max(len(tracks), 1),
        )

        output = {
            "sitrep_narrative": narrative,
            "key_threats": key_threats,
            "recommended_actions": recommended_actions,
            "data_sources_consulted": data_sources,
            "confidence": round(confidence, 3),
        }
        return json.dumps(output)

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
