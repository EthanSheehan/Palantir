import { Button, Tag, Intent, ProgressBar, NonIdealState } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import { useSelectedAsset, useSelectedMission, useSelectedAlert } from '../../store/selectors';
import * as api from '../../services/apiClient';
import './InspectorPanel.css';

export function InspectorPanel() {
  const selection = useAppStore((s) => s.selection);

  if (selection.primaryAssetId) return <AssetInspector />;
  if (selection.missionId) return <MissionInspector />;
  if (selection.alertId) return <AlertInspector />;

  return (
    <NonIdealState
      icon="search"
      title="Inspector"
      description="Select an asset, mission, or alert to inspect."
      className="inspector-empty"
    />
  );
}

function AssetInspector() {
  const asset = useSelectedAsset();
  if (!asset) return null;

  const pos = asset.position || { lon: 0, lat: 0 };
  const batteryPct = asset.battery_pct ?? 0;
  const linkPct = (asset.link_quality ?? 0) * 100;

  return (
    <div className="inspector-content">
      <div className="inspector-header">
        <h3>{asset.name || asset.id}</h3>
        <Tag intent={asset.status === 'active' ? Intent.SUCCESS : Intent.NONE} minimal>
          {asset.status}
        </Tag>
      </div>

      <Section title="Info">
        <Row label="Type" value={asset.type} />
        <Row label="Mode" value={asset.mode} />
        <Row label="Health" value={asset.health} />
      </Section>

      <Section title="Telemetry">
        <Row label="Lon" value={pos.lon?.toFixed(5)} />
        <Row label="Lat" value={pos.lat?.toFixed(5)} />
        <Row label="Alt" value={`${(pos.alt_m ?? 0).toFixed(0)} m`} />
        <Row label="Heading" value={`${(asset.heading_deg ?? 0).toFixed(1)}\u00B0`} />
      </Section>

      <Section title="Systems">
        <Row label="Battery" value={`${batteryPct.toFixed(1)}%`} />
        <ProgressBar
          value={batteryPct / 100}
          intent={batteryPct > 30 ? Intent.SUCCESS : Intent.DANGER}
          stripes={false}
          className="inspector-bar"
        />
        <Row label="Link" value={`${linkPct.toFixed(0)}%`} />
      </Section>
    </div>
  );
}

function MissionInspector() {
  const mission = useSelectedMission();
  const selectAsset = useAppStore((s) => s.selectAsset);

  if (!mission) return null;

  return (
    <div className="inspector-content">
      <div className="inspector-header">
        <h3>{mission.name || mission.id}</h3>
        <Tag intent={stateIntent(mission.state)} minimal>{mission.state}</Tag>
      </div>

      <Section title="Details">
        <Row label="Type" value={mission.type} />
        <Row label="Priority" value={mission.priority} />
        <Row label="Objective" value={mission.objective || 'None'} />
      </Section>

      {mission.asset_ids && mission.asset_ids.length > 0 && (
        <Section title={`Assets (${mission.asset_ids.length})`}>
          {mission.asset_ids.map((aid) => (
            <div
              key={aid}
              className="inspector-row clickable"
              onClick={() => selectAsset(aid)}
            >
              <span>{aid}</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function AlertInspector() {
  const alert = useSelectedAlert();
  if (!alert) return null;

  const handleAck = async () => {
    try { await api.acknowledgeAlert(alert.id); } catch (e) { console.error(e); }
  };

  const handleClear = async () => {
    try { await api.clearAlert(alert.id); } catch (e) { console.error(e); }
  };

  return (
    <div className="inspector-content">
      <div className="inspector-header">
        <h3>Alert</h3>
        <Tag intent={severityIntent(alert.severity)} minimal>{alert.severity}</Tag>
        <Tag minimal>{alert.state}</Tag>
      </div>

      <Section title="Details">
        <Row label="Type" value={alert.type.replace(/_/g, ' ')} />
        <Row label="Source" value={`${alert.source_type}: ${alert.source_id}`} />
      </Section>

      <div className="inspector-section">
        <p className="inspector-text">{alert.message}</p>
      </div>

      <div className="inspector-actions">
        {alert.state === 'open' && (
          <Button small intent={Intent.SUCCESS} onClick={handleAck}>Acknowledge</Button>
        )}
        {alert.state === 'acknowledged' && (
          <Button small intent={Intent.WARNING} onClick={handleClear}>Clear</Button>
        )}
      </div>
    </div>
  );
}

// Helper components
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="inspector-section">
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="inspector-row">
      <span className="inspector-label">{label}</span>
      <span className="inspector-value">{value ?? '-'}</span>
    </div>
  );
}

function stateIntent(state: string): Intent {
  switch (state) {
    case 'active': return Intent.SUCCESS;
    case 'completed': return Intent.PRIMARY;
    case 'failed': case 'aborted': return Intent.DANGER;
    case 'paused': return Intent.WARNING;
    default: return Intent.NONE;
  }
}

function severityIntent(severity: string): Intent {
  switch (severity) {
    case 'critical': return Intent.DANGER;
    case 'warning': return Intent.WARNING;
    default: return Intent.PRIMARY;
  }
}
