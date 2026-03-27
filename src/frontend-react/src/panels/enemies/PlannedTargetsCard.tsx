import React from 'react';
import { Card, Tag, Intent, Icon } from '@blueprintjs/core';

interface Aimpoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  description?: string;
}

interface PlannedTargetData {
  id: string;
  name: string;
  lat: number;
  lon: number;
  target_type: string;
  priority: number;
  notes: string;
  aimpoints: Aimpoint[];
}

const PRIORITY_INTENT: Record<number, Intent> = {
  1: Intent.DANGER,
  2: Intent.WARNING,
  3: Intent.PRIMARY,
  4: Intent.SUCCESS,
  5: Intent.NONE,
};

export function PlannedTargetsCard({ targets }: { targets: PlannedTargetData[] }) {
  if (targets.length === 0) {
    return (
      <Card style={{ margin: '8px 0', padding: '12px', background: 'rgba(0,0,0,0.2)' }}>
        <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, textAlign: 'center' }}>
          No planned targets
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)', padding: '8px 0 4px' }}>
        PLANNED TARGETS ({targets.length})
      </div>
      {targets.map((t) => (
        <Card key={t.id} style={{ padding: '8px 10px', background: 'rgba(0,0,0,0.25)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <Icon icon="locate" size={12} />
            <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{t.name}</span>
            <Tag minimal intent={PRIORITY_INTENT[t.priority] || Intent.NONE} style={{ fontSize: 10 }}>
              P{t.priority}
            </Tag>
            <Tag minimal style={{ fontSize: 10 }}>{t.target_type}</Tag>
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>
            {t.lat.toFixed(4)}&deg;N, {t.lon.toFixed(4)}&deg;E
          </div>
          {t.aimpoints.length > 0 && (
            <div style={{ marginTop: 4, paddingLeft: 12, borderLeft: '2px solid rgba(100,180,255,0.3)' }}>
              {t.aimpoints.map((ap) => (
                <div key={ap.id} style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', padding: '1px 0' }}>
                  <Icon icon="small-cross" size={10} /> {ap.name} ({ap.lat.toFixed(4)}, {ap.lon.toFixed(4)})
                </div>
              ))}
            </div>
          )}
          {t.notes && (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 4, fontStyle: 'italic' }}>
              {t.notes}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
