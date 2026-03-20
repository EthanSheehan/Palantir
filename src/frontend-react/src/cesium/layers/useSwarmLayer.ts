import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../../store/SimulationStore';

const TRACKING_MODES = new Set(['FOLLOW', 'PAINT', 'INTERCEPT', 'SUPPORT']);

export function useSwarmLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Cesium.Entity[]>([]);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['swarm'] ?? false;

      if (!visible) {
        // Remove all entities when not visible
        for (const entity of entitiesRef.current) {
          viewer.entities.remove(entity);
        }
        entitiesRef.current = [];
        return;
      }

      // Remove old entities and rebuild
      for (const entity of entitiesRef.current) {
        viewer.entities.remove(entity);
      }
      entitiesRef.current = [];

      const targetsById = new Map(state.targets.map((t) => [t.id, t]));

      for (const uav of state.uavs) {
        if (!TRACKING_MODES.has(uav.mode)) continue;
        if (uav.tracked_target_ids.length === 0) continue;

        const primaryId = uav.primary_target_id ?? uav.tracked_target_ids[0];
        const target = targetsById.get(primaryId);
        if (!target) continue;

        const entity = viewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights([
              uav.lon, uav.lat, uav.altitude_m ?? 2000,
              target.lon, target.lat, 0,
            ]),
            width: 2,
            material: new Cesium.PolylineDashMaterialProperty({
              color: Cesium.Color.CYAN.withAlpha(0.6),
              dashLength: 16,
            }),
          },
        });

        entitiesRef.current.push(entity);
      }
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        for (const entity of entitiesRef.current) {
          viewer.entities.remove(entity);
        }
      }
      entitiesRef.current = [];
    };
  }, [viewerRef]);
}
