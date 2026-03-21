"""SQLite persistence layer for mission data.

Stores target lifecycle events, drone assignments, engagement outcomes,
and simulation state checkpoints.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    theater TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS target_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details_json TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS drone_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    drone_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    drone_id INTEGER NOT NULL,
    coa_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details_json TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    mission_id INTEGER PRIMARY KEY,
    state_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionStore:
    def __init__(self, db_path: str = "missions.db"):
        self._db_path = db_path
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_mission(self, name: str, theater: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO missions (name, theater, start_time, status) VALUES (?, ?, ?, ?)",
                (name, theater, _now_iso(), "ACTIVE"),
            )
            return cursor.lastrowid

    def end_mission(self, mission_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE missions SET end_time = ?, status = ? WHERE id = ?",
                (_now_iso(), "COMPLETED", mission_id),
            )

    def get_mission(self, mission_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
            return dict(row) if row else None

    def list_missions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM missions ORDER BY start_time DESC").fetchall()
            return [dict(r) for r in rows]

    def log_target_event(
        self,
        mission_id: int,
        target_id: int,
        target_type: str,
        event_type: str,
        details: dict | None = None,
    ) -> None:
        details_json = json.dumps(details) if details else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO target_events (mission_id, target_id, target_type, event_type, timestamp, details_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mission_id, target_id, target_type, event_type, _now_iso(), details_json),
            )

    def log_drone_assignment(self, mission_id: int, drone_id: int, target_id: int, mode: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO drone_assignments (mission_id, drone_id, target_id, mode, start_time) "
                "VALUES (?, ?, ?, ?, ?)",
                (mission_id, drone_id, target_id, mode, _now_iso()),
            )

    def log_engagement(
        self,
        mission_id: int,
        target_id: int,
        drone_id: int,
        coa_type: str,
        outcome: str,
        details: dict | None = None,
    ) -> None:
        details_json = json.dumps(details) if details else None
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO engagements (mission_id, target_id, drone_id, coa_type, outcome, timestamp, details_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mission_id, target_id, drone_id, coa_type, outcome, _now_iso(), details_json),
            )

    def get_target_history(self, mission_id: int, target_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM target_events WHERE mission_id = ? AND target_id = ? ORDER BY timestamp ASC",
                (mission_id, target_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_mission_summary(self, mission_id: int) -> dict:
        with self._connect() as conn:
            te_count = conn.execute(
                "SELECT COUNT(*) FROM target_events WHERE mission_id = ?", (mission_id,)
            ).fetchone()[0]
            da_count = conn.execute(
                "SELECT COUNT(*) FROM drone_assignments WHERE mission_id = ?", (mission_id,)
            ).fetchone()[0]
            eng_count = conn.execute("SELECT COUNT(*) FROM engagements WHERE mission_id = ?", (mission_id,)).fetchone()[
                0
            ]
            outcome_rows = conn.execute(
                "SELECT outcome, COUNT(*) as cnt FROM engagements WHERE mission_id = ? GROUP BY outcome",
                (mission_id,),
            ).fetchall()
            outcomes = {row["outcome"]: row["cnt"] for row in outcome_rows}
            return {
                "target_events": te_count,
                "drone_assignments": da_count,
                "engagements": eng_count,
                "outcomes": outcomes,
            }

    def save_checkpoint(self, mission_id: int, state_json: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (mission_id, state_json, saved_at) VALUES (?, ?, ?)",
                (mission_id, state_json, _now_iso()),
            )

    def load_checkpoint(self, mission_id: int) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT state_json FROM checkpoints WHERE mission_id = ?", (mission_id,)).fetchone()
            return row["state_json"] if row else None
