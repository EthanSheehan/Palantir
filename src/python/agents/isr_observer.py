"""
agents/isr_observer.py
======================
ISR Observer Agent — ingests multi-domain sensor data (UAV, Satellite, SIGINT),
fuses detections into tracks, and maps them to the Common Ontology.

Supports both LLM-enhanced and heuristic processing paths.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from llm_adapter import LLMAdapter, LLMResponse
from schemas.ontology import (
    Detection,
    ISRObserverOutput,
    TargetClassification,
    Track,
)

logger = structlog.get_logger()

ISR_OBSERVER_PROMPT = """You are the ISR Observer Agent. Your primary function is to ingest multi-domain sensor data (UAV, Satellite, SIGINT) and map it to the Project Antigravity Common Ontology.

Instructions:

Filter and Fuse: Consolidate multiple detections of the same coordinate into a single 'Track ID'.

Classification: Identify objects with high confidence (e.g., TEL, SAM site, Command Post).

Alerting: Immediately flag any detection that matches the High-Priority Target list to the Strategy Analyst.

Constraint: Do not interpret intent; provide only verified spatial and object data. Output must be strictly valid JSON according to the Ontology schema.

High Priority Targets:
- TEL
- SAM
- Command Post
"""

_LLM_TRACK_CORRELATION_PROMPT = """Analyze the following sensor detections and determine:
1. Track correlation: which detections likely refer to the same physical target?
2. Classification confidence: how confident are you in each target type?
3. Sensor retasking: which sensors should be redirected for better coverage?

Respond with valid JSON:
{{
  "correlated_groups": [
    {{
      "track_id": "TRK-<id>",
      "detection_indices": [0, 1],
      "classification": "SAM|TEL|Command Post|Unknown",
      "confidence": 0.0-1.0,
      "reasoning": "why these detections are correlated"
    }}
  ],
  "sensor_retasking": [
    {{
      "sensor": "UAV|Satellite|SIGINT",
      "reason": "why retask this sensor"
    }}
  ]
}}

Detections:
{detections_json}"""

# Distance threshold for grouping detections (degrees, ~1km)
_CORRELATION_DISTANCE_DEG = 0.01

HIGH_PRIORITY_TYPES = frozenset({
    TargetClassification.TEL,
    TargetClassification.SAM,
    TargetClassification.CP,
})


class ISRObserverAgent:
    def __init__(self, llm_client: Any = None, llm_adapter: LLMAdapter | None = None):
        self.llm_client = llm_client
        self.llm_adapter = llm_adapter
        self.system_prompt = ISR_OBSERVER_PROMPT

    def process_sensor_data(self, raw_sensor_data: str) -> ISRObserverOutput:
        return self._process_heuristic(raw_sensor_data)

    async def process_with_llm(
        self,
        detections: list[dict[str, Any]],
    ) -> ISRObserverOutput:
        if not self.llm_adapter or not self.llm_adapter.is_available():
            logger.info("isr_llm_unavailable_falling_back_to_heuristic")
            return self._process_heuristic_from_dicts(detections)

        prompt = _LLM_TRACK_CORRELATION_PROMPT.format(
            detections_json=json.dumps(detections, indent=2),
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            response: LLMResponse = await self.llm_adapter.complete(
                messages,
                model_hint="fast",
            )

            if response.provider == "fallback":
                logger.info("isr_llm_returned_fallback")
                return self._process_heuristic_from_dicts(detections)

            return self._parse_llm_response(response.content, detections)
        except Exception as exc:
            logger.error("isr_llm_processing_failed", error=str(exc))
            return self._process_heuristic_from_dicts(detections)

    def _parse_llm_response(
        self,
        content: str,
        detections: list[dict[str, Any]],
    ) -> ISRObserverOutput:
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            logger.warning("isr_llm_json_parse_failed", content_preview=content[:200])
            return self._process_heuristic_from_dicts(detections)

        groups = parsed.get("correlated_groups", [])
        if not groups:
            return self._process_heuristic_from_dicts(detections)

        tracks: list[Track] = []
        alerts: list[str] = []

        for group in groups:
            track_id = group.get("track_id", f"TRK-LLM-{len(tracks)}")
            indices = group.get("detection_indices", [])
            classification_str = group.get("classification", "Unknown")
            confidence = float(group.get("confidence", 0.5))
            reasoning = group.get("reasoning", "")

            classification = _safe_classification(classification_str)

            group_dets = [
                _dict_to_detection(detections[i])
                for i in indices
                if i < len(detections)
            ]
            if not group_dets:
                continue

            avg_lat = sum(d.lat for d in group_dets) / len(group_dets)
            avg_lon = sum(d.lon for d in group_dets) / len(group_dets)
            is_hp = classification in HIGH_PRIORITY_TYPES

            track = Track(
                track_id=track_id,
                lat=avg_lat,
                lon=avg_lon,
                classification=classification,
                confidence=confidence,
                detections=group_dets,
                is_high_priority=is_hp,
            )
            tracks.append(track)

            if is_hp:
                alerts.append(
                    f"High Priority Target: {classification.value} at "
                    f"({avg_lat:.4f}, {avg_lon:.4f}) — {reasoning}"
                )

            logger.info(
                "isr_llm_track_correlated",
                track_id=track_id,
                classification=classification.value,
                confidence=confidence,
                reasoning=reasoning,
            )

        retasking = parsed.get("sensor_retasking", [])
        for rt in retasking:
            logger.info(
                "isr_sensor_retasking_recommended",
                sensor=rt.get("sensor"),
                reason=rt.get("reason"),
            )

        return ISRObserverOutput(tracks=tracks, alerts=alerts)

    def _process_heuristic_from_dicts(
        self,
        detections: list[dict[str, Any]],
    ) -> ISRObserverOutput:
        tracks: list[Track] = []
        alerts: list[str] = []

        for i, data in enumerate(detections):
            det = _dict_to_detection(data)
            classification = det.classification
            is_hp = classification in HIGH_PRIORITY_TYPES

            reasoning = _heuristic_reasoning(classification, det.confidence)

            track = Track(
                track_id=f"TRK-{data.get('id', i)}",
                lat=det.lat,
                lon=det.lon,
                classification=classification,
                confidence=det.confidence,
                detections=[det],
                is_high_priority=is_hp,
            )
            tracks.append(track)

            if is_hp:
                alerts.append(
                    f"High Priority Target Detected: {classification.value} — {reasoning}"
                )

            logger.info(
                "isr_heuristic_track_created",
                track_id=track.track_id,
                classification=classification.value,
                confidence=det.confidence,
                reasoning=reasoning,
            )

        return ISRObserverOutput(tracks=tracks, alerts=alerts)

    def _process_heuristic(self, raw_sensor_data: str) -> ISRObserverOutput:
        try:
            data = json.loads(raw_sensor_data)
            det = Detection(
                source=data.get("source", "UAV"),
                lat=data.get("lat", 0.0),
                lon=data.get("lon", 0.0),
                confidence=data.get("confidence", 0.5),
                classification=_safe_classification(
                    data.get("classification", "Unknown")
                ),
                timestamp=data.get("timestamp", ""),
            )

            classification = det.classification
            is_hp = classification in HIGH_PRIORITY_TYPES
            reasoning = _heuristic_reasoning(classification, det.confidence)

            track = Track(
                track_id=f"TRK-{data.get('id', 'MOCK')}",
                lat=det.lat,
                lon=det.lon,
                classification=classification,
                confidence=det.confidence,
                detections=[det],
                is_high_priority=is_hp,
            )

            alerts = []
            if is_hp:
                alerts.append(
                    f"High Priority Target Detected: {classification.value} — {reasoning}"
                )

            logger.info(
                "isr_heuristic_track_created",
                track_id=track.track_id,
                classification=classification.value,
                confidence=det.confidence,
                reasoning=reasoning,
            )

            return ISRObserverOutput(tracks=[track], alerts=alerts)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            logger.error("heuristic_processing_failed", error=str(exc))
            return ISRObserverOutput(
                tracks=[], alerts=[f"Error processing data: {str(exc)}"]
            )


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions)
# ---------------------------------------------------------------------------

def _safe_classification(value: str) -> TargetClassification:
    try:
        return TargetClassification(value)
    except ValueError:
        return TargetClassification.UNKNOWN


def _dict_to_detection(data: dict[str, Any]) -> Detection:
    return Detection(
        source=data.get("source", "UAV"),
        lat=float(data.get("lat", 0.0)),
        lon=float(data.get("lon", 0.0)),
        confidence=float(data.get("confidence", 0.5)),
        classification=_safe_classification(data.get("classification", "Unknown")),
        timestamp=data.get("timestamp", ""),
    )


def _heuristic_reasoning(
    classification: TargetClassification,
    confidence: float,
) -> str:
    if classification in HIGH_PRIORITY_TYPES:
        return (
            f"Classification '{classification.value}' is on the High-Priority Target "
            f"list. Confidence {confidence:.0%} exceeds alerting threshold."
        )
    return (
        f"Classification '{classification.value}' is not high-priority. "
        f"Confidence {confidence:.0%}. Monitoring."
    )
