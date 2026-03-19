"""Tests for the async JSONL event logger."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

# Ensure src/python is importable
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import event_logger


@pytest.fixture(autouse=True)
def _reset_logger():
    """Reset logger state between tests."""
    event_logger._queue = None
    event_logger._writer_task_handle = None
    yield
    # Cleanup after test
    event_logger._queue = None
    event_logger._writer_task_handle = None


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Redirect LOG_DIR to a temp directory."""
    monkeypatch.setattr(event_logger, "LOG_DIR", tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_start_and_log_event(log_dir):
    """Events enqueued via log_event are written to a JSONL file."""
    await event_logger.start_logger()
    event_logger.log_event("test_event", {"key": "value"})
    await event_logger.stop_logger()

    files = list(log_dir.glob("events-*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "test_event"
    assert record["data"] == {"key": "value"}
    assert "timestamp" in record


@pytest.mark.asyncio
async def test_multiple_events(log_dir):
    """Multiple events are appended to the same file."""
    await event_logger.start_logger()
    for i in range(5):
        event_logger.log_event("evt", {"i": i})
    await event_logger.stop_logger()

    files = list(log_dir.glob("events-*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 5
    for idx, line in enumerate(lines):
        assert json.loads(line)["data"]["i"] == idx


@pytest.mark.asyncio
async def test_log_event_before_start():
    """log_event before start_logger silently drops the event."""
    # Should not raise
    event_logger.log_event("dropped", {"x": 1})


@pytest.mark.asyncio
async def test_json_format(log_dir):
    """Each line is valid JSON with required fields."""
    await event_logger.start_logger()
    event_logger.log_event("detection", {"target_id": 42, "type": "SAM"})
    await event_logger.stop_logger()

    files = list(log_dir.glob("events-*.jsonl"))
    record = json.loads(files[0].read_text().strip())
    assert set(record.keys()) == {"timestamp", "event_type", "data"}
    assert record["timestamp"].endswith("+00:00")


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    """Calling stop_logger when not started doesn't raise."""
    await event_logger.stop_logger()


@pytest.mark.asyncio
async def test_start_is_idempotent(log_dir):
    """Calling start_logger twice reuses the existing queue."""
    await event_logger.start_logger()
    q1 = event_logger._queue
    await event_logger.start_logger()
    assert event_logger._queue is q1
    await event_logger.stop_logger()
