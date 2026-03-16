"""
Tests for the Synthesis & Query Agent.

All tests are self-contained — no live LLM is required.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from schemas.ontology import (
    SITREPQuery,
    SynthesisQueryOutput,
    Track,
    Detection,
    TargetClassification,
    SensorSource,
    TargetNomination,
    EngagementDecision,
    BattleDamageAssessment,
    BDAResult,
)
from agents.synthesis_query_agent import SynthesisQueryAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_track() -> Track:
    return Track(
        track_id="TRK-001",
        lat=34.0522,
        lon=-118.2437,
        classification=TargetClassification.TEL,
        confidence=0.92,
        detections=[
            Detection(
                source=SensorSource.UAV,
                lat=34.0522,
                lon=-118.2437,
                confidence=0.92,
                classification=TargetClassification.TEL,
                timestamp="2026-03-14T12:00:00Z",
            )
        ],
        is_high_priority=True,
    )


@pytest.fixture
def sample_nomination() -> TargetNomination:
    return TargetNomination(
        track_id="TRK-001",
        decision=EngagementDecision.NOMINATE,
        roe_compliance=True,
        collateral_risk="LOW",
        reasoning="TEL detected with high confidence, clear of civilian structures.",
    )


@pytest.fixture
def sample_bda() -> BattleDamageAssessment:
    return BattleDamageAssessment(
        strike_id="STK-001",
        target_track_id="TRK-001",
        coa_id="COA-1",
        result=BDAResult.DESTROYED,
        confidence=0.95,
        notes="Post-strike imagery confirms destruction.",
    )


@pytest.fixture
def agent() -> SynthesisQueryAgent:
    return SynthesisQueryAgent(llm_client=MagicMock())


VALID_LLM_RESPONSE = json.dumps(
    {
        "sitrep_narrative": "One high-priority TEL detected in sector 4. Strike executed; BDA confirms destruction.",
        "key_threats": ["TEL in sector 4 (destroyed)"],
        "recommended_actions": ["Continue ISR sweep of adjacent sectors."],
        "data_sources_consulted": ["UAV feed", "Post-strike imagery"],
        "confidence": 0.88,
    }
)


# ── Schema Validation Tests ──────────────────────────────────────────────────


class TestSchemaValidation:
    """Verify SITREPQuery and SynthesisQueryOutput accept/reject data correctly."""

    def test_sitrep_query_minimal(self):
        """A query with only the required 'query' field should be valid."""
        q = SITREPQuery(query="What is the current threat picture?")
        assert q.query == "What is the current threat picture?"
        assert q.context_tracks is None
        assert q.context_nominations is None
        assert q.context_bda is None

    def test_sitrep_query_with_context(self, sample_track, sample_nomination, sample_bda):
        """A fully populated query should parse without errors."""
        q = SITREPQuery(
            query="Summarise the last hour.",
            context_tracks=[sample_track],
            context_nominations=[sample_nomination],
            context_bda=[sample_bda],
        )
        assert len(q.context_tracks) == 1
        assert len(q.context_nominations) == 1
        assert len(q.context_bda) == 1

    def test_sitrep_query_missing_query_raises(self):
        """Omitting the required 'query' field should raise ValidationError."""
        with pytest.raises(Exception):
            SITREPQuery()  # type: ignore[call-arg]

    def test_synthesis_output_valid(self):
        """A well-formed output should validate."""
        out = SynthesisQueryOutput.model_validate_json(VALID_LLM_RESPONSE)
        assert out.confidence == 0.88
        assert "TEL" in out.key_threats[0]

    def test_synthesis_output_confidence_bounds(self):
        """Confidence outside 0–1 should be rejected."""
        bad_payload = json.dumps(
            {
                "sitrep_narrative": "N/A",
                "key_threats": [],
                "recommended_actions": [],
                "data_sources_consulted": [],
                "confidence": 1.5,
            }
        )
        with pytest.raises(Exception):
            SynthesisQueryOutput.model_validate_json(bad_payload)


# ── Context Builder Tests ────────────────────────────────────────────────────


class TestContextBuilder:
    """Verify _build_context_payload produces correct JSON."""

    def test_empty_context(self, agent):
        """No context should yield '{}'."""
        q = SITREPQuery(query="What happened?")
        result = agent._build_context_payload(q)
        assert result == "{}"

    def test_context_with_tracks(self, agent, sample_track):
        """Tracks should appear under the 'tracks' key."""
        q = SITREPQuery(query="Status?", context_tracks=[sample_track])
        result = json.loads(agent._build_context_payload(q))
        assert "tracks" in result
        assert result["tracks"][0]["track_id"] == "TRK-001"

    def test_full_context(self, agent, sample_track, sample_nomination, sample_bda):
        """All three context sections should be present."""
        q = SITREPQuery(
            query="Full SITREP",
            context_tracks=[sample_track],
            context_nominations=[sample_nomination],
            context_bda=[sample_bda],
        )
        result = json.loads(agent._build_context_payload(q))
        assert "tracks" in result
        assert "nominations" in result
        assert "bda_results" in result


# ── End-to-End Mock Tests ────────────────────────────────────────────────────


class TestGenerateSITREP:
    """Mock the LLM call and verify the full pipeline."""

    def test_generate_sitrep_returns_valid_output(self, agent, sample_track):
        """Mocked LLM response should parse into a valid SynthesisQueryOutput."""
        with patch.object(agent, "_generate_response", return_value=VALID_LLM_RESPONSE):
            q = SITREPQuery(query="Current threats?", context_tracks=[sample_track])
            output = agent.generate_sitrep(q)

            assert isinstance(output, SynthesisQueryOutput)
            assert output.confidence == 0.88
            assert "TEL" in output.sitrep_narrative

    def test_generate_sitrep_raises_without_llm(self, agent):
        """Without an LLM integration, the stub should raise NotImplementedError."""
        q = SITREPQuery(query="Report?")
        with pytest.raises(NotImplementedError):
            agent.generate_sitrep(q)
