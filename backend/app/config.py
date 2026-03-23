import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "ams.db")
TICK_RATE = 10  # Hz
ADAPTER_TYPE = os.environ.get("AMS_ADAPTER", "simulator")  # simulator | playback | mavlink

TELEMETRY_PERSIST_INTERVAL = 10  # persist every Nth tick (1Hz at 10Hz tick rate)

SNAPSHOT_INTERVAL_SEC = 30       # capture domain snapshot every N seconds
SNAPSHOT_RETENTION_HOURS = 24    # prune snapshots older than N hours
