from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def client():
    from api_main import app

    return TestClient(app)


def test_health_endpoint_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_has_status_ok(client):
    response = client.get("/health")
    assert response.json()["status"] == "ok"


def test_health_includes_version(client):
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] == "2.0.0"


def test_ready_endpoint_returns_200(client):
    response = client.get("/ready")
    assert response.status_code == 200


def test_ready_endpoint_returns_sim_initialized(client):
    response = client.get("/ready")
    data = response.json()
    assert "sim_initialized" in data
    assert data["sim_initialized"] is True
