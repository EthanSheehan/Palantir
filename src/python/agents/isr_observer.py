import json
from typing import Any, Dict
from schemas.ontology import ISRObserverOutput

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

class ISRObserverAgent:
    def __init__(self, llm_client: Any):
        """
        Initialize the ISR Observer Agent.
        
        Args:
            llm_client: An initialized LLM client (e.g., OpenAI, Anthropic, or wrapped LiteLLM client).
        """
        self.llm_client = llm_client
        self.system_prompt = ISR_OBSERVER_PROMPT

    def _generate_response(self, raw_sensor_data: str) -> str:
        """
        Wrapper to call the underlying LLM. Implement according to specifically chosen LLM provider.
        """
        # Example for OpenAI client:
        # response = self.llm_client.beta.chat.completions.parse(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": f"Raw Sensor Data:\n{raw_sensor_data}"}
        #     ],
        #     response_format=ISRObserverOutput,
        # )
        # return response.choices[0].message.content
        raise NotImplementedError("LLM integration needs to be completed.")

    def process_sensor_data(self, raw_sensor_data: str) -> ISRObserverOutput:
        """
        Ingest multi-domain sensor data, fuse detections, and map to Common Ontology.
        """
        if self.llm_client is None or getattr(self.llm_client, "is_mock", False):
            return self._process_heuristic(raw_sensor_data)
            
        response_content = self._generate_response(raw_sensor_data)
        return ISRObserverOutput.model_validate_json(response_content)

    def _process_heuristic(self, raw_sensor_data: str) -> ISRObserverOutput:
        """
        Simple heuristic to map raw json data to Tracks.
        """
        try:
            data = json.loads(raw_sensor_data)
            from schemas.ontology import Track, Detection, TargetClassification
            
            # If it's a single detection, wrap it in a track
            det = Detection(
                source=data.get("source", "UAV"),
                lat=data.get("lat", 0.0),
                lon=data.get("lon", 0.0),
                confidence=data.get("confidence", 0.5),
                classification=TargetClassification(data.get("classification", "Unknown")),
                timestamp=data.get("timestamp", "")
            )
            
            track = Track(
                track_id=f"TRK-{data.get('id', 'MOCK')}",
                lat=det.lat,
                lon=det.lon,
                classification=det.classification,
                confidence=det.confidence,
                detections=[det],
                is_high_priority=det.classification in [TargetClassification.TEL, TargetClassification.SAM, TargetClassification.CP]
            )
            
            return ISRObserverOutput(tracks=[track], alerts=["High Priority Target Detected"] if track.is_high_priority else [])
        except Exception as e:
            return ISRObserverOutput(tracks=[], alerts=[f"Error processing data: {str(e)}"])
