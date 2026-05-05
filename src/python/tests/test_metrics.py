"""Tests for src/python/metrics.py and the /metrics HTTP endpoint."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset module state before each test for isolation."""
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def client():
    from api_main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit: counter helpers
# ---------------------------------------------------------------------------


def test_increment_detection_increments_counter():
    metrics.increment_detection()
    snap = metrics.get_snapshot()
    assert snap.detection_events_total == 1


def test_increment_detection_multiple():
    for _ in range(5):
        metrics.increment_detection()
    snap = metrics.get_snapshot()
    assert snap.detection_events_total == 5


def test_increment_approval():
    metrics.increment_approval()
    snap = metrics.get_snapshot()
    assert snap.hitl_approvals_total == 1


def test_increment_rejection():
    metrics.increment_rejection()
    snap = metrics.get_snapshot()
    assert snap.hitl_rejections_total == 1


def test_counters_are_independent():
    metrics.increment_detection()
    metrics.increment_approval()
    metrics.increment_rejection()
    snap = metrics.get_snapshot()
    assert snap.detection_events_total == 1
    assert snap.hitl_approvals_total == 1
    assert snap.hitl_rejections_total == 1


# ---------------------------------------------------------------------------
# Unit: gauge helpers
# ---------------------------------------------------------------------------


def test_update_gauges_sets_clients():
    metrics.update_gauges(client_count=3, target_count=5, drone_count=2, autonomy_level="SUPERVISED")
    snap = metrics.get_snapshot()
    assert snap.connected_clients == 3


def test_update_gauges_sets_targets():
    metrics.update_gauges(client_count=0, target_count=7, drone_count=0, autonomy_level="MANUAL")
    snap = metrics.get_snapshot()
    assert snap.targets_active == 7


def test_update_gauges_sets_drones():
    metrics.update_gauges(client_count=0, target_count=0, drone_count=4, autonomy_level="MANUAL")
    snap = metrics.get_snapshot()
    assert snap.drones_active == 4


def test_update_gauges_sets_autonomy_level():
    metrics.update_gauges(client_count=0, target_count=0, drone_count=0, autonomy_level="AUTONOMOUS")
    snap = metrics.get_snapshot()
    assert snap.autonomy_level == "AUTONOMOUS"


def test_update_gauges_overwrites_previous():
    metrics.update_gauges(client_count=5, target_count=0, drone_count=0, autonomy_level="MANUAL")
    metrics.update_gauges(client_count=2, target_count=0, drone_count=0, autonomy_level="MANUAL")
    snap = metrics.get_snapshot()
    assert snap.connected_clients == 2


# ---------------------------------------------------------------------------
# Unit: tick histogram
# ---------------------------------------------------------------------------


def test_record_tick_accumulates():
    metrics.record_tick(0.05)
    metrics.record_tick(0.10)
    snap = metrics.get_snapshot()
    assert snap.tick_count == 2
    assert abs(snap.tick_duration_sum - 0.15) < 1e-9


def test_record_tick_empty_snapshot():
    snap = metrics.get_snapshot()
    assert snap.tick_count == 0
    assert snap.tick_duration_sum == 0.0


# ---------------------------------------------------------------------------
# Unit: generate_metrics_text format
# ---------------------------------------------------------------------------


def test_generate_metrics_text_returns_string():
    text = metrics.generate_metrics_text()
    assert isinstance(text, str)


def test_generate_metrics_text_contains_tick_histogram():
    metrics.record_tick(0.01)
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_tick_duration_seconds" in text
    assert "grid_sentinel_tick_duration_seconds_count 1" in text


def test_generate_metrics_text_contains_connected_clients():
    metrics.update_gauges(client_count=3, target_count=0, drone_count=0, autonomy_level="MANUAL")
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_connected_clients 3" in text


def test_generate_metrics_text_contains_detection_counter():
    metrics.increment_detection()
    metrics.increment_detection()
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_detection_events_total 2" in text


def test_generate_metrics_text_contains_hitl_approvals():
    metrics.increment_approval()
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_hitl_approvals_total 1" in text


def test_generate_metrics_text_contains_hitl_rejections():
    metrics.increment_rejection()
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_hitl_rejections_total 1" in text


def test_generate_metrics_text_contains_targets_gauge():
    metrics.update_gauges(client_count=0, target_count=8, drone_count=0, autonomy_level="MANUAL")
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_targets_active 8" in text


def test_generate_metrics_text_contains_drones_gauge():
    metrics.update_gauges(client_count=0, target_count=0, drone_count=6, autonomy_level="MANUAL")
    text = metrics.generate_metrics_text()
    assert "grid_sentinel_drones_active 6" in text


def test_generate_metrics_text_autonomy_level_labels():
    metrics.update_gauges(client_count=0, target_count=0, drone_count=0, autonomy_level="SUPERVISED")
    text = metrics.generate_metrics_text()
    assert 'grid_sentinel_autonomy_level{level="SUPERVISED"} 1' in text
    assert 'grid_sentinel_autonomy_level{level="MANUAL"} 0' in text
    assert 'grid_sentinel_autonomy_level{level="AUTONOMOUS"} 0' in text


def test_generate_metrics_text_has_help_lines():
    text = metrics.generate_metrics_text()
    assert "# HELP grid_sentinel_tick_duration_seconds" in text
    assert "# HELP grid_sentinel_connected_clients" in text
    assert "# HELP grid_sentinel_detection_events_total" in text


def test_generate_metrics_text_has_type_lines():
    text = metrics.generate_metrics_text()
    assert "# TYPE grid_sentinel_tick_duration_seconds histogram" in text
    assert "# TYPE grid_sentinel_connected_clients gauge" in text


def test_generate_metrics_text_ends_with_newline():
    text = metrics.generate_metrics_text()
    assert text.endswith("\n")


# ---------------------------------------------------------------------------
# Integration: /metrics HTTP endpoint
# ---------------------------------------------------------------------------


def test_metrics_endpoint_returns_200(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_content_type(client):
    response = client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]
    assert "0.0.4" in response.headers["content-type"]


def test_metrics_endpoint_returns_prometheus_text(client):
    response = client.get("/metrics")
    text = response.text
    assert "grid_sentinel_connected_clients" in text
    assert "grid_sentinel_tick_duration_seconds" in text


def test_metrics_endpoint_reflects_incremented_counter(client):
    metrics.increment_detection()
    metrics.increment_detection()
    metrics.increment_detection()
    response = client.get("/metrics")
    assert "grid_sentinel_detection_events_total 3" in response.text


def test_metrics_endpoint_reflects_gauge_update(client):
    metrics.update_gauges(client_count=0, target_count=9, drone_count=0, autonomy_level="MANUAL")
    response = client.get("/metrics")
    assert "grid_sentinel_targets_active 9" in response.text
