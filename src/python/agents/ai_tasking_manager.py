import json
import uuid
from typing import Any, List

from schemas.ontology import (
    CollectionType,
    Detection,
    SensorAsset,
    SensorStatusEnum,
    SensorTaskingOrder,
    TaskingManagerOutput,
)

AI_TASKING_MANAGER_PROMPT = """You are the AI Tasking Manager (Resource Governance) Agent. Your function is to evaluate sensor availability and task the nearest high-fidelity imaging asset to confirm target ID.

Instructions:

1. You will receive a low-confidence detection and a list of available sensor assets with their locations, capabilities, and operational status.

2. Evaluate which available assets can reach the target area fastest while providing the required collection type (EO/IR, SAR, SIGINT, FMV, or GMTI).

3. Issue one or more Sensor Tasking Orders directing assets to provide secondary verification of the detection.

4. Provide a reasoning trace ("Why-trace") for every tasking decision: which asset was chosen, why it was preferred over alternatives, and the expected time to collection.

5. If no suitable assets are available, state this clearly with a reasoning trace and issue zero tasking orders.

Constraint: You do not assess threat intent or ROE compliance. You only manage sensor resources. Output must be strictly valid JSON to the TaskingManagerOutput schema.
"""


class AITaskingManagerAgent:
    """Orchestrator agent that manages sensor retasking for secondary verification."""

    def __init__(self, llm_client: Any, confidence_threshold: float = 0.7):
        """
        Initialize the AI Tasking Manager Agent.

        Args:
            llm_client: An initialized LLM client (e.g., OpenAI, Anthropic, or wrapped LiteLLM client).
            confidence_threshold: Detections below this confidence trigger retasking (default 0.7).
        """
        self.llm_client = llm_client
        self.system_prompt = AI_TASKING_MANAGER_PROMPT
        self.confidence_threshold = confidence_threshold

    def _generate_response(self, prompt: str) -> str:
        """
        Wrapper to call the underlying LLM. Implement according to specifically chosen LLM provider.
        """
        # Example for OpenAI client:
        # response = self.llm_client.beta.chat.completions.parse(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": prompt}
        #     ],
        #     response_format=TaskingManagerOutput,
        # )
        # return response.choices[0].message.content
        raise NotImplementedError("LLM integration needs to be completed.")

    def _generate_response_heuristic(self, detection: Detection, available_assets: List[SensorAsset]) -> str:
        """Score assets by proximity and sensor match. No LLM needed."""
        import math

        det_lat = getattr(detection, "lat", 0.0)
        det_lon = getattr(detection, "lon", 0.0)
        ranked = []
        for asset in available_assets:
            if asset.status != SensorStatusEnum.AVAILABLE:
                continue
            a_lat = getattr(asset, "lat", 0.0)
            a_lon = getattr(asset, "lon", 0.0)
            dist = math.hypot(a_lon - det_lon, a_lat - det_lat)
            ranked.append((dist, asset))
        ranked.sort(key=lambda x: x[0])
        track_id = getattr(detection, "track_id", "UNKNOWN")
        tasking_orders = []
        for dist, asset in ranked[:2]:
            cap = asset.capabilities[0] if asset.capabilities else CollectionType.EO_IR
            tasking_orders.append(
                SensorTaskingOrder(
                    order_id=str(uuid.uuid4()),
                    asset_id=asset.asset_id,
                    target_detection_id=str(track_id),
                    collection_type=cap,
                    priority=5 if dist < 0.5 else 3,
                    estimated_collection_time_minutes=round(dist * 10.0, 1),
                    reasoning=f"Nearest available asset at distance {dist:.3f} deg",
                )
            )
        output = TaskingManagerOutput(
            tasking_orders=tasking_orders,
            confidence_gap=round(self.confidence_threshold - detection.confidence, 4),
            reasoning=f"Heuristic: assigned {len(tasking_orders)} nearest assets for secondary verification.",
        )
        return output.model_dump_json()

    def _build_prompt(self, detection: Detection, available_assets: List[SensorAsset]) -> str:
        """Build the user prompt from a detection and the sensor ledger."""
        assets_payload = [asset.model_dump(mode="json") for asset in available_assets]
        return (
            f"Low-Confidence Detection (confidence {detection.confidence}):\n"
            f"{detection.model_dump_json(indent=2)}\n\n"
            f"Available Sensor Assets:\n"
            f"{json.dumps(assets_payload, indent=2)}\n\n"
            f"Confidence threshold for autonomous action: {self.confidence_threshold}\n"
            f"Confidence gap: {round(self.confidence_threshold - detection.confidence, 4)}\n\n"
            f"Issue Sensor Tasking Orders to confirm target identification."
        )

    def evaluate_and_retask(
        self,
        detection: Detection,
        available_assets: List[SensorAsset],
    ) -> TaskingManagerOutput:
        """
        Main entry point. Evaluate a detection and, if confidence is below
        threshold, task available sensors for secondary verification.

        Args:
            detection: The detection to evaluate.
            available_assets: Current sensor ledger.

        Returns:
            TaskingManagerOutput with tasking orders (empty if above threshold).
        """
        # Gate: if detection confidence is already sufficient, no retasking needed
        if detection.confidence >= self.confidence_threshold:
            return TaskingManagerOutput(
                tasking_orders=[],
                confidence_gap=0.0,
                reasoning=(
                    f"Detection {detection.track_id if hasattr(detection, 'track_id') else 'N/A'} "
                    f"confidence ({detection.confidence}) meets or exceeds threshold "
                    f"({self.confidence_threshold}). No retasking required."
                ),
            )

        # Filter to only available assets
        ready_assets = [a for a in available_assets if a.status == SensorStatusEnum.AVAILABLE]

        if not ready_assets:
            return TaskingManagerOutput(
                tasking_orders=[],
                confidence_gap=round(self.confidence_threshold - detection.confidence, 4),
                reasoning="No sensor assets currently available for retasking.",
            )

        # Build prompt and invoke LLM (or heuristic fallback when llm_client is None)
        prompt = self._build_prompt(detection, ready_assets)
        if self.llm_client is None:
            response_content = self._generate_response_heuristic(detection, ready_assets)
        else:
            response_content = self._generate_response(prompt)

        # Parse the JSON string into the Pydantic model
        output = TaskingManagerOutput.model_validate_json(response_content)

        return output
