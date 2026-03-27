"""SQLite-backed persistence for pre-planned strike targets and aimpoints."""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

DB_PATH = "planned_targets.db"

VALID_TARGET_TYPES = {"SAM", "TEL", "CP", "RADAR", "C2_NODE", "LOGISTICS", "CUSTOM"}


@dataclass(frozen=True)
class Aimpoint:
    id: str
    name: str
    lat: float
    lon: float
    target_id: str
    description: str = ""


@dataclass(frozen=True)
class PlannedTarget:
    id: str
    name: str
    lat: float
    lon: float
    target_type: str
    priority: int = 3
    notes: str = ""
    created_at: float = 0.0
    aimpoints: List[Aimpoint] = field(default_factory=list)


class TargetStore:
    def __init__(self, db_path: str = DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS planned_targets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'CUSTOM',
                priority INTEGER NOT NULL DEFAULT 3,
                notes TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS aimpoints (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                target_id TEXT NOT NULL REFERENCES planned_targets(id) ON DELETE CASCADE,
                description TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def add_target(self, target: PlannedTarget) -> PlannedTarget:
        created = target.created_at if target.created_at else time.time()
        target = PlannedTarget(
            id=target.id,
            name=target.name,
            lat=target.lat,
            lon=target.lon,
            target_type=target.target_type,
            priority=target.priority,
            notes=target.notes,
            created_at=created,
            aimpoints=target.aimpoints,
        )
        self._conn.execute(
            "INSERT INTO planned_targets (id, name, lat, lon, target_type, priority, notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (target.id, target.name, target.lat, target.lon,
             target.target_type, target.priority, target.notes, target.created_at),
        )
        for ap in target.aimpoints:
            self._conn.execute(
                "INSERT INTO aimpoints (id, name, lat, lon, target_id, description) VALUES (?, ?, ?, ?, ?, ?)",
                (ap.id, ap.name, ap.lat, ap.lon, target.id, ap.description),
            )
        self._conn.commit()
        return target

    def get_all(self) -> List[PlannedTarget]:
        rows = self._conn.execute(
            "SELECT * FROM planned_targets ORDER BY priority ASC, created_at DESC"
        ).fetchall()
        targets = []
        for row in rows:
            ap_rows = self._conn.execute(
                "SELECT * FROM aimpoints WHERE target_id = ?", (row["id"],)
            ).fetchall()
            aimpoints = [
                Aimpoint(
                    id=a["id"],
                    name=a["name"],
                    lat=a["lat"],
                    lon=a["lon"],
                    target_id=a["target_id"],
                    description=a["description"],
                )
                for a in ap_rows
            ]
            targets.append(
                PlannedTarget(
                    id=row["id"],
                    name=row["name"],
                    lat=row["lat"],
                    lon=row["lon"],
                    target_type=row["target_type"],
                    priority=row["priority"],
                    notes=row["notes"],
                    created_at=row["created_at"],
                    aimpoints=aimpoints,
                )
            )
        return targets

    def delete_target(self, target_id: str) -> bool:
        self._conn.execute("DELETE FROM aimpoints WHERE target_id = ?", (target_id,))
        cursor = self._conn.execute(
            "DELETE FROM planned_targets WHERE id = ?", (target_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def to_dict_list(self) -> List[Dict[str, Any]]:
        result = []
        for t in self.get_all():
            result.append({
                "id": t.id,
                "name": t.name,
                "lat": t.lat,
                "lon": t.lon,
                "target_type": t.target_type,
                "priority": t.priority,
                "notes": t.notes,
                "created_at": t.created_at,
                "aimpoints": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "lat": a.lat,
                        "lon": a.lon,
                        "description": a.description,
                    }
                    for a in t.aimpoints
                ],
            })
        return result
