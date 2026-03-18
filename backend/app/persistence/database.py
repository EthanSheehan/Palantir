from __future__ import annotations
import sqlite3
import os
import logging

from ..config import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'quadrotor',
    status TEXT NOT NULL DEFAULT 'idle',
    mode TEXT NOT NULL DEFAULT 'simulated',
    lon REAL NOT NULL DEFAULT 0.0,
    lat REAL NOT NULL DEFAULT 0.0,
    alt_m REAL NOT NULL DEFAULT 0.0,
    vx_mps REAL DEFAULT 0.0,
    vy_mps REAL DEFAULT 0.0,
    vz_mps REAL DEFAULT 0.0,
    heading_deg REAL DEFAULT 0.0,
    battery_pct REAL DEFAULT 100.0,
    link_quality REAL DEFAULT 1.0,
    health TEXT DEFAULT 'nominal',
    payload_state TEXT DEFAULT '',
    home_lon REAL DEFAULT 0.0,
    home_lat REAL DEFAULT 0.0,
    home_alt_m REAL DEFAULT 0.0,
    assigned_mission_id TEXT,
    assigned_task_id TEXT,
    last_telemetry_time TEXT,
    capabilities TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL DEFAULT 'custom',
    priority TEXT NOT NULL DEFAULT 'normal',
    objective TEXT DEFAULT '',
    state TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT DEFAULT 'operator',
    approved_by TEXT,
    constraints TEXT DEFAULT '{}',
    assigned_asset_ids TEXT DEFAULT '[]',
    task_ids TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'goto',
    priority TEXT NOT NULL DEFAULT 'normal',
    state TEXT NOT NULL DEFAULT 'waiting',
    target TEXT DEFAULT '{}',
    service_time_sec REAL,
    earliest_start TEXT,
    latest_finish TEXT,
    assigned_asset_ids TEXT DEFAULT '[]',
    dependencies TEXT DEFAULT '[]',
    constraints TEXT DEFAULT '{}',
    version INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload TEXT DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT DEFAULT 'operator',
    approved_at TEXT,
    approved_by TEXT,
    dispatched_at TEXT,
    acknowledged_at TEXT,
    completed_at TEXT,
    failure_reason TEXT,
    correlation_id TEXT,
    version INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS timeline_reservations (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    mission_id TEXT,
    task_id TEXT,
    phase TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    source TEXT NOT NULL DEFAULT 'planned',
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    state TEXT NOT NULL DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now')),
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS event_log (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source_service TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_log_entity ON event_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_event_log_time ON event_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(type);
"""

_connection: sqlite3.Connection | None = None


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    global _connection
    logger.info("Initializing database at %s", db_path)
    _connection = sqlite3.connect(db_path, check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA journal_mode=WAL")
    _connection.execute("PRAGMA foreign_keys=ON")
    _connection.executescript(SCHEMA_SQL)
    _connection.commit()
    return _connection


def get_db() -> sqlite3.Connection:
    if _connection is None:
        return init_db()
    return _connection


def close_db():
    global _connection
    if _connection:
        _connection.close()
        _connection = None
