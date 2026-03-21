"""
Tests for the AI Tasking Manager (Resource Governance) Agent.

Covers:
  1. Schema validation (SensorAsset, SensorTaskingOrder, TaskingManagerOutput)
  2. Threshold gating (high-confidence detections skip the LLM)
  3. No-available-assets edge case
  4. LLM response parsing via mocked _generate_response
"""

import json
import os

# Allow running from the src/python directory
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.ai_tasking_manager import AITaskingManagerAgent
from schemas.ontology import (
    CollectionType,
    Detection,
    SensorAsset,
    SensorSource,
    SensorStatusEnum,
    SensorTaskingOrder,
    TargetClassification,
    TaskingManagerOutput,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_detection(confidence: float = 0.4) -> Detection:
    return Detection(
        source=SensorSource.UAV,
        lat=34.05,
        lon=-118.25,
        confidence=confidence,
        classification=TargetClassification.TEL,
        timestamp="2026-03-14T23:00:00Z",
    )


def _make_assets() -> list[SensorAsset]:
    return [
        SensorAsset(
            asset_id="uav-01",
            asset_name="MQ-9 Reaper #1",
            sensor_type=SensorSource.UAV,
            status=SensorStatusEnum.AVAILABLE,
            lat=34.10,
            lon=-118.30,
            capabilities=[CollectionType.EO_IR, CollectionType.FMV],
            time_to_station_minutes=12.0,
        ),
        SensorAsset(
            asset_id="sat-02",
            asset_name="WorldView-4",
            sensor_type=SensorSource.SATELLITE,
            status=SensorStatusEnum.OFFLINE,
            lat=0.0,
            lon=0.0,
            capabilities=[CollectionType.SAR],
            time_to_station_minutes=None,
        ),
    ]


# ── 1. Schema Validation ─────────────────────────────────────────────────────


class TestSchemaValidation:
    def test_sensor_asset_valid(self):
        asset = _make_assets()[0]
        assert asset.asset_id == "uav-01"
        assert asset.status == SensorStatusEnum.AVAILABLE

    def test_sensor_asset_rejects_invalid_status(self):
        with pytest.raises(Exception):
            SensorAsset(
                asset_id="x",
                asset_name="x",
                sensor_type=SensorSource.UAV,
                status="flying",  # invalid
                lat=0,
                lon=0,
            )

    def test_sensor_tasking_order_priority_bounds(self):
        with pytest.raises(Exception):
            SensorTaskingOrder(
                order_id="o1",
                asset_id="a1",
                target_detection_id="d1",
                collection_type=CollectionType.EO_IR,
                priority=10,  # out of range (max 5)
                estimated_collection_time_minutes=5.0,
                reasoning="test",
            )

    def test_tasking_manager_output_roundtrip(self):
        out = TaskingManagerOutput(
            tasking_orders=[],
            confidence_gap=0.3,
            reasoning="No retasking needed.",
        )
        data = json.loads(out.model_dump_json())
        rebuilt = TaskingManagerOutput.model_validate(data)
        assert rebuilt.confidence_gap == 0.3


# ── 2. Threshold Gating ──────────────────────────────────────────────────────


class TestThresholdGating:
    def test_high_confidence_skips_llm(self):
        agent = AITaskingManagerAgent(llm_client=None, confidence_threshold=0.7)
        detection = _make_detection(confidence=0.85)
        result = agent.evaluate_and_retask(detection, _make_assets())

        assert result.tasking_orders == []
        assert result.confidence_gap == 0.0
        assert "meets or exceeds" in result.reasoning

    def test_exact_threshold_skips_llm(self):
        agent = AITaskingManagerAgent(llm_client=None, confidence_threshold=0.7)
        detection = _make_detection(confidence=0.7)
        result = agent.evaluate_and_retask(detection, _make_assets())

        assert result.tasking_orders == []


# ── 3. No Available Assets ───────────────────────────────────────────────────


class TestNoAvailableAssets:
    def test_all_assets_offline(self):
        agent = AITaskingManagerAgent(llm_client=None, confidence_threshold=0.7)
        detection = _make_detection(confidence=0.3)

        offline_assets = [
            SensorAsset(
                asset_id="sat-offline",
                asset_name="Dead Satellite",
                sensor_type=SensorSource.SATELLITE,
                status=SensorStatusEnum.OFFLINE,
                lat=0,
                lon=0,
                capabilities=[CollectionType.SAR],
            )
        ]
        result = agent.evaluate_and_retask(detection, offline_assets)

        assert result.tasking_orders == []
        assert result.confidence_gap == pytest.approx(0.4)
        assert "No sensor assets" in result.reasoning


# ── 4. Mocked LLM Response Parsing ──────────────────────────────────────────


class TestMockedLLMParsing:
    def test_parses_valid_llm_response(self):
        mock_response = TaskingManagerOutput(
            tasking_orders=[
                SensorTaskingOrder(
                    order_id="ord-001",
                    asset_id="uav-01",
                    target_detection_id="det-abc",
                    collection_type=CollectionType.EO_IR,
                    priority=4,
                    estimated_collection_time_minutes=12.0,
                    reasoning="Nearest available UAV with EO/IR capability.",
                )
            ],
            confidence_gap=0.3,
            reasoning="Detection confidence 0.4 is below threshold 0.7. Tasking MQ-9 Reaper #1.",
        )

        agent = AITaskingManagerAgent(llm_client=None, confidence_threshold=0.7)

        with patch.object(agent, "_generate_response", return_value=mock_response.model_dump_json()):
            detection = _make_detection(confidence=0.4)
            result = agent.evaluate_and_retask(detection, _make_assets())

        assert len(result.tasking_orders) == 1
        assert result.tasking_orders[0].asset_id == "uav-01"
        assert result.confidence_gap == pytest.approx(0.3)
