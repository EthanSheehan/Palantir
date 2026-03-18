from __future__ import annotations
import asyncio
import fnmatch
import logging
from typing import Any, Callable, Coroutine

from .domain.models import DomainEvent

logger = logging.getLogger(__name__)

Handler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Handler]] = {}
        self._log_repo = None  # set via set_log_repo after DB init

    def set_log_repo(self, repo):
        self._log_repo = repo

    def subscribe(self, pattern: str, handler: Handler):
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)

    def unsubscribe(self, pattern: str, handler: Handler):
        if pattern in self._subscribers:
            self._subscribers[pattern] = [
                h for h in self._subscribers[pattern] if h is not handler
            ]

    async def publish(self, event: DomainEvent):
        # Persist to event log
        if self._log_repo:
            try:
                await self._log_repo.append(event)
            except Exception:
                logger.exception("Failed to persist event %s", event.id)

        # Dispatch to matching subscribers
        for pattern, handlers in self._subscribers.items():
            if self._matches(pattern, event.type):
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception(
                            "Handler error for event %s pattern %s",
                            event.type, pattern
                        )

    @staticmethod
    def _matches(pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        return fnmatch.fnmatch(event_type, pattern)
