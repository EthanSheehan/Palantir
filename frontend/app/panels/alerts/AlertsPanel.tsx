import { useEffect } from 'react';
import { Button, Card, Tag, Intent, NonIdealState } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import type { Alert } from '../../store/types';
import * as api from '../../services/apiClient';
import { cesiumBridge } from '../../store/adapters/cesiumBridge';
import './AlertsPanel.css';

const SEVERITY_INTENT: Record<string, Intent> = {
  critical: Intent.DANGER,
  warning: Intent.WARNING,
  info: Intent.PRIMARY,
};

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

export function AlertsPanel() {
  const alerts = useAppStore((s) => s.alerts);
  const selectedAlertId = useAppStore((s) => s.selection.alertId);
  const selectAlert = useAppStore((s) => s.selectAlert);

  const updateAlertInStore = useAppStore((s) => s.updateAlert);

  // Load alerts from API on mount
  useEffect(() => {
    api.listAlerts()
      .then((data) => {
        data.alerts.forEach((a) => updateAlertInStore(a));
      })
      .catch(() => { /* API might not be ready */ });
  }, [updateAlertInStore]);

  const alertList = Object.values(alerts)
    .filter((a) => a.state !== 'cleared')
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 2) - (SEVERITY_ORDER[b.severity] ?? 2));

  if (alertList.length === 0) {
    return (
      <NonIdealState
        icon="notifications"
        title="No active alerts"
        className="alerts-empty"
      />
    );
  }

  return (
    <div className="alerts-panel">
      <h3 className="alerts-title">Alerts</h3>
      {alertList.map((alert) => (
        <AlertCard
          key={alert.id}
          alert={alert}
          isSelected={alert.id === selectedAlertId}
          onSelect={() => {
            selectAlert(alert.id);
            // Fly to the source entity on the map if it's an asset
            if (alert.source_type === 'asset' && alert.source_id) {
              cesiumBridge.flyToEntity(alert.source_id);
            }
          }}
        />
      ))}
    </div>
  );
}

function AlertCard({
  alert,
  isSelected,
  onSelect,
}: {
  alert: Alert;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const updateAlertInStore = useAppStore((s) => s.updateAlert);

  const handleAck = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.acknowledgeAlert(alert.id);
      const data = await api.listAlerts();
      data.alerts.forEach((a: Alert) => updateAlertInStore(a));
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const intent = SEVERITY_INTENT[alert.severity] ?? Intent.NONE;

  return (
    <Card
      className={`alert-card-bp${isSelected ? ' alert-selected' : ''}`}
      interactive
      onClick={onSelect}
    >
      <div className="alert-header">
        <Tag intent={intent} minimal>
          {alert.severity.toUpperCase()}
        </Tag>
        <span className="alert-type">{alert.type.replace(/_/g, ' ')}</span>
        <Tag className="alert-state-tag" minimal>
          {alert.state}
        </Tag>
      </div>
      <div className="alert-message">{alert.message}</div>
      <div className="alert-footer">
        <span className="alert-source">
          {alert.source_type}: {alert.source_id}
        </span>
        {alert.state === 'open' && (
          <Button
            small
            intent={Intent.SUCCESS}
            onClick={handleAck}
          >
            ACK
          </Button>
        )}
      </div>
    </Card>
  );
}
