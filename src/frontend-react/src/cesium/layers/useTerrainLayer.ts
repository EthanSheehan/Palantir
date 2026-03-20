import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../../store/SimulationStore';

export function useTerrainLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Cesium.Entity[]>([]);
  const prevVisibleRef = useRef<boolean>(false);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['terrain'] ?? false;

      if (!visible) {
        // Reset terrain exaggeration and remove LOS lines
        if (prevVisibleRef.current) {
          if ('terrainExaggeration' in viewer.scene.globe) {
            (viewer.scene.globe as any).terrainExaggeration = 1.0;
          }
          for (const entity of entitiesRef.current) {
            viewer.entities.remove(entity);
          }
          entitiesRef.current = [];
        }
        prevVisibleRef.current = false;
        return;
      }

      // Apply terrain exaggeration
      if ('terrainExaggeration' in viewer.scene.globe) {
        (viewer.scene.globe as any).terrainExaggeration = 2.0;
      }

      // Rebuild LOS lines
      for (const entity of entitiesRef.current) {
        viewer.entities.remove(entity);
      }
      entitiesRef.current = [];

      const targetsById = new Map(state.targets.map((t) => [t.id, t]));

      for (const uav of state.uavs) {
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
            width: 1,
            material: Cesium.Color.LIME.withAlpha(0.5),
          },
        });

        entitiesRef.current.push(entity);
      }

      prevVisibleRef.current = true;
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        // CRITICAL: reset terrain exaggeration on cleanup
        if ('terrainExaggeration' in viewer.scene.globe) {
          (viewer.scene.globe as any).terrainExaggeration = 1.0;
        }
        for (const entity of entitiesRef.current) {
          viewer.entities.remove(entity);
        }
      }
      entitiesRef.current = [];
    };
  }, [viewerRef]);
}
