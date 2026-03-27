import React from 'react';
import { Card, Tag, Intent, Icon } from '@blueprintjs/core';
import { useSimStore } from '../../store/SimulationStore';

interface OpsAlertData {
  id: string;
  alert_type: string;
  severity: string;
  drone_id: number;
  message: string;
  timestamp: number;
  acknowledged: boolean;
}

const SEVERITY_INTENT: Record<string, Intent> = {
  critical: Intent.DANGER,
  warning: Intent.WARNING,
  info: Intent.PRIMARY,
};

const SEVERITY_ICON: Record<string, any> = {
  critical: 'error',
  warning: 'warning-sign',
  info: 'info-sign',
};

export function OpsAlertsPanel() {
  const opsAlerts = useSimStore((s) => (s as any).opsAlerts ?? []) as OpsAlertData[];

  if (opsAlerts.length === 0) {
    return (
      <Card style={{ margin: '8px 0', padding: '12px', background: 'rgba(0,0,0,0.2)' }}>
        <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, textAlign: 'center' }}>
          No active alerts
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)', padding: '8px 0 4px' }}>
        OPS ALERTS ({opsAlerts.length})
      </div>
      {opsAlerts.map((alert) => (
        <Card
          key={alert.id}
          style={{
            padding: '8px 10px',
            background: alert.acknowledged ? 'rgba(0,0,0,0.15)' : 'rgba(0,0,0,0.3)',
            opacity: alert.acknowledged ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Icon icon={SEVERITY_ICON[alert.severity] || 'info-sign'} intent={SEVERITY_INTENT[alert.severity]} size={14} />
          <span style={{ flex: 1, fontSize: 12 }}>{alert.message}</span>
          <Tag minimal intent={SEVERITY_INTENT[alert.severity]} style={{ fontSize: 10 }}>
            {alert.severity.toUpperCase()}
          </Tag>
        </Card>
      ))}
    </div>
  );
}
