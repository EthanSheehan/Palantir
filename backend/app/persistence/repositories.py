from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from ..domain.models import (
    Asset, Mission, Task, Command, TimelineReservation, Alert, DomainEvent,
    Position, Velocity, MissionConstraints, TaskTarget, TaskConstraints,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Asset Repository ──

class AssetRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def upsert(self, asset: Asset):
        self.db.execute(
            """INSERT INTO assets (id, name, type, status, mode,
                lon, lat, alt_m, vx_mps, vy_mps, vz_mps,
                heading_deg, battery_pct, link_quality, health, payload_state,
                home_lon, home_lat, home_alt_m,
                assigned_mission_id, assigned_task_id, last_telemetry_time,
                capabilities, version, updated_at)
            VALUES (?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, type=excluded.type, status=excluded.status, mode=excluded.mode,
                lon=excluded.lon, lat=excluded.lat, alt_m=excluded.alt_m,
                vx_mps=excluded.vx_mps, vy_mps=excluded.vy_mps, vz_mps=excluded.vz_mps,
                heading_deg=excluded.heading_deg, battery_pct=excluded.battery_pct,
                link_quality=excluded.link_quality, health=excluded.health,
                payload_state=excluded.payload_state,
                home_lon=excluded.home_lon, home_lat=excluded.home_lat, home_alt_m=excluded.home_alt_m,
                assigned_mission_id=excluded.assigned_mission_id,
                assigned_task_id=excluded.assigned_task_id,
                last_telemetry_time=excluded.last_telemetry_time,
                capabilities=excluded.capabilities, version=excluded.version,
                updated_at=excluded.updated_at
            """,
            (
                asset.id, asset.name, asset.type, asset.status.value, asset.mode.value,
                asset.position.lon, asset.position.lat, asset.position.alt_m,
                asset.velocity.vx_mps, asset.velocity.vy_mps, asset.velocity.vz_mps,
                asset.heading_deg, asset.battery_pct, asset.link_quality,
                asset.health.value, asset.payload_state,
                asset.home_location.lon, asset.home_location.lat, asset.home_location.alt_m,
                asset.assigned_mission_id, asset.assigned_task_id, asset.last_telemetry_time,
                json.dumps(asset.capabilities), asset.version, asset.updated_at,
            ),
        )
        self.db.commit()

    def get(self, asset_id: str) -> Optional[Asset]:
        row = self.db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            return None
        return self._row_to_asset(row)

    def list_all(self, status: str = None, mode: str = None, health: str = None,
                 mission_id: str = None, capability: str = None) -> list[Asset]:
        query = "SELECT * FROM assets WHERE 1=1"
        params: list = []
        if status:
            query += " AND status=?"
            params.append(status)
        if mode:
            query += " AND mode=?"
            params.append(mode)
        if health:
            query += " AND health=?"
            params.append(health)
        if mission_id:
            query += " AND assigned_mission_id=?"
            params.append(mission_id)
        rows = self.db.execute(query, params).fetchall()
        assets = [self._row_to_asset(r) for r in rows]
        if capability:
            assets = [a for a in assets if capability in a.capabilities]
        return assets

    def delete(self, asset_id: str):
        self.db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
        self.db.commit()

    @staticmethod
    def _row_to_asset(row) -> Asset:
        return Asset(
            id=row["id"], name=row["name"], type=row["type"],
            status=row["status"], mode=row["mode"],
            position=Position(lon=row["lon"], lat=row["lat"], alt_m=row["alt_m"]),
            velocity=Velocity(vx_mps=row["vx_mps"], vy_mps=row["vy_mps"], vz_mps=row["vz_mps"]),
            heading_deg=row["heading_deg"], battery_pct=row["battery_pct"],
            link_quality=row["link_quality"], health=row["health"],
            payload_state=row["payload_state"],
            home_location=Position(lon=row["home_lon"], lat=row["home_lat"], alt_m=row["home_alt_m"]),
            assigned_mission_id=row["assigned_mission_id"],
            assigned_task_id=row["assigned_task_id"],
            last_telemetry_time=row["last_telemetry_time"],
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            version=row["version"], updated_at=row["updated_at"] or "",
        )


# ── Mission Repository ──

class MissionRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, mission: Mission):
        self.db.execute(
            """INSERT INTO missions (id, name, type, priority, objective, state,
                created_at, created_by, approved_by, constraints,
                assigned_asset_ids, task_ids, tags, version, updated_at)
            VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?,?,?)""",
            (
                mission.id, mission.name, mission.type.value, mission.priority.value,
                mission.objective, mission.state.value,
                mission.created_at, mission.created_by, mission.approved_by,
                mission.constraints.model_dump_json(),
                json.dumps(mission.assigned_asset_ids),
                json.dumps(mission.task_ids), json.dumps(mission.tags),
                mission.version, mission.updated_at,
            ),
        )
        self.db.commit()

    def update(self, mission: Mission):
        self.db.execute(
            """UPDATE missions SET name=?, type=?, priority=?, objective=?, state=?,
                approved_by=?, constraints=?, assigned_asset_ids=?, task_ids=?,
                tags=?, version=?, updated_at=?
            WHERE id=?""",
            (
                mission.name, mission.type.value, mission.priority.value,
                mission.objective, mission.state.value, mission.approved_by,
                mission.constraints.model_dump_json(),
                json.dumps(mission.assigned_asset_ids), json.dumps(mission.task_ids),
                json.dumps(mission.tags), mission.version, _now(), mission.id,
            ),
        )
        self.db.commit()

    def get(self, mission_id: str) -> Optional[Mission]:
        row = self.db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        if not row:
            return None
        return self._row_to_mission(row)

    def list_all(self, state: str = None, priority: str = None,
                 mission_type: str = None, asset_id: str = None) -> list[Mission]:
        query = "SELECT * FROM missions WHERE 1=1"
        params: list = []
        if state:
            query += " AND state=?"
            params.append(state)
        if priority:
            query += " AND priority=?"
            params.append(priority)
        if mission_type:
            query += " AND type=?"
            params.append(mission_type)
        rows = self.db.execute(query, params).fetchall()
        missions = [self._row_to_mission(r) for r in rows]
        if asset_id:
            missions = [m for m in missions if asset_id in m.assigned_asset_ids]
        return missions

    @staticmethod
    def _row_to_mission(row) -> Mission:
        return Mission(
            id=row["id"], name=row["name"], type=row["type"],
            priority=row["priority"], objective=row["objective"], state=row["state"],
            created_at=row["created_at"] or "", created_by=row["created_by"] or "operator",
            approved_by=row["approved_by"],
            constraints=MissionConstraints.model_validate_json(row["constraints"] or "{}"),
            assigned_asset_ids=json.loads(row["assigned_asset_ids"] or "[]"),
            task_ids=json.loads(row["task_ids"] or "[]"),
            tags=json.loads(row["tags"] or "[]"),
            version=row["version"], updated_at=row["updated_at"] or "",
        )


# ── Task Repository ──

class TaskRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, task: Task):
        self.db.execute(
            """INSERT INTO tasks (id, mission_id, type, priority, state, target,
                service_time_sec, earliest_start, latest_finish,
                assigned_asset_ids, dependencies, constraints, version, updated_at)
            VALUES (?,?,?,?,?,?, ?,?,?, ?,?,?,?,?)""",
            (
                task.id, task.mission_id, task.type.value, task.priority.value,
                task.state.value, task.target.model_dump_json(),
                task.service_time_sec, task.earliest_start, task.latest_finish,
                json.dumps(task.assigned_asset_ids), json.dumps(task.dependencies),
                task.constraints.model_dump_json(), task.version, task.updated_at,
            ),
        )
        self.db.commit()

    def update(self, task: Task):
        self.db.execute(
            """UPDATE tasks SET type=?, priority=?, state=?, target=?,
                service_time_sec=?, earliest_start=?, latest_finish=?,
                assigned_asset_ids=?, dependencies=?, constraints=?,
                version=?, updated_at=?
            WHERE id=?""",
            (
                task.type.value, task.priority.value, task.state.value,
                task.target.model_dump_json(), task.service_time_sec,
                task.earliest_start, task.latest_finish,
                json.dumps(task.assigned_asset_ids), json.dumps(task.dependencies),
                task.constraints.model_dump_json(), task.version, _now(), task.id,
            ),
        )
        self.db.commit()

    def get(self, task_id: str) -> Optional[Task]:
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        return self._row_to_task(row)

    def list_by_mission(self, mission_id: str) -> list[Task]:
        rows = self.db.execute("SELECT * FROM tasks WHERE mission_id=?", (mission_id,)).fetchall()
        return [self._row_to_task(r) for r in rows]

    def delete(self, task_id: str):
        self.db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.db.commit()

    @staticmethod
    def _row_to_task(row) -> Task:
        return Task(
            id=row["id"], mission_id=row["mission_id"], type=row["type"],
            priority=row["priority"], state=row["state"],
            target=TaskTarget.model_validate_json(row["target"] or "{}"),
            service_time_sec=row["service_time_sec"],
            earliest_start=row["earliest_start"], latest_finish=row["latest_finish"],
            assigned_asset_ids=json.loads(row["assigned_asset_ids"] or "[]"),
            dependencies=json.loads(row["dependencies"] or "[]"),
            constraints=TaskConstraints.model_validate_json(row["constraints"] or "{}"),
            version=row["version"], updated_at=row["updated_at"] or "",
        )


# ── Command Repository ──

class CommandRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, cmd: Command):
        self.db.execute(
            """INSERT INTO commands (id, type, target_type, target_id, payload, state,
                created_at, created_by, approved_at, approved_by,
                dispatched_at, acknowledged_at, completed_at,
                failure_reason, correlation_id, version)
            VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?)""",
            (
                cmd.id, cmd.type.value, cmd.target_type.value, cmd.target_id,
                json.dumps(cmd.payload), cmd.state.value,
                cmd.created_at, cmd.created_by, cmd.approved_at, cmd.approved_by,
                cmd.dispatched_at, cmd.acknowledged_at, cmd.completed_at,
                cmd.failure_reason, cmd.correlation_id, cmd.version,
            ),
        )
        self.db.commit()

    def update(self, cmd: Command):
        self.db.execute(
            """UPDATE commands SET state=?, approved_at=?, approved_by=?,
                dispatched_at=?, acknowledged_at=?, completed_at=?,
                failure_reason=?, version=?
            WHERE id=?""",
            (
                cmd.state.value, cmd.approved_at, cmd.approved_by,
                cmd.dispatched_at, cmd.acknowledged_at, cmd.completed_at,
                cmd.failure_reason, cmd.version, cmd.id,
            ),
        )
        self.db.commit()

    def get(self, cmd_id: str) -> Optional[Command]:
        row = self.db.execute("SELECT * FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return None
        return self._row_to_command(row)

    def list_all(self, state: str = None, cmd_type: str = None,
                 target_type: str = None, target_id: str = None) -> list[Command]:
        query = "SELECT * FROM commands WHERE 1=1"
        params: list = []
        if state:
            query += " AND state=?"
            params.append(state)
        if cmd_type:
            query += " AND type=?"
            params.append(cmd_type)
        if target_type:
            query += " AND target_type=?"
            params.append(target_type)
        if target_id:
            query += " AND target_id=?"
            params.append(target_id)
        rows = self.db.execute(query, params).fetchall()
        return [self._row_to_command(r) for r in rows]

    @staticmethod
    def _row_to_command(row) -> Command:
        return Command(
            id=row["id"], type=row["type"], target_type=row["target_type"],
            target_id=row["target_id"],
            payload=json.loads(row["payload"] or "{}"),
            state=row["state"], created_at=row["created_at"] or "",
            created_by=row["created_by"] or "operator",
            approved_at=row["approved_at"], approved_by=row["approved_by"],
            dispatched_at=row["dispatched_at"], acknowledged_at=row["acknowledged_at"],
            completed_at=row["completed_at"], failure_reason=row["failure_reason"],
            correlation_id=row["correlation_id"], version=row["version"],
        )


# ── Timeline Reservation Repository ──

class TimelineRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, res: TimelineReservation):
        self.db.execute(
            """INSERT INTO timeline_reservations (id, asset_id, mission_id, task_id,
                phase, start_time, end_time, status, source)
            VALUES (?,?,?,?, ?,?,?,?,?)""",
            (
                res.id, res.asset_id, res.mission_id, res.task_id,
                res.phase.value, res.start_time, res.end_time,
                res.status.value, res.source.value,
            ),
        )
        self.db.commit()

    def update(self, res: TimelineReservation):
        self.db.execute(
            """UPDATE timeline_reservations SET phase=?, start_time=?, end_time=?,
                status=?, source=?
            WHERE id=?""",
            (res.phase.value, res.start_time, res.end_time, res.status.value, res.source.value, res.id),
        )
        self.db.commit()

    def get(self, res_id: str) -> Optional[TimelineReservation]:
        row = self.db.execute("SELECT * FROM timeline_reservations WHERE id=?", (res_id,)).fetchone()
        if not row:
            return None
        return self._row_to_reservation(row)

    def list_all(self, asset_id: str = None, mission_id: str = None,
                 start_after: str = None, end_before: str = None,
                 status: str = None, source: str = None) -> list[TimelineReservation]:
        query = "SELECT * FROM timeline_reservations WHERE 1=1"
        params: list = []
        if asset_id:
            query += " AND asset_id=?"
            params.append(asset_id)
        if mission_id:
            query += " AND mission_id=?"
            params.append(mission_id)
        if start_after:
            query += " AND start_time>=?"
            params.append(start_after)
        if end_before:
            query += " AND end_time<=?"
            params.append(end_before)
        if status:
            query += " AND status=?"
            params.append(status)
        if source:
            query += " AND source=?"
            params.append(source)
        rows = self.db.execute(query, params).fetchall()
        return [self._row_to_reservation(r) for r in rows]

    def list_conflicts(self) -> list[TimelineReservation]:
        rows = self.db.execute("SELECT * FROM timeline_reservations WHERE status='conflict'").fetchall()
        return [self._row_to_reservation(r) for r in rows]

    @staticmethod
    def _row_to_reservation(row) -> TimelineReservation:
        return TimelineReservation(
            id=row["id"], asset_id=row["asset_id"],
            mission_id=row["mission_id"], task_id=row["task_id"],
            phase=row["phase"], start_time=row["start_time"], end_time=row["end_time"],
            status=row["status"], source=row["source"],
        )


# ── Alert Repository ──

class AlertRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert(self, alert: Alert):
        self.db.execute(
            """INSERT INTO alerts (id, type, severity, state, created_at,
                source_type, source_id, message, metadata)
            VALUES (?,?,?,?,?, ?,?,?,?)""",
            (
                alert.id, alert.type.value, alert.severity.value, alert.state.value,
                alert.created_at, alert.source_type.value, alert.source_id,
                alert.message, json.dumps(alert.metadata),
            ),
        )
        self.db.commit()

    def update(self, alert: Alert):
        self.db.execute(
            "UPDATE alerts SET state=?, metadata=? WHERE id=?",
            (alert.state.value, json.dumps(alert.metadata), alert.id),
        )
        self.db.commit()

    def get(self, alert_id: str) -> Optional[Alert]:
        row = self.db.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not row:
            return None
        return self._row_to_alert(row)

    def list_all(self, state: str = None, severity: str = None,
                 alert_type: str = None, source_type: str = None,
                 source_id: str = None) -> list[Alert]:
        query = "SELECT * FROM alerts WHERE 1=1"
        params: list = []
        if state:
            query += " AND state=?"
            params.append(state)
        if severity:
            query += " AND severity=?"
            params.append(severity)
        if alert_type:
            query += " AND type=?"
            params.append(alert_type)
        if source_type:
            query += " AND source_type=?"
            params.append(source_type)
        if source_id:
            query += " AND source_id=?"
            params.append(source_id)
        rows = self.db.execute(query, params).fetchall()
        return [self._row_to_alert(r) for r in rows]

    @staticmethod
    def _row_to_alert(row) -> Alert:
        return Alert(
            id=row["id"], type=row["type"], severity=row["severity"],
            state=row["state"], created_at=row["created_at"] or "",
            source_type=row["source_type"], source_id=row["source_id"],
            message=row["message"],
            metadata=json.loads(row["metadata"] or "{}"),
        )


# ── Event Log Repository ──

class EventLogRepo:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    async def append(self, event: DomainEvent):
        self.db.execute(
            """INSERT INTO event_log (id, type, timestamp, source_service,
                entity_type, entity_id, version, payload)
            VALUES (?,?,?,?, ?,?,?,?)""",
            (
                event.id, event.type, event.timestamp, event.source_service,
                event.entity_type, event.entity_id, event.version,
                json.dumps(event.payload),
            ),
        )
        self.db.commit()

    def query(self, from_time: str = None, to_time: str = None,
              entity_type: str = None, entity_id: str = None,
              event_type: str = None, limit: int = 1000) -> list[DomainEvent]:
        query = "SELECT * FROM event_log WHERE 1=1"
        params: list = []
        if from_time:
            query += " AND timestamp>=?"
            params.append(from_time)
        if to_time:
            query += " AND timestamp<=?"
            params.append(to_time)
        if entity_type:
            query += " AND entity_type=?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id=?"
            params.append(entity_id)
        if event_type:
            query += " AND type=?"
            params.append(event_type)
        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        rows = self.db.execute(query, params).fetchall()
        return [
            DomainEvent(
                id=r["id"], type=r["type"], timestamp=r["timestamp"],
                source_service=r["source_service"], entity_type=r["entity_type"],
                entity_id=r["entity_id"], version=r["version"],
                payload=json.loads(r["payload"] or "{}"),
            )
            for r in rows
        ]
