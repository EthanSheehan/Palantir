"""Async JSONL event logger with daily rotation.

Events are enqueued non-blocking via ``log_event()`` and drained to
``logs/events-{date}.jsonl`` by a background asyncio task.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

LOG_DIR = Path("logs")

_queue: asyncio.Queue[dict] | None = None
_writer_task_handle: asyncio.Task | None = None


async def _writer_loop() -> None:
    """Background coroutine that drains the queue to disk.

    Keeps the file handle open to avoid per-event open/close syscalls.
    Reopens the handle when the date changes (daily rotation).
    """
    assert _queue is not None
    LOG_DIR.mkdir(exist_ok=True)
    current_date = date.today()
    log_path = LOG_DIR / f"events-{current_date.isoformat()}.jsonl"
    f = open(log_path, "a")
    try:
        while True:
            event = await _queue.get()
            today = date.today()
            if today != current_date:
                # Date changed — rotate to new file
                f.flush()
                f.close()
                current_date = today
                log_path = LOG_DIR / f"events-{current_date.isoformat()}.jsonl"
                f = open(log_path, "a")
            f.write(json.dumps(event, default=str) + "\n")
            f.flush()
            _queue.task_done()
    finally:
        f.close()


def log_event(event_type: str, data: dict) -> None:
    """Non-blocking enqueue.  Safe to call from sync or async contexts."""
    if _queue is None:
        return  # logger not started yet — silently drop
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "data": data,
    }
    try:
        _queue.put_nowait(event)
    except asyncio.QueueFull:
        pass  # drop rather than block the sim loop


async def start_logger(maxsize: int = 10_000) -> None:
    """Create the queue and spawn the background writer task."""
    global _queue, _writer_task_handle
    if _queue is not None:
        return  # already running
    _queue = asyncio.Queue(maxsize=maxsize)
    _writer_task_handle = asyncio.create_task(_writer_loop())


async def stop_logger() -> None:
    """Drain remaining events and cancel the writer task."""
    global _queue, _writer_task_handle
    if _writer_task_handle is None:
        return
    # drain
    if _queue is not None:
        await _queue.join()
    _writer_task_handle.cancel()
    try:
        await _writer_task_handle
    except asyncio.CancelledError:
        pass
    _writer_task_handle = None
    _queue = None


def rotate_logs(max_days: int = 7) -> None:
    """Delete event log files older than max_days, keeping the most recent ones."""
    files = sorted(glob.glob(str(LOG_DIR / "events-*.jsonl")))
    if len(files) > max_days:
        for old in files[:-max_days]:
            try:
                os.remove(old)
            except OSError:
                pass
