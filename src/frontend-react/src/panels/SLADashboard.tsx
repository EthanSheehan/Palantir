import React, { useEffect, useState } from 'react';
import { Button, Icon, IconName, Tag } from '@blueprintjs/core';

/**
 * SLADashboard — sensor-to-shooter SLA dashboard for the F2T2EA kill chain.
 *
 * Renders 6 sparkline-style histograms (one per F2T2EA stage) on top of KPI
 * cards (median, p95, p99). Sources data from the Prometheus `/metrics`
 * endpoint via a parsed JSON proxy on the WebSocket (`get_sla_snapshot`).
 *
 * Until the backend serves real numbers, the panel renders synthetic latencies
 * sampled from a log-normal distribution so the UI shape is verifiable.
 */

interface StageMetrics {
  stage: 'FIND' | 'FIX' | 'TRACK' | 'TARGET' | 'ENGAGE' | 'ASSESS';
  median_ms: number;
  p95_ms: number;
  p99_ms: number;
  samples: number[]; // ms, last N
  threshold_ms: number;
}

const STAGE_COLORS: Record<StageMetrics['stage'], string> = {
  FIND:   '#22d3ee',
  FIX:    '#fbbf24',
  TRACK:  '#22c55e',
  TARGET: '#fb923c',
  ENGAGE: '#ef4444',
  ASSESS: '#06b6d4',
};

function synth(stage: StageMetrics['stage']): StageMetrics {
  const base = { FIND: 1500, FIX: 4000, TRACK: 6000, TARGET: 12000, ENGAGE: 25000, ASSESS: 18000 }[stage];
  const samples: number[] = [];
  for (let i = 0; i < 60; i++) {
    const noise = Math.exp(Math.random() * 1.5 - 0.5);
    samples.push(Math.round(base * noise * 0.6));
  }
  const sorted = [...samples].sort((a, b) => a - b);
  return {
    stage,
    median_ms: sorted[Math.floor(sorted.length * 0.5)],
    p95_ms: sorted[Math.floor(sorted.length * 0.95)],
    p99_ms: sorted[Math.floor(sorted.length * 0.99)],
    samples,
    threshold_ms: base * 1.5,
  };
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

interface Props { visible: boolean; onClose: () => void; }

export function SLADashboard({ visible, onClose }: Props) {
  const [metrics, setMetrics] = useState<StageMetrics[]>(() => (
    ['FIND', 'FIX', 'TRACK', 'TARGET', 'ENGAGE', 'ASSESS'] as const
  ).map(synth));

  useEffect(() => {
    if (!visible) return;
    function tick() {
      setMetrics(m => m.map(stage => synth(stage.stage)));
    }
    const interval = setInterval(tick, 5000);
    function onResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && Array.isArray(detail.metrics)) {
        setMetrics(detail.metrics);
      }
    }
    window.addEventListener('grid-sentinel:sla-snapshot', onResponse);
    return () => {
      clearInterval(interval);
      window.removeEventListener('grid-sentinel:sla-snapshot', onResponse);
    };
  }, [visible]);

  if (!visible) return null;

  const totalMedian = metrics.reduce((s, m) => s + m.median_ms, 0);
  const totalP95 = metrics.reduce((s, m) => s + m.p95_ms, 0);
  const breaches = metrics.filter(m => m.p95_ms > m.threshold_ms).length;

  return (
    <div
      role="region"
      aria-label="SLA dashboard"
      style={{
        position: 'fixed',
        top: 80,
        right: 12,
        width: 480,
        maxHeight: 'calc(100vh - 100px)',
        background: 'rgba(7, 11, 17, 0.97)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        boxShadow: '-8px 8px 32px rgba(0,0,0,0.55)',
        zIndex: 8200,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15, 20, 30, 0.95)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon={'timeline-bar-chart' as IconName} size={12} color="#ef4444" />
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 11, letterSpacing: '0.16em', color: '#e2e8f0' }}>
            SENSOR-TO-SHOOTER SLA
          </span>
        </div>
        <Button minimal small icon={'cross' as IconName} onClick={onClose} aria-label="Close" />
      </div>

      {/* KPI strip */}
      <div style={{
        display: 'flex',
        gap: 6,
        padding: '8px 10px',
        background: 'rgba(15, 20, 30, 0.6)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <Kpi label="F2T2EA median" value={fmtMs(totalMedian)} accent="#22c55e" />
        <Kpi label="F2T2EA p95" value={fmtMs(totalP95)} accent="#fbbf24" />
        <Kpi label="SLA breaches" value={String(breaches)} accent={breaches > 0 ? '#ef4444' : '#22c55e'} />
      </div>

      {/* Stage histograms */}
      <div style={{ padding: '6px 10px', overflowY: 'auto', flex: 1 }}>
        {metrics.map(m => <StageRow key={m.stage} m={m} />)}
      </div>

      <div style={{
        padding: '4px 10px',
        borderTop: '1px solid rgba(255,255,255,0.05)',
        fontSize: 9,
        color: '#475569',
        fontFamily: 'monospace',
      }}>
        {breaches > 0
          ? `⚠ ${breaches} stage(s) over SLA threshold`
          : 'all stages within SLA · refreshed every 5s'}
      </div>
    </div>
  );
}

function Kpi({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div style={{
      flex: 1,
      padding: 6,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 3,
    }}>
      <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        {label}
      </div>
      <div style={{ fontFamily: 'monospace', fontSize: 16, fontWeight: 700, color: accent, marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

function StageRow({ m }: { m: StageMetrics }) {
  const color = STAGE_COLORS[m.stage];
  const breached = m.p95_ms > m.threshold_ms;
  const max = Math.max(...m.samples, m.threshold_ms);
  const thresholdPct = (m.threshold_ms / max) * 100;
  return (
    <div style={{
      padding: '6px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <Tag minimal style={{
          background: `${color}22`, color, border: `1px solid ${color}55`,
          fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.08em',
        }}>{m.stage}</Tag>
        <div style={{ display: 'flex', gap: 8, fontSize: 10, fontFamily: 'monospace', color: '#cbd5e1' }}>
          <span>p50 <span style={{ color }}>{fmtMs(m.median_ms)}</span></span>
          <span>p95 <span style={{ color: breached ? '#ef4444' : color }}>{fmtMs(m.p95_ms)}</span></span>
          <span>p99 <span style={{ color: breached ? '#ef4444' : color }}>{fmtMs(m.p99_ms)}</span></span>
        </div>
      </div>
      {/* Mini histogram */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 24, position: 'relative' }}>
        {m.samples.map((s, i) => {
          const h = Math.max(2, (s / max) * 24);
          const over = s > m.threshold_ms;
          return (
            <span key={i} style={{
              flex: 1,
              height: h,
              background: over ? '#ef4444' : color,
              opacity: 0.85,
              borderRadius: 1,
            }} />
          );
        })}
        <div style={{
          position: 'absolute',
          left: 0, right: 0,
          bottom: thresholdPct / 100 * 24,
          height: 1,
          background: '#ef4444aa',
          borderTop: '1px dashed #ef4444',
        }} />
      </div>
    </div>
  );
}
