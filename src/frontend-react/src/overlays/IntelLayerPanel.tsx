import React, { useState } from 'react';
import { Switch, Slider, Icon, IconName } from '@blueprintjs/core';

/**
 * IntelLayerPanel — stack of toggleable INT-discipline layers.
 *
 * Maven shows EO + SAR + SIGINT + MTI as separate, simultaneously stackable
 * filters on the same map. Our backend already attaches `sensor_type` to every
 * detection contribution; this panel exposes the filter to the operator.
 *
 * The panel writes to `window.__gsIntelFilter` which is read by the Cesium
 * hooks; an `intel-filter-changed` CustomEvent fires on every change so hooks
 * can reactively update without prop drilling.
 */

export interface IntelLayer {
  key: string;
  label: string;
  icon: IconName;
  color: string;
  description: string;
}

export const INTEL_LAYERS: IntelLayer[] = [
  { key: 'EO_IR',  label: 'EO / IR',  icon: 'eye-open',         color: '#4A90E2', description: 'Electro-optical & infrared imagery' },
  { key: 'SAR',    label: 'SAR',      icon: 'horizontal-bar-chart', color: '#7ED321', description: 'Synthetic-aperture radar (all-weather)' },
  { key: 'SIGINT', label: 'SIGINT',   icon: 'feed',             color: '#F5A623', description: 'RF emitter geolocation' },
  { key: 'MTI',    label: 'MTI',      icon: 'arrow-right',      color: '#a855f7', description: 'Moving-target indicator' },
  { key: 'GEO',    label: 'GEOINT',   icon: 'geosearch',        color: '#00bcd4', description: 'Geospatial / map overlays' },
  { key: 'OSINT',  label: 'OSINT',    icon: 'globe-network',    color: '#94a3b8', description: 'Open-source intelligence' },
];

export interface IntelFilterState {
  enabled: Record<string, boolean>;
  opacity: Record<string, number>;
}

export const DEFAULT_INTEL_FILTER: IntelFilterState = {
  enabled: { EO_IR: true, SAR: true, SIGINT: true, MTI: false, GEO: true, OSINT: false },
  opacity: { EO_IR: 1.0, SAR: 0.85, SIGINT: 0.85, MTI: 0.7, GEO: 0.6, OSINT: 0.6 },
};

declare global {
  interface Window { __gsIntelFilter?: IntelFilterState; }
}

function publish(state: IntelFilterState) {
  window.__gsIntelFilter = state;
  window.dispatchEvent(new CustomEvent('grid-sentinel:intel-filter-changed', { detail: state }));
}

interface Props { visible?: boolean; }

export function IntelLayerPanel({ visible = true }: Props) {
  const [state, setState] = useState<IntelFilterState>(() => {
    if (!window.__gsIntelFilter) publish(DEFAULT_INTEL_FILTER);
    return window.__gsIntelFilter ?? DEFAULT_INTEL_FILTER;
  });

  if (!visible) return null;

  const update = (next: IntelFilterState) => { setState(next); publish(next); };
  const toggle = (key: string) => update({ ...state, enabled: { ...state.enabled, [key]: !state.enabled[key] } });
  const setOpacity = (key: string, v: number) => update({ ...state, opacity: { ...state.opacity, [key]: v } });

  return (
    <div
      role="region"
      aria-label="Intel layer filters"
      style={{
        position: 'absolute',
        top: 12,
        left: 12,
        width: 220,
        background: 'rgba(7, 11, 17, 0.94)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        padding: '6px 8px',
        zIndex: 7000,
        boxShadow: '0 6px 16px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{
        fontFamily: 'monospace',
        fontSize: 10,
        letterSpacing: '0.16em',
        color: '#94a3b8',
        marginBottom: 6,
        paddingBottom: 4,
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        INTEL LAYERS
      </div>
      {INTEL_LAYERS.map(layer => {
        const on = state.enabled[layer.key];
        return (
          <div key={layer.key} style={{
            padding: '4px 0',
            borderBottom: '1px solid rgba(255,255,255,0.03)',
            opacity: on ? 1 : 0.45,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Icon icon={layer.icon} size={12} color={layer.color} />
              <span style={{ flex: 1, fontSize: 11, fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.04em' }}>
                {layer.label}
              </span>
              <Switch
                checked={on}
                onChange={() => toggle(layer.key)}
                style={{ margin: 0 }}
                large={false}
                aria-label={`Toggle ${layer.label}`}
              />
            </div>
            {on && (
              <div style={{ paddingLeft: 18, marginTop: 2 }}>
                <Slider
                  min={0} max={1} stepSize={0.05}
                  value={state.opacity[layer.key] ?? 1}
                  onChange={(v: number) => setOpacity(layer.key, v)}
                  labelRenderer={false}
                />
              </div>
            )}
            {on && (
              <div style={{ fontSize: 9, color: '#64748b', paddingLeft: 18 }}>
                {layer.description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
