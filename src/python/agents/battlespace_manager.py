"""
battlespace_manager.py — Battlespace Management Agent (Gaia Integration).

Provides the geospatial backbone for the multi-agent C2 system: real-time
map layer management, threat-ring modelling, and terrain-aware mission-path
generation that avoids known adversary SAM envelopes.
"""

import json
from typing import Any, Dict, List, Optional

from schemas.ontology import (
    BattlespaceManagerOutput,
    Coordinate,
    MapLayer,
    MapLayerType,
    MissionPath,
    ThreatRing,
    Track,
    Waypoint,
)
from utils.geo_utils import filter_safe_waypoints, haversine_distance

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

BATTLESPACE_MANAGER_PROMPT = """You are the Battlespace Management Agent. You serve as the geospatial backbone of the multi-agent system (integrating with Gaia), providing a dynamic, real-time map of the operational environment.

Instructions:

Data Integration: Constantly ingest and synchronize live data feeds (sensor data, unit locations, intelligence reports) into the shared spatial environment, mapping them to the common ontology.

Layer Management: Maintain and dynamically adjust customizable map layers, integrating third-party platform data as required by the commander's Common Operational Picture (COP).

Geospatial Analysis: Perform advanced terrain analysis, line-of-sight calculations, and threat ring modeling based on current intelligence.

Path Generation: Generate a terrain-aware mission path for the Tactical Planner that actively avoids known adversary SAM-ring ranges and optimizes for asset survivability.

Constraint: All output must be strictly valid JSON conforming to the BattlespaceManagerOutput schema. Every generated path MUST avoid all active threat rings. Include the IDs of every avoided threat ring in the output.
"""


class BattlespaceManagerAgent:
    """
    Manages geospatial data, threat modelling, and mission-path generation
    for the Antigravity C2 system.
    """

    def __init__(self, llm_client: Any) -> None:
        """
        Initialise the Battlespace Management Agent.

        Args:
            llm_client: An initialised LLM client (e.g. OpenAI, Anthropic,
                        or a wrapped LiteLLM client).
        """
        self.llm_client = llm_client
        self.system_prompt = BATTLESPACE_MANAGER_PROMPT

        # Internal state
        self._threat_rings: List[ThreatRing] = []
        self._map_layers: List[MapLayer] = self._default_layers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_mission_path(
        self,
        tracks: List[Track],
        threat_rings: List[ThreatRing],
        terrain_data: str,
    ) -> BattlespaceManagerOutput:
        """
        Generate a terrain-aware mission path that avoids all known
        adversary SAM-ring ranges.

        Args:
            tracks:       Current ISR fused tracks.
            threat_rings: Known threat envelopes in the area of operations.
            terrain_data: Free-text or JSON terrain context for the LLM.

        Returns:
            A validated ``BattlespaceManagerOutput`` containing the mission
            path, active threat rings, and map layer state.
        """
        self._threat_rings = threat_rings

        query = self._build_query(tracks, threat_rings, terrain_data)
        response_content = self._generate_response(query)

        output = BattlespaceManagerOutput.model_validate_json(response_content)

        # Post-process: enforce SAM-ring avoidance deterministically
        safe_waypoints = filter_safe_waypoints(
            output.mission_path.waypoints,
            self._threat_rings,
        )
        # Re-sequence after filtering
        for idx, wp in enumerate(safe_waypoints):
            safe_waypoints[idx] = wp.model_copy(update={"sequence": idx})

        # Recalculate total distance
        total_km = 0.0
        for i in range(1, len(safe_waypoints)):
            total_km += haversine_distance(
                safe_waypoints[i - 1].position,
                safe_waypoints[i].position,
            )

        avoided_ids = [tr.threat_id for tr in self._threat_rings]

        output.mission_path = output.mission_path.model_copy(
            update={
                "waypoints": safe_waypoints,
                "total_distance_km": round(total_km, 3),
                "avoided_threats": avoided_ids,
            }
        )
        output.active_threat_rings = self._threat_rings
        output.active_layers = self._map_layers

        return output

    def get_active_layers(self) -> List[MapLayer]:
        """Return the current map-layer configuration."""
        return list(self._map_layers)

    def update_threat_rings(self, new_intel: List[ThreatRing]) -> None:
        """
        Ingest new intelligence to refresh the threat-ring dataset.

        Args:
            new_intel: Newly identified or updated threat rings.
        """
        existing_ids = {tr.threat_id for tr in self._threat_rings}
        for tr in new_intel:
            if tr.threat_id in existing_ids:
                # Replace existing entry with updated intel
                self._threat_rings = [
                    t if t.threat_id != tr.threat_id else tr
                    for t in self._threat_rings
                ]
            else:
                self._threat_rings.append(tr)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_response(self, query: str) -> str:
        """
        Wrapper to call the underlying LLM.
        Implement according to specifically chosen LLM provider.
        """
        # Example for OpenAI client:
        # response = self.llm_client.beta.chat.completions.parse(
        #     model="gpt-4o",
        #     messages=[
        #         {"role": "system", "content": self.system_prompt},
        #         {"role": "user", "content": query},
        #     ],
        #     response_format=BattlespaceManagerOutput,
        # )
        # return response.choices[0].message.content
        raise NotImplementedError("LLM integration needs to be completed.")

    def _build_query(
        self,
        tracks: List[Track],
        threat_rings: List[ThreatRing],
        terrain_data: str,
    ) -> str:
        """Compose a structured prompt for the LLM from input data."""
        tracks_json = json.dumps(
            [t.model_dump() for t in tracks], indent=2
        )
        threats_json = json.dumps(
            [tr.model_dump() for tr in threat_rings], indent=2
        )
        return (
            f"CURRENT ISR TRACKS:\n{tracks_json}\n\n"
            f"KNOWN THREAT RINGS:\n{threats_json}\n\n"
            f"TERRAIN CONTEXT:\n{terrain_data}\n\n"
            "Generate a terrain-aware mission path that avoids ALL listed "
            "SAM-ring ranges. Output strictly valid JSON conforming to "
            "BattlespaceManagerOutput."
        )

    @staticmethod
    def _default_layers() -> List[MapLayer]:
        """Return the baseline COP layer stack."""
        return [
            MapLayer(
                layer_id="layer-terrain",
                layer_type=MapLayerType.TERRAIN,
                name="Terrain & Elevation",
                visible=True,
            ),
            MapLayer(
                layer_id="layer-threats",
                layer_type=MapLayerType.THREATS,
                name="Threat Rings",
                visible=True,
            ),
            MapLayer(
                layer_id="layer-friendly",
                layer_type=MapLayerType.FRIENDLY_UNITS,
                name="Friendly Units",
                visible=True,
            ),
            MapLayer(
                layer_id="layer-isr",
                layer_type=MapLayerType.ISR_DETECTIONS,
                name="ISR Detections",
                visible=True,
            ),
            MapLayer(
                layer_id="layer-paths",
                layer_type=MapLayerType.MISSION_PATHS,
                name="Mission Paths",
                visible=False,
            ),
        ]
