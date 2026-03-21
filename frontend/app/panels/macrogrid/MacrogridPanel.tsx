import { useEffect } from 'react';
import { Button, Card, Tag, Intent, NonIdealState } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import type { Recommendation } from '../../store/types';
import * as api from '../../services/apiClient';
import './MacrogridPanel.css';

export function MacrogridPanel() {
  const recommendations = useAppStore((s) => s.recommendations);

  // Periodic refresh
  useEffect(() => {
    const updateRec = useAppStore.getState().updateRecommendation;
    const load = async () => {
      try {
        const data = await api.getRecommendations();
        data.recommendations.forEach((r: Recommendation) => updateRec(r));
      } catch { /* API may not be ready */ }
    };

    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const recList = Object.values(recommendations).sort(
    (a, b) => Math.abs(b.pressure_delta ?? 0) - Math.abs(a.pressure_delta ?? 0)
  );

  if (recList.length === 0) {
    return (
      <NonIdealState
        icon="grid-view"
        title="Macro-Grid"
        description="No active recommendations"
        className="macrogrid-empty"
      />
    );
  }

  return (
    <div className="macrogrid-panel">
      <h3 className="panel-title">Macro-Grid Recommendations</h3>
      {recList.map((rec) => (
        <RecCard key={rec.id} rec={rec} />
      ))}
    </div>
  );
}

function formatZone(zone?: { id: number[]; lon: number; lat: number }): string {
  if (!zone) return '?';
  return `[${zone.id.join(',')}]`;
}

function RecCard({ rec }: { rec: Recommendation }) {
  const handleConvert = async () => {
    try {
      const mission = await api.convertRecommendation(rec.id);
      useAppStore.getState().updateMission(mission);
    } catch (e) {
      console.error('Convert failed:', e);
    }
  };

  return (
    <Card className="rec-card-bp">
      <div className="rec-header">
        <span className="rec-zones">
          {formatZone(rec.source_zone)} &rarr; {formatZone(rec.target_zone)}
        </span>
        <Tag intent={Intent.PRIMARY} minimal>
          {((rec.confidence ?? 0) * 100).toFixed(0)}%
        </Tag>
      </div>
      <div className="rec-meta">
        <span>Move {rec.suggested_asset_count ?? 0} asset(s)</span>
        <span>Pressure: {(rec.pressure_delta ?? 0).toFixed(1)}</span>
      </div>
      <Button small intent={Intent.SUCCESS} onClick={handleConvert}>
        Convert to Mission
      </Button>
    </Card>
  );
}
