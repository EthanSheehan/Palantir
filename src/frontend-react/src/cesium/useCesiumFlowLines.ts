import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import type { FlowLine } from '../store/types';

/** Build a stable key for a flow line so we can diff without teardown. */
function flowKey(flow: FlowLine): string {
  return `${flow.source[0]},${flow.source[1]}->${flow.target[0]},${flow.target[1]}`;
}

/** Serialize flow array to a fingerprint for cheap equality check. */
function flowsFingerprint(flows: FlowLine[]): string {
  return flows.map(flowKey).sort().join('|');
}

export function useCesiumFlowLines(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entityMapRef = useRef<Map<string, Cesium.Entity>>(new Map());
  const prevFingerprintRef = useRef('');

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const flows = state.flows;
      const flowsVisible = state.layerVisibility?.['flows'] ?? true;
      const fp = flowsFingerprint(flows);
      if (fp === prevFingerprintRef.current) {
        // Still apply visibility even if flow topology hasn't changed
        entityMapRef.current.forEach((e) => { e.show = flowsVisible; });
        return;
      }
      prevFingerprintRef.current = fp;

      const nextKeys = new Set(flows.map(flowKey));

      // Remove stale lines
      for (const [key, entity] of entityMapRef.current) {
        if (!nextKeys.has(key)) {
          viewer.entities.remove(entity);
          entityMapRef.current.delete(key);
        }
      }

      // Add new lines (skip existing — flow lines are static per key)
      for (const flow of flows) {
        const key = flowKey(flow);
        if (entityMapRef.current.has(key)) continue;
        const entity = viewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights([
              flow.source[0], flow.source[1], 2000,
              flow.target[0], flow.target[1], 2000,
            ]),
            width: 3,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.2,
              color: Cesium.Color.CYAN,
            }),
            arcType: Cesium.ArcType.GEODESIC,
          },
        });
        entity.show = flowsVisible;
        entityMapRef.current.set(key, entity);
      }

      // Apply visibility to all entities
      entityMapRef.current.forEach((e) => { e.show = flowsVisible; });

      viewer.scene.requestRender();
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        entityMapRef.current.forEach((e) => viewer.entities.remove(e));
      }
      entityMapRef.current.clear();
      prevFingerprintRef.current = '';
    };
  }, [viewerRef]);
}
