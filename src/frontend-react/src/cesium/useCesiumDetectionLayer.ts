import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { Target } from '../store/types';

/**
 * Maven-style numbered detection-dot layer.
 *
 * Every target gets a small ring with its stable ID (#0042) inside, color-coded
 * by verification state. The number persists across modality/sensor handoffs so
 * the operator sees that "this is the same track even after SAR took over from
 * EO". Complementary to useCesiumTargets (icons/threat rings) — this is the
 * cross-INT fusion overlay.
 */

const STATE_COLORS: Record<string, string> = {
  UNDETECTED:  '#3b3f47',
  DETECTED:    '#dc2626',
  CLASSIFIED:  '#f59e0b',
  VERIFIED:    '#22c55e',
  NOMINATED:   '#fbbf24',
  AUTHORIZED:  '#3b82f6',
  ENGAGING:    '#a855f7',
  ENGAGED:     '#a855f7',
  BDA:         '#06b6d4',
  ASSESSED:    '#06b6d4',
  COMPLETE:    '#475569',
  NEUTRALIZED: '#475569',
};

const dotSvgCache: Record<string, string> = {};

function getDotIcon(target: Target): string {
  const state = (target.state ?? 'DETECTED').toUpperCase();
  const color = STATE_COLORS[state] ?? '#cbd5e1';
  const fused = Math.max(0, Math.min(1, target.fused_confidence ?? 0));
  const sensorCount = target.sensor_count ?? 0;
  const id = String(target.id).padStart(4, '0');
  const ring = state === 'NOMINATED' ? 3 : 2;
  const flash = state === 'NOMINATED' ? '<animate attributeName="opacity" values="1;0.4;1" dur="1s" repeatCount="indefinite"/>' : '';
  const cacheKey = `${id}_${state}_${Math.round(fused * 10)}_${sensorCount}`;
  if (dotSvgCache[cacheKey]) return dotSvgCache[cacheKey];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
    <circle cx="23" cy="23" r="14" fill="rgba(7,11,17,0.85)" stroke="${color}" stroke-width="${ring}">${flash}</circle>
    <text x="23" y="22" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="9" font-weight="700" fill="${color}" text-anchor="middle">#${id}</text>
    <text x="23" y="32" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="7" fill="${color}" text-anchor="middle" opacity="0.85">${Math.round(fused * 100)}% · ${sensorCount}S</text>
  </svg>`;
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  dotSvgCache[cacheKey] = url;
  return url;
}

export function useCesiumDetectionLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const live = new Set<number>();
      for (const t of state.targets) {
        live.add(t.id);
        const url = getDotIcon(t);
        const pos = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 30);

        const existing = entitiesRef.current[t.id];
        if (existing) {
          existing.position = pos as any;
          if (existing.billboard) {
            existing.billboard.image = url as any;
          }
        } else {
          const entity = viewer.entities.add({
            id: `detection-dot-${t.id}`,
            position: pos,
            billboard: {
              image: url,
              width: 46,
              height: 46,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(28, -8),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
              translucencyByDistance: new Cesium.NearFarScalar(1e3, 1.0, 5e6, 0.0),
            },
          });
          entitiesRef.current[t.id] = entity;
        }
      }

      // Sweep stale
      for (const idStr of Object.keys(entitiesRef.current)) {
        const id = Number(idStr);
        if (!live.has(id)) {
          viewer.entities.remove(entitiesRef.current[id]);
          delete entitiesRef.current[id];
        }
      }
    });
    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        for (const id of Object.keys(entitiesRef.current)) {
          viewer.entities.remove(entitiesRef.current[Number(id)]);
        }
      }
      entitiesRef.current = {};
    };
  }, [viewerRef]);
}
