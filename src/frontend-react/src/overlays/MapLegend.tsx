import React from 'react';
import { Card } from '@blueprintjs/core';

interface LegendItem {
  color: string;
  label: string;
  shape?: 'circle' | 'square' | 'diamond' | 'line' | 'dashed';
}

interface LegendCategory {
  title: string;
  items: LegendItem[];
}

const LEGEND_CATEGORIES: LegendCategory[] = [
  {
    title: 'Drones',
    items: [
      { color: '#3b82f6', label: 'IDLE / SEARCH', shape: 'circle' },
      { color: '#22c55e', label: 'FOLLOW / PAINT', shape: 'circle' },
      { color: '#ef4444', label: 'INTERCEPT', shape: 'circle' },
      { color: '#a855f7', label: 'OVERWATCH / BDA', shape: 'circle' },
      { color: '#f59e0b', label: 'RTB / REPOSITIONING', shape: 'circle' },
    ],
  },
  {
    title: 'Targets',
    items: [
      { color: '#ef4444', label: 'SAM / TEL / RADAR', shape: 'square' },
      { color: '#f59e0b', label: 'CP / C2_NODE', shape: 'square' },
      { color: '#94a3b8', label: 'TRUCK / LOGISTICS', shape: 'square' },
      { color: '#ec4899', label: 'MANPADS / APC', shape: 'square' },
      { color: '#dc2626', label: 'ARTILLERY', shape: 'diamond' },
    ],
  },
  {
    title: 'Enemy UAVs',
    items: [
      { color: '#f87171', label: 'RECON', shape: 'diamond' },
      { color: '#dc2626', label: 'ATTACK', shape: 'diamond' },
      { color: '#fbbf24', label: 'JAMMING', shape: 'diamond' },
      { color: '#94a3b8', label: 'EVADING / DESTROYED', shape: 'diamond' },
    ],
  },
  {
    title: 'Zones & Overlays',
    items: [
      { color: 'rgba(59,130,246,0.3)', label: 'Grid Zone', shape: 'square' },
      { color: '#22c55e', label: 'Coverage Layer', shape: 'line' },
      { color: '#ef4444', label: 'Threat Layer', shape: 'square' },
      { color: '#a855f7', label: 'Fusion Layer', shape: 'circle' },
      { color: '#3b82f6', label: 'Swarm Assignment', shape: 'dashed' },
      { color: '#94a3b8', label: 'Flow Lines', shape: 'line' },
    ],
  },
];

function ShapeIcon({ color, shape = 'circle' }: { color: string; shape?: LegendItem['shape'] }) {
  const base: React.CSSProperties = { flexShrink: 0, display: 'inline-block' };

  if (shape === 'circle') {
    return (
      <div style={{ ...base, width: 10, height: 10, borderRadius: '50%', background: color }} />
    );
  }
  if (shape === 'square') {
    return (
      <div style={{ ...base, width: 10, height: 10, borderRadius: 2, background: color }} />
    );
  }
  if (shape === 'diamond') {
    return (
      <div style={{
        ...base,
        width: 8,
        height: 8,
        background: color,
        transform: 'rotate(45deg)',
        borderRadius: 1,
      }} />
    );
  }
  if (shape === 'line') {
    return (
      <div style={{ ...base, width: 14, height: 2, background: color, borderRadius: 1, marginTop: 4 }} />
    );
  }
  if (shape === 'dashed') {
    return (
      <div style={{
        ...base,
        width: 14,
        height: 2,
        borderTop: `2px dashed ${color}`,
        marginTop: 4,
        background: 'transparent',
      }} />
    );
  }
  return null;
}

interface MapLegendProps {
  visible: boolean;
}

export function MapLegend({ visible }: MapLegendProps) {
  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 40,
        right: 16,
        zIndex: 1000,
        width: 220,
        pointerEvents: 'auto',
      }}
    >
      <Card
        style={{
          background: 'rgba(15, 20, 30, 0.94)',
          border: '1px solid rgba(255,255,255,0.1)',
          padding: 12,
          borderRadius: 4,
        }}
      >
        <div style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: '0.1em',
          color: '#94a3b8',
          textTransform: 'uppercase',
          marginBottom: 10,
          display: 'flex',
          justifyContent: 'space-between',
        }}>
          <span>MAP LEGEND</span>
          <span style={{ color: '#475569', fontSize: 9 }}>L to toggle</span>
        </div>

        {LEGEND_CATEGORIES.map(cat => (
          <div key={cat.title} style={{ marginBottom: 10 }}>
            <div style={{
              fontSize: 9,
              fontWeight: 700,
              color: '#64748b',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              marginBottom: 5,
              borderBottom: '1px solid rgba(255,255,255,0.04)',
              paddingBottom: 3,
            }}>
              {cat.title}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {cat.items.map(item => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <ShapeIcon color={item.color} shape={item.shape} />
                  <span style={{ fontSize: 10, color: '#94a3b8' }}>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
