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

function getDotIcon(target: Target, pulse: boolean = false): string {
  const state = (target.state ?? 'DETECTED').toUpperCase();
  const color = STATE_COLORS[state] ?? '#cbd5e1';
  const fused = Math.max(0, Math.min(1, target.fused_confidence ?? 0));
  const sensorCount = target.sensor_count ?? 0;
  const id = String(target.id).padStart(4, '0');
  const ring = state === 'NOMINATED' ? 3 : 2;
  const flash = state === 'NOMINATED' ? '<animate attributeName="opacity" values="1;0.4;1" dur="1s" repeatCount="indefinite"/>' : '';
  const cacheKey = `${id}_${state}_${Math.round(fused * 10)}_${sensorCount}_${pulse}`;
  if (dotSvgCache[cacheKey]) return dotSvgCache[cacheKey];
  // Pulse ring fires once on every state advance (600ms outer ring grows
  // from r=14 to r=22 with opacity fading 0.6 → 0). Beyond-Maven flair —
  // operators see when a track moves through the kill chain at a glance.
  const pulseRing = pulse
    ? `<circle cx="23" cy="23" r="14" fill="none" stroke="${color}" stroke-width="2">
         <animate attributeName="r" from="14" to="22" dur="0.6s" begin="0s" fill="freeze" />
         <animate attributeName="opacity" from="0.7" to="0" dur="0.6s" begin="0s" fill="freeze" />
       </circle>`
    : '';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
    ${pulseRing}
    <circle cx="23" cy="23" r="14" fill="rgba(7,11,17,0.85)" stroke="${color}" stroke-width="${ring}">${flash}</circle>
    <text x="23" y="22" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="9" font-weight="700" fill="${color}" text-anchor="middle">#${id}</text>
    <text x="23" y="32" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="7" fill="${color}" text-anchor="middle" opacity="0.85">${Math.round(fused * 100)}% · ${sensorCount}S</text>
  </svg>`;
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  dotSvgCache[cacheKey] = url;
  return url;
}

/**
 * Read the IntelLayerPanel's filter state. The panel writes
 * `window.__gsIntelFilter` and dispatches a custom event when it changes.
 * Returns `true` if a target should be visible given the active filters,
 * which here means: at least one of its sensor_contributions matches an
 * enabled INT layer (or no contributions at all so we fall back to "show").
 */
function targetMatchesFilter(target: Target): boolean {
  const filter = (window as any).__gsIntelFilter as
    | { enabled: Record<string, boolean> }
    | undefined;
  if (!filter || !filter.enabled) return true;
  const enabled = filter.enabled;
  const contribs = target.sensor_contributions ?? [];
  if (contribs.length === 0) return enabled.EO_IR ?? true; // fallback
  for (const c of contribs) {
    if (enabled[c.sensor_type]) return true;
  }
  return false;
}

export function useCesiumDetectionLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});
  const lastTargetsRef = useRef<Target[]>([]);
  // Tracks last-known state per target id so we can fire the SVG pulse
  // animation exactly once on a state advance (DETECTED → CLASSIFIED, etc.)
  const lastStateRef = useRef<Record<number, string>>({});
  // When we set pulse=true for a target, schedule clearing it next tick
  // so subsequent renders revert to the pulse-free icon.
  const pulseClearTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    function applyTargets(targets: Target[]) {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      lastTargetsRef.current = targets;
      const live = new Set<number>();
      for (const t of targets) {
        const visible = targetMatchesFilter(t);
        if (!visible) {
          // If we already created the entity, just toggle its visibility
          const existing = entitiesRef.current[t.id];
          if (existing) existing.show = false;
          continue;
        }
        live.add(t.id);
        // Detect state transition since last frame and fire pulse once.
        const currentState = (t.state ?? 'DETECTED').toUpperCase();
        const previous = lastStateRef.current[t.id];
        const justAdvanced = previous !== undefined && previous !== currentState;
        lastStateRef.current[t.id] = currentState;
        if (justAdvanced && pulseClearTimers.current[t.id]) {
          clearTimeout(pulseClearTimers.current[t.id]);
        }
        if (justAdvanced) {
          // Schedule a re-render after 700ms to clear the pulse so the cache
          // doesn't keep serving the animated SVG forever.
          pulseClearTimers.current[t.id] = setTimeout(() => {
            applyTargets(lastTargetsRef.current);
          }, 700);
        }
        const url = getDotIcon(t, justAdvanced);
        const pos = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 30);

        const existing = entitiesRef.current[t.id];
        if (existing) {
          existing.show = true;
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

      // Sweep stale (target removed entirely from sim)
      for (const idStr of Object.keys(entitiesRef.current)) {
        const id = Number(idStr);
        if (!targets.find(t => t.id === id)) {
          viewer.entities.remove(entitiesRef.current[id]);
          delete entitiesRef.current[id];
        }
      }
    }

    const unsub = useSimStore.subscribe((state) => applyTargets(state.targets));

    // Re-apply visibility when the IntelLayerPanel filter changes — same
    // target list, just different show/hide rules.
    function onFilterChanged() {
      applyTargets(lastTargetsRef.current);
    }
    window.addEventListener('grid-sentinel:intel-filter-changed', onFilterChanged);

    return () => {
      unsub();
      window.removeEventListener('grid-sentinel:intel-filter-changed', onFilterChanged);
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
