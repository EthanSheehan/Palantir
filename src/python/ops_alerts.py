from dataclasses import dataclass
from typing import Dict, List
import time


@dataclass(frozen=True)
class OpsAlert:
    id: str
    alert_type: str  # 'low_battery', 'rtb_active'
    severity: str  # 'info', 'warning', 'critical'
    drone_id: int
    message: str
    timestamp: float
    acknowledged: bool = False


class OpsAlertManager:
    def __init__(self):
        self._alerts: Dict[str, OpsAlert] = {}

    def evaluate_drone(self, drone_id: int, fuel_hours: float, mode: str) -> List[OpsAlert]:
        new_alerts = []

        battery_key = f"battery_{drone_id}"
        if fuel_hours < 1.0:
            severity = 'critical' if fuel_hours < 0.5 else 'warning'
            existing = self._alerts.get(battery_key)
            if existing is None or existing.severity != severity:
                alert = OpsAlert(
                    id=battery_key,
                    alert_type='low_battery',
                    severity=severity,
                    drone_id=drone_id,
                    message=f"UAV-{drone_id} fuel low: {fuel_hours:.1f}h remaining",
                    timestamp=time.time(),
                )
                self._alerts[battery_key] = alert
                new_alerts.append(alert)
        elif battery_key in self._alerts:
            del self._alerts[battery_key]

        rtb_key = f"rtb_{drone_id}"
        if mode == 'RTB':
            if rtb_key not in self._alerts:
                alert = OpsAlert(
                    id=rtb_key,
                    alert_type='rtb_active',
                    severity='info',
                    drone_id=drone_id,
                    message=f"UAV-{drone_id} returning to base",
                    timestamp=time.time(),
                )
                self._alerts[rtb_key] = alert
                new_alerts.append(alert)
        elif rtb_key in self._alerts:
            del self._alerts[rtb_key]

        return new_alerts

    def acknowledge(self, alert_id: str) -> bool:
        if alert_id not in self._alerts:
            return False
        old = self._alerts[alert_id]
        self._alerts[alert_id] = OpsAlert(
            id=old.id,
            alert_type=old.alert_type,
            severity=old.severity,
            drone_id=old.drone_id,
            message=old.message,
            timestamp=old.timestamp,
            acknowledged=True,
        )
        return True

    def get_active_alerts(self) -> List[dict]:
        return [
            {
                'id': a.id,
                'alert_type': a.alert_type,
                'severity': a.severity,
                'drone_id': a.drone_id,
                'message': a.message,
                'timestamp': a.timestamp,
                'acknowledged': a.acknowledged,
            }
            for a in sorted(self._alerts.values(), key=lambda a: a.timestamp, reverse=True)
        ]

    def clear_drone_alerts(self, drone_id: int):
        keys = [k for k, a in self._alerts.items() if a.drone_id == drone_id]
        for k in keys:
            del self._alerts[k]
