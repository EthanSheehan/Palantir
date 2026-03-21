"""
New tests for SynthesisQueryAgent._generate_response() heuristic.
These must FAIL before implementation and PASS after.
"""

import pytest
from agents.synthesis_query_agent import SynthesisQueryAgent
from schemas.ontology import (
    BattleDamageAssessment,
    BDAResult,
    EngagementDecision,
    SITREPQuery,
    SynthesisQueryOutput,
    TargetClassification,
    TargetNomination,
    Track,
)


def _make_track(track_id: str, classification: str = "SAM", confidence: float = 0.8) -> Track:
    return Track(
        track_id=track_id,
        lat=33.4,
        lon=44.3,
        classification=TargetClassification(classification),
        confidence=confidence,
        detections=[],
        is_high_priority=True,
    )


def _make_nomination(track_id: str) -> TargetNomination:
    return TargetNomination(
        track_id=track_id,
        decision=EngagementDecision.NOMINATE,
        roe_compliance=True,
        collateral_risk="LOW",
        reasoning="High-confidence target",
    )


def _make_bda(track_id: str) -> BattleDamageAssessment:
    return BattleDamageAssessment(
        strike_id="strike-001",
        target_track_id=track_id,
        coa_id="coa-001",
        result=BDAResult.DESTROYED,
        confidence=0.9,
        notes="Confirmed",
    )


@pytest.fixture
def agent_no_llm():
    return SynthesisQueryAgent(llm_client=None)


class TestSynthesisHeuristicResponse:
    def test_synthesis_generates_sitrep_from_state(self, agent_no_llm):
        tracks = [_make_track("T-1"), _make_track("T-2")]
        query = SITREPQuery(query="SITREP", context_tracks=tracks)
        result = agent_no_llm.generate_sitrep(query)
        assert isinstance(result, SynthesisQueryOutput)
        assert len(result.sitrep_narrative) > 0

    def test_synthesis_handles_empty_state(self, agent_no_llm):
        query = SITREPQuery(query="SITREP")
        result = agent_no_llm.generate_sitrep(query)
        assert isinstance(result, SynthesisQueryOutput)
        assert 0.0 <= result.confidence <= 1.0

    def test_synthesis_includes_threat_summary(self, agent_no_llm):
        tracks = [_make_track("T-1", "SAM", 0.9), _make_track("T-2", "TEL", 0.7)]
        query = SITREPQuery(query="SITREP", context_tracks=tracks)
        result = agent_no_llm.generate_sitrep(query)
        assert len(result.key_threats) > 0

    def test_synthesis_with_nominations(self, agent_no_llm):
        tracks = [_make_track("T-1")]
        nominations = [_make_nomination("T-1")]
        query = SITREPQuery(query="SITREP", context_tracks=tracks, context_nominations=nominations)
        result = agent_no_llm.generate_sitrep(query)
        assert len(result.data_sources_consulted) > 0

    def test_synthesis_with_bda(self, agent_no_llm):
        tracks = [_make_track("T-1")]
        bda = [_make_bda("T-1")]
        query = SITREPQuery(query="SITREP", context_tracks=tracks, context_bda=bda)
        result = agent_no_llm.generate_sitrep(query)
        assert result.sitrep_narrative

    def test_no_agent_raises_not_implemented(self, agent_no_llm):
        query = SITREPQuery(query="SITREP")
        try:
            agent_no_llm.generate_sitrep(query)
        except NotImplementedError:
            pytest.fail("generate_sitrep raised NotImplementedError with llm_client=None")
