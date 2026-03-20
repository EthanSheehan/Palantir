"""IntelFeedRouter — subscription-filtered broadcast for typed event streams.

Clients can subscribe to named feeds (INTEL_FEED, COMMAND_FEED, SENSOR_FEED).
Legacy clients without a 'subscriptions' key receive all broadcasts unchanged.
"""

from __future__ import annotations

import collections
import json
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from event_logger import log_event


class IntelFeedRouter:
    """Routes typed feed events to subscribed clients via a broadcast function."""

    def __init__(self, broadcast_fn: Callable[..., Coroutine[Any, Any, None]], max_history: int = 200) -> None:
        self._broadcast = broadcast_fn
        self._history: collections.deque[dict] = collections.deque(maxlen=max_history)

    async def emit(self, feed_type: str, event: dict) -> None:
        """Emit an event on the given feed.

        Enriches the event with feed metadata, logs it, appends to history,
        and broadcasts to subscribed clients.
        """
        enriched = {
            "feed": feed_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        self._history.append(enriched)
        log_event(feed_type, event)
        msg = json.dumps({"type": "FEED_EVENT", "feed": feed_type, "data": enriched})
        await self._broadcast(msg, feed=feed_type)

    def get_history(self, feed_type: str | None = None) -> list[dict]:
        """Return history for all feeds, or filtered by feed_type."""
        if feed_type:
            return [e for e in self._history if e["feed"] == feed_type]
        return list(self._history)


def _client_subscribed(info: dict, feed: str) -> bool:
    """Return True if a client should receive events for the given feed.

    Legacy clients (no 'subscriptions' key) receive all broadcasts.
    """
    subs = info.get("subscriptions")
    if subs is None:
        return True
    return feed in subs
