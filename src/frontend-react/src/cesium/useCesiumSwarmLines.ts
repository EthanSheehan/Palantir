import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

export function useCesiumSwarmLines(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Cesium.Entity[]>([]);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      // Remove existing swarm line entities
      entitiesRef.current.forEach((e) => viewer.entities.remove(e));
      entitiesRef.current = [];

      const { swarmTasks, uavs, targets } = state;

      // Build lookup maps
      const uavMap = new Map(uavs.map(u => [u.id, u]));
      const targetMap = new Map(targets.map(t => [t.id, t]));

      // Draw dashed cyan lines from each SUPPORT UAV to its target
      swarmTasks.forEach((task) => {
        const target = targetMap.get(task.target_id);
        if (!target) return;

        task.assigned_uav_ids.forEach((uavId) => {
          const uav = uavMap.get(uavId);
          if (!uav) return;

          const line = viewer.entities.add({
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArrayHeights([
                uav.lon, uav.lat, 2000,
                target.lon, target.lat, 500,
              ]),
              width: 2,
              material: new Cesium.PolylineDashMaterialProperty({
                color: Cesium.Color.CYAN.withAlpha(0.7),
                gapColor: Cesium.Color.TRANSPARENT,
                dashLength: 16.0,
                dashPattern: 255,
              }),
              arcType: Cesium.ArcType.GEODESIC,
            },
          });
          entitiesRef.current.push(line);
        });
      });

      viewer.scene.requestRender();
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        entitiesRef.current.forEach((e) => viewer.entities.remove(e));
      }
      entitiesRef.current = [];
    };
  }, [viewerRef]);
}
