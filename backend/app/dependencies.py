"""Singleton holders for services, repos, bus, and adapter.

Initialized once at startup from main.py.
"""
from __future__ import annotations
from typing import Optional

from .event_bus import EventBus
from .persistence.database import get_db
from .persistence.repositories import (
    AssetRepo, MissionRepo, TaskRepo, CommandRepo,
    TimelineRepo, AlertRepo, EventLogRepo,
)
from .services.asset_service import AssetService
from .services.mission_service import MissionService
from .services.command_service import CommandService
from .services.timeline_service import TimelineService
from .services.alert_service import AlertService
from .services.macrogrid_service import MacroGridService
from .adapters.base import ExecutionAdapter


class AppContext:
    """Holds all singletons. Created once at startup."""

    def __init__(self):
        self.bus: Optional[EventBus] = None
        self.adapter: Optional[ExecutionAdapter] = None

        # Repos
        self.asset_repo: Optional[AssetRepo] = None
        self.mission_repo: Optional[MissionRepo] = None
        self.task_repo: Optional[TaskRepo] = None
        self.command_repo: Optional[CommandRepo] = None
        self.timeline_repo: Optional[TimelineRepo] = None
        self.alert_repo: Optional[AlertRepo] = None
        self.event_log_repo: Optional[EventLogRepo] = None

        # Services
        self.asset_service: Optional[AssetService] = None
        self.mission_service: Optional[MissionService] = None
        self.command_service: Optional[CommandService] = None
        self.timeline_service: Optional[TimelineService] = None
        self.alert_service: Optional[AlertService] = None
        self.macrogrid_service: Optional[MacroGridService] = None

    def init(self, adapter: ExecutionAdapter, grid=None):
        db = get_db()
        self.bus = EventBus()

        # Repos
        self.asset_repo = AssetRepo(db)
        self.mission_repo = MissionRepo(db)
        self.task_repo = TaskRepo(db)
        self.command_repo = CommandRepo(db)
        self.timeline_repo = TimelineRepo(db)
        self.alert_repo = AlertRepo(db)
        self.event_log_repo = EventLogRepo(db)

        # Wire event log to bus
        self.bus.set_log_repo(self.event_log_repo)

        # Services
        self.adapter = adapter
        self.asset_service = AssetService(self.asset_repo, self.bus)
        self.mission_service = MissionService(self.mission_repo, self.task_repo, self.bus)
        self.command_service = CommandService(self.command_repo, self.bus, adapter)
        self.timeline_service = TimelineService(self.timeline_repo, self.bus)
        self.alert_service = AlertService(self.alert_repo, self.bus)
        if grid:
            self.macrogrid_service = MacroGridService(grid, self.bus)


# Global singleton
ctx = AppContext()
