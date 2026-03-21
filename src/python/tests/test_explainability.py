"""Tests for the AI Explainability Layer (W4-001)."""

from __future__ import annotations

import pytest


@pytest.fixture
def engine():
    from explainability import ExplainabilityEngine

    return ExplainabilityEngine()


# ---------------------------------------------------------------------------
# DecisionExplanation creation
# ---------------------------------------------------------------------------


class TestDecisionExplanation:
    def test_create_with_all_fields(self):
        from explainability import DecisionExplanation

        exp = DecisionExplanation(
            action="NOMINATE",
            source="AI: Gemini-2.0",
            confidence=0.85,
            top_factors=[
                {"name": "threat_level", "weight": 0.6, "description": "High threat SAM site"},
            ],
            roe_rule_satisfied="ROE-1: Engage hostile",
            alternatives_rejected=[
                {"action": "OBSERVE_ONLY", "reason": "Threat too high for passive observation"},
            ],
            counterfactual_threshold="Confidence below 0.7 would trigger OBSERVE_ONLY",
            timestamp="2026-03-21T12:00:00Z",
        )
        assert exp.action == "NOMINATE"
        assert exp.source == "AI: Gemini-2.0"
        assert exp.confidence == 0.85
        assert len(exp.top_factors) == 1
        assert exp.roe_rule_satisfied == "ROE-1: Engage hostile"
        assert len(exp.alternatives_rejected) == 1
        assert exp.counterfactual_threshold is not None
        assert exp.timestamp == "2026-03-21T12:00:00Z"

    def test_frozen(self):
        from explainability import DecisionExplanation

        exp = DecisionExplanation(
            action="NOMINATE",
            source="Heuristic: Rule 3",
            confidence=0.9,
            top_factors=[],
            roe_rule_satisfied=None,
            alternatives_rejected=[],
            counterfactual_threshold=None,
            timestamp="2026-03-21T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            exp.action = "INTERCEPT"

    def test_confidence_bounds_low(self):
        from explainability import DecisionExplanation

        with pytest.raises((ValueError, TypeError)):
            DecisionExplanation(
                action="NOMINATE",
                source="test",
                confidence=-0.1,
                top_factors=[],
                roe_rule_satisfied=None,
                alternatives_rejected=[],
                counterfactual_threshold=None,
                timestamp="2026-03-21T12:00:00Z",
            )

    def test_confidence_bounds_high(self):
        from explainability import DecisionExplanation

        with pytest.raises((ValueError, TypeError)):
            DecisionExplanation(
                action="NOMINATE",
                source="test",
                confidence=1.1,
                top_factors=[],
                roe_rule_satisfied=None,
                alternatives_rejected=[],
                counterfactual_threshold=None,
                timestamp="2026-03-21T12:00:00Z",
            )

    def test_top_factors_limited_to_3(self):
        from explainability import DecisionExplanation

        factors = [{"name": f"factor_{i}", "weight": 0.1, "description": f"desc {i}"} for i in range(5)]
        with pytest.raises((ValueError, TypeError)):
            DecisionExplanation(
                action="NOMINATE",
                source="test",
                confidence=0.5,
                top_factors=factors,
                roe_rule_satisfied=None,
                alternatives_rejected=[],
                counterfactual_threshold=None,
                timestamp="2026-03-21T12:00:00Z",
            )

    def test_optional_fields_can_be_none(self):
        from explainability import DecisionExplanation

        exp = DecisionExplanation(
            action="OBSERVE",
            source="Heuristic: Rule 1",
            confidence=0.5,
            top_factors=[],
            roe_rule_satisfied=None,
            alternatives_rejected=[],
            counterfactual_threshold=None,
            timestamp="2026-03-21T12:00:00Z",
        )
        assert exp.roe_rule_satisfied is None
        assert exp.counterfactual_threshold is None

    def test_to_dict(self):
        from explainability import DecisionExplanation

        exp = DecisionExplanation(
            action="NOMINATE",
            source="AI: Gemini-2.0",
            confidence=0.85,
            top_factors=[{"name": "x", "weight": 0.5, "description": "y"}],
            roe_rule_satisfied="ROE-1",
            alternatives_rejected=[],
            counterfactual_threshold=None,
            timestamp="2026-03-21T12:00:00Z",
        )
        d = exp.to_dict()
        assert isinstance(d, dict)
        assert d["action"] == "NOMINATE"
        assert d["confidence"] == 0.85


# ---------------------------------------------------------------------------
# Source label formatting
# ---------------------------------------------------------------------------


class TestSourceLabel:
    def test_gemini_label(self):
        from explainability import format_source_label

        label = format_source_label("gemini", "gemini-2.0-flash")
        assert "Gemini" in label
        assert "gemini-2.0-flash" in label

    def test_anthropic_label(self):
        from explainability import format_source_label

        label = format_source_label("anthropic", "claude-sonnet-4-6")
        assert "Anthropic" in label
        assert "claude-sonnet-4-6" in label

    def test_heuristic_label(self):
        from explainability import format_source_label

        label = format_source_label("fallback", None)
        assert "Heuristic" in label

    def test_ollama_label(self):
        from explainability import format_source_label

        label = format_source_label("ollama", "llama3.2:8b")
        assert "Ollama" in label
        assert "llama3.2:8b" in label

    def test_unknown_provider(self):
        from explainability import format_source_label

        label = format_source_label("unknown_provider", "model-x")
        assert "unknown_provider" in label


# ---------------------------------------------------------------------------
# ExplainabilityEngine.explain_nomination
# ---------------------------------------------------------------------------


class TestExplainNomination:
    def test_basic_nomination(self, engine):
        target = {"target_id": 1, "target_type": "SAM", "detection_confidence": 0.9}
        fusion_result = {"confidence": 0.92, "sensor_count": 3}
        roe_decision = "PERMITTED"
        autonomy_level = "SUPERVISED"

        exp = engine.explain_nomination(target, fusion_result, roe_decision, autonomy_level)

        assert exp.action == "NOMINATE"
        assert exp.confidence > 0.0
        assert len(exp.top_factors) <= 3
        assert exp.roe_rule_satisfied is not None
        assert exp.timestamp

    def test_nomination_includes_target_type_factor(self, engine):
        target = {"target_id": 1, "target_type": "TEL", "detection_confidence": 0.95}
        fusion_result = {"confidence": 0.95, "sensor_count": 2}
        roe_decision = "PERMITTED"

        exp = engine.explain_nomination(target, fusion_result, roe_decision, "AUTONOMOUS")
        factor_names = [f["name"] for f in exp.top_factors]
        assert any("target" in n.lower() or "threat" in n.lower() or "type" in n.lower() for n in factor_names)

    def test_nomination_with_denied_roe(self, engine):
        target = {"target_id": 2, "target_type": "TRUCK", "detection_confidence": 0.6}
        fusion_result = {"confidence": 0.6, "sensor_count": 1}
        roe_decision = "DENIED"

        exp = engine.explain_nomination(target, fusion_result, roe_decision, "MANUAL")
        assert "DENIED" in (exp.roe_rule_satisfied or "")

    def test_nomination_with_low_confidence(self, engine):
        target = {"target_id": 3, "target_type": "UNKNOWN", "detection_confidence": 0.3}
        fusion_result = {"confidence": 0.3, "sensor_count": 1}
        roe_decision = "ESCALATE"

        exp = engine.explain_nomination(target, fusion_result, roe_decision, "SUPERVISED")
        assert exp.confidence <= 0.5


# ---------------------------------------------------------------------------
# ExplainabilityEngine.explain_coa
# ---------------------------------------------------------------------------


class TestExplainCOA:
    def test_basic_coa(self, engine):
        coa = {
            "id": "COA-1",
            "effector_name": "JDAM",
            "pk_estimate": 0.85,
            "time_to_effect_min": 5.0,
            "risk_score": 3.0,
        }
        target = {"target_type": "SAM", "target_id": 1}
        alternatives = [
            {"id": "COA-2", "effector_name": "Hellfire", "pk_estimate": 0.7, "reason": "Lower Pk"},
        ]
        roe_decision = "PERMITTED"

        exp = engine.explain_coa(coa, target, alternatives, roe_decision)
        assert exp.action == "AUTHORIZE_COA"
        assert exp.confidence > 0.0
        assert len(exp.alternatives_rejected) >= 1

    def test_coa_includes_effector_in_factors(self, engine):
        coa = {
            "id": "COA-1",
            "effector_name": "JDAM",
            "pk_estimate": 0.9,
            "time_to_effect_min": 3.0,
            "risk_score": 2.0,
        }
        target = {"target_type": "TEL", "target_id": 2}

        exp = engine.explain_coa(coa, target, [], "PERMITTED")
        factor_names = [f["name"] for f in exp.top_factors]
        assert len(factor_names) > 0

    def test_coa_alternatives_in_explanation(self, engine):
        coa = {"id": "COA-1", "effector_name": "JDAM", "pk_estimate": 0.9, "time_to_effect_min": 3.0, "risk_score": 2.0}
        target = {"target_type": "SAM", "target_id": 1}
        alternatives = [
            {"id": "COA-2", "effector_name": "Hellfire", "pk_estimate": 0.7, "reason": "Lower Pk"},
            {"id": "COA-3", "effector_name": "SDB", "pk_estimate": 0.6, "reason": "Too slow"},
        ]

        exp = engine.explain_coa(coa, target, alternatives, "PERMITTED")
        assert len(exp.alternatives_rejected) == 2


# ---------------------------------------------------------------------------
# ExplainabilityEngine.explain_intercept
# ---------------------------------------------------------------------------


class TestExplainIntercept:
    def test_basic_intercept(self, engine):
        enemy = {"id": 1001, "type": "ATTACK", "fused_confidence": 0.85}
        drone = {"id": 1, "mode": "IDLE"}
        threat_level = "HIGH"

        exp = engine.explain_intercept(enemy, drone, threat_level)
        assert exp.action == "INTERCEPT"
        assert exp.confidence > 0.0
        assert len(exp.top_factors) <= 3

    def test_intercept_threat_in_factors(self, engine):
        enemy = {"id": 1002, "type": "JAMMING", "fused_confidence": 0.75}
        drone = {"id": 2, "mode": "SEARCH"}
        threat_level = "MEDIUM"

        exp = engine.explain_intercept(enemy, drone, threat_level)
        factor_names = [f["name"] for f in exp.top_factors]
        assert any("threat" in n.lower() for n in factor_names)

    def test_intercept_counterfactual(self, engine):
        enemy = {"id": 1003, "type": "RECON", "fused_confidence": 0.6}
        drone = {"id": 3, "mode": "IDLE"}

        exp = engine.explain_intercept(enemy, drone, "LOW")
        assert exp.counterfactual_threshold is not None


# ---------------------------------------------------------------------------
# Integration with HITL entries
# ---------------------------------------------------------------------------


class TestHITLIntegration:
    def test_explanation_serializable_for_hitl(self, engine):
        target = {"target_id": 1, "target_type": "SAM", "detection_confidence": 0.9}
        fusion_result = {"confidence": 0.92, "sensor_count": 3}

        exp = engine.explain_nomination(target, fusion_result, "PERMITTED", "SUPERVISED")
        d = exp.to_dict()

        assert isinstance(d, dict)
        assert "action" in d
        assert "source" in d
        assert "confidence" in d
        assert "top_factors" in d
        assert "roe_rule_satisfied" in d
        assert "alternatives_rejected" in d
        assert "timestamp" in d

    def test_explanation_fits_hitl_entry_field(self, engine):
        """The to_dict() output should be usable as the 'explanation' field on a HITL entry."""
        target = {"target_id": 5, "target_type": "TEL", "detection_confidence": 0.88}
        fusion_result = {"confidence": 0.88, "sensor_count": 2}

        exp = engine.explain_nomination(target, fusion_result, "PERMITTED", "AUTONOMOUS")
        d = exp.to_dict()

        # Simulate attaching to a HITL-style dict
        hitl_entry = {"id": "SB-TEST", "status": "PENDING", "explanation": d}
        assert hitl_entry["explanation"]["action"] == "NOMINATE"


# ---------------------------------------------------------------------------
# ROE rule reference in explanation
# ---------------------------------------------------------------------------


class TestROERuleReference:
    def test_permitted_roe_in_explanation(self, engine):
        target = {"target_id": 1, "target_type": "SAM", "detection_confidence": 0.9}
        fusion = {"confidence": 0.9, "sensor_count": 2}

        exp = engine.explain_nomination(target, fusion, "PERMITTED", "SUPERVISED")
        assert "PERMITTED" in exp.roe_rule_satisfied

    def test_escalate_roe_in_explanation(self, engine):
        target = {"target_id": 2, "target_type": "UNKNOWN", "detection_confidence": 0.5}
        fusion = {"confidence": 0.5, "sensor_count": 1}

        exp = engine.explain_nomination(target, fusion, "ESCALATE", "MANUAL")
        assert "ESCALATE" in exp.roe_rule_satisfied
