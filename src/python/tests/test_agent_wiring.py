"""
Tests for ISR Observer and Strategy Analyst agent wiring.
==========================================================
Covers heuristic processing, priority scoring, reasoning traces,
and strike board nomination format.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")

from agents.isr_observer import (
    ISRObserverAgent,
)
from agents.isr_observer import (
    _heuristic_reasoning as isr_heuristic_reasoning,
)
from agents.strategy_analyst import (
    StrategyAnalystAgent,
    TargetEvaluation,
    _heuristic_priority_for_type,
    _recommendation_for_priority,
)
from llm_adapter import LLMAdapter
from schemas.ontology import EngagementDecision, ISRObserverOutput, TargetClassification

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isr_agent():
    return ISRObserverAgent()


@pytest.fixture()
def strategy_agent():
    return StrategyAnalystAgent()


@pytest.fixture()
def adapter_no_ollama():
    with patch("llm_adapter._probe_ollama", return_value=(False, [])):
        return LLMAdapter()


@pytest.fixture()
def isr_agent_with_adapter(adapter_no_ollama):
    return ISRObserverAgent(llm_adapter=adapter_no_ollama)


@pytest.fixture()
def strategy_agent_with_adapter(adapter_no_ollama):
    return StrategyAnalystAgent(llm_adapter=adapter_no_ollama)


def _make_detection(
    target_type="SAM",
    confidence=0.85,
    lat=45.0,
    lon=25.0,
    source="UAV",
    target_id=1,
):
    return {
        "id": target_id,
        "type": target_type,
        "source": source,
        "lat": lat,
        "lon": lon,
        "confidence": confidence,
        "classification": target_type,
        "timestamp": "2025-01-01T00:00:00Z",
    }


def _make_raw_sensor_json(**kwargs):
    return json.dumps(_make_detection(**kwargs))


# ---------------------------------------------------------------------------
# ISR Observer — heuristic processing
# ---------------------------------------------------------------------------


class TestISRObserverHeuristic:
    def test_process_single_detection(self, isr_agent):
        raw = _make_raw_sensor_json(target_type="SAM", confidence=0.9)
        result = isr_agent.process_sensor_data(raw)

        assert isinstance(result, ISRObserverOutput)
        assert len(result.tracks) == 1
        assert result.tracks[0].classification == TargetClassification.SAM
        assert result.tracks[0].is_high_priority is True

    def test_process_low_priority_target(self, isr_agent):
        raw = _make_raw_sensor_json(target_type="Unknown", confidence=0.3)
        result = isr_agent.process_sensor_data(raw)

        assert len(result.tracks) == 1
        assert result.tracks[0].is_high_priority is False
        assert len(result.alerts) == 0

    def test_process_tel_is_high_priority(self, isr_agent):
        raw = _make_raw_sensor_json(target_type="TEL", confidence=0.8)
        result = isr_agent.process_sensor_data(raw)

        assert result.tracks[0].is_high_priority is True
        assert len(result.alerts) > 0

    def test_process_cp_is_high_priority(self, isr_agent):
        raw = _make_raw_sensor_json(target_type="CP", confidence=0.75)
        result = isr_agent.process_sensor_data(raw)

        assert result.tracks[0].is_high_priority is True

    def test_invalid_json_returns_empty_tracks(self, isr_agent):
        result = isr_agent.process_sensor_data("not valid json")

        assert result.tracks == []
        assert len(result.alerts) == 1
        assert "Error" in result.alerts[0]

    def test_heuristic_from_dicts(self, isr_agent):
        detections = [
            _make_detection(target_type="SAM", target_id=1),
            _make_detection(target_type="TEL", target_id=2),
        ]
        result = isr_agent._process_heuristic_from_dicts(detections)

        assert len(result.tracks) == 2
        assert result.tracks[0].track_id == "TRK-1"
        assert result.tracks[1].track_id == "TRK-2"


class TestISRObserverLLMFallback:
    @pytest.mark.asyncio
    async def test_falls_back_when_no_adapter(self, isr_agent):
        detections = [_make_detection()]
        result = await isr_agent.process_with_llm(detections)

        assert isinstance(result, ISRObserverOutput)
        assert len(result.tracks) == 1

    @pytest.mark.asyncio
    async def test_falls_back_when_adapter_unavailable(self, isr_agent_with_adapter):
        detections = [_make_detection()]
        result = await isr_agent_with_adapter.process_with_llm(detections)

        assert isinstance(result, ISRObserverOutput)
        assert len(result.tracks) == 1


# ---------------------------------------------------------------------------
# Strategy Analyst — heuristic evaluation
# ---------------------------------------------------------------------------


class TestStrategyAnalystHeuristic:
    def test_evaluate_sam_high_priority(self, strategy_agent):
        target = _make_detection(target_type="SAM")
        evaluation = strategy_agent._evaluate_target_heuristic(target)

        assert isinstance(evaluation, TargetEvaluation)
        assert evaluation.priority_score == 9
        assert evaluation.roe_compliant is True
        assert evaluation.recommendation == "NOMINATE"

    def test_evaluate_tel_high_priority(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="TEL"))
        assert evaluation.priority_score == 8
        assert evaluation.recommendation == "NOMINATE"

    def test_evaluate_radar_moderate(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="RADAR"))
        assert evaluation.priority_score == 7
        assert evaluation.recommendation == "NOMINATE"

    def test_evaluate_cp_moderate(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="CP"))
        assert evaluation.priority_score == 6
        assert evaluation.recommendation == "MONITOR"

    def test_evaluate_manpads(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="MANPADS"))
        assert evaluation.priority_score == 5
        assert evaluation.recommendation == "MONITOR"

    def test_evaluate_truck_low(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="TRUCK"))
        assert evaluation.priority_score == 3
        assert evaluation.recommendation == "IGNORE"

    def test_evaluate_logistics_low(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="LOGISTICS"))
        assert evaluation.priority_score == 3

    def test_evaluate_unknown_default(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="UNKNOWN_THING"))
        assert evaluation.priority_score == _heuristic_priority_for_type("UNKNOWN_THING")
        assert evaluation.roe_compliant is True


# ---------------------------------------------------------------------------
# Priority scoring logic
# ---------------------------------------------------------------------------


class TestPriorityScoring:
    def test_sam_priority(self):
        assert _heuristic_priority_for_type("SAM") == 9

    def test_tel_priority(self):
        assert _heuristic_priority_for_type("TEL") == 8

    def test_radar_priority(self):
        assert _heuristic_priority_for_type("RADAR") == 7

    def test_cp_priority(self):
        assert _heuristic_priority_for_type("CP") == 6

    def test_c2_node_priority(self):
        assert _heuristic_priority_for_type("C2_NODE") == 6

    def test_manpads_priority(self):
        assert _heuristic_priority_for_type("MANPADS") == 5

    def test_truck_priority(self):
        assert _heuristic_priority_for_type("TRUCK") == 3

    def test_unknown_gets_default(self):
        assert _heuristic_priority_for_type("SOMETHING_ELSE") == 4

    def test_recommendation_nominate(self):
        assert _recommendation_for_priority(9) == "NOMINATE"
        assert _recommendation_for_priority(7) == "NOMINATE"

    def test_recommendation_monitor(self):
        assert _recommendation_for_priority(6) == "MONITOR"
        assert _recommendation_for_priority(4) == "MONITOR"

    def test_recommendation_ignore(self):
        assert _recommendation_for_priority(3) == "IGNORE"
        assert _recommendation_for_priority(1) == "IGNORE"


# ---------------------------------------------------------------------------
# Reasoning traces
# ---------------------------------------------------------------------------


class TestReasoningTraces:
    def test_isr_heuristic_reasoning_high_priority(self):
        reasoning = isr_heuristic_reasoning(TargetClassification.SAM, 0.9)
        assert len(reasoning) > 0
        assert "SAM" in reasoning
        assert "High-Priority" in reasoning

    def test_isr_heuristic_reasoning_low_priority(self):
        reasoning = isr_heuristic_reasoning(TargetClassification.UNKNOWN, 0.3)
        assert len(reasoning) > 0
        assert "not high-priority" in reasoning

    def test_strategy_evaluation_has_reasoning(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="SAM"))
        assert len(evaluation.reasoning_trace) > 0
        assert "SAM" in evaluation.reasoning_trace

    def test_strategy_evaluation_reasoning_for_low_target(self, strategy_agent):
        evaluation = strategy_agent._evaluate_target_heuristic(_make_detection(target_type="TRUCK"))
        assert len(evaluation.reasoning_trace) > 0
        assert "TRUCK" in evaluation.reasoning_trace

    def test_track_evaluation_has_reasoning(self, strategy_agent):
        isr_agent = ISRObserverAgent()
        raw = _make_raw_sensor_json(target_type="TEL")
        isr_output = isr_agent.process_sensor_data(raw)
        result = strategy_agent.evaluate_tracks(isr_output)

        assert len(result.nominations) == 1
        assert len(result.nominations[0].reasoning) > 0


# ---------------------------------------------------------------------------
# Strike board nomination
# ---------------------------------------------------------------------------


class TestStrikeBoardNomination:
    @pytest.mark.asyncio
    async def test_nomination_format(self, strategy_agent):
        target = _make_detection(target_type="SAM", target_id=42)
        evaluation = TargetEvaluation(
            priority_score=9,
            roe_compliant=True,
            recommendation="NOMINATE",
            collateral_risk="LOW",
            reasoning_trace="High-threat SAM site detected.",
        )

        entry = await strategy_agent.nominate_to_strike_board(target, evaluation)

        assert entry["target_id"] == 42
        assert entry["target_type"] == "SAM"
        assert entry["priority_score"] == 9
        assert entry["roe_compliant"] is True
        assert entry["recommendation"] == "NOMINATE"
        assert entry["collateral_risk"] == "LOW"
        assert entry["reasoning"] == "High-threat SAM site detected."
        assert entry["status"] == "PENDING_HITL_REVIEW"
        assert "lat" in entry
        assert "lon" in entry

    @pytest.mark.asyncio
    async def test_nomination_for_monitor_target(self, strategy_agent):
        target = _make_detection(target_type="TRUCK", target_id=99)
        evaluation = TargetEvaluation(
            priority_score=3,
            roe_compliant=True,
            recommendation="MONITOR",
            collateral_risk="LOW",
            reasoning_trace="Low-priority logistics target.",
        )

        entry = await strategy_agent.nominate_to_strike_board(target, evaluation)

        assert entry["recommendation"] == "MONITOR"
        assert entry["status"] == "PENDING_HITL_REVIEW"


# ---------------------------------------------------------------------------
# End-to-end: ISR -> Strategy pipeline (heuristic)
# ---------------------------------------------------------------------------


class TestPipelineHeuristic:
    def test_isr_to_strategy_pipeline(self):
        isr = ISRObserverAgent()
        analyst = StrategyAnalystAgent()

        raw = _make_raw_sensor_json(target_type="TEL", confidence=0.85)
        isr_output = isr.process_sensor_data(raw)
        result = analyst.evaluate_tracks(isr_output)

        assert len(result.nominations) == 1
        nom = result.nominations[0]
        assert nom.decision == EngagementDecision.NOMINATE
        assert nom.roe_compliance is True
        assert len(nom.reasoning) > 0

    @pytest.mark.asyncio
    async def test_evaluate_target_async(self, strategy_agent):
        target = _make_detection(target_type="SAM")
        evaluation = await strategy_agent.evaluate_target(target)

        assert isinstance(evaluation, TargetEvaluation)
        assert evaluation.priority_score == 9
        assert evaluation.recommendation == "NOMINATE"


# ---------------------------------------------------------------------------
# Evaluation immutability
# ---------------------------------------------------------------------------


class TestEvaluationImmutability:
    def test_target_evaluation_is_frozen(self):
        evaluation = TargetEvaluation(
            priority_score=8,
            roe_compliant=True,
            recommendation="NOMINATE",
            collateral_risk="LOW",
            reasoning_trace="test",
        )
        with pytest.raises(AttributeError):
            evaluation.priority_score = 5
