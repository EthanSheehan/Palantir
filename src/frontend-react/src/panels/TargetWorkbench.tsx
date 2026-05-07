import React, { useMemo, useState } from 'react';
import { Button, Intent, Tag, Icon, IconName, Tooltip } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';
import { Target } from '../store/types';

/**
 * TargetWorkbench — Maven-style kanban replacing the floating strike board.
 *
 * Eight columns map exactly onto the F2T2EA + verification + engagement
 * lifecycle. State advancement is enforced by the backend `verification_engine`
 * (no drag-to-advance — that would bypass ROE). Approve / Reject / Retask
 * actions are the only operator levers and they live on the NOMINATED column.
 */

type StageKey =
  | 'DETECTED'
  | 'CLASSIFIED'
  | 'VERIFIED'
  | 'NOMINATED'
  | 'AUTHORIZED'
  | 'ENGAGING'
  | 'BDA'
  | 'COMPLETE';

interface Stage {
  key: StageKey;
  label: string;
  states: string[];
  accent: string;
  hint: string;
}

const STAGES: Stage[] = [
  { key: 'DETECTED',   label: 'DETECTED',   states: ['DETECTED'],                 accent: '#dc2626', hint: 'Sensor contact, low confidence' },
  { key: 'CLASSIFIED', label: 'CLASSIFIED', states: ['CLASSIFIED'],               accent: '#f59e0b', hint: 'Type identified' },
  { key: 'VERIFIED',   label: 'VERIFIED',   states: ['VERIFIED'],                 accent: '#22c55e', hint: 'Multi-INT corroborated' },
  { key: 'NOMINATED',  label: 'NOMINATED',  states: ['NOMINATED'],                accent: '#fbbf24', hint: 'Awaiting human approval', },
  { key: 'AUTHORIZED', label: 'AUTHORIZED', states: ['AUTHORIZED', 'APPROVED'],   accent: '#3b82f6', hint: 'COA approved, awaiting effector' },
  { key: 'ENGAGING',   label: 'ENGAGING',   states: ['ENGAGED', 'ENGAGING'],      accent: '#a855f7', hint: 'Effector dispatched' },
  { key: 'BDA',        label: 'BDA',        states: ['BDA', 'ASSESSED'],          accent: '#06b6d4', hint: 'Battle damage assessment' },
  { key: 'COMPLETE',   label: 'COMPLETE',   states: ['COMPLETE', 'CLOSED', 'NEUTRALIZED'], accent: '#475569', hint: 'Closed' },
];

const TYPE_COLORS: Record<string, string> = {
  SAM:       '#ef4444',
  TEL:       '#fb923c',
  TRUCK:     '#e2e8f0',
  CP:        '#3b82f6',
  MANPADS:   '#c084fc',
  RADAR:     '#22d3ee',
  C2_NODE:   '#facc15',
  LOGISTICS: '#94a3b8',
  ARTILLERY: '#f472b6',
  APC:       '#a16207',
};

interface CardProps {
  target: Target;
  stage: Stage;
}

function TargetCard({ target, stage }: CardProps) {
  const sendMessage = useSendMessage();
  const selectTarget = useSimStore(s => s.selectTarget);
  const setActiveTab = useSimStore(s => s.setActiveTab);
  const typeColor = TYPE_COLORS[target.type] ?? '#cbd5e1';
  const fused = Math.round((target.fused_confidence ?? 0) * 100);
  const sensorTypes = useMemo<string[]>(() => {
    const set = new Set<string>();
    for (const c of target.sensor_contributions ?? []) set.add(c.sensor_type);
    return Array.from(set);
  }, [target.sensor_contributions]);

  const onSelect = () => {
    selectTarget(target.id);
    setActiveTab('enemies');
  };

  const isNominated = stage.key === 'NOMINATED';

  return (
    <div
      onClick={onSelect}
      className="gs-card-enter"
      style={{
        background: 'rgba(15, 20, 30, 0.92)',
        border: `1px solid ${stage.accent}66`,
        borderLeft: `3px solid ${stage.accent}`,
        borderRadius: 3,
        padding: '6px 8px',
        marginBottom: 6,
        cursor: 'pointer',
        fontSize: 11,
        transition: 'background 80ms',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(30, 41, 59, 0.95)')}
      onMouseLeave={e => (e.currentTarget.style.background = 'rgba(15, 20, 30, 0.92)')}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontFamily: 'monospace', fontSize: 10, color: '#94a3b8', letterSpacing: '0.06em' }}>
          #{String(target.id).padStart(4, '0')}
        </span>
        <span style={{ color: typeColor, fontWeight: 700, fontSize: 11, letterSpacing: '0.08em' }}>
          {target.type}
        </span>
      </div>

      {/* Fused confidence bar */}
      <div style={{ height: 4, background: 'rgba(255,255,255,0.07)', borderRadius: 2, overflow: 'hidden', marginBottom: 4 }}>
        <div style={{
          width: `${fused}%`,
          height: '100%',
          background: `linear-gradient(90deg, ${stage.accent}88, ${stage.accent})`,
          transition: 'width 180ms',
        }} />
      </div>
      {/* Confidence sparkline — beyond-Maven differentiator. Maven shows
          only the snapshot; we show whether confidence is climbing or
          decaying over the last ~60 ticks (~6s at 10Hz). */}
      <ConfidenceSparkline values={target.confidence_history} accent={stage.accent} />

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginBottom: 4 }}>
        <span>{fused}% conf</span>
        <span>{target.sensor_count ?? 0} sensors</span>
        <span>{Math.floor(target.time_in_state_sec ?? 0)}s</span>
      </div>

      {sensorTypes.length > 0 && (
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', marginBottom: isNominated ? 6 : 0 }}>
          {sensorTypes.map(s => (
            <span key={s} style={{
              fontSize: 8,
              padding: '1px 4px',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 2,
              color: '#cbd5e1',
              fontFamily: 'monospace',
              letterSpacing: '0.04em',
            }}>{s}</span>
          ))}
        </div>
      )}

      {isNominated && (
        <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
          <Button
            small minimal intent={Intent.SUCCESS}
            text="APPROVE"
            style={{ fontSize: 9, padding: '2px 6px' }}
            onClick={() => sendMessage({ action: 'approve_nomination', target_id: target.id, rationale: 'Workbench approve' })}
          />
          <Button
            small minimal intent={Intent.DANGER}
            text="REJECT"
            style={{ fontSize: 9, padding: '2px 6px' }}
            onClick={() => sendMessage({ action: 'reject_nomination', target_id: target.id, rationale: 'Workbench reject' })}
          />
          <Button
            small minimal
            text="RETASK"
            style={{ fontSize: 9, padding: '2px 6px', color: '#94a3b8' }}
            onClick={() => sendMessage({ action: 'retask_nomination', target_id: target.id })}
          />
        </div>
      )}
    </div>
  );
}

function ConfidenceSparkline({ values, accent }: { values?: number[]; accent: string }) {
  if (!values || values.length < 2) {
    return null;
  }
  const v = values.slice(-60);
  const max = 1.0; // confidence space is [0, 1]
  const W = 160;   // virtual width — scales via SVG viewBox
  const H = 18;
  const stepX = W / (v.length - 1);
  const points = v.map((val, i) => {
    const x = i * stepX;
    const y = H - Math.max(0, Math.min(1, val / max)) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  // Trend arrow: compare last 5 vs first 5
  const head = v.slice(0, Math.min(5, v.length));
  const tail = v.slice(-Math.min(5, v.length));
  const headAvg = head.reduce((a, b) => a + b, 0) / head.length;
  const tailAvg = tail.reduce((a, b) => a + b, 0) / tail.length;
  const trend = tailAvg - headAvg;
  const trendChar = trend > 0.05 ? '▲' : trend < -0.05 ? '▼' : '·';
  const trendColor = trend > 0.05 ? '#22c55e' : trend < -0.05 ? '#ef4444' : '#475569';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ flex: 1, height: H, overflow: 'visible' }} preserveAspectRatio="none">
        <polyline
          fill="none"
          stroke={accent}
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
          opacity={0.85}
        />
      </svg>
      <span style={{ fontSize: 9, color: trendColor, fontFamily: 'monospace', minWidth: 8, textAlign: 'right' }}>
        {trendChar}
      </span>
    </div>
  );
}


interface ColumnProps {
  stage: Stage;
  targets: Target[];
}

function Column({ stage, targets }: ColumnProps) {
  return (
    <div style={{
      flex: '1 1 0',
      minWidth: 168,
      borderRight: '1px solid rgba(255,255,255,0.05)',
      display: 'flex',
      flexDirection: 'column',
      background: 'rgba(11, 15, 23, 0.6)',
    }}>
      <div style={{
        padding: '8px 10px',
        borderBottom: `2px solid ${stage.accent}`,
        background: `${stage.accent}11`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 10, letterSpacing: '0.14em', color: stage.accent }}>
            {stage.label}
          </span>
          <Tag minimal style={{
            background: `${stage.accent}22`,
            color: stage.accent,
            border: `1px solid ${stage.accent}55`,
            fontSize: 9,
            padding: '0 5px',
            minHeight: 16,
          }}>{targets.length}</Tag>
        </div>
        <Tooltip content={stage.hint} compact>
          <div style={{ fontSize: 9, color: '#64748b', marginTop: 2, letterSpacing: '0.04em' }}>
            {stage.hint}
          </div>
        </Tooltip>
      </div>
      <div style={{ flex: 1, padding: 6, overflowY: 'auto', minHeight: 0 }}>
        {targets.length === 0 ? (
          <div style={{ color: '#334155', fontSize: 10, fontStyle: 'italic', padding: '12px 6px', textAlign: 'center' }}>
            (none)
          </div>
        ) : (
          targets.map(t => <TargetCard key={t.id} target={t} stage={stage} />)
        )}
      </div>
    </div>
  );
}

interface Props {
  visible: boolean;
  onToggle: () => void;
}

export function TargetWorkbench({ visible, onToggle }: Props) {
  const targets = useSimStore(s => s.targets);
  const [collapsed, setCollapsed] = useState(false);

  const buckets = useMemo(() => {
    const result: Record<StageKey, Target[]> = {
      DETECTED: [], CLASSIFIED: [], VERIFIED: [], NOMINATED: [],
      AUTHORIZED: [], ENGAGING: [], BDA: [], COMPLETE: [],
    };
    for (const t of targets) {
      const s = (t.state ?? '').toUpperCase();
      const stage = STAGES.find(stage => stage.states.includes(s));
      if (stage) result[stage.key].push(t);
    }
    // Sort each bucket: highest fused_confidence first
    for (const key of Object.keys(result) as StageKey[]) {
      result[key].sort((a, b) => (b.fused_confidence ?? 0) - (a.fused_confidence ?? 0));
    }
    return result;
  }, [targets]);

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Target Workbench"
      className="gs-glass"
      style={{
        position: 'fixed',
        left: 12,
        right: 12,
        bottom: 12,
        height: collapsed ? 32 : 320,
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        zIndex: 8500,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        transition: 'height 180ms',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '4px 10px',
        background: 'rgba(15, 20, 30, 0.95)',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon icon={'target' as IconName} size={12} color="#fbbf24" />
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 11, letterSpacing: '0.18em', color: '#e2e8f0' }}>
            TARGET WORKBENCH
          </span>
          <span style={{ fontSize: 10, color: '#64748b' }}>· F2T2EA pipeline</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Button minimal small icon={collapsed ? ('chevron-up' as IconName) : ('minimize' as IconName)}
                  onClick={() => setCollapsed(c => !c)} aria-label="Collapse" />
          <Button minimal small icon={'cross' as IconName} onClick={onToggle} aria-label="Close" />
        </div>
      </div>

      {/* Columns */}
      {!collapsed && (
        <div style={{ display: 'flex', flexDirection: 'row', flex: 1, minHeight: 0 }}>
          {STAGES.map(stage => (
            <Column key={stage.key} stage={stage} targets={buckets[stage.key]} />
          ))}
        </div>
      )}
    </div>
  );
}
