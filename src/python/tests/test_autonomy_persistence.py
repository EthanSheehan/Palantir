"""Tests for autonomy level persistence across theater switches."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    import api_main

    api_main.sim = api_main.SimulationModel(theater_name="romania")
    return TestClient(api_main.app)


class TestAutonomyPersistenceAcrossTheaterSwitch:
    """Autonomy level must survive theater switches."""

    def test_autonomy_persists_after_theater_switch(self, client):
        """Switching theater should preserve the current autonomy level."""
        import api_main

        api_main.sim.autonomy_level = "AUTONOMOUS"

        resp = client.post("/api/theater", json={"theater": "romania"})
        assert resp.status_code == 200

        assert api_main.sim.autonomy_level == "AUTONOMOUS"

    def test_autonomy_persists_supervised(self, client):
        """SUPERVISED autonomy should also persist."""
        import api_main

        api_main.sim.autonomy_level = "SUPERVISED"

        resp = client.post("/api/theater", json={"theater": "romania"})
        assert resp.status_code == 200

        assert api_main.sim.autonomy_level == "SUPERVISED"

    def test_manual_autonomy_persists(self, client):
        """MANUAL (default) should persist without issues."""
        import api_main

        api_main.sim.autonomy_level = "MANUAL"

        resp = client.post("/api/theater", json={"theater": "romania"})
        assert resp.status_code == 200

        assert api_main.sim.autonomy_level == "MANUAL"

    def test_warning_logged_on_non_manual_theater_switch(self, client, caplog):
        """A warning should be logged when switching theaters with non-MANUAL autonomy."""
        import api_main

        api_main.sim.autonomy_level = "AUTONOMOUS"

        with caplog.at_level(logging.WARNING):
            resp = client.post("/api/theater", json={"theater": "romania"})
            assert resp.status_code == 200

        assert any(
            "autonomy" in record.message.lower() and "theater" in record.message.lower()
            for record in caplog.records
            if record.levelno >= logging.WARNING
        )

    def test_no_warning_logged_on_manual_theater_switch(self, client, caplog):
        """No warning when switching theaters with MANUAL autonomy."""
        import api_main

        api_main.sim.autonomy_level = "MANUAL"

        with caplog.at_level(logging.WARNING):
            resp = client.post("/api/theater", json={"theater": "romania"})
            assert resp.status_code == 200

        autonomy_warnings = [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING and "autonomy" in r.message.lower() and "theater" in r.message.lower()
        ]
        assert len(autonomy_warnings) == 0
