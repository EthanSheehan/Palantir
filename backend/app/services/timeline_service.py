from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..domain.models import TimelineReservation, DomainEvent, _now
from ..domain.enums import ReservationPhase, ReservationStatus, ReservationSource
from ..event_bus import EventBus
from ..persistence.repositories import TimelineRepo


class TimelineService:
    SPEED_MPS = 500.0  # approximate cruise speed in m/s

    def __init__(self, repo: TimelineRepo, bus: EventBus):
        self.repo = repo
        self.bus = bus

    async def create_reservation(self, res: TimelineReservation) -> TimelineReservation:
        self.repo.insert(res)
        await self.bus.publish(DomainEvent(
            type="timeline.reservation_created",
            source_service="timeline_service",
            entity_type="timeline_reservation",
            entity_id=res.id,
            version=1,
            payload=res.model_dump(),
        ))
        return res

    async def update_reservation(self, res: TimelineReservation) -> TimelineReservation:
        self.repo.update(res)
        await self.bus.publish(DomainEvent(
            type="timeline.reservation_updated",
            source_service="timeline_service",
            entity_type="timeline_reservation",
            entity_id=res.id,
            version=1,
            payload={"reservation_id": res.id},
        ))
        return res

    def get_reservation(self, res_id: str) -> Optional[TimelineReservation]:
        return self.repo.get(res_id)

    def list_reservations(self, **filters) -> list[TimelineReservation]:
        return self.repo.list_all(**filters)

    def list_conflicts(self) -> list[TimelineReservation]:
        return self.repo.list_conflicts()

    async def detect_conflicts(self) -> list[dict]:
        """Check all planned/active reservations for overlaps per asset."""
        all_res = self.repo.list_all()
        conflicts = []

        # Group by asset
        by_asset: dict[str, list[TimelineReservation]] = {}
        for r in all_res:
            if r.status.value in ("planned", "active") and r.phase.value != "idle":
                by_asset.setdefault(r.asset_id, []).append(r)

        for asset_id, reservations in by_asset.items():
            reservations.sort(key=lambda r: r.start_time)
            for i in range(len(reservations)):
                for j in range(i + 1, len(reservations)):
                    a, b = reservations[i], reservations[j]
                    if a.start_time < b.end_time and b.start_time < a.end_time:
                        conflict = {
                            "conflict_type": "double_booking",
                            "asset_id": asset_id,
                            "reservation_a_id": a.id,
                            "reservation_b_id": b.id,
                            "overlap_start": max(a.start_time, b.start_time),
                            "overlap_end": min(a.end_time, b.end_time),
                        }
                        conflicts.append(conflict)
                        await self.bus.publish(DomainEvent(
                            type="timeline.conflict_detected",
                            source_service="timeline_service",
                            entity_type="timeline_reservation",
                            entity_id=a.id,
                            version=1,
                            payload=conflict,
                        ))

        return conflicts

    def estimate_transit_time_sec(self, from_lon: float, from_lat: float,
                                   to_lon: float, to_lat: float) -> float:
        """Great-circle distance estimate → transit time."""
        R = 6371000  # Earth radius in meters
        dlat = math.radians(to_lat - from_lat)
        dlon = math.radians(to_lon - from_lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(from_lat)) * math.cos(math.radians(to_lat)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_m = R * c
        return distance_m / self.SPEED_MPS if self.SPEED_MPS > 0 else float("inf")

    async def generate_predicted_reservations(
        self, asset_id: str, mission_id: str,
        tasks: list[dict], start_time: str,
        asset_lon: float, asset_lat: float,
    ) -> list[TimelineReservation]:
        """Generate predicted timeline blocks for a mission's tasks."""
        reservations = []
        current_time = datetime.fromisoformat(start_time)
        current_lon, current_lat = asset_lon, asset_lat

        # Launch phase
        launch_duration = timedelta(seconds=60)
        res_launch = TimelineReservation(
            asset_id=asset_id, mission_id=mission_id,
            phase=ReservationPhase.launch,
            start_time=current_time.isoformat(),
            end_time=(current_time + launch_duration).isoformat(),
            source=ReservationSource.predicted,
        )
        reservations.append(res_launch)
        await self.create_reservation(res_launch)
        current_time += launch_duration

        for task_info in tasks:
            target_lon = task_info.get("lon", current_lon)
            target_lat = task_info.get("lat", current_lat)
            service_time = task_info.get("service_time_sec", 300)

            # Transit to task
            transit_sec = self.estimate_transit_time_sec(
                current_lon, current_lat, target_lon, target_lat
            )
            transit_duration = timedelta(seconds=transit_sec)
            res_transit = TimelineReservation(
                asset_id=asset_id, mission_id=mission_id,
                task_id=task_info.get("task_id"),
                phase=ReservationPhase.transit,
                start_time=current_time.isoformat(),
                end_time=(current_time + transit_duration).isoformat(),
                source=ReservationSource.predicted,
            )
            reservations.append(res_transit)
            await self.create_reservation(res_transit)
            current_time += transit_duration

            # Task execution
            exec_duration = timedelta(seconds=service_time)
            res_exec = TimelineReservation(
                asset_id=asset_id, mission_id=mission_id,
                task_id=task_info.get("task_id"),
                phase=ReservationPhase.task_execution,
                start_time=current_time.isoformat(),
                end_time=(current_time + exec_duration).isoformat(),
                source=ReservationSource.predicted,
            )
            reservations.append(res_exec)
            await self.create_reservation(res_exec)
            current_time += exec_duration
            current_lon, current_lat = target_lon, target_lat

        # Return phase
        return_sec = self.estimate_transit_time_sec(
            current_lon, current_lat, asset_lon, asset_lat
        )
        return_duration = timedelta(seconds=return_sec)
        res_return = TimelineReservation(
            asset_id=asset_id, mission_id=mission_id,
            phase=ReservationPhase.return_,
            start_time=current_time.isoformat(),
            end_time=(current_time + return_duration).isoformat(),
            source=ReservationSource.predicted,
        )
        reservations.append(res_return)
        await self.create_reservation(res_return)
        current_time += return_duration

        # Recovery phase
        recovery_duration = timedelta(seconds=120)
        res_recovery = TimelineReservation(
            asset_id=asset_id, mission_id=mission_id,
            phase=ReservationPhase.recovery,
            start_time=current_time.isoformat(),
            end_time=(current_time + recovery_duration).isoformat(),
            source=ReservationSource.predicted,
        )
        reservations.append(res_recovery)
        await self.create_reservation(res_recovery)

        return reservations
