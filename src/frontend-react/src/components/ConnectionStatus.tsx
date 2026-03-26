import React, { useEffect, useRef, useState } from 'react';
import { Tag } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';

const MAX_SAMPLES = 20;

function latencyColor(latencyMs: number | null, connected: boolean): string {
  if (!connected) return '#ef4444';
  if (latencyMs === null) return '#eab308';
  if (latencyMs < 1000) return '#22c55e';
  if (latencyMs < 5000) return '#eab308';
  return '#ef4444';
}

function latencyLabel(latencyMs: number | null, connected: boolean): string {
  if (!connected) return 'DISCONNECTED';
  if (latencyMs === null) return 'CONNECTING';
  if (latencyMs < 1000) return `${latencyMs}ms`;
  return `${(latencyMs / 1000).toFixed(1)}s`;
}

export function ConnectionStatus() {
  const connected = useSimStore(s => s.connected);
  const [avgLatency, setAvgLatency] = useState<number | null>(null);
  const samplesRef = useRef<number[]>([]);
  const lastTickRef = useRef<number>(Date.now());

  // Use a store field that changes every tick to drive latency measurement
  const tickCount = useSimStore(s => s.targets?.length ?? 0);

  // Measure time between state updates as a proxy for latency
  useEffect(() => {
    if (!connected) {
      samplesRef.current = [];
      setAvgLatency(null);
      return;
    }
    const now = Date.now();
    const delta = now - lastTickRef.current;
    lastTickRef.current = now;

    if (delta < 30000) {
      samplesRef.current = [...samplesRef.current, delta].slice(-MAX_SAMPLES);
      const avg = Math.round(
        samplesRef.current.reduce((a, b) => a + b, 0) / samplesRef.current.length
      );
      setAvgLatency(avg);
    }
  }, [connected, tickCount]);

  const color = latencyColor(avgLatency, connected);
  const label = latencyLabel(avgLatency, connected);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 5px 1px ${color}88`,
          flexShrink: 0,
        }}
      />
      <Tag
        minimal
        style={{
          background: 'transparent',
          color: color,
          fontSize: 9,
          fontFamily: 'monospace',
          letterSpacing: '0.04em',
          padding: '0 4px',
          minHeight: 'unset',
        }}
      >
        {label}
      </Tag>
    </div>
  );
}
