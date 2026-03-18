from .enums import AssetStatus, MissionState, TaskState, CommandState, AlertState

# Each dict maps a state to its set of valid target states.
# "*" key means "from any state" (wildcard transitions).

ASSET_TRANSITIONS: dict[str, set[str]] = {
    AssetStatus.idle: {AssetStatus.reserved, AssetStatus.launching},
    AssetStatus.reserved: {AssetStatus.launching, AssetStatus.idle},
    AssetStatus.launching: {AssetStatus.transiting},
    AssetStatus.transiting: {AssetStatus.on_task, AssetStatus.returning},
    AssetStatus.on_task: {AssetStatus.returning, AssetStatus.transiting},
    AssetStatus.returning: {AssetStatus.landing},
    AssetStatus.landing: {AssetStatus.charging, AssetStatus.idle},
    AssetStatus.charging: {AssetStatus.idle, AssetStatus.maintenance},
    AssetStatus.maintenance: {AssetStatus.idle},
    AssetStatus.offline: {AssetStatus.idle},
    AssetStatus.degraded: {AssetStatus.idle, AssetStatus.maintenance},
    AssetStatus.lost: {AssetStatus.idle, AssetStatus.offline},
    "*": {AssetStatus.degraded, AssetStatus.lost, AssetStatus.offline},
}

MISSION_TRANSITIONS: dict[str, set[str]] = {
    MissionState.draft: {MissionState.proposed},
    MissionState.proposed: {MissionState.approved, MissionState.draft},
    MissionState.approved: {MissionState.queued},
    MissionState.queued: {MissionState.active},
    MissionState.active: {MissionState.paused, MissionState.completed, MissionState.aborted, MissionState.failed},
    MissionState.paused: {MissionState.active, MissionState.aborted},
    MissionState.completed: {MissionState.archived},
    MissionState.aborted: {MissionState.archived},
    MissionState.failed: {MissionState.archived},
}

TASK_TRANSITIONS: dict[str, set[str]] = {
    TaskState.waiting: {TaskState.ready, TaskState.cancelled},
    TaskState.ready: {TaskState.assigned, TaskState.cancelled},
    TaskState.assigned: {TaskState.transit, TaskState.cancelled},
    TaskState.transit: {TaskState.active, TaskState.blocked},
    TaskState.active: {TaskState.completed, TaskState.failed, TaskState.blocked},
    TaskState.blocked: {TaskState.transit, TaskState.active, TaskState.cancelled},
}

COMMAND_TRANSITIONS: dict[str, set[str]] = {
    CommandState.proposed: {CommandState.validated, CommandState.rejected, CommandState.cancelled},
    CommandState.validated: {CommandState.approved, CommandState.rejected, CommandState.cancelled},
    CommandState.approved: {CommandState.queued, CommandState.cancelled},
    CommandState.queued: {CommandState.sent, CommandState.cancelled},
    CommandState.sent: {CommandState.acknowledged, CommandState.failed, CommandState.expired},
    CommandState.acknowledged: {CommandState.active, CommandState.expired},
    CommandState.active: {CommandState.completed, CommandState.failed},
}

ALERT_TRANSITIONS: dict[str, set[str]] = {
    AlertState.open: {AlertState.acknowledged, AlertState.cleared},
    AlertState.acknowledged: {AlertState.cleared},
}

_TRANSITION_MAPS = {
    "asset": ASSET_TRANSITIONS,
    "mission": MISSION_TRANSITIONS,
    "task": TASK_TRANSITIONS,
    "command": COMMAND_TRANSITIONS,
    "alert": ALERT_TRANSITIONS,
}


class InvalidTransitionError(Exception):
    def __init__(self, entity_type: str, from_state: str, to_state: str):
        self.entity_type = entity_type
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid {entity_type} transition: {from_state} -> {to_state}"
        )


def validate_transition(entity_type: str, from_state: str, to_state: str) -> bool:
    transitions = _TRANSITION_MAPS.get(entity_type)
    if transitions is None:
        raise ValueError(f"Unknown entity type: {entity_type}")

    # Check wildcard transitions first
    wildcard = transitions.get("*", set())
    if to_state in wildcard:
        return True

    valid = transitions.get(from_state, set())
    if to_state in valid:
        return True

    raise InvalidTransitionError(entity_type, from_state, to_state)
