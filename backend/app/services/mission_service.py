from __future__ import annotations
from typing import Optional

from ..domain.models import Mission, Task, DomainEvent, _now
from ..domain.enums import MissionState, TaskState
from ..domain.state_machines import validate_transition
from ..event_bus import EventBus
from ..persistence.repositories import MissionRepo, TaskRepo


class MissionService:
    def __init__(self, mission_repo: MissionRepo, task_repo: TaskRepo, bus: EventBus):
        self.mission_repo = mission_repo
        self.task_repo = task_repo
        self.bus = bus

    async def create_mission(self, mission: Mission) -> Mission:
        mission.state = MissionState.draft
        self.mission_repo.insert(mission)
        await self.bus.publish(DomainEvent(
            type="mission.created",
            source_service="mission_service",
            entity_type="mission",
            entity_id=mission.id,
            version=mission.version,
            payload=mission.model_dump(),
        ))
        return mission

    async def _transition_mission(self, mission_id: str, new_state: MissionState,
                                   reason: str = "", **extra_fields) -> Mission:
        mission = self.mission_repo.get(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id} not found")

        old_state = mission.state
        validate_transition("mission", old_state.value, new_state.value)

        mission.state = new_state
        mission.version += 1
        mission.updated_at = _now()
        for k, v in extra_fields.items():
            if hasattr(mission, k):
                setattr(mission, k, v)
        self.mission_repo.update(mission)

        await self.bus.publish(DomainEvent(
            type="mission.state_changed",
            source_service="mission_service",
            entity_type="mission",
            entity_id=mission.id,
            version=mission.version,
            payload={
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason,
            },
        ))
        return mission

    async def propose(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.proposed, "Submitted for review")

    async def approve(self, mission_id: str, approved_by: str = "operator") -> Mission:
        return await self._transition_mission(
            mission_id, MissionState.approved, "Approved",
            approved_by=approved_by,
        )

    async def reject(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.draft, "Returned for edits")

    async def queue(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.queued, "Awaiting resources")

    async def activate(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.active, "Execution started")

    async def pause(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.paused, "Paused by operator")

    async def resume(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.active, "Resumed by operator")

    async def abort(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.aborted, "Aborted by operator")

    async def complete(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.completed, "All tasks completed")

    async def fail(self, mission_id: str, reason: str = "") -> Mission:
        return await self._transition_mission(mission_id, MissionState.failed, reason)

    async def archive(self, mission_id: str) -> Mission:
        return await self._transition_mission(mission_id, MissionState.archived, "Archived")

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self.mission_repo.get(mission_id)

    def list_missions(self, **filters) -> list[Mission]:
        return self.mission_repo.list_all(**filters)

    # ── Task management ──

    async def add_task(self, task: Task) -> Task:
        mission = self.mission_repo.get(task.mission_id)
        if not mission:
            raise ValueError(f"Mission {task.mission_id} not found")

        self.task_repo.insert(task)
        mission.task_ids.append(task.id)
        mission.version += 1
        self.mission_repo.update(mission)

        await self.bus.publish(DomainEvent(
            type="task.created",
            source_service="mission_service",
            entity_type="task",
            entity_id=task.id,
            version=task.version,
            payload=task.model_dump(),
        ))
        return task

    async def update_task_state(self, task_id: str, new_state: TaskState,
                                 reason: str = "", asset_id: str = None) -> Task:
        task = self.task_repo.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        old_state = task.state
        validate_transition("task", old_state.value, new_state.value)

        task.state = new_state
        task.version += 1
        task.updated_at = _now()
        self.task_repo.update(task)

        await self.bus.publish(DomainEvent(
            type="task.state_changed",
            source_service="mission_service",
            entity_type="task",
            entity_id=task.id,
            version=task.version,
            payload={
                "old_state": old_state.value,
                "new_state": new_state.value,
                "asset_id": asset_id,
                "reason": reason,
            },
        ))
        return task

    async def remove_task(self, task_id: str):
        task = self.task_repo.get(task_id)
        if not task:
            return
        mission = self.mission_repo.get(task.mission_id)
        if mission and task_id in mission.task_ids:
            mission.task_ids.remove(task_id)
            mission.version += 1
            self.mission_repo.update(mission)
        self.task_repo.delete(task_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.task_repo.get(task_id)

    def list_tasks(self, mission_id: str) -> list[Task]:
        return self.task_repo.list_by_mission(mission_id)
