from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone, timedelta

from ..domain.models import _now
from ..persistence.repositories import (
    SnapshotRepo, AssetRepo, AimpointRepo, TargetRepo,
    MissionRepo, TimelineRepo, AlertRepo, EventLogRepo,
)


class SnapshotService:
    def __init__(self, snapshot_repo: SnapshotRepo, asset_repo: AssetRepo,
                 aimpoint_repo: AimpointRepo, target_repo: TargetRepo,
                 mission_repo: MissionRepo, timeline_repo: TimelineRepo,
                 alert_repo: AlertRepo, event_log_repo: EventLogRepo):
        self.snapshot_repo = snapshot_repo
        self.asset_repo = asset_repo
        self.aimpoint_repo = aimpoint_repo
        self.target_repo = target_repo
        self.mission_repo = mission_repo
        self.timeline_repo = timeline_repo
        self.alert_repo = alert_repo
        self.event_log_repo = event_log_repo

    def capture_snapshot(self) -> str:
        """Capture current domain state and persist to domain_snapshots."""
        timestamp = _now()
        snapshot_id = uuid.uuid4().hex[:12]

        snapshot = {
            "assets": [a.model_dump() for a in self.asset_repo.list_all()],
            "aimpoints": [a.model_dump() for a in self.aimpoint_repo.list_all()],
            "targets": [t.model_dump() for t in self.target_repo.list_all()],
            "missions": [m.model_dump() for m in self.mission_repo.list_all()],
            "reservations": [r.model_dump() for r in self.timeline_repo.list_all()],
            "alerts": [a.model_dump() for a in self.alert_repo.list_all()],
        }

        self.snapshot_repo.insert(snapshot_id, timestamp, json.dumps(snapshot))
        return snapshot_id

    def reconstruct_state_at(self, timestamp: str) -> dict:
        """Reconstruct domain state at a given timestamp.

        1. Find nearest snapshot before timestamp
        2. Replay events from snapshot time to target time
        3. Return reconstructed state
        """
        snap = self.snapshot_repo.get_nearest_before(timestamp)

        if not snap:
            # No snapshot available — return empty state
            return {
                "timestamp": timestamp,
                "assets": [],
                "aimpoints": [],
                "targets": [],
                "missions": [],
                "reservations": [],
                "alerts": [],
            }

        state = snap["snapshot"]
        snap_time = snap["timestamp"]

        # Replay events from snapshot time to target time
        events = self.event_log_repo.query(
            from_time=snap_time,
            to_time=timestamp,
            limit=100000,
        )

        # Index state by entity for efficient replay
        assets_by_id = {a["id"]: a for a in state.get("assets", [])}
        aimpoints_by_id = {a["id"]: a for a in state.get("aimpoints", [])}
        targets_by_id = {t["id"]: t for t in state.get("targets", [])}
        missions_by_id = {m["id"]: m for m in state.get("missions", [])}
        reservations_by_id = {r["id"]: r for r in state.get("reservations", [])}
        alerts_by_id = {a["id"]: a for a in state.get("alerts", [])}

        for event in events:
            etype = event.type
            eid = event.entity_id
            payload = event.payload

            # Asset events
            if etype == "asset.telemetry_received" and eid in assets_by_id:
                a = assets_by_id[eid]
                if "position" in payload:
                    a["position"] = payload["position"]
                if "velocity" in payload:
                    a["velocity"] = payload["velocity"]
                for field in ("heading_deg", "pitch_deg", "roll_deg",
                              "battery_pct", "link_quality"):
                    if field in payload:
                        a[field] = payload[field]
            elif etype == "asset.status_changed" and eid in assets_by_id:
                assets_by_id[eid]["status"] = payload.get("new_status",
                                                           assets_by_id[eid]["status"])
            elif etype == "asset.created":
                assets_by_id[eid] = payload

            # Aimpoint events
            elif etype == "aimpoint.created":
                aimpoints_by_id[eid] = payload
            elif etype == "aimpoint.updated" and eid in aimpoints_by_id:
                aimpoints_by_id[eid].update(payload)
            elif etype == "aimpoint.deleted":
                aimpoints_by_id.pop(eid, None)

            # Target events
            elif etype == "target.created":
                targets_by_id[eid] = payload
            elif etype in ("target.updated", "target.aimpoint_added",
                           "target.aimpoint_removed"):
                if eid in targets_by_id:
                    targets_by_id[eid].update(payload)
                else:
                    targets_by_id[eid] = payload
            elif etype == "target.deleted":
                targets_by_id.pop(eid, None)

            # Mission events
            elif etype == "mission.created":
                missions_by_id[eid] = payload
            elif etype == "mission.state_changed" and eid in missions_by_id:
                missions_by_id[eid]["state"] = payload.get("new_state",
                                                            missions_by_id[eid].get("state"))

            # Reservation events
            elif etype == "timeline.reservation_created":
                reservations_by_id[eid] = payload
            elif etype == "timeline.reservation_updated" and eid in reservations_by_id:
                reservations_by_id[eid].update(payload)

            # Alert events
            elif etype == "alert.created":
                alerts_by_id[eid] = payload
            elif etype == "alert.state_changed" and eid in alerts_by_id:
                alerts_by_id[eid]["state"] = payload.get("new_state",
                                                          alerts_by_id[eid].get("state"))

        return {
            "timestamp": timestamp,
            "assets": list(assets_by_id.values()),
            "aimpoints": list(aimpoints_by_id.values()),
            "targets": list(targets_by_id.values()),
            "missions": list(missions_by_id.values()),
            "reservations": list(reservations_by_id.values()),
            "alerts": list(alerts_by_id.values()),
        }

    def prune_old_snapshots(self, retention_hours: int = 24):
        """Delete snapshots older than retention period."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()
        self.snapshot_repo.prune(cutoff)

    def get_available_range(self) -> dict | None:
        """Return earliest/latest snapshot timestamps."""
        return self.snapshot_repo.get_range()
