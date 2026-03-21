"""Tests for the ROE (Rules of Engagement) Engine — W3-001."""

from __future__ import annotations

import time

import pytest
import yaml
from roe_engine import ROEChangeLog, ROEDecision, ROEEngine, ROERule

# ---------------------------------------------------------------------------
# ROEDecision enum
# ---------------------------------------------------------------------------


class TestROEDecision:
    def test_values_exist(self):
        assert ROEDecision.PERMITTED.value == "PERMITTED"
        assert ROEDecision.DENIED.value == "DENIED"
        assert ROEDecision.ESCALATE.value == "ESCALATE"

    def test_enum_members(self):
        assert set(ROEDecision) == {ROEDecision.PERMITTED, ROEDecision.DENIED, ROEDecision.ESCALATE}


# ---------------------------------------------------------------------------
# ROERule frozen dataclass
# ---------------------------------------------------------------------------


class TestROERule:
    def test_frozen(self):
        rule = ROERule(name="test", decision=ROEDecision.DENIED)
        with pytest.raises(AttributeError):
            rule.name = "changed"

    def test_defaults(self):
        rule = ROERule(name="test", decision=ROEDecision.PERMITTED)
        assert rule.target_type is None
        assert rule.zone_id is None
        assert rule.min_autonomy_level is None
        assert rule.max_collateral_radius_m is None

    def test_full_construction(self):
        rule = ROERule(
            name="SAM allowed",
            target_type="SAM",
            zone_id="zone_alpha",
            min_autonomy_level="SUPERVISED",
            max_collateral_radius_m=500.0,
            decision=ROEDecision.PERMITTED,
        )
        assert rule.target_type == "SAM"
        assert rule.zone_id == "zone_alpha"
        assert rule.min_autonomy_level == "SUPERVISED"
        assert rule.max_collateral_radius_m == 500.0


# ---------------------------------------------------------------------------
# ROEEngine.evaluate — basic decisions
# ---------------------------------------------------------------------------


class TestROEEngineBasicDecisions:
    def test_permitted(self):
        rules = [ROERule(name="allow SAM", target_type="SAM", decision=ROEDecision.PERMITTED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.PERMITTED

    def test_denied(self):
        rules = [ROERule(name="deny all", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="TRUCK", zone_id=None, autonomy_level="MANUAL") == ROEDecision.DENIED

    def test_escalate(self):
        rules = [ROERule(name="escalate", decision=ROEDecision.ESCALATE)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="TEL", zone_id=None, autonomy_level="SUPERVISED") == ROEDecision.ESCALATE

    def test_no_rules_default_escalate(self):
        engine = ROEEngine([])
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.ESCALATE

    def test_no_matching_rules_default_escalate(self):
        rules = [ROERule(name="SAM only", target_type="SAM", decision=ROEDecision.PERMITTED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="TRUCK", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.ESCALATE


# ---------------------------------------------------------------------------
# Rule ordering — first DENIED wins
# ---------------------------------------------------------------------------


class TestROERuleOrdering:
    def test_first_denied_wins(self):
        rules = [
            ROERule(name="deny trucks", target_type="TRUCK", decision=ROEDecision.DENIED),
            ROERule(name="allow all", decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="TRUCK", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.DENIED

    def test_denied_overrides_permitted(self):
        rules = [
            ROERule(name="allow SAM", target_type="SAM", decision=ROEDecision.PERMITTED),
            ROERule(name="deny zone", zone_id="civilian_area", decision=ROEDecision.DENIED),
        ]
        engine = ROEEngine(rules)
        # SAM in civilian zone — DENIED should override PERMITTED
        assert (
            engine.evaluate(target_type="SAM", zone_id="civilian_area", autonomy_level="AUTONOMOUS")
            == ROEDecision.DENIED
        )

    def test_permitted_when_no_denied(self):
        rules = [
            ROERule(name="allow SAM", target_type="SAM", decision=ROEDecision.PERMITTED),
            ROERule(name="escalate rest", decision=ROEDecision.ESCALATE),
        ]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.PERMITTED


# ---------------------------------------------------------------------------
# Wildcard zone matching
# ---------------------------------------------------------------------------


class TestROEWildcardZone:
    def test_wildcard_prefix(self):
        rules = [ROERule(name="deny civilian zones", zone_id="civilian_*", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert (
            engine.evaluate(target_type="SAM", zone_id="civilian_north", autonomy_level="AUTONOMOUS")
            == ROEDecision.DENIED
        )

    def test_wildcard_no_match(self):
        rules = [ROERule(name="deny civilian zones", zone_id="civilian_*", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert (
            engine.evaluate(target_type="SAM", zone_id="military_base", autonomy_level="AUTONOMOUS")
            == ROEDecision.ESCALATE
        )

    def test_exact_zone_match(self):
        rules = [ROERule(name="deny zone_a", zone_id="zone_a", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id="zone_a", autonomy_level="AUTONOMOUS") == ROEDecision.DENIED

    def test_wildcard_star_only_matches_all(self):
        rules = [ROERule(name="deny all zones", zone_id="*", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id="anything", autonomy_level="AUTONOMOUS") == ROEDecision.DENIED

    def test_none_zone_matches_none_rule(self):
        rules = [ROERule(name="deny unzoned", zone_id=None, decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.DENIED

    def test_wildcard_zone_does_not_match_none_zone(self):
        rules = [ROERule(name="deny civilian zones", zone_id="civilian_*", decision=ROEDecision.DENIED)]
        engine = ROEEngine(rules)
        # zone_id=None should not match "civilian_*"
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.ESCALATE


# ---------------------------------------------------------------------------
# min_autonomy_level enforcement
# ---------------------------------------------------------------------------

AUTONOMY_LEVELS = {"MANUAL": 0, "SUPERVISED": 1, "AUTONOMOUS": 2}


class TestROEAutonomyLevel:
    def test_autonomy_below_minimum_no_match(self):
        rules = [
            ROERule(name="supervised+", min_autonomy_level="SUPERVISED", decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        # MANUAL < SUPERVISED — rule should not match
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="MANUAL") == ROEDecision.ESCALATE

    def test_autonomy_meets_minimum(self):
        rules = [
            ROERule(name="supervised+", min_autonomy_level="SUPERVISED", decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="SUPERVISED") == ROEDecision.PERMITTED

    def test_autonomy_exceeds_minimum(self):
        rules = [
            ROERule(name="supervised+", min_autonomy_level="SUPERVISED", decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.PERMITTED

    def test_autonomous_required(self):
        rules = [
            ROERule(name="auto only", min_autonomy_level="AUTONOMOUS", decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="SUPERVISED") == ROEDecision.ESCALATE
        assert engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS") == ROEDecision.PERMITTED


# ---------------------------------------------------------------------------
# Collateral radius check
# ---------------------------------------------------------------------------


class TestROECollateralRadius:
    def test_within_max_radius(self):
        rules = [
            ROERule(name="low collateral", max_collateral_radius_m=100.0, decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert (
            engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS", collateral_radius_m=50.0)
            == ROEDecision.PERMITTED
        )

    def test_exceeds_max_radius(self):
        rules = [
            ROERule(name="low collateral", max_collateral_radius_m=100.0, decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        # 150 > 100 — rule should not match
        assert (
            engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS", collateral_radius_m=150.0)
            == ROEDecision.ESCALATE
        )

    def test_exact_max_radius(self):
        rules = [
            ROERule(name="low collateral", max_collateral_radius_m=100.0, decision=ROEDecision.PERMITTED),
        ]
        engine = ROEEngine(rules)
        assert (
            engine.evaluate(target_type="SAM", zone_id=None, autonomy_level="AUTONOMOUS", collateral_radius_m=100.0)
            == ROEDecision.PERMITTED
        )


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestROEYAMLLoading:
    def test_load_from_yaml(self, tmp_path):
        yaml_content = {
            "rules": [
                {"name": "deny civilian", "zone_id": "civilian_*", "decision": "DENIED"},
                {"name": "allow SAM", "target_type": "SAM", "decision": "PERMITTED"},
                {"name": "catch-all", "decision": "ESCALATE"},
            ]
        }
        yaml_file = tmp_path / "test_roe.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        engine = ROEEngine.load_from_yaml(str(yaml_file))
        assert len(engine.rules) == 3
        assert engine.rules[0].name == "deny civilian"
        assert engine.rules[0].decision == ROEDecision.DENIED

    def test_load_with_all_fields(self, tmp_path):
        yaml_content = {
            "rules": [
                {
                    "name": "complex rule",
                    "target_type": "TEL",
                    "zone_id": "zone_a",
                    "min_autonomy_level": "SUPERVISED",
                    "max_collateral_radius_m": 200.0,
                    "decision": "PERMITTED",
                },
            ]
        }
        yaml_file = tmp_path / "test_roe.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))

        engine = ROEEngine.load_from_yaml(str(yaml_file))
        rule = engine.rules[0]
        assert rule.target_type == "TEL"
        assert rule.zone_id == "zone_a"
        assert rule.min_autonomy_level == "SUPERVISED"
        assert rule.max_collateral_radius_m == 200.0

    def test_load_empty_rules(self, tmp_path):
        yaml_file = tmp_path / "test_roe.yaml"
        yaml_file.write_text(yaml.dump({"rules": []}))
        engine = ROEEngine.load_from_yaml(str(yaml_file))
        assert len(engine.rules) == 0

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            ROEEngine.load_from_yaml("/nonexistent/path.yaml")

    def test_load_invalid_decision(self, tmp_path):
        yaml_content = {"rules": [{"name": "bad", "decision": "INVALID_VALUE"}]}
        yaml_file = tmp_path / "test_roe.yaml"
        yaml_file.write_text(yaml.dump(yaml_content))
        with pytest.raises(ValueError):
            ROEEngine.load_from_yaml(str(yaml_file))


# ---------------------------------------------------------------------------
# ROEChangeLog
# ---------------------------------------------------------------------------


class TestROEChangeLog:
    def test_append_and_retrieve(self):
        log = ROEChangeLog()
        rule = ROERule(name="test", decision=ROEDecision.PERMITTED)
        log.record("ADD", rule_before=None, rule_after=rule)
        entries = log.entries
        assert len(entries) == 1
        assert entries[0].action == "ADD"
        assert entries[0].rule_before is None
        assert entries[0].rule_after == rule

    def test_entries_are_immutable_copy(self):
        log = ROEChangeLog()
        rule = ROERule(name="test", decision=ROEDecision.PERMITTED)
        log.record("ADD", rule_before=None, rule_after=rule)
        entries1 = log.entries
        entries2 = log.entries
        assert entries1 == entries2
        assert entries1 is not entries2  # should be a copy

    def test_multiple_entries(self):
        log = ROEChangeLog()
        r1 = ROERule(name="old", decision=ROEDecision.PERMITTED)
        r2 = ROERule(name="new", decision=ROEDecision.DENIED)
        log.record("ADD", rule_before=None, rule_after=r1)
        log.record("MODIFY", rule_before=r1, rule_after=r2)
        log.record("REMOVE", rule_before=r2, rule_after=None)
        assert len(log.entries) == 3

    def test_entry_has_timestamp(self):
        log = ROEChangeLog()
        before = time.time()
        log.record("ADD", rule_before=None, rule_after=ROERule(name="t", decision=ROEDecision.DENIED))
        after = time.time()
        entry = log.entries[0]
        assert before <= entry.timestamp <= after

    def test_entry_frozen(self):
        log = ROEChangeLog()
        log.record("ADD", rule_before=None, rule_after=ROERule(name="t", decision=ROEDecision.DENIED))
        entry = log.entries[0]
        with pytest.raises(AttributeError):
            entry.action = "CHANGED"


# ---------------------------------------------------------------------------
# Complex multi-rule scenarios
# ---------------------------------------------------------------------------


class TestROEComplexScenarios:
    def _build_romania_engine(self) -> ROEEngine:
        return ROEEngine(
            [
                ROERule(name="No engagement in civilian zones", zone_id="civilian_*", decision=ROEDecision.DENIED),
                ROERule(name="SAM sites always permitted", target_type="SAM", decision=ROEDecision.PERMITTED),
                ROERule(
                    name="Default requires SUPERVISED+",
                    min_autonomy_level="SUPERVISED",
                    decision=ROEDecision.PERMITTED,
                ),
                ROERule(name="Catch-all escalate", decision=ROEDecision.ESCALATE),
            ]
        )

    def test_romania_sam_permitted(self):
        engine = self._build_romania_engine()
        assert (
            engine.evaluate(target_type="SAM", zone_id="military", autonomy_level="AUTONOMOUS") == ROEDecision.PERMITTED
        )

    def test_romania_sam_in_civilian_zone_denied(self):
        engine = self._build_romania_engine()
        assert (
            engine.evaluate(target_type="SAM", zone_id="civilian_west", autonomy_level="AUTONOMOUS")
            == ROEDecision.DENIED
        )

    def test_romania_truck_supervised_permitted(self):
        engine = self._build_romania_engine()
        assert (
            engine.evaluate(target_type="TRUCK", zone_id="military", autonomy_level="SUPERVISED")
            == ROEDecision.PERMITTED
        )

    def test_romania_truck_manual_escalate(self):
        engine = self._build_romania_engine()
        assert engine.evaluate(target_type="TRUCK", zone_id="military", autonomy_level="MANUAL") == ROEDecision.ESCALATE

    def test_romania_tel_in_civilian_denied(self):
        engine = self._build_romania_engine()
        assert (
            engine.evaluate(target_type="TEL", zone_id="civilian_east", autonomy_level="AUTONOMOUS")
            == ROEDecision.DENIED
        )

    def test_collateral_and_zone_combined(self):
        rules = [
            ROERule(name="deny civilian", zone_id="civilian_*", decision=ROEDecision.DENIED),
            ROERule(name="low collateral only", max_collateral_radius_m=50.0, decision=ROEDecision.PERMITTED),
            ROERule(name="catch-all", decision=ROEDecision.ESCALATE),
        ]
        engine = ROEEngine(rules)
        # Military zone, low collateral → PERMITTED
        assert (
            engine.evaluate(
                target_type="TEL", zone_id="military", autonomy_level="AUTONOMOUS", collateral_radius_m=30.0
            )
            == ROEDecision.PERMITTED
        )
        # Military zone, high collateral → ESCALATE (rule doesn't match)
        assert (
            engine.evaluate(
                target_type="TEL", zone_id="military", autonomy_level="AUTONOMOUS", collateral_radius_m=100.0
            )
            == ROEDecision.ESCALATE
        )
