"""
New tests for PatternAnalyzerAgent._generate_response() heuristic.
These must FAIL before implementation and PASS after.
"""

import pytest
from agents.pattern_analyzer import PatternAnalyzerAgent
from schemas.ontology import PatternAnalyzerOutput


@pytest.fixture
def agent_no_llm():
    return PatternAnalyzerAgent(llm_client=None)


class TestPatternAnalyzerHeuristicResponse:
    def test_pattern_analyzer_returns_patterns(self, agent_no_llm):
        result = agent_no_llm.analyze_patterns("Bravo")
        assert isinstance(result, PatternAnalyzerOutput)
        assert result.sector_assessed == "Bravo"

    def test_pattern_analyzer_handles_no_targets(self, agent_no_llm):
        result = agent_no_llm.analyze_patterns("Zulu")
        assert isinstance(result, PatternAnalyzerOutput)
        assert result.sector_assessed == "Zulu"

    def test_pattern_analyzer_uses_assessment(self, agent_no_llm):
        result = agent_no_llm.analyze_patterns("Bravo")
        assert isinstance(result.anomalies, list)
        assert isinstance(result.historical_window_days, int)
        assert result.historical_window_days > 0

    def test_pattern_analyzer_bravo_detects_anomalies(self, agent_no_llm):
        result = agent_no_llm.analyze_patterns("Bravo")
        assert len(result.anomalies) > 0

    def test_pattern_analyzer_returns_summary(self, agent_no_llm):
        result = agent_no_llm.analyze_patterns("Bravo")
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_no_agent_raises_not_implemented(self, agent_no_llm):
        try:
            agent_no_llm.analyze_patterns("Bravo")
        except NotImplementedError:
            pytest.fail("analyze_patterns raised NotImplementedError with llm_client=None")
