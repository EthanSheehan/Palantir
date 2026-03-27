import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

DB_PATH = "sim_history.db"
SNAPSHOT_INTERVAL_SEC = 5.0


class HistoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._last_snapshot_time: float = 0.0

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL UNIQUE,
                state_json TEXT NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_ts ON snapshots(timestamp)"
        )
        self._conn.commit()

    def maybe_capture(self, state: Dict[str, Any]) -> bool:
        now = time.time()
        if now - self._last_snapshot_time < SNAPSHOT_INTERVAL_SEC:
            return False
        self._last_snapshot_time = now
        snapshot = {
            "uavs": [
                {
                    "id": u["id"],
                    "lat": u["lat"],
                    "lon": u["lon"],
                    "altitude_m": u["altitude_m"],
                    "mode": u["mode"],
                    "heading_deg": u["heading_deg"],
                }
                for u in state.get("uavs", [])
            ],
            "targets": [
                {
                    "id": t["id"],
                    "lat": t["lat"],
                    "lon": t["lon"],
                    "type": t["type"],
                    "state": t["state"],
                    "detection_confidence": t["detection_confidence"],
                }
                for t in state.get("targets", [])
            ],
        }
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO snapshots (timestamp, state_json) VALUES (?, ?)",
                (now, json.dumps(snapshot)),
            )
            self._conn.commit()
        except Exception:
            pass
        return True

    def get_state_at(self, timestamp: float) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT state_json FROM snapshots WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
            (timestamp,),
        ).fetchone()
        if row:
            return json.loads(row["state_json"])
        return None

    def get_time_range(self) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT MIN(timestamp) as start_time, MAX(timestamp) as end_time, COUNT(*) as count FROM snapshots"
        ).fetchone()
        if row and row["count"] > 0:
            return {
                "start": row["start_time"],
                "end": row["end_time"],
                "count": row["count"],
            }
        return {"start": None, "end": None, "count": 0}

    def clear(self) -> None:
        self._conn.execute("DELETE FROM snapshots")
        self._conn.commit()
        self._last_snapshot_time = 0.0
