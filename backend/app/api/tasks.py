from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..dependencies import ctx
from ..domain.models import Task, TaskTarget, TaskConstraints
from ..domain.enums import TaskType, Priority, TargetKind
from ..domain.state_machines import InvalidTransitionError

router = APIRouter(prefix="/missions/{mission_id}/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    type: str = "goto"
    priority: str = "normal"
    target: dict = {}
    target_id: Optional[str] = None
    aimpoint_id: Optional[str] = None
    service_time_sec: Optional[float] = None
    earliest_start: Optional[str] = None
    latest_finish: Optional[str] = None
    dependencies: list[str] = []
    constraints: dict = {}


@router.get("")
def list_tasks(mission_id: str):
    tasks = ctx.mission_service.list_tasks(mission_id)
    return {"tasks": [t.model_dump() for t in tasks], "count": len(tasks)}


@router.post("")
async def create_task(mission_id: str, req: CreateTaskRequest):
    target_kind = req.target.get("kind", "point")
    target_data = req.target.get("data", {})

    task = Task(
        mission_id=mission_id,
        type=TaskType(req.type) if req.type in TaskType.__members__ else TaskType.goto,
        priority=Priority(req.priority) if req.priority in Priority.__members__ else Priority.normal,
        target=TaskTarget(
            kind=TargetKind(target_kind) if target_kind in TargetKind.__members__ else TargetKind.point,
            target_id=req.target_id,
            aimpoint_id=req.aimpoint_id,
            data=target_data,
        ),
        service_time_sec=req.service_time_sec,
        earliest_start=req.earliest_start,
        latest_finish=req.latest_finish,
        dependencies=req.dependencies,
        constraints=TaskConstraints(**req.constraints) if req.constraints else TaskConstraints(),
    )
    try:
        result = await ctx.mission_service.add_task(task)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{task_id}")
def get_task(mission_id: str, task_id: str):
    task = ctx.mission_service.get_task(task_id)
    if not task or task.mission_id != mission_id:
        raise HTTPException(404, f"Task {task_id} not found")
    return task.model_dump()


@router.delete("/{task_id}")
async def delete_task(mission_id: str, task_id: str):
    await ctx.mission_service.remove_task(task_id)
    return {"status": "ok"}
