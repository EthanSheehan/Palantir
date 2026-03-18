from __future__ import annotations
from typing import Optional

from ..domain.models import Command, DomainEvent, _now
from ..domain.enums import CommandState, CommandType
from ..domain.state_machines import validate_transition
from ..event_bus import EventBus
from ..persistence.repositories import CommandRepo


class CommandService:
    def __init__(self, repo: CommandRepo, bus: EventBus, adapter=None):
        self.repo = repo
        self.bus = bus
        self.adapter = adapter

    async def create_command(self, cmd: Command) -> Command:
        cmd.state = CommandState.proposed
        self.repo.insert(cmd)

        await self.bus.publish(DomainEvent(
            type="command.created",
            source_service="command_service",
            entity_type="command",
            entity_id=cmd.id,
            version=cmd.version,
            payload=cmd.model_dump(),
        ))

        # Auto-validate
        await self._transition(cmd, CommandState.validated, "Validation passed")

        # Auto-approve for simple commands
        if cmd.type in (CommandType.move_to, CommandType.hold_position, CommandType.return_home):
            await self.approve_command(cmd.id, approved_by="auto")

        return cmd

    async def approve_command(self, cmd_id: str, approved_by: str = "operator") -> Command:
        cmd = self.repo.get(cmd_id)
        if not cmd:
            raise ValueError(f"Command {cmd_id} not found")

        await self._transition(cmd, CommandState.approved, "Approved",
                               approved_at=_now(), approved_by=approved_by)

        # Auto-queue and dispatch
        await self._transition(cmd, CommandState.queued, "Queued for dispatch")
        await self._dispatch(cmd)
        return cmd

    async def cancel_command(self, cmd_id: str) -> Command:
        cmd = self.repo.get(cmd_id)
        if not cmd:
            raise ValueError(f"Command {cmd_id} not found")
        await self._transition(cmd, CommandState.cancelled, "Cancelled by operator")
        return cmd

    async def handle_ack(self, cmd_id: str) -> Command:
        cmd = self.repo.get(cmd_id)
        if not cmd:
            raise ValueError(f"Command {cmd_id} not found")
        await self._transition(cmd, CommandState.acknowledged, "Adapter acknowledged",
                               acknowledged_at=_now())
        await self._transition(cmd, CommandState.active, "Execution started")
        return cmd

    async def handle_completion(self, cmd_id: str) -> Command:
        cmd = self.repo.get(cmd_id)
        if not cmd:
            raise ValueError(f"Command {cmd_id} not found")
        await self._transition(cmd, CommandState.completed, "Execution completed",
                               completed_at=_now())
        return cmd

    async def handle_failure(self, cmd_id: str, reason: str = "") -> Command:
        cmd = self.repo.get(cmd_id)
        if not cmd:
            raise ValueError(f"Command {cmd_id} not found")
        await self._transition(cmd, CommandState.failed, reason,
                               failure_reason=reason, completed_at=_now())
        return cmd

    def get_command(self, cmd_id: str) -> Optional[Command]:
        return self.repo.get(cmd_id)

    def list_commands(self, **filters) -> list[Command]:
        return self.repo.list_all(**filters)

    # ── Internal ──

    async def _transition(self, cmd: Command, new_state: CommandState,
                           reason: str = "", **extra):
        old_state = cmd.state
        validate_transition("command", old_state.value, new_state.value)

        cmd.state = new_state
        cmd.version += 1
        for k, v in extra.items():
            if hasattr(cmd, k):
                setattr(cmd, k, v)
        self.repo.update(cmd)

        event_type = f"command.{new_state.value}"
        if new_state == CommandState.validated:
            event_type = "command.validated"
        elif new_state == CommandState.approved:
            event_type = "command.approved"
        elif new_state == CommandState.sent:
            event_type = "command.sent"
        elif new_state == CommandState.acknowledged:
            event_type = "command.acknowledged"
        elif new_state == CommandState.completed:
            event_type = "command.completed"
        elif new_state == CommandState.failed:
            event_type = "command.failed"

        await self.bus.publish(DomainEvent(
            type=event_type,
            source_service="command_service",
            entity_type="command",
            entity_id=cmd.id,
            version=cmd.version,
            payload={
                "command_id": cmd.id,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason,
            },
        ))

    async def _dispatch(self, cmd: Command):
        if self.adapter is None:
            return

        await self._transition(cmd, CommandState.sent, "Dispatched to adapter",
                               dispatched_at=_now())

        try:
            result = self.adapter.send_command(cmd)
            if result and result.get("success"):
                await self.handle_ack(cmd.id)
        except Exception as e:
            await self.handle_failure(cmd.id, str(e))
